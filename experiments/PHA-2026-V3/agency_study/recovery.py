"""Durable collection checkpoints and audited recovery of interrupted requests."""
from __future__ import annotations

import json
import os
import random
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from .core import canonical, docs, now, sha, tutor_settings
from .providers import build_request, cost_usd, parse_response

RECOVERY_VERSION='collection-recovery-2026-10-24-v1'


def ensure_recovery_schema(con):
    con.execute('''CREATE TABLE IF NOT EXISTS recovery_events(
        event_id TEXT PRIMARY KEY, run_id TEXT, attempt_id TEXT,
        action TEXT NOT NULL, reason TEXT NOT NULL, created_utc TEXT NOT NULL,
        UNIQUE(attempt_id,action))''')
    if not con.execute("SELECT 1 FROM metadata WHERE key='collection_recovery_version'").fetchone():
        initial={'version':RECOVERY_VERSION,'module_sha256':sha(Path(__file__).read_bytes()),
                 'installed_utc':now(),
                 'run_status_counts':dict(con.execute('SELECT status,COUNT(*) FROM runs GROUP BY status'))}
        con.execute("INSERT INTO metadata VALUES('collection_recovery_version',?)",(canonical(initial),))
        audit(con,None,None,'recovery_runtime_adopted',canonical(initial))
    con.commit()


def audit(con, run_id, attempt_id, action, reason):
    con.execute('INSERT OR IGNORE INTO recovery_events VALUES(?,?,?,?,?,?)',
                ('recovery-'+uuid.uuid4().hex, run_id, attempt_id, action, reason, now()))


def retry_authorized(con, attempt_id):
    return con.execute("SELECT 1 FROM recovery_events WHERE attempt_id=? AND action='retry_authorized'",
                       (attempt_id,)).fetchone() is not None


def unresolved_attempt(con, stage, object_id):
    ensure_recovery_schema(con)
    return con.execute('''SELECT a.attempt_id FROM attempts a
        WHERE a.stage=? AND a.object_id=? AND a.status IN ('in_flight','ambiguous')
        AND NOT EXISTS(SELECT 1 FROM recovery_events e WHERE e.attempt_id=a.attempt_id
                       AND e.action='retry_authorized') LIMIT 1''', (stage, object_id)).fetchone()


def database_path(con):
    return Path(next(row[2] for row in con.execute('PRAGMA database_list') if row[1]=='main'))


@contextmanager
def collection_lock(db):
    """Prevent two collector processes from issuing requests for the same study."""
    import fcntl
    target = Path(str(db)+'.collection.lock')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another collector is running for this database; wait for it to finish') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def queue_order(con, seed, metadata_key='tutor_run_order'):
    ids = [row[0] for row in con.execute('SELECT run_id FROM runs ORDER BY run_id')]
    stored = con.execute('SELECT value_json FROM metadata WHERE key=?', (metadata_key,)).fetchone()
    if stored:
        order = json.loads(stored[0])
        if len(order)!=len(ids) or set(order)!=set(ids):
            raise ValueError('Saved collection order does not match the frozen run manifest')
        return order
    order = ids[:]
    random.Random(seed).shuffle(order)
    con.execute('INSERT INTO metadata VALUES(?,?)', (metadata_key, canonical(order)))
    audit(con, None, None, 'queue_checkpoint_created',
          'Persist collection order for restarts; existing completed responses are retained')
    con.commit()
    return order


