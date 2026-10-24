"""Reproducible study artifacts, independent from any network provider."""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .student_inputs import configured_student_messages

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ('hint', 'explanation', 'solution')
CONDITIONS = ('A', 'B', 'C')
SUFFIXES = {
 'hint': 'Please give me one focused hint, diagnostic question, or check. Leave the diagnosis and repair to me; do not give the complete diagnosis, exact correction, corrected code, or a step-by-step recipe that supplies the answer.',
 'explanation': 'Please explain what is going wrong and why, including the relevant concept. Leave the exact correction and implementation to me; do not give corrected code or a step-by-step recipe that supplies the finished repair.',
 'solution': 'Please give me the complete corrected code that satisfies the task and its constraints, with a brief explanation of why it works.'
}

def now(): return datetime.now(timezone.utc).isoformat()
def canonical(x): return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
def sha(x):
    if not isinstance(x, bytes): x = x.encode('utf-8')
    return hashlib.sha256(x).hexdigest()
def get_config(path=None):
    path = Path(path) if path else ROOT / 'config.json'
    c = json.loads(path.read_text(encoding='utf-8'))
    c['_root'] = str(path.resolve().parent)
    return c
def source_file(config, key): return Path(config['_root']) / config[key]
def dataset(config): return json.loads(source_file(config, 'dataset').read_text(encoding='utf-8'))
def cards(config): return json.loads(source_file(config, 'cards').read_text(encoding='utf-8'))
def docs(config):
    raw = source_file(config, 'tutor_document').read_text(encoding='utf-8')
    markers = ['## Tutor A:', '## Tutor B:', '## Tutor C:']
    p={}
    for i,key in enumerate(CONDITIONS):
        val = raw.split(markers[i],1)[1]
        val = val.split(markers[i+1],1)[0] if i+1<3 else val.split('## Methodological notes',1)[0]
        val = val.split('\n---',1)[0].strip()
        val = '### Role'+val.split('### Role',1)[1]
        assert "### Response\nRespond directly to the student's message." in val
        p[key] = val
    without_examples=p['C'].split('### Assistance examples',1)[0].rstrip()+'\n\n### Response'+p['C'].split('### Response',1)[1]
    assert without_examples==p['B'], 'Condition C must add only examples to condition B'
    stu=source_file(config, 'student_document').read_text(encoding='utf-8').split('```text\n',1)[1].split('\n```',1)[0]
    return p,stu

def provenance(c):
    pp,sp=docs(c)
    facts = {'study_id':c['study_id'], 'dataset_sha256':sha(source_file(c,'dataset').read_bytes()),
        'cards_sha256':sha(source_file(c,'cards').read_bytes()),
        'rubric_sha256':sha(source_file(c,'rubric').read_bytes()),
        'schema_sha256':sha(source_file(c,'schema').read_bytes()),
        'student_prompt_sha256':sha(sp), 'tutor_prompt_sha256':{k:sha(v) for k,v in pp.items()},
        'suffix_sha256':{k:sha(v) for k,v in SUFFIXES.items()},
        'student_model':c['student']['model'],'tutor_model':c['tutor']['model'],
        'acquisition_config_sha256':sha(canonical({'student':c['student'],'tutor':c['tutor'],'retry':c['retry'],'randomization_seed':c['randomization_seed'],'concurrency':c['concurrency']}))}
    # Keep legacy V2 provenance reconstructible with its saved configuration.
    if c.get('student_input_mode') == 'standardized_import':
        messages = configured_student_messages(c)
        facts.update(student_input_mode='standardized_import', student_model=None,
            student_messages_sha256=sha(source_file(c, 'student_messages').read_bytes()),
            standardized_body_sha256={str(sid):sha(item['body']) for sid,item in messages.items()})
    if c.get('original_dataset'):
        facts['original_dataset_sha256'] = sha(source_file(c, 'original_dataset').read_bytes())
    return facts

