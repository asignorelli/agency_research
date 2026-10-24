"""Idempotent, durable pipeline. Successful responses never regenerated."""
from __future__ import annotations
import json,os,random,secrets,sqlite3,time,uuid
from pathlib import Path
from .core import LEVELS,CONDITIONS,build_student_payload,canonical,check_body,connect,dataset,docs,freeze_body,initialize,now,provenance,seed_runs,sha,tutor_settings,validate_sources,verify_db_sources
from .providers import DEFAULT_TIMEOUT_SECONDS,ModelMismatchError,ProviderError,build_request,conservative_reservation,cost_usd,invoke
from .recovery import (collection_lock,ensure_recovery_schema,prepare_resume,queue_order,
                       save_tutor_result,unresolved_attempt,write_checkpoint)
from .student_inputs import configured_student_messages,parse_student_messages


def append_archive(path,event):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload=canonical(event)+'\n'
    with path.open('a',encoding='utf-8') as f:
        f.write(payload);f.flush();os.fsync(f.fileno())
    return sha(payload)

def spent(con):
    # Include successful and unsuccessful attempts with billed usage.
    v=con.execute('SELECT COALESCE(SUM(cost_usd),0) FROM attempts').fetchone()[0]
    return float(v or 0)

def reserve_budget(con,estimate,cap,config=None):
    if cap is None or cap<=0:raise ValueError('Live calls require positive --max-usd')
    used=spent(con)
    uncertain=0.0
    if config is not None:
        for row in con.execute("SELECT stage,raw_request_json FROM attempts WHERE status IN ('in_flight','ambiguous')"):
            rates=config.get(row[0],{})
            if rates.get('input_usd_per_million') is not None and rates.get('output_usd_per_million') is not None:
                uncertain+=conservative_reservation(json.loads(row[1]),rates)
    if used+uncertain+estimate>cap:
        raise ValueError(f'Spending guard: estimated next request ${estimate:.4f} + recorded ${used:.4f} + reserved uncertain usage ${uncertain:.4f} exceeds cap ${cap:.4f}. This is an estimate, not a strict billing cap.')

def ensure_live_config(c,role):
    provider=c[role]['provider']
    if provider not in ('anthropic','openai','deepinfra'):raise ValueError('Configure supported provider')
    cost_usd(1,1,c[role])


def ensure_model_unblocked(con, role):
    table = 'student_candidates' if role == 'student' else 'runs'
    if con.execute(f"SELECT 1 FROM {table} WHERE status='blocked_model_mismatch' LIMIT 1").fetchone():
        raise ModelMismatchError(
            f'{role} collection is blocked by a preserved model mismatch; '
            'review it before continuing, and use a new study if the model must change'
        )


def model_mismatch(result, requested_model):
    return result.get('served_model') != requested_model


def halt_model_mismatch(result, requested_model):
    raise ModelMismatchError(
        f'Expected model {requested_model!r}, received {result.get("served_model")!r}. '
        'Response and usage preserved; batch halted without retry'
    )

def store_attempt_start(con,stage,obj,payload):
    # No auto resend after an unresolved attempt; transient HTTP errors are classified explicitly.
    n=con.execute('SELECT COALESCE(MAX(number),0)+1 FROM attempts WHERE stage=? AND object_id=?',(stage,obj)).fetchone()[0]
    aid=f'{stage}-{obj}-try{n}'
    con.execute('INSERT INTO attempts(attempt_id,stage,object_id,number,status,raw_request_json,started_utc) VALUES(?,?,?,?,?,?,?)', (aid,stage,obj,n,'in_flight',canonical(payload),now()))
    con.commit()
    return aid

def update_attempt(con,aid,status,output=None,error=None,est_cost=None,archive_hash=None):
    con.execute('UPDATE attempts SET status=?, raw_response_json=?, error_json=?, input_tokens=?, output_tokens=?,cost_usd=?,finished_utc=?,archive_sha256=? WHERE attempt_id=?',
        (status,canonical(output['raw']) if output else None,canonical(error) if error else None,
         output['input_tokens'] if output else None,output['output_tokens'] if output else None,
         est_cost,now(),archive_hash,aid))
    con.commit()

