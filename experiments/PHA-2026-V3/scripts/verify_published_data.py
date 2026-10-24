"""Offline integrity checks; prints counts without exposing answers or outcomes."""
from pathlib import Path
import hashlib
import json
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def jsonl(path):
    with path.open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for record in manifest['files']:
        path = ROOT / record['path']
        assert path.is_file(), 'Missing file: ' + record['path']
        assert path.stat().st_size == record['bytes'], 'File size mismatch: ' + record['path']
        assert digest(path) == record['sha256'], 'Checksum mismatch: ' + record['path']
    for path in ROOT.glob('published_data/researcher_only/grading/*/raw/*.parts.json'):
        archive = json.loads(path.read_text())
        full_hash, byte_count = hashlib.sha256(), 0
        for part in archive['parts']:
            file = path.parent / part['file']
            assert digest(file) == part['sha256']
            assert file.stat().st_size == part['bytes']
            with file.open('rb') as handle:
                lines = 0
                for line in handle:
                    json.loads(line)
                    full_hash.update(line)
                    byte_count += len(line)
                    lines += 1
            assert lines == part['records']
        assert byte_count == archive['original_bytes']
        assert full_hash.hexdigest() == archive['original_sha256']
    metadata = json.loads((ROOT / 'publication_metadata.json').read_text())
    database = ROOT / 'published_data/researcher_only/experiment_v3.sqlite'
    assert digest(database) == metadata['database_source_sha256']
    con = sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)
    con.row_factory = sqlite3.Row
    try:
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert con.execute('SELECT count(*) FROM student_requests').fetchone()[0] == 60
        assert con.execute("SELECT count(*) FROM runs WHERE status='complete'").fetchone()[0] == 180
        rater = metadata['active_rater_identifier']
        finals = {row['blind_id']: json.loads(row['result_json']) for row in con.execute(
            'SELECT blind_id,result_json FROM evaluations WHERE rater_identifier=?', (rater,))}
        assert len(finals) == 180
        prefix = metadata['active_grading_pipeline'][:12]
        published = jsonl(ROOT / ('published_data/researcher_only/grading/' + prefix + '/grades.jsonl'))
        assert len(published) == 180 and all(finals[g['blind_id']] == g for g in published)
        requests = jsonl(ROOT / 'published_data/inputs/frozen_student_requests.jsonl')
        assert len(requests) == 60
        saved_requests = {row['request_id']: dict(row) for row in con.execute('SELECT * FROM student_requests')}
        assert all(saved_requests[row['request_id']] == row for row in requests)
        runs = jsonl(ROOT / 'published_data/researcher_only/tutor_runs.jsonl')
        saved_runs = {row['run_id']: dict(row) for row in con.execute('SELECT * FROM runs')}
        assert len(runs) == 180 and all(saved_runs[row['run_id']] == row for row in runs)
        queue = jsonl(ROOT / 'published_data/blinded/responses.jsonl')
        assert len(queue) == 180 and len({row['blind_id'] for row in queue}) == 180
        forbidden = {'condition', 'run_id', 'scenario_id', 'served_model', 'provider', 'grade', 'adherence'}
        for item in queue:
            assert not forbidden.intersection(item), 'Unblinded metadata in review queue'
            original = con.execute('''SELECT r.response_text,sr.request_text,sr.level
                FROM blinded b JOIN runs r USING(run_id) JOIN student_requests sr USING(request_id)
                WHERE b.blind_id=?''', (item['blind_id'],)).fetchone()
            assert item['student_request'] == original['request_text']
            assert item['tutor_response'] == original['response_text']
            assert item['requested_level'] == original['level']
            grade = finals[item['blind_id']]
            assert grade['rater_type'] == 'llm'
            assert all(e['quote'] in item['tutor_response'] for e in grade['disclosure_evidence'])
        print(json.dumps({'status': 'VERIFIED', 'files_checked': len(manifest['files']),
                          'frozen_requests': 60, 'captured_responses': 180,
                          'blinded_review_items': 180, 'provisional_automated_grades': 180,
                          'original_archives_reconstruct_exactly': True}, indent=2))
    finally:
        con.close()


if __name__ == '__main__':
    main()
