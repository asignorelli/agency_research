"""An unscored, held-out tutor pilot with its own database and archive."""
from __future__ import annotations

import json
import random
from pathlib import Path

from .core import (
    CONDITIONS, LEVELS, SCHEMA, SUFFIXES, canonical, connect, dataset, docs,
    now, provenance, sha, tutor_settings,
)
from .runner import run_tutor_jobs, spent
from .recovery import collection_lock,prepare_resume,write_checkpoint


def pilot_cases(c):
    path = Path(c['_root']) / 'pilots/tutor_cases.json'
    content = json.loads(path.read_text(encoding='utf-8'))
    cases = content['cases']
    ids = [case['id'] for case in cases]
    if not cases or len(set(ids)) != len(ids):
        raise ValueError('Pilot needs distinct held-out cases')
    if set(ids) & {p['id'] for p in dataset(c)['problems']}:
        raise ValueError('Pilot case IDs overlap the scored dataset')
    if any(not case['title'] or not case['student_body'].strip() for case in cases):
        raise ValueError('Pilot cases need a title and a student body')
    return cases, sha(path.read_bytes())


def pilot_provenance(c):
    _, source_hash = pilot_cases(c)
    return {
        **provenance(c),
        'study_id': c['study_id'] + '-TUTOR-PILOT',
        'collection_kind': 'held_out_unscored_tutor_pilot',
        'pilot_cases_sha256': source_hash,
    }


def initialize_pilot(c, db):
    facts = pilot_provenance(c)
    cases, _ = pilot_cases(c)
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = connect(db)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        existing = con.execute("SELECT value_json FROM metadata WHERE key='provenance'").fetchone() if 'metadata' in tables else None
        if existing:
            if json.loads(existing[0]) != facts:
                raise ValueError('Pilot sources/config changed or this is a main-study DB; use a separate new pilot DB')
            return facts
        if tables:
            raise ValueError('Refusing to initialize a pilot over an existing database')
        con.executescript(SCHEMA)
        con.execute('INSERT INTO metadata VALUES(?,?)', ('provenance', canonical(facts)))
        prompts, _ = docs(c)
        for condition, text in prompts.items():
            con.execute('INSERT INTO prompts VALUES(?,?,?,?)',
                        ('tutor_' + condition, 'tutor', text, sha(text)))
        order = []
        rng = random.Random(c['randomization_seed'])
        for case in cases:
            con.execute('INSERT INTO scenarios VALUES(?,?,?,?)',
                        (case['id'], case['title'], 'held_out_unscored_pilot', canonical(case)))
            for level in LEVELS:
                request_id = f'PILOT-{case["id"]}-{level.upper()}'
                body = case['student_body']
                request = body.rstrip() + '\n\n' + SUFFIXES[level]
                con.execute('INSERT INTO student_requests VALUES(?,?,?,?,?,?,?)',
                            (request_id, case['id'], level, sha(body), request, sha(request), now()))
                conditions = list(CONDITIONS)
                rng.shuffle(conditions)
                # Each block of three jobs covers A/B/C for the SAME request.
                for condition in conditions:
                    run_id = request_id + '-' + condition
                    order.append(run_id)
                    con.execute('''INSERT INTO runs
                        (run_id,request_id,condition,status,requested_model,served_model,
                         prompt_sha256,settings_json,created_utc) VALUES(?,?,?,?,?,?,?,?,?)''',
                        (run_id, request_id, condition, 'planned', c['tutor']['model'], None,
                         sha(prompts[condition]), canonical(tutor_settings(c)), now()))
        con.execute('INSERT INTO metadata VALUES(?,?)', ('pilot_run_order', canonical(order)))
        con.commit()
        return facts
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _run_pilot_unlocked(c, db, archive, live=False, cap=None, limit=3,*,
                        timeout_seconds=None,continue_on_error=True,retry_ambiguous=False):
    if limit is not None and limit <= 0:
        raise ValueError('Limit must be positive')
    if live and (cap is None or cap <= 0):
        raise ValueError('Live pilot requires a positive --max-usd')
    if Path(db).resolve() == Path(archive).resolve():
        raise ValueError('Pilot database and archive must be different files')
    facts = initialize_pilot(c, db)
    con = connect(db)
    try:
        order = json.loads(con.execute("SELECT value_json FROM metadata WHERE key='pilot_run_order'").fetchone()[0])
        rows = {r['run_id']: r for r in con.execute('''SELECT r.run_id,r.request_id,r.condition,r.status,
                    sr.level,sr.request_text FROM runs r JOIN student_requests sr USING(request_id)''')}
        if live:
            prepare_resume(c,con,archive,retry_ambiguous)
            rows = {r['run_id']:r for r in con.execute('''SELECT r.run_id,r.request_id,r.condition,r.status,
                    sr.level,sr.request_text FROM runs r JOIN student_requests sr USING(request_id)''')}
        pending = [rows[run_id] for run_id in order if rows[run_id]['status'] == 'planned']
        completed = run_tutor_jobs(c, con, pending, archive, live, cap, limit,
            timeout_seconds=timeout_seconds,continue_on_error=continue_on_error) if live else 0
        return {
            'collection_kind': facts['collection_kind'],
            'study_id': facts['study_id'],
            'live': live,
            'database': str(Path(db).resolve()),
            'archive': str(Path(archive).resolve()),
            'completed_this_invocation': completed,
            'spend_recorded_usd': round(spent(con), 6),
            'runs': [dict(r) for r in con.execute('SELECT status,COUNT(*) n FROM runs GROUP BY status')],
            'next_jobs': [
                {'run_id': rows[rid]['run_id'], 'condition': rows[rid]['condition'],
                 'requested_level': rows[rid]['level']}
                for rid in order
                if con.execute('SELECT status FROM runs WHERE run_id=?', (rid,)).fetchone()[0] == 'planned'
            ][:limit],
            'note': 'Held-out pilot responses are excluded from the 180 scored jobs. '
                    'Without --live, no provider is called. The first three jobs cover A/B/C.',
        }
    finally:
        con.close()


def run_pilot(c,db,archive,live=False,cap=None,limit=3,*,timeout_seconds=None,
              continue_on_error=True,retry_ambiguous=False):
    with collection_lock(db):
        return _run_pilot_unlocked(c,db,archive,live,cap,limit,timeout_seconds=timeout_seconds,
            continue_on_error=continue_on_error,retry_ambiguous=retry_ambiguous)