def progress(con):
    counts = dict(con.execute('SELECT status,COUNT(*) FROM runs GROUP BY status'))
    total = sum(counts.values())
    failures = []
    for row in con.execute("SELECT run_id,status FROM runs WHERE status NOT IN ('planned','complete') ORDER BY run_id"):
        attempt = con.execute('''SELECT attempt_id,number,status,error_json,started_utc,finished_utc
            FROM attempts WHERE stage='tutor' AND object_id=? ORDER BY number DESC LIMIT 1''', (row[0],)).fetchone()
        item = {'run_id':row[0], 'status':row[1]}
        if attempt:
            error = json.loads(attempt[3]) if attempt[3] else {}
            item.update(attempt_id=attempt[0], attempt_number=attempt[1], attempt_status=attempt[2],
                        error=error.get('message'), http_status=error.get('http_status'),
                        started_utc=attempt[4], finished_utc=attempt[5])
        failures.append(item)
    recent = con.execute("SELECT run_id,completed_utc FROM runs WHERE completed_utc IS NOT NULL ORDER BY completed_utc DESC LIMIT 1").fetchone()
    order_row = con.execute("SELECT value_json FROM metadata WHERE key IN ('tutor_run_order','pilot_run_order') ORDER BY key DESC LIMIT 1").fetchone()
    order = json.loads(order_row[0]) if order_row else [row[0] for row in con.execute('SELECT run_id FROM runs ORDER BY run_id')]
    pending = {row[0] for row in con.execute("SELECT run_id FROM runs WHERE status='planned'")}
    unknown = con.execute("SELECT COUNT(*) FROM attempts WHERE status IN ('ambiguous','in_flight')").fetchone()[0]
    has_recovery = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='recovery_events'").fetchone()
    retries = con.execute("SELECT COUNT(*) FROM recovery_events WHERE action='retry_authorized'").fetchone()[0] if has_recovery else 0
    return {'total_runs':total, 'complete':counts.get('complete',0),
            'captured':counts.get('complete',0)+counts.get('completed_unscorable',0),
            'pending':counts.get('planned',0), 'in_flight':counts.get('in_flight',0),
            'status_counts':counts, 'failures':failures,
            'last_completed_run':recent[0] if recent else None,
            'next_pending_run':next((rid for rid in order if rid in pending),None),
            'unknown_charge_attempts':unknown, 'audited_ambiguous_retries':retries,
            'recorded_cost_usd':round(con.execute('SELECT COALESCE(SUM(cost_usd),0) FROM attempts').fetchone()[0],8),
            'cost_note':'Charges for timed-out requests are unknown and are not included in recorded cost.',
            'updated_utc':now()}


def write_checkpoint(con):
    """SQLite is authoritative; JSON is an atomic, human-readable progress view."""
    result = progress(con)
    target = Path(str(database_path(con))+'.progress.json')
    handle, temporary = tempfile.mkstemp(prefix=target.name+'.', dir=target.parent)
    try:
        with os.fdopen(handle,'w',encoding='utf-8') as stream:
            json.dump(result,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,target)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    return result


def save_tutor_result(con, c, run_id, result, expense):
    stop = result['stop_reason']; text = result['text']
    status = 'complete' if text.strip() and stop not in ('length','max_tokens','model_context_window_exceeded') else 'completed_unscorable'
    if result.get('served_model') != c['tutor']['model']:
        status = 'blocked_model_mismatch'
    con.execute('''UPDATE runs SET status=?,served_model=?,response_text=?,stop_reason=?,
        provider_response_id=?,input_tokens=?,output_tokens=?,cost_usd=?,completed_utc=?
        WHERE run_id=? AND response_text IS NULL''',
        (status,result.get('served_model'),text,stop,result.get('response_id'),
         result['input_tokens'],result['output_tokens'],expense,now(),run_id))
    con.commit()
    return status


def archived_successes(archive):
    result = {}
    source = Path(archive)
    if not source.exists():return result
    with source.open(encoding='utf-8') as stream:
        for number,line in enumerate(stream,1):
            if not line.strip():continue
            try:event=json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(f'Archive has an incomplete or invalid JSON record at line {number}; preserve and inspect it before resuming') from None
            if event.get('event')=='provider_success' and event.get('stage')=='tutor':
                key=event['attempt_id']
                if key in result and result[key][0]!=event:
                    raise ValueError('Conflicting archived responses for attempt '+key)
                result[key]=(event,sha(line))
    return result


