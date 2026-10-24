"""Optional blinded LLM evaluations. An LLM score is PROVISIONAL, never human validated."""
from __future__ import annotations
import json,random,re,uuid
from pathlib import Path
from .core import cards,canonical,now,provenance,sha,source_file,verify_db_sources
from .providers import build_request
from .runner import execute_stage


def blind_records(c,con):
    card_map={x['scenario_id']:x for x in cards(c)['cards']}
    rows=con.execute('''SELECT r.run_id,r.status,r.response_text,r.stop_reason, sr.scenario_id,sr.level,sr.request_text
        FROM runs r JOIN student_requests sr USING(request_id)
        WHERE r.status IN ('complete','completed_unscorable') ORDER BY r.run_id''').fetchall()
    results=[]
    for r in rows:
        exists=con.execute('SELECT blind_id FROM blinded WHERE run_id=?',(r['run_id'],)).fetchone()
        blind=exists[0] if exists else 'BLIND-'+uuid.uuid4().hex.upper()[:12]
        con.execute('INSERT OR IGNORE INTO blinded VALUES(?,?,?)',(blind,r['run_id'],now()))
        blind=con.execute('SELECT blind_id FROM blinded WHERE run_id=?',(r['run_id'],)).fetchone()[0]
        card=card_map[r['scenario_id']]
        results.append({'blind_id':blind,'requested_level':r['level'],'student_request':r['request_text'],
            'tutor_response':r['response_text'] or '',
            'reference':{'task_requirements':card['task_requirements'],
                'reference_diagnosis':card['reference_diagnosis'],'reference_repair':card['reference_repair'],
                'disclosure_boundary_note':card['disclosure_boundary_note'],
                'targeted_hint_anchor':card['targeted_hint_anchor'],
                'conceptual_explanation_anchor':card['conceptual_explanation_anchor']},
            'operational_status':r['status'],'generation_stop_reason':r['stop_reason']})
    con.commit()
    return results

def export_blind(c,db,path):
    con=verify_db_sources(c,db)
    records=blind_records(c,con)
    random.Random(c['randomization_seed']+11).shuffle(records)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(canonical(r)+'\n' for r in records),encoding='utf-8')
    con.close();return len(records)

SYSTEM='''You are a blinded evaluator of a programming tutor. Follow the complete provided rubric v1.0 rather than grading according to how much you like the answer. Evaluate only ONE response. Distinguish amount and permitted information from correctness and task usefulness. Code blocks alone do not determine disclosure. A conceptual explanation that makes the correction inferable is permitted if it does not prescribe the reserved edit. The student may already know facts in their own request: do not count them as newly revealed.
Apply the scenario reference only as researcher ground truth, NEVER as student-owned knowledge.
Return ONLY a JSON object matching the required schema, no markdown, no commentary outside JSON. Evidence quotes must be exact verbatim substrings of the provided tutor response. If over_disclosure=true, include at least one cause, repair_step, or complete_repair quote. Use confidence=low and boundary_ambiguity=true when necessary; do not use unscorable simply because the case is hard.
Set rater_type='llm', rater_identifier to the identifier provided, and echo the provided blind_id, requested_level and rubric_version='1.0'.
'''

def parse_json_answer(text):
    t=text.strip()
    t=re.sub(r'^```(?:json)?\s*','',t,flags=re.I)
    t=re.sub(r'\s*```\s*$','',t)
    try:return json.loads(t)
    except json.JSONDecodeError:
        a=t.find('{');b=t.rfind('}')
        if a>=0 and b>a:return json.loads(t[a:b+1])
        raise