def validate_sources(c):
    d=dataset(c); cc=cards(c)
    assert d['schema_version']=='2.0'
    problems=d['problems']; ids={p['id'] for p in problems}
    assert len(problems)==20 and ids==set(range(1,21)), 'Need 20 distinct problems numbered 1..20'
    assert len(cc['cards'])==20 and {p['scenario_id'] for p in cc['cards']}==ids
    cats=Counter(p['researcher_only'].get('case_design',{}).get('category','original_continuity') for p in problems)
    expected=d['experiment_design'].get('case_counts')
    if expected is not None and dict(cats) != expected:
        raise ValueError('Scenario categories do not match the declared dataset composition')
    card_map={card['scenario_id']:card for card in cc['cards']}
    for p in problems:
        v=p['student_visible']; a=p['researcher_only']
        assert v['task'] and v['starting_code'] and v['observed_examples']
        assert isinstance(v['attempt_history'],list)
        assert a['diagnosis'] and a['repair']
        card=card_map[p['id']]
        for key,value in [('title',p['title']),('task_requirements',v['task']),
                          ('reference_diagnosis',a['diagnosis']),('reference_repair',a['repair'])]:
            if card[key] != value:
                raise ValueError(f'Scoring card {p["id"]} has mismatched {key}')
        if cc.get('source_dataset_sha256') and card.get('source_code_sha256') != sha(v['starting_code']):
            raise ValueError(f'Scoring card {p["id"]} has mismatched attempt code')
    if cc.get('source_dataset_sha256') and cc['source_dataset_sha256'] != sha(source_file(c,'dataset').read_bytes()):
        raise ValueError('Scoring cards were built for a different dataset')
    if c.get('student_input_mode') == 'standardized_import':
        messages=configured_student_messages(c)
        originals={p['id']:p for p in json.loads(source_file(c,'original_dataset').read_text(encoding='utf-8'))}
        for p in problems:
            item=messages[p['id']]; original=originals[p['id']]
            if item['title'] != p['title'] or original['title'] != p['title']:
                raise ValueError(f'Student message {p["id"]} has a mismatched title')
            outcome=check_body(item['body'],p)
            if not outcome['pass']:
                raise ValueError(f'Student message {p["id"]} failed checks: {outcome["issues"]}')
            if p['student_visible']['starting_code'] != original['attempt_history'][0]:
                raise ValueError(f'Scenario {p["id"]} does not use the original buggy attempt')
            if p['student_visible']['task'] not in item['body']:
                raise ValueError(f'Student message {p["id"]} omits the supplied task')
            if card_map[p['id']].get('student_body_sha256') != sha(item['body']):
                raise ValueError(f'Scoring card {p["id"]} does not match the standardized student body')
    pp,st=docs(c)
    assert len(pp)==3 and st
    assert c['tutor']['model'] and c['student']['model']
    return provenance(c)

def connect(db):
    conn=sqlite3.connect(str(db))
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=15000')
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

SCHEMA='''
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS prompts(prompt_key TEXT PRIMARY KEY, kind TEXT NOT NULL, exact_text TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scenarios(scenario_id INTEGER PRIMARY KEY, title TEXT NOT NULL, case_category TEXT NOT NULL, record_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS student_candidates(candidate_id TEXT PRIMARY KEY, scenario_id INTEGER REFERENCES scenarios(scenario_id), body TEXT, validation_json TEXT, status TEXT NOT NULL, provider TEXT, requested_model TEXT, served_model TEXT, raw_response_json TEXT, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, created_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS student_bodies(scenario_id INTEGER PRIMARY KEY REFERENCES scenarios(scenario_id), candidate_id TEXT REFERENCES student_candidates(candidate_id), body TEXT NOT NULL, body_sha256 TEXT NOT NULL, validation_method TEXT NOT NULL, frozen_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS student_requests(request_id TEXT PRIMARY KEY, scenario_id INTEGER NOT NULL REFERENCES scenarios(scenario_id), level TEXT NOT NULL CHECK(level IN ('hint','explanation','solution')), body_sha256 TEXT NOT NULL, request_text TEXT NOT NULL, request_sha256 TEXT NOT NULL, created_utc TEXT NOT NULL, UNIQUE(scenario_id,level));
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES student_requests(request_id), condition TEXT NOT NULL CHECK(condition IN ('A','B','C')), status TEXT NOT NULL, requested_model TEXT NOT NULL, served_model TEXT, prompt_sha256 TEXT NOT NULL, settings_json TEXT NOT NULL, response_text TEXT, stop_reason TEXT, provider_response_id TEXT, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, created_utc TEXT NOT NULL, completed_utc TEXT, UNIQUE(request_id,condition));
CREATE TABLE IF NOT EXISTS attempts(attempt_id TEXT PRIMARY KEY, stage TEXT NOT NULL, object_id TEXT NOT NULL, number INTEGER NOT NULL, status TEXT NOT NULL, raw_request_json TEXT NOT NULL, raw_response_json TEXT, error_json TEXT, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, started_utc TEXT NOT NULL, finished_utc TEXT, archive_sha256 TEXT, UNIQUE(stage,object_id,number));
CREATE TABLE IF NOT EXISTS blinded(blind_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES runs(run_id), created_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evaluations(evaluation_id TEXT PRIMARY KEY, blind_id TEXT NOT NULL REFERENCES blinded(blind_id), rubric_sha256 TEXT NOT NULL, rater_type TEXT NOT NULL, rater_identifier TEXT NOT NULL, result_json TEXT NOT NULL, provider TEXT, served_model TEXT, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL, created_utc TEXT NOT NULL, UNIQUE(blind_id,rater_identifier,rubric_sha256));
'''