def execute_stage(con,c,stage,obj,payload,role,archive,live,cap,retry_limit=None,timeout_seconds=None):
    if not live:raise ValueError('Network calls disabled: supply --live and a spending cap')
    ensure_live_config(c,role)
    provider=c[role]['provider'];rates=c[role]
    retry_limit=retry_limit or c['retry']['maximum_attempts']
    # Detect an earlier unresolved attempt. Never silently duplicate.
    unknown=unresolved_attempt(con,stage,obj)
    if unknown:raise ValueError(f'Unresolved provider attempt {unknown[0]}: investigate before re-running')
    for i in range(retry_limit):
        reserve_budget(con,conservative_reservation(payload,rates),cap,c)
        aid=store_attempt_start(con,stage,obj,payload)
        try:
            if stage=='tutor':write_checkpoint(con)
            output=invoke(provider,payload,timeout=timeout_seconds) if timeout_seconds is not None else invoke(provider,payload)
            expense=cost_usd(output['input_tokens'],output['output_tokens'],rates)
            event={'event':'provider_success','stage':stage,'object':obj,'attempt_id':aid,'request':payload,'response':output['raw'], 'transport_timeout_seconds':timeout_seconds or DEFAULT_TIMEOUT_SECONDS, 'created_utc':now()}
            digest=append_archive(archive,event)
            update_attempt(con,aid,'success',output=output,est_cost=expense,archive_hash=digest)
            return output,aid,expense
        except ProviderError as e:
            status='ambiguous' if str(e).startswith('AMBIGUOUS_NETWORK_FAILURE') else 'transient_error' if e.retryable else 'terminal_error'
            err={'message':str(e),'http_status':e.status,'retryable':e.retryable,'raw':e.raw}
            digest=append_archive(archive,{'event':'provider_error','stage':stage,'object':obj,'attempt_id':aid,'request':payload,'error':err,'transport_timeout_seconds':timeout_seconds or DEFAULT_TIMEOUT_SECONDS,'created_utc':now()})
            update_attempt(con,aid,status,error=err,archive_hash=digest)
            if not e.retryable or i==retry_limit-1:raise
            time.sleep(max(e.retry_after or 0, min(25,c['retry']['base_delay_seconds']*(2**i)+random.random())))
    raise RuntimeError('Unexpected retry loop exit')