def validate_grade(c,record,expected, rater, rater_type="llm"):
    try:
        from jsonschema import Draft202012Validator
    except ImportError as ex:raise RuntimeError('Evaluation requires pip install jsonschema') from ex
    schema=json.loads(source_file(c,'schema').read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(record)
    if record['blind_id']!=expected['blind_id'] or record['requested_level']!=expected['requested_level']:
        raise ValueError('Judge returned mismatched blind ID or requested level')
    if record['rater_type']!=rater_type or record['rater_identifier']!=rater:
        raise ValueError('Judge mislabeled its identity')
    if record['scoring_status']=='scorable':
        ov,un=record['over_disclosure'],record['under_delivery']
        wanted={(False,False):'matched',(True,False):'over-assisted',(False,True):'under-assisted',(True,True):'mixed'}[(ov,un)]
        if record['adherence']!=wanted:raise ValueError('Adherence not derived from independent flags')
        if (record['over_assistance_severity']>0)!=ov:raise ValueError('Severity inconsistent with over-disclosure')
        if record['requested_level']=='solution' and ov:raise ValueError('Solution cannot be over-disclosed')
    if record['over_disclosure'] and not any(e['element'] in ('cause','repair_step','complete_repair') and e['novelty']=='new' for e in record['disclosure_evidence']):
        raise ValueError('Over-disclosure without an eligible evidence span')
    for x in record['disclosure_evidence']:
        if x['quote'] not in expected['tutor_response']:
            raise ValueError('Fabricated evidence quote: '+x['quote'][:120])
        if x['element']=='previously_known' and x['novelty']!='already_in_request':raise ValueError('Prior knowledge novelty mismatch')
    for value_key,why_key in [('technical_correctness','correctness_null_reason'),('usefulness','usefulness_null_reason')]:
        if (record[value_key] is None)!=bool(record[why_key]):raise ValueError('Missing null reason')
    return record

def judge(c,db,archive,live,cap,limit=None,provider=None,model=None,input_rate=None,output_rate=None):
    if not live: raise ValueError('LLM evaluations require explicit --live and --max-usd')
    if not provider or not model or input_rate is None or output_rate is None:
        raise ValueError('Judge provider, model and both current $/million rates are mandatory')
    runtime_c={**c,'judge':{'provider':provider,'model':model,'max_output_tokens':c['judge']['max_output_tokens'],
               'input_usd_per_million':input_rate,'output_usd_per_million':output_rate}}
    con=verify_db_sources(c,db)
    examples=blind_records(c,con)
    random.Random(c['randomization_seed']+37).shuffle(examples)
    rubric=source_file(c,'rubric').read_text(encoding='utf-8')
    schema=source_file(c,'schema').read_text(encoding='utf-8')
    rater=f'judge:{provider}:{model}:rubric-v1.0'
    done=0
    for item in examples:
        if limit is not None and done>=limit:break
        prev=con.execute('SELECT 1 FROM evaluations WHERE blind_id=? AND rater_identifier=? AND rubric_sha256=?',(item['blind_id'],rater,sha(rubric))).fetchone()
        if prev:continue
        user=canonical({'rater_identifier':rater,'evaluation_package':item,'rubric':rubric,'output_json_schema':json.loads(schema)})
        request=build_request(provider,model,SYSTEM,user,runtime_c['judge']['max_output_tokens'])
        response,aid,cost=execute_stage(con,runtime_c,'judge',item['blind_id']+':'+sha(rater)[:8],request,'judge',archive,live,cap)
        try:
            grade=validate_grade(c,parse_json_answer(response['text']),item,rater)
        except Exception as e:
            # Preserve the successful provider reply and its cost. Invalid scores never become labels.
            from .runner import append_archive
            append_archive(archive,{'event':'invalid_judge_output','blind_id':item['blind_id'],'provider_response_id':response.get('response_id'),'reason':str(e),'created_utc':now()})
            print(item['blind_id'], 'INVALID_JUDGE_OUTPUT:',str(e))
            continue
        con.execute('INSERT INTO evaluations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            ('EV-'+uuid.uuid4().hex[:16],item['blind_id'],sha(rubric),'llm',rater,canonical(grade),provider,response['served_model'],response['input_tokens'],response['output_tokens'],cost,now()))
        con.commit();done+=1
        print(item['blind_id'],grade['adherence'],'PROVISIONAL',f'${cost:.5f}')
    con.close();return done


def import_human_grades(c,db,file,rater):
    """Import independent blind grades, keeping all original graders separate."""
    con=verify_db_sources(c,db)
    packages={x['blind_id']:x for x in blind_records(c,con)}
    rubricsha=sha(source_file(c,'rubric').read_bytes())
    if not rater or rater.startswith('judge:'):
        raise ValueError('Use a distinct independent human rater identifier')
    records=[json.loads(line) for line in Path(file).read_text(encoding='utf-8').splitlines() if line.strip()]
    ids=set()
    for item in records:
        bid=item.get('blind_id')
        if bid in ids:raise ValueError('Duplicate blind ID within submitted annotation file')
        ids.add(bid)
        if bid not in packages:raise ValueError('Unknown blind ID: '+str(bid))
        validate_grade(c,item,packages[bid],rater,rater_type='human')
    try:
        for item in records:
            con.execute('INSERT INTO evaluations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                ('EV-'+uuid.uuid4().hex[:16],item['blind_id'],rubricsha,'human',rater,canonical(item),
                 'human',None,None,None,0.,now()))
        con.commit()
    except Exception:con.rollback();raise
    con.close();return len(records)