def prepare_resume(c, con, archive, retry_ambiguous=False):
    """Recover received responses first; only explicitly authorize uncertain resends."""
    ensure_recovery_schema(con)
    archived = archived_successes(archive)
    prompts,_=docs(c)
    settings=tutor_settings(c)
    result = {'restored':[], 'requeued_safe':[], 'requeued_ambiguous':[], 'blocked':[]}
    rows = list(con.execute("""SELECT run_id,status FROM runs r WHERE response_text IS NULL AND
        (status IN ('in_flight','failed_api','blocked_ambiguous') OR
         (status='planned' AND EXISTS(SELECT 1 FROM attempts a WHERE a.stage='tutor' AND a.object_id=r.run_id)))
        ORDER BY created_utc,run_id"""))
    for row in rows:
        rid = row[0]
        attempt = con.execute("SELECT * FROM attempts WHERE stage='tutor' AND object_id=? ORDER BY number DESC LIMIT 1", (rid,)).fetchone()
        if attempt:
            frozen=con.execute('''SELECT r.condition,s.request_text FROM runs r
                JOIN student_requests s USING(request_id) WHERE r.run_id=?''',(rid,)).fetchone()
            expected=build_request(c['tutor']['provider'],c['tutor']['model'],prompts[frozen[0]],
                frozen[1],settings['max_output_tokens'],temperature=settings['temperature'])
            if json.loads(attempt['raw_request_json'])!=expected:
                raise ValueError('Attempt does not match the frozen request/settings: '+rid)
        if attempt and (attempt['status']=='success' or attempt['attempt_id'] in archived):
            raw = json.loads(attempt['raw_response_json']) if attempt['raw_response_json'] else None
            digest = attempt['archive_sha256']
            if attempt['attempt_id'] in archived:
                event, archive_hash = archived[attempt['attempt_id']]
                if event.get('object')!=rid or event['request']!=json.loads(attempt['raw_request_json']):
                    raise ValueError('Archive/request mismatch for '+rid)
                if digest and digest!=archive_hash:
                    raise ValueError('Archive hash mismatch for '+rid)
                if raw is not None and raw!=event['response']:
                    raise ValueError('Database/archive response mismatch for '+rid)
                raw=event['response'];digest=archive_hash
            if raw is None:raise ValueError('Saved successful attempt has no recoverable response: '+rid)
            output=parse_response(c['tutor']['provider'],raw)
            expense=cost_usd(output['input_tokens'],output['output_tokens'],c['tutor'])
            con.execute('''UPDATE attempts SET status='success',raw_response_json=?,error_json=NULL,
                input_tokens=?,output_tokens=?,cost_usd=?,finished_utc=COALESCE(finished_utc,?),archive_sha256=?
                WHERE attempt_id=?''', (canonical(raw),output['input_tokens'],output['output_tokens'],expense,now(),digest,attempt['attempt_id']))
            audit(con,rid,attempt['attempt_id'],'response_restored','Restore already received response; no provider call')
            save_tutor_result(con,c,rid,output,expense)
            result['restored'].append(rid)
        elif not attempt or attempt['status'] in ('terminal_error','transient_error'):
            if attempt and attempt['status']=='terminal_error':
                error=json.loads(attempt['error_json']) if attempt['error_json'] else {}
                if error.get('http_status') is None and 'no request sent' not in error.get('message',''):
                    # A malformed returned response is evidence, not permission to regenerate it.
                    result['blocked'].append(rid)
                    continue
            con.execute("UPDATE runs SET status='planned' WHERE run_id=?", (rid,))
            audit(con,rid,attempt['attempt_id'] if attempt else None,'safe_requeue','No successful response or uncertain provider attempt')
            result['requeued_safe'].append(rid)
        elif attempt['status'] in ('in_flight','ambiguous'):
            if attempt['status']=='in_flight':
                error={'message':'PROCESS_INTERRUPTED: provider outcome unknown','http_status':None,'retryable':False}
                con.execute("UPDATE attempts SET status='ambiguous',error_json=?,finished_utc=? WHERE attempt_id=?",
                            (canonical(error),now(),attempt['attempt_id']))
            if retry_ambiguous or retry_authorized(con,attempt['attempt_id']):
                audit(con,rid,attempt['attempt_id'],'retry_authorized',
                      'Explicit --retry-ambiguous: prior outcome and charges unknown; retain old attempt and use first newly received response')
                con.execute("UPDATE runs SET status='planned' WHERE run_id=?", (rid,))
                result['requeued_ambiguous'].append(rid)
            else:
                con.execute("UPDATE runs SET status='blocked_ambiguous' WHERE run_id=?", (rid,))
                result['blocked'].append(rid)
        else:
            raise ValueError('Unrecognized attempt state for '+rid+': '+attempt['status'])
    con.commit()
    return result