def generate_student_bodies(c,db,archive,live=False,cap=None,limit=None):
    if c.get('student_input_mode') == 'standardized_import':
        raise ValueError('This study imports fixed student messages. Use import-students; generation would change the inputs')
    con=verify_db_sources(c,db)
    try:
        ensure_model_unblocked(con, 'student')
    except Exception:
        con.close()
        raise
    pp,system=docs(c)
    problems=dataset(c)['problems']
    done=0
    for p in problems:
        sid=p['id']
        if con.execute('SELECT 1 FROM student_bodies WHERE scenario_id=?',(sid,)).fetchone():continue
        if con.execute("SELECT 1 FROM student_candidates WHERE scenario_id=? AND status='valid_candidate'",(sid,)).fetchone():continue
        if limit is not None and done>=limit:break
        payload=build_request(c['student']['provider'],c['student']['model'],system,canonical(build_student_payload(p)),c['student']['max_output_tokens'],
            effort=c['student'].get('effort'),thinking=c['student'].get('thinking'))
        result,aid,expense=execute_stage(con,c,'student',f'P{sid:02d}',payload,'student',archive,live,cap)
        validation=check_body(result['text'],p)
        cid=f'candidate-P{sid:02d}-{uuid.uuid4().hex[:8]}'
        status='valid_candidate' if validation['pass'] and result['stop_reason'] not in ('max_tokens','length','refusal','model_context_window_exceeded') else 'needs_revision'
        if model_mismatch(result, c['student']['model']):
            status = 'blocked_model_mismatch'
        con.execute('INSERT INTO student_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (cid,sid,result['text'],canonical(validation),status,c['student']['provider'],c['student']['model'],result['served_model'],canonical(result['raw']),result['input_tokens'],result['output_tokens'],expense,now()))
        con.commit();done+=1
        if status == 'blocked_model_mismatch':
            con.close()
            halt_model_mismatch(result, c['student']['model'])
        print(f'P{sid:02d}: {status}, candidate={cid}, ${expense:.5f}')
    con.close()
    return done

def export_students(c,db,path):
    con=verify_db_sources(c,db)
    records=[]
    for r in con.execute("SELECT c.candidate_id,c.scenario_id,c.body,c.validation_json,s.title FROM student_candidates c JOIN scenarios s ON c.scenario_id=s.scenario_id WHERE c.status='valid_candidate' ORDER BY c.scenario_id,c.created_utc"):
        records.append({'candidate_id':r['candidate_id'],'scenario_id':r['scenario_id'],'title':r['title'],'body':r['body'],'validation':json.loads(r['validation_json'])})
    Path(path).write_text(json.dumps({'note':'Review accuracy, forbidden diagnoses, supplied observations, verbatim code; auto checks cannot establish factual validity','candidates':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    con.close();return len(records)

def import_student_edit(c,db,scenario_id,body_file):
    """Create one reviewable candidate from a locally edited file; supersede old candidates."""
    if c.get('student_input_mode') == 'standardized_import':
        expected=configured_student_messages(c).get(scenario_id)
        if expected is None or Path(body_file).read_text(encoding='utf-8') != expected['body']:
            raise ValueError('Standardized messages are source-controlled; revise sources and start a new study to change one')
    con=verify_db_sources(c,db)
    if con.execute('SELECT 1 FROM student_bodies WHERE scenario_id=?',(scenario_id,)).fetchone():
        raise ValueError('Student request already frozen: cannot edit in this study')
    p=next((p for p in dataset(c)['problems'] if p['id']==scenario_id),None)
    if p is None:raise ValueError('Invalid scenario ID')
    body=Path(body_file).read_text(encoding='utf-8')
    valid=check_body(body,p)
    if not valid['pass']:raise ValueError('Proposed student edit fails checks: '+str(valid['issues']))
    cid='manual-P%02d-%s'%(scenario_id,uuid.uuid4().hex[:8])
    con.execute("UPDATE student_candidates SET status='superseded' WHERE scenario_id=? AND status='valid_candidate'",(scenario_id,))
    con.execute('INSERT INTO student_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (cid,scenario_id,body,canonical(valid),'valid_candidate','manual','manual','manual',
             canonical({'note':'User-edited student body; no model call'}),0,0,0.0,now()))
    con.commit();con.close();return cid


def import_student_messages(c,db,body_file=None):
    """Import the configured corpus atomically, with source hashes and no model call."""
    if c.get('student_input_mode') != 'standardized_import':
        raise ValueError('import-students requires standardized_import input mode')
    validate_sources(c)
    expected=configured_student_messages(c)
    supplied=parse_student_messages(Path(body_file).read_text(encoding='utf-8')) if body_file else expected
    if supplied != expected:
        raise ValueError('Import file differs from the configured student corpus; use a new source version')
    con=verify_db_sources(c,db)
    imported=0
    try:
        if con.execute('SELECT 1 FROM student_bodies LIMIT 1').fetchone():
            raise ValueError('Student bodies are already frozen; import cannot overwrite them')
        source_hash=sha((Path(c['_root'])/c['student_messages']).read_bytes())
        problems={p['id']:p for p in dataset(c)['problems']}
        for sid,item in supplied.items():
            rows=con.execute("SELECT body FROM student_candidates WHERE scenario_id=? AND status='valid_candidate'",(sid,)).fetchall()
            if rows:
                if len(rows)==1 and rows[0]['body']==item['body']:
                    continue
                raise ValueError(f'Existing candidate differs for P{sid:02d}; refusing to overwrite it')
            validation=check_body(item['body'],problems[sid])
            validation.update(input_origin='standardized_import',source_sha256=source_hash)
            candidate_id=f'import-P{sid:02d}-{sha(item["body"])[:12]}'
            raw={'input_origin':'standardized_synthetic_messages_with_human_revisions',
                 'source_file':c['student_messages'],'source_sha256':source_hash,'model_call':False,
                 'human_review_attested':False}
            con.execute('INSERT INTO student_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (candidate_id,sid,item['body'],canonical(validation),'valid_candidate',
                 'standardized_import',None,None,canonical(raw),0,0,0.0,now()))
            imported+=1
        con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',
            ('student_input_import',canonical({'source_file':c['student_messages'],
             'source_sha256':source_hash,'model_calls':0,'human_review_attested':False})))
        con.commit()
        return imported
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def freeze_candidates(c,db,ack_reviewed=False):
    if not ack_reviewed:raise ValueError('Freeze needs --ack-reviewed, meaning you have actually reviewed all 20 bodies')
    con=verify_db_sources(c,db)
    try:
        ensure_model_unblocked(con, 'student')
    except Exception:
        con.close()
        raise
    rows=con.execute("SELECT c.* FROM student_candidates c WHERE c.status='valid_candidate' ORDER BY c.scenario_id,c.created_utc").fetchall()
    byscenario={}
    for r in rows:byscenario.setdefault(r['scenario_id'],[]).append(r)
    if set(byscenario)!=set(range(1,21)) or any(len(v)!=1 for v in byscenario.values()):
        raise ValueError('Exactly one valid candidate per scenario is required; manually resolve duplicates and missing candidates first')
    if con.execute('SELECT COUNT(*) FROM student_bodies').fetchone()[0]:raise ValueError('Some student bodies already frozen; refusing partial re-freeze')
    if c.get('student_input_mode') == 'standardized_import':
        expected=configured_student_messages(c)
        if any(rs[0]['body'] != expected[sid]['body'] for sid,rs in byscenario.items()):
            con.close()
            raise ValueError('A candidate differs from the standardized corpus; refusing to freeze changed inputs')
    try:
        for sid,rs in byscenario.items():freeze_body(con,sid,rs[0]['body'],rs[0]['candidate_id'],'human_review_acknowledged')
        total=seed_runs(c,con)
        con.commit()
    except Exception:con.rollback();raise
    con.close();return total

def run_tutors(c,db,archive,live=False,cap=None,limit=None,*,timeout_seconds=None,
               continue_on_error=True,retry_ambiguous=False):
    if not live or cap is None or cap<=0:
        raise ValueError('Paid tutor calls require --live and a positive --max-usd')
    with collection_lock(db):
        con=verify_db_sources(c,db)
        try:
            if con.execute('SELECT COUNT(*) FROM runs').fetchone()[0]!=180:
                raise ValueError('Need frozen 180-run manifest')
            ensure_recovery_schema(con)
            order=queue_order(con,c['randomization_seed'])
            resumed=prepare_resume(c,con,archive,retry_ambiguous)
            write_checkpoint(con)
            print('Recovery:',json.dumps(resumed),flush=True)
            pending={r['run_id']:r for r in con.execute("SELECT r.run_id,r.request_id,r.condition,s.request_text FROM runs r JOIN student_requests s ON r.request_id=s.request_id WHERE r.status='planned'")}
            # Explicit retries go first; remaining work keeps its persisted queue order.
            priority=resumed['requeued_ambiguous']+resumed['requeued_safe']
            selected=list(dict.fromkeys(priority+order))
            rows=[pending[rid] for rid in selected if rid in pending]
            return run_tutor_jobs(c,con,rows,archive,live,cap,limit,
                timeout_seconds=timeout_seconds,continue_on_error=continue_on_error)
        finally:
            con.close()


def run_tutor_jobs(c,con,rows,archive,live=False,cap=None,limit=None,*,
                   timeout_seconds=None,continue_on_error=True):
    """Checkpoint every request; continue after network failures without discarding results."""
    ensure_model_unblocked(con,'tutor')
    ensure_live_config(c,'tutor')
    if not live or cap is None or cap<=0:
        raise ValueError('Paid tutor calls require --live and a positive --max-usd')
    if limit is not None and limit<=0:raise ValueError('Limit must be positive')
    if timeout_seconds is not None and (not isinstance(timeout_seconds,(int,float)) or not 0<timeout_seconds<float('inf')):
        raise ValueError('Request timeout must be a positive finite number')
    ensure_recovery_schema(con)
    prompts,_=docs(c);settings=tutor_settings(c);done=0;attempted=0
    con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('last_collection_session',canonical({
        'created_utc':now(),'transport_timeout_seconds':timeout_seconds or DEFAULT_TIMEOUT_SECONDS,
        'continue_on_network_error':continue_on_error,'maximum_new_jobs':limit})))
    con.commit()
    write_checkpoint(con)
    for r in rows:
        if limit is not None and attempted>=limit:break
        rid=r['run_id']
        payload=build_request(c['tutor']['provider'],c['tutor']['model'],prompts[r['condition']],r['request_text'],settings['max_output_tokens'],temperature=settings['temperature'])
        reserve_budget(con,conservative_reservation(payload,c['tutor']),cap,c)
        claim=con.execute("UPDATE runs SET status='in_flight' WHERE run_id=? AND status='planned'",(rid,))
        con.commit()
        if claim.rowcount!=1:continue
        attempted+=1
        try:
            write_checkpoint(con)
            result,aid,expense=execute_stage(con,c,'tutor',rid,payload,'tutor',archive,live,cap,timeout_seconds=timeout_seconds)
            status=save_tutor_result(con,c,rid,result,expense)
            done+=1
            checkpoint=write_checkpoint(con)
            print(f'{rid}: {status}, ${expense:.5f} [{checkpoint["captured"]}/{checkpoint["total_runs"]} captured]',flush=True)
            if status=='blocked_model_mismatch':halt_model_mismatch(result,c['tutor']['model'])
        except ProviderError as e:
            ambiguous=str(e).startswith('AMBIGUOUS_NETWORK_FAILURE')
            status='blocked_ambiguous' if ambiguous else 'failed_api'
            con.execute("UPDATE runs SET status=? WHERE run_id=? AND response_text IS NULL",(status,rid));con.commit()
            write_checkpoint(con)
            print(f'{rid}: {status}: {e}',flush=True)
            if continue_on_error and (ambiguous or e.retryable):continue
            raise
        except KeyboardInterrupt:
            last=con.execute("SELECT status FROM attempts WHERE stage='tutor' AND object_id=? ORDER BY number DESC LIMIT 1",(rid,)).fetchone()
            status='blocked_ambiguous' if last and last[0] in ('in_flight','ambiguous') else 'planned' if not last else 'in_flight'
            con.execute("UPDATE runs SET status=? WHERE run_id=? AND response_text IS NULL",(status,rid));con.commit()
            write_checkpoint(con)
            print('Collection interrupted; progress saved. Use resume-tutors to continue.',flush=True)
            raise
        except Exception:
            last=con.execute("SELECT status FROM attempts WHERE stage='tutor' AND object_id=? ORDER BY number DESC LIMIT 1",(rid,)).fetchone()
            if not last:con.execute("UPDATE runs SET status='planned' WHERE run_id=? AND response_text IS NULL",(rid,));con.commit()
            write_checkpoint(con)
            raise
    checkpoint=write_checkpoint(con)
    print('Collection progress:',json.dumps({k:checkpoint[k] for k in
        ('captured','total_runs','pending','status_counts','unknown_charge_attempts')}),flush=True)
    return done


def repair_planned_after_safe_error(c,db):
    con=verify_db_sources(c,db)
    rows=con.execute("SELECT run_id,status FROM runs WHERE status IN ('failed_api','in_flight')").fetchall()
    repaired=[]
    for r in rows:
        ats=list(con.execute("SELECT status FROM attempts WHERE stage='tutor' AND object_id=? ORDER BY number",(r['run_id'],)))
        if (not ats and r['status']=='in_flight') or (ats and ats[-1][0] in ('transient_error','terminal_error')):
            con.execute("UPDATE runs SET status='planned' WHERE run_id=?",(r['run_id'],));repaired.append(r['run_id'])
    con.commit();con.close();return repaired