def initialize(c,db):
    facts=validate_sources(c)
    db=Path(db); db.parent.mkdir(parents=True,exist_ok=True)
    con=connect(db); con.executescript(SCHEMA)
    existing=con.execute("SELECT value_json FROM metadata WHERE key='provenance'").fetchone()
    if existing and json.loads(existing[0])!=facts:
        raise ValueError('Source/config has changed since database creation; start a new DB to preserve provenance')
    con.execute("INSERT OR IGNORE INTO metadata VALUES('provenance',?)",(canonical(facts),))
    pp,sp=docs(c)
    for k,t in [('student',sp)]+[(f'tutor_{k}',v) for k,v in pp.items()]:
        con.execute('INSERT OR IGNORE INTO prompts VALUES(?,?,?,?)',(k,'student' if k=='student' else 'tutor',t,sha(t)))
    for p in dataset(c)['problems']:
        cat=p['researcher_only'].get('case_design',{}).get('category','original_continuity')
        con.execute('INSERT OR IGNORE INTO scenarios VALUES(?,?,?,?)',(p['id'],p['title'],cat,canonical(p)))
    con.commit(); con.close()
    return facts

def verify_db_sources(c,db):
    con=connect(db)
    row=con.execute("SELECT value_json FROM metadata WHERE key='provenance'").fetchone()
    if not row: raise ValueError('DB not initialized. Run init')
    if json.loads(row[0]) != provenance(c): raise ValueError('Sources/config changed; do not continue this experiment DB')
    return con

def sanitize_visible(problem):
    vis=json.loads(canonical(problem['student_visible']))
    for ex in vis.get('observed_examples',[]): ex.pop('verification',None)
    return vis

def build_student_payload(problem):
    vis=sanitize_visible(problem)
    return {'mode':'opening_body','student_visible':vis,
        'task_title':problem['title'], 'task_difficulty':problem['difficulty'],
        'runtime_conventions_note':'Follow the student-visible task and code as given; preserve all supplied code verbatim.'}

def check_body(text,problem):
    code=problem['student_visible']['starting_code']
    reasons=[]
    if not isinstance(text,str) or not text.strip(): reasons.append('empty')
    elif code not in text: reasons.append('starting_code_not_verbatim')
    if len(text or '')>12000: reasons.append('excessive_length')
    # Language in a student's own code can contain these phrases; check only framing outside fenced code.
    prose=re.sub(r'```[\s\S]*?```','',text or '',flags=re.MULTILINE).lower()
    if re.search(r'\b(please give me (a|one) (hint|explanation)|give me (the|a) complete (solution|code)|please solve)\b',prose):
        reasons.append('premature_assistance_request')
    if re.search(r'\b(system prompt|as an ai|tutor condition|grading rubric|researcher_only)\b',prose):
        reasons.append('role_leakage')
    return {'pass':not reasons,'issues':reasons,'requires_factual_review':True,
            'note':'Automatic checks cannot verify narrative consistency, so student inputs are provisional unless reviewed.'}

def freeze_body(con,scenario_id,body,candidate_id=None,method='author_acknowledged'):
    p=json.loads(con.execute('SELECT record_json FROM scenarios WHERE scenario_id=?',(scenario_id,)).fetchone()[0])
    outcome=check_body(body,p)
    if not outcome['pass']: raise ValueError(f'Body failed structural checks: {outcome["issues"]}')
    if con.execute('SELECT 1 FROM student_requests WHERE scenario_id=?',(scenario_id,)).fetchone(): raise ValueError('Requests are already frozen for this scenario')
    con.execute('INSERT INTO student_bodies VALUES(?,?,?,?,?,?)', (scenario_id,candidate_id,body,sha(body),method,now()))
    for level in LEVELS:
        req=body.rstrip()+'\n\n'+SUFFIXES[level]
        rid=f'P{scenario_id:02d}-{level.upper()}'
        con.execute('INSERT INTO student_requests VALUES(?,?,?,?,?,?,?)',(rid,scenario_id,level,sha(body),req,sha(req),now()))

def seed_runs(c,con):
    import random
    n=con.execute('SELECT count(*) FROM student_requests').fetchone()[0]
    if n!=60: raise ValueError(f'Need 60 frozen requests; have {n}')
    pp,_=docs(c); records=[]
    for r in con.execute('SELECT request_id FROM student_requests ORDER BY request_id'):
        for condition in CONDITIONS:
            rid=f'{r[0]}-{condition}'
            records.append((rid,r[0],condition,'planned',c['tutor']['model'],None,sha(pp[condition]),
                            canonical(tutor_settings(c)),now()))
    random.Random(c['randomization_seed']).shuffle(records)
    for x in records:
        con.execute('INSERT OR IGNORE INTO runs(run_id,request_id,condition,status,requested_model,served_model,prompt_sha256,settings_json,created_utc) VALUES(?,?,?,?,?,?,?,?,?)',x)
    return len(records)


def tutor_settings(c):
    """The inference settings used to build every tutor request."""
    return {
        'max_output_tokens': c['tutor']['max_output_tokens'],
        'temperature': c['tutor'].get('temperature'),
        'tools': False,
    }
