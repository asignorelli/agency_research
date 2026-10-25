"""Regression checks for live-request provenance, model drift, and pilot isolation.

All provider responses are mocked or HTTP is explicitly blocked.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency_study.core import connect, get_config, initialize, verify_db_sources
from agency_study.pilot import run_pilot
from agency_study.providers import ModelMismatchError, build_request, invoke
from agency_study.runner import (
    freeze_candidates, generate_student_bodies, repair_planned_after_safe_error,
    run_tutors, spent,
)


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'main.sqlite'
        self.archive = self.root / 'main.jsonl'
        self.c = get_config()
        self.c.pop('student_input_mode',None)
        self.c.pop('student_messages',None)
        initialize(self.c, self.db)

    def fake_response(self, provider, payload):
        if provider == 'anthropic':
            visible = json.loads(payload['messages'][0]['content'])['student_visible']
            text = 'I am working on this task: ' + visible['task']
            text += '\n```python\n' + visible['starting_code'] + '\n```\n'
            text += 'I am confused about the supplied observations.'
        else:
            text = 'Compare what each variable represents with the task requirements.'
        return {
            'text': text, 'raw': {'mock': True, 'model': payload['model'], 'text': text},
            'served_model': payload['model'], 'response_id': 'mock-response',
            'input_tokens': 1000, 'output_tokens': 100,
            'stop_reason': 'stop', 'elapsed_seconds': 0.0,
        }

    def freeze_mock_inputs(self):
        with patch('agency_study.runner.invoke', side_effect=self.fake_response):
            generate_student_bodies(self.c, self.db, self.archive, True, 1)
        freeze_candidates(self.c, self.db, True)

    def test_student_requests_archive_explicit_reasoning_settings(self):
        with patch('agency_study.runner.invoke', side_effect=self.fake_response) as provider:
            self.assertEqual(generate_student_bodies(self.c, self.db, self.archive, True, 1, 1), 1)
        request = provider.call_args.args[1]
        self.assertEqual(request['output_config']['effort'], 'medium')
        self.assertEqual(request['thinking'], {'type': 'adaptive'})
        self.assertNotIn('temperature', request)
        archived = json.loads(self.archive.read_text().splitlines()[0])['request']
        self.assertEqual(archived, request)

    def test_tutor_settings_match_actual_archived_requests(self):
        self.freeze_mock_inputs()
        with patch('agency_study.runner.invoke', side_effect=self.fake_response):
            run_tutors(self.c, self.db, self.archive, True, 1, 3)
        con = connect(self.db)
        self.addCleanup(con.close)
        rows = con.execute('''SELECT r.settings_json,a.raw_request_json FROM runs r
            JOIN attempts a ON r.run_id=a.object_id AND a.stage='tutor'
            WHERE r.status='complete' ''').fetchall()
        self.assertEqual(len(rows), 3)
        for row in rows:
            settings = json.loads(row['settings_json'])
            request = json.loads(row['raw_request_json'])
            self.assertEqual(settings['temperature'], request['temperature'])
            self.assertEqual(settings['temperature'], 0.0)
            self.assertEqual(settings['max_output_tokens'], request['max_tokens'])
            self.assertFalse(settings['tools'])
            self.assertNotIn('tools', request)

    def test_student_model_mismatch_preserves_response_and_blocks_resume_and_freeze(self):
        def mismatch(provider, payload):
            response = self.fake_response(provider, payload)
            response['served_model'] = 'unexpected-student-model'
            response['raw']['model'] = response['served_model']
            return response
        with patch('agency_study.runner.invoke', side_effect=mismatch) as provider:
            with self.assertRaises(ModelMismatchError):
                generate_student_bodies(self.c, self.db, self.archive, True, 1, 2)
            with self.assertRaises(ModelMismatchError):
                generate_student_bodies(self.c, self.db, self.archive, True, 1, 2)
            with self.assertRaises(ModelMismatchError):
                freeze_candidates(self.c, self.db, True)
            self.assertEqual(provider.call_count, 1)
        con = connect(self.db)
        self.addCleanup(con.close)
        candidate = con.execute('SELECT * FROM student_candidates').fetchone()
        self.assertEqual(candidate['status'], 'blocked_model_mismatch')
        self.assertTrue(candidate['body'])
        self.assertGreater(spent(con), 0)
        self.assertEqual(len(self.archive.read_text().splitlines()), 1)

    def test_tutor_model_drift_halts_after_preserving_billed_response(self):
        self.freeze_mock_inputs()
        calls = 0
        def drift(provider, payload):
            nonlocal calls
            calls += 1
            response = self.fake_response(provider, payload)
            if calls == 2:
                response['served_model'] = 'unexpected-tutor-model'
                response['raw']['model'] = response['served_model']
            return response
        with patch('agency_study.runner.invoke', side_effect=drift) as provider:
            with self.assertRaises(ModelMismatchError):
                run_tutors(self.c, self.db, self.archive, True, 1, 3)
            with self.assertRaises(ModelMismatchError):
                run_tutors(self.c, self.db, self.archive, True, 1, 3)
            self.assertEqual(provider.call_count, 2)
        con = connect(self.db)
        self.addCleanup(con.close)
        counts = dict(con.execute('SELECT status,COUNT(*) FROM runs GROUP BY status').fetchall())
        self.assertEqual(counts, {'complete': 1, 'blocked_model_mismatch': 1, 'planned': 178})
        blocked = con.execute("SELECT response_text,served_model,cost_usd FROM runs WHERE status='blocked_model_mismatch'").fetchone()
        self.assertTrue(blocked['response_text'])
        self.assertEqual(blocked['served_model'], 'unexpected-tutor-model')
        self.assertGreater(blocked['cost_usd'], 0)
        self.assertEqual(repair_planned_after_safe_error(self.c, self.db), [])

    def test_missing_api_key_is_not_left_as_an_ambiguous_attempt(self):
        with patch.dict(os.environ, {}, clear=True), patch('urllib.request.urlopen') as http:
            with self.assertRaisesRegex(Exception, 'ANTHROPIC_API_KEY is not set'):
                generate_student_bodies(self.c, self.db, self.archive, True, 1, 1)
            http.assert_not_called()
        con = connect(self.db)
        self.addCleanup(con.close)
        self.assertEqual(con.execute('SELECT status FROM attempts').fetchone()[0], 'terminal_error')
        self.assertEqual(spent(con), 0)

    def test_provider_does_not_invent_a_missing_served_model(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json.dumps({'choices': [{'message': {'content': 'Mock response'},
                                               'finish_reason': 'stop'}]}).encode()
        payload = build_request('deepinfra', self.c['tutor']['model'], 'System', 'Student', 20)
        with patch.dict(os.environ, {'DEEPINFRA_API_KEY': 'mock-key'}), \
                patch('urllib.request.urlopen', return_value=Response()):
            result = invoke('deepinfra', payload)
        self.assertIsNone(result['served_model'])

    def test_held_out_pilot_covers_conditions_and_levels_without_touching_main(self):
        pilot_db = self.root / 'pilot.sqlite'
        pilot_archive = self.root / 'pilot.jsonl'
        with patch('agency_study.runner.invoke') as provider:
            preview = run_pilot(self.c, pilot_db, pilot_archive)
            provider.assert_not_called()
        self.assertEqual({job['condition'] for job in preview['next_jobs']}, {'A', 'B', 'C'})
        self.assertEqual(preview['runs'], [{'status': 'planned', 'n': 9}])
        self.assertFalse(pilot_archive.exists())
        with patch('agency_study.runner.invoke', side_effect=self.fake_response) as provider:
            first = run_pilot(self.c, pilot_db, pilot_archive, True, 1, 3)
            remaining = run_pilot(self.c, pilot_db, pilot_archive, True, 1, 9)
            resumed = run_pilot(self.c, pilot_db, pilot_archive, True, 1, 9)
            self.assertEqual(provider.call_count, 9)
        self.assertEqual(first['completed_this_invocation'], 3)
        self.assertEqual(remaining['completed_this_invocation'], 6)
        self.assertEqual(resumed['completed_this_invocation'], 0)
        main = verify_db_sources(self.c, self.db)
        self.addCleanup(main.close)
        for table in ('student_candidates', 'student_requests', 'runs', 'attempts'):
            self.assertEqual(main.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
        con = connect(pilot_db)
        self.addCleanup(con.close)
        for row in con.execute('''SELECT sr.level,COUNT(*) n,COUNT(DISTINCT r.condition) conditions,
                COUNT(DISTINCT sr.request_sha256) requests FROM runs r
                JOIN student_requests sr USING(request_id) GROUP BY sr.level'''):
            self.assertEqual(row['n'], 3)
            self.assertEqual(row['conditions'], 3)
            self.assertEqual(row['requests'], 1)
        self.assertEqual(len(pilot_archive.read_text().splitlines()), 9)
        with self.assertRaisesRegex(ValueError, 'Sources/config changed'):
            verify_db_sources(self.c, pilot_db)

    def test_pilot_refuses_main_database_and_changed_sources(self):
        with self.assertRaisesRegex(ValueError, 'main-study DB'):
            run_pilot(self.c, self.db, self.root / 'pilot.jsonl')
        pilot_db = self.root / 'pilot.sqlite'
        run_pilot(self.c, pilot_db, self.root / 'pilot.jsonl')
        changed = {**self.c, 'tutor': {**self.c['tutor'], 'temperature': 0.25}}
        with self.assertRaisesRegex(ValueError, 'Pilot sources/config changed'):
            run_pilot(changed, pilot_db, self.root / 'pilot.jsonl')


if __name__ == '__main__':
    unittest.main()
