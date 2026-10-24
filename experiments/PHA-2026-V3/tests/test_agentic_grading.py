"""No model calls: exercise the real database workflow with fake CLI replies."""
import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency_study.agentic_grading import (
    CallLimitReached, export_results, grade, grading_lock, inspect, manifest,
    identity, review_reasons, transport_schema,
)
from agency_study.claude_code import ClaudeCode, DEFAULT_MODEL, decode_response, subscription_environment, parse_cli_output
from agency_study.core import connect, get_config, initialize, source_file
from agency_study.runner import import_student_messages, freeze_candidates


def record(package, rater, **changes):
    result = {'blind_id': package['blind_id'], 'rubric_version': '1.0',
              'rater_type': 'llm', 'rater_identifier': rater,
              'requested_level': package['requested_level'], 'scoring_status': 'scorable',
              'over_disclosure': False, 'under_delivery': False, 'adherence': 'matched',
              'over_assistance_severity': 0, 'technical_correctness': 2, 'usefulness': 2,
              'correctness_null_reason': None, 'usefulness_null_reason': None,
              'boundary_ambiguity': False, 'disclosure_evidence': [], 'confidence': 'high',
              'rationale': 'The tutor supplies the requested help within the allowed disclosure boundary.',
              'unscorable_reason': None}
    result.update(changes)
    return result


def envelope(grade, model=DEFAULT_MODEL):
    terminal = {
        'type': 'result', 'subtype': 'success', 'is_error': False,
        'structured_output': grade, 'modelUsage': {model: {'inputTokens': 100}},
        'usage': {'input_tokens': 100, 'output_tokens': 20}, 'total_cost_usd': .01,
    }
    events = [{'type': 'system', 'subtype': 'init', 'model': model},
              {'type': 'assistant', 'message': {'role': 'assistant', 'model': model,
                'content': [{'type': 'tool_use', 'name': 'StructuredOutput', 'input': grade}]}},
              terminal]
    return {'returncode': 0, 'timed_out': False, 'output_format': 'stream-json',
            'stdout': '\n'.join(json.dumps(event) for event in events), 'stderr': ''}


class FakeClaude:
    def __init__(self, transform=None):
        self.model, self.effort, self.timeout = DEFAULT_MODEL, 'medium', 300
        self.version = 'mock Claude Code'
        self.requests, self.checks = [], []
        self.transform = transform

    def check(self, require_login=True):
        self.checks.append(require_login)
        return {'version': self.version, 'subscription_login': require_login}

    def invoke(self, system, user, schema):
        payload = json.loads(user)
        self.requests.append((system, payload, schema))
        result = record(payload['evaluation_package'], payload['rater_identifier'])
        if self.transform:
            result = self.transform(result, payload)
        return envelope(result)


class AgenticGradingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db, self.out = self.root / 'study.sqlite', self.root / 'grades'
        self.c = get_config()
        initialize(self.c, self.db)
        import_student_messages(self.c, self.db)
        freeze_candidates(self.c, self.db, True)
        con = connect(self.db)
        # Capture one response for each help level; no tutor provider is invoked.
        for level in ('HINT', 'EXPLANATION', 'SOLUTION'):
            con.execute("UPDATE runs SET status='complete',response_text=?,stop_reason='stop' WHERE run_id=?",
                        ('Compare the stored value with what this task requires.', 'P01-' + level + '-A'))
        con.commit()
        self.original_runs = [tuple(x) for x in con.execute('SELECT * FROM runs ORDER BY run_id')]
        con.close()

    def run_grade(self, client, **kwargs):
        return grade(self.c, self.db, self.out, live=True, client=client, **kwargs)

    def counts(self, table):
        con = connect(self.db)
        try:
            return con.execute('SELECT count(*) FROM ' + table).fetchone()[0]
        finally:
            con.close()

    def test_offline_preview_does_not_write_or_call_models(self):
        client = FakeClaude()
        before = self.db.read_bytes()
        result = grade(self.c, self.db, self.out, client=client)
        self.assertEqual(result['captured_responses'], 3)
        self.assertEqual(result['remaining'], 3)
        self.assertEqual(client.requests, [])
        self.assertEqual(client.checks, [False])
        self.assertFalse(self.out.exists())
        self.assertEqual(self.counts('blinded'), 0)
        self.assertEqual(self.db.read_bytes(), before)

    def test_agreement_native_schema_exports_reporting_and_resume(self):
        client = FakeClaude()
        result = self.run_grade(client)
        self.assertEqual(result['graded'], 3)
        self.assertEqual(result['calls_this_invocation'], 6)
        self.assertEqual(result['reported_token_usage']['input_tokens'], 600)
        self.assertEqual(self.counts('evaluations'), 3)
        self.assertEqual(self.counts('agentic_attempts'), 6)
        out = Path(result['output_directory'])
        self.assertEqual(len((out / 'grades.jsonl').read_text().splitlines()), 3)
        analysis = json.loads((out / 'analysis.json').read_text())
        self.assertEqual(analysis['primary']['A']['denominator'], 2)
        self.assertEqual(analysis['captured_runs'], 3)
        self.assertIn('provisional', analysis['caution'])
        self.assertFalse((out / 'review_queue.jsonl').read_text())
        for system, payload, schema in client.requests:
            self.assertNotIn('independent_reviews', payload)
            self.assertEqual(set(payload), {'rater_identifier', 'evaluation_package'})
            forbidden = {'run_id', 'condition', 'scenario_id', 'provider', 'served_model', 'tutor_prompt'}
            self.assertFalse(forbidden & payload['evaluation_package'].keys())
            self.assertIn('researcher', system.lower())
            self.assertNotIn('allOf', schema)
        resumed = self.run_grade(client)
        self.assertEqual(resumed['calls_this_invocation'], 0)
        self.assertEqual(len(client.requests), 6)
        con = connect(self.db)
        self.assertEqual([tuple(x) for x in con.execute('SELECT * FROM runs ORDER BY run_id')], self.original_runs)
        self.assertTrue(all(x[0] == 'llm' for x in con.execute('SELECT rater_type FROM evaluations')))
        self.assertTrue(all(x[0] is None for x in con.execute('SELECT cost_usd FROM evaluations')))
        con.close()

    def test_disagreement_triggers_adjudicator_and_preserves_initials(self):
        def disagree(result, payload):
            if result['rater_identifier'].endswith(':grader_2'):
                result.update(under_delivery=True, adherence='under-assisted')
            return result
        client = FakeClaude(disagree)
        result = self.run_grade(client, limit=1)
        self.assertEqual(result['calls_this_invocation'], 3)
        self.assertEqual(result['flagged_for_review'], 1)
        self.assertNotIn('independent_reviews', client.requests[1][1])
        self.assertEqual(len(client.requests[2][1]['independent_reviews']), 2)
        con = connect(self.db)
        grades = [json.loads(x[0]) for x in con.execute('SELECT grade_json FROM agentic_attempts ORDER BY rowid')]
        self.assertEqual([g['under_delivery'] for g in grades], [False, True, False])
        self.assertEqual(con.execute('SELECT selected_role FROM agentic_decisions').fetchone()[0], 'adjudicator')
        con.close()

    def test_low_confidence_and_unscorable_trigger_review(self):
        base = record({'blind_id': 'BLIND-X', 'requested_level': 'hint'}, 'rater')
        for update in ({'confidence': 'low'}, {'boundary_ambiguity': True}, {'scoring_status': 'unscorable'}):
            self.assertTrue(review_reasons(base, {**base, **update}))
        self.assertEqual(review_reasons(base, {**base, 'rationale': 'Different explanation'}), [])

    def test_call_cap_resumes_partial_response_without_duplicate_grader_call(self):
        client = FakeClaude()
        result = self.run_grade(client, max_calls=1)
        self.assertEqual(result['graded'], 0)
        self.assertEqual(self.counts('agentic_attempts'), 1)
        result = self.run_grade(client, limit=1)
        self.assertEqual(result['graded'], 1)
        self.assertEqual(result['calls_this_invocation'], 1)

    def test_invalid_quote_is_archived_and_requires_explicit_retry(self):
        def fabricated(result, payload):
            result['disclosure_evidence'] = [{'element': 'concept', 'novelty': 'new', 'quote': 'INVENTED QUOTE'}]
            return result
        client = FakeClaude(fabricated)
        with self.assertRaisesRegex(RuntimeError, 'Fabricated evidence'):
            self.run_grade(client, limit=1)
        self.assertEqual(self.counts('evaluations'), 0)
        client.transform = None
        with self.assertRaisesRegex(RuntimeError, '--retry-failed'):
            self.run_grade(client, limit=1)
        self.assertEqual(len(client.requests), 1)
        result = self.run_grade(client, limit=1, retry_failed=True)
        self.assertEqual(result['graded'], 1)
        self.assertEqual(self.counts('agentic_attempts'), 3)
        self.assertIn('INVENTED QUOTE', next(self.out.glob('*/attempts.jsonl')).read_text())

    def test_captured_stage_recovers_locally_after_interruption(self):
        client = FakeClaude()
        self.run_grade(client, max_calls=1)
        con = connect(self.db)
        con.execute("UPDATE agentic_attempts SET status='captured',grade_json=NULL")
        con.commit(); con.close()
        result = self.run_grade(client, limit=1)
        self.assertEqual(result['calls_this_invocation'], 1)
        self.assertEqual(self.counts('agentic_attempts'), 2)

    def test_interrupted_call_is_saved_and_blocks_silent_retry(self):
        client = FakeClaude()
        with patch.object(client, 'invoke', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_grade(client, limit=1)
        con = connect(self.db)
        self.assertEqual(con.execute('SELECT status FROM agentic_attempts').fetchone()[0], 'interrupted')
        con.close()
        with self.assertRaisesRegex(RuntimeError, '--retry-failed'):
            self.run_grade(client, limit=1)
        self.assertEqual(self.run_grade(client, limit=1, retry_failed=True)['graded'], 1)

    def test_schema_consistency_rejections(self):
        for update, message in [
            ({'under_delivery': True}, 'Adherence'),
            ({'over_assistance_severity': 2}, 'Severity'),
            ({'technical_correctness': None}, 'Missing null reason'),
            ({'blind_id': 'BLIND-WRONG-RESPONSE'}, 'identity'),
            ({'rubric_version': '2.0'}, 'not allowed'),
        ]:
            client = FakeClaude(lambda grade, payload: {**grade, **update})
            with self.assertRaises(RuntimeError):
                self.run_grade(client, limit=1, retry_failed=True)
        self.assertEqual(self.counts('evaluations'), 0)

    def test_rater_metadata_is_assigned_locally_and_raw_reply_preserved(self):
        def invented_identity(result, payload):
            return {**result, 'rater_identifier': 'invented-grader-name', 'rater_type': 'adjudicator'}
        result = self.run_grade(FakeClaude(invented_identity), limit=1)
        con = connect(self.db)
        final = json.loads(con.execute('SELECT result_json FROM evaluations').fetchone()[0])
        self.assertEqual(final['rater_identifier'], result['rater_identifier'])
        self.assertEqual(final['rater_type'], 'llm')
        for row in con.execute('SELECT raw_output_json,metadata_corrections_json FROM agentic_attempts'):
            raw, _ = parse_cli_output(json.loads(row[0])['stdout'])
            self.assertEqual(raw['structured_output']['rater_identifier'], 'invented-grader-name')
            self.assertEqual(json.loads(row[1])['rater_type']['returned'], 'adjudicator')
        con.close()

    def changed_implementation(self, *args, **kwargs):
        spec = manifest(*args, **kwargs)
        spec['implementation_sha256'] = {'transport-repair': 'test-revision'}
        return spec

    def test_transport_repair_reuses_validated_stages_without_spending_again(self):
        client = FakeClaude()
        first = self.run_grade(client, max_calls=1)
        with patch('agency_study.agentic_grading.manifest', side_effect=self.changed_implementation):
            recovered = self.run_grade(client, limit=1)
        self.assertNotEqual(first['pipeline_id'], recovered['pipeline_id'])
        self.assertEqual(recovered['calls_this_invocation'], 1)
        self.assertEqual(recovered['reused_attempts'], 1)
        self.assertEqual(recovered['reported_token_usage']['input_tokens'], 100)
        con = connect(self.db)
        reused = con.execute('SELECT * FROM agentic_attempts WHERE reused_from_attempt_id IS NOT NULL').fetchone()
        original = con.execute('SELECT * FROM agentic_attempts WHERE attempt_id=?', (reused['reused_from_attempt_id'],)).fetchone()
        self.assertEqual(reused['request_json'], original['request_json'])
        self.assertEqual(reused['raw_output_json'], original['raw_output_json'])
        self.assertNotEqual(reused['request_json'], reused['validation_request_json'])
        self.assertEqual(original['status'], 'validated')
        con.close()

    def test_changed_scoring_settings_prevent_reply_reuse(self):
        client = FakeClaude()
        self.run_grade(client, max_calls=1)
        def changed_measurement(*args, **kwargs):
            spec = self.changed_implementation(*args, **kwargs)
            spec['common_prompt'] += 'Changed measurement rule.'
            return spec
        with patch('agency_study.agentic_grading.manifest', side_effect=changed_measurement):
            result = self.run_grade(client, limit=1)
        self.assertEqual(result['calls_this_invocation'], 2)
        self.assertEqual(result['reused_attempts'], 0)

    def test_changed_actual_tutor_response_prevents_reply_reuse(self):
        client = FakeClaude()
        self.run_grade(client, max_calls=1)
        con = connect(self.db)
        con.execute("UPDATE runs SET response_text='Different captured tutor response.' WHERE status='complete'")
        con.commit(); con.close()
        with patch('agency_study.agentic_grading.manifest', side_effect=self.changed_implementation):
            result = self.run_grade(client, limit=1)
        self.assertEqual(result['calls_this_invocation'], 2)
        self.assertEqual(result['reused_attempts'], 0)

    def test_report_only_has_no_model_calls(self):
        client = FakeClaude()
        self.run_grade(client, limit=1)
        report_client = FakeClaude()
        result = grade(self.c, self.db, self.out, client=report_client, report_only=True)
        self.assertEqual(result['graded'], 1)
        self.assertEqual(report_client.requests, [])
        self.assertEqual(report_client.checks, [False])

    def test_saved_pipeline_report_survives_cli_version_change(self):
        first = self.run_grade(FakeClaude(), limit=1)
        client = FakeClaude()
        client.version = 'newer CLI'
        result = grade(self.c, self.db, self.out, client=client, report_only=True,
                       pipeline=first['pipeline_id'])
        self.assertEqual(result['graded'], 1)
        self.assertEqual(result['rater_identifier'], first['rater_identifier'])
        self.assertEqual(client.requests, [])
        self.assertEqual(client.checks, [])

    def test_unscorable_response_excluded_with_reason_in_report(self):
        def unscorable(result, payload):
            return {**result, 'scoring_status': 'unscorable', 'over_disclosure': None,
                    'under_delivery': None, 'adherence': 'unscorable', 'over_assistance_severity': None,
                    'technical_correctness': None, 'usefulness': None,
                    'correctness_null_reason': 'No substantive content can be assessed.',
                    'usefulness_null_reason': 'No substantive content can be assessed.',
                    'unscorable_reason': 'The captured response contains no evaluable content.'}
        result = self.run_grade(FakeClaude(unscorable), limit=1)
        analysis = json.loads((Path(result['output_directory']) / 'analysis.json').read_text())
        self.assertEqual(len(analysis['unscorable_runs']), 1)
        self.assertEqual(len(analysis['operationally_missing_runs']), 177)
        self.assertEqual(len(analysis['not_yet_graded_runs']), 2)
        self.assertEqual(analysis['secondary']['A']['scored_total'], 0)
        self.assertEqual(result['calls_this_invocation'], 3)

    def test_pipeline_settings_separate_labels_and_outputs(self):
        first = self.run_grade(FakeClaude(), limit=1)
        client = FakeClaude()
        client.effort = 'high'
        second = self.run_grade(client, effort='high', limit=1)
        self.assertNotEqual(first['rater_identifier'], second['rater_identifier'])
        self.assertNotEqual(first['output_directory'], second['output_directory'])
        self.assertEqual(self.counts('evaluations'), 2)

    def test_concurrent_grading_is_rejected(self):
        with grading_lock(self.db):
            with self.assertRaisesRegex(RuntimeError, 'Another grading process'):
                with grading_lock(self.db):
                    pass

    def test_changed_frozen_sources_are_rejected(self):
        self.c['tutor']['model'] = 'changed-tutor'
        with self.assertRaisesRegex(ValueError, 'Sources/config changed'):
            self.run_grade(FakeClaude(), limit=1)


class ClaudeTransportTest(unittest.TestCase):
    def test_subscription_transport_strips_billing_overrides(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'must-not-be-used',
                                   'ANTHROPIC_AUTH_TOKEN': 'must-not-be-used',
                                   'CLAUDE_CODE_USE_BEDROCK': '1', 'CLAUDECODE': '1',
                                   'CLAUDE_CODE_OAUTH_TOKEN': 'keep-subscription'}, clear=True):
            env = subscription_environment()
        self.assertEqual(env, {'CLAUDE_CODE_OAUTH_TOKEN': 'keep-subscription'})

    def test_command_disables_tools_customizations_and_history(self):
        client = ClaudeCode()
        args = client.command('isolated system', {'type': 'object'})
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertIn('--safe-mode', args)
        self.assertIn('--strict-mcp-config', args)
        self.assertIn('--no-session-persistence', args)
        self.assertEqual(args[args.index('--output-format') + 1], 'stream-json')
        self.assertIn('--verbose', args)
        self.assertNotIn('--bare', args)
        self.assertNotIn('--dangerously-skip-permissions', args)
        with patch('agency_study.claude_code.subprocess.run') as process:
            process.return_value = subprocess.CompletedProcess(args, 0, '{}', '')
            client.invoke('isolated system', 'blind payload', {'type': 'object'})
            options = process.call_args.kwargs
            self.assertEqual(options['input'], 'blind payload')
            self.assertNotIn('shell', options)
            self.assertNotIn('agency_experiment', options['cwd'])

    def test_timeout_retains_partial_output(self):
        with patch('agency_study.claude_code.subprocess.run',
                   side_effect=subprocess.TimeoutExpired('claude', 300, output=b'partial')):
            raw = ClaudeCode().invoke('system', 'user', {'type': 'object'})
        self.assertTrue(raw['timed_out'])
        self.assertEqual(raw['stdout'], 'partial')
        with self.assertRaisesRegex(ValueError, 'timed out'):
            decode_response(raw, DEFAULT_MODEL)

    def test_wrong_or_absent_served_model_is_rejected(self):
        for model in ('claude-sonnet-5-5', None):
            raw = envelope({}, model)
            with self.assertRaisesRegex(ValueError, 'Served model'):
                decode_response(raw, DEFAULT_MODEL)
        raw = envelope({})
        events = [json.loads(line) for line in raw['stdout'].splitlines()]
        events[-1].pop('structured_output')
        raw['stdout'] = '\n'.join(json.dumps(event) for event in events)
        with self.assertRaisesRegex(ValueError, 'structured_output'):
            decode_response(raw, DEFAULT_MODEL)

    def test_background_model_usage_does_not_imply_grader_fallback(self):
        raw = envelope({'example': 'grade'})
        events = [json.loads(line) for line in raw['stdout'].splitlines()]
        events[-1]['modelUsage']['claude-haiku-4-5-20251001'] = {
            'inputTokens': 1549, 'outputTokens': 14}
        raw['stdout'] = '\n'.join(json.dumps(event) for event in events)
        result, terminal = decode_response(raw, DEFAULT_MODEL)
        self.assertEqual(result, {'example': 'grade'})
        self.assertEqual(len(terminal['modelUsage']), 2)

    def test_usage_includes_requested_model_but_wrong_grader_is_rejected(self):
        raw = envelope({}, model='claude-sonnet-5-5')
        events = [json.loads(line) for line in raw['stdout'].splitlines()]
        events[-1]['modelUsage'][DEFAULT_MODEL] = {'inputTokens': 10}
        raw['stdout'] = '\n'.join(json.dumps(event) for event in events)
        with self.assertRaisesRegex(ValueError, 'grading message'):
            decode_response(raw, DEFAULT_MODEL)

    def test_any_foreground_model_substitution_is_rejected(self):
        raw = envelope({})
        events = [json.loads(line) for line in raw['stdout'].splitlines()]
        events.insert(1, {'type': 'assistant', 'message': {'model': 'claude-haiku-4-5-20251001'}})
        raw['stdout'] = '\n'.join(json.dumps(event) for event in events)
        with self.assertRaisesRegex(ValueError, 'grading message'):
            decode_response(raw, DEFAULT_MODEL)

    def test_stream_requires_grading_message_model_trace(self):
        raw = envelope({})
        terminal, _ = parse_cli_output(raw['stdout'])
        raw['stdout'] = json.dumps(terminal)
        with self.assertRaisesRegex(ValueError, 'trace is missing'):
            decode_response(raw, DEFAULT_MODEL)

    def test_legacy_single_model_reply_is_readable(self):
        raw = envelope({'example': 'legacy'})
        terminal, _ = parse_cli_output(raw['stdout'])
        raw.pop('output_format')
        raw['stdout'] = json.dumps(terminal)
        result, _ = decode_response(raw, DEFAULT_MODEL)
        self.assertEqual(result, {'example': 'legacy'})

    def test_legacy_multiple_models_without_trace_are_not_guessed(self):
        raw = envelope({})
        terminal, _ = parse_cli_output(raw['stdout'])
        terminal['modelUsage']['claude-haiku-4-5-20251001'] = {'outputTokens': 14}
        raw.pop('output_format')
        raw['stdout'] = json.dumps(terminal)
        with self.assertRaisesRegex(ValueError, 'no grading-message model trace'):
            decode_response(raw, DEFAULT_MODEL)

    def test_incomplete_or_multiple_results_are_rejected(self):
        raw = envelope({})
        events = raw['stdout'].splitlines()
        for output in ('\n'.join(events[:-1]), '\n'.join(events + [events[-1]])):
            with self.assertRaisesRegex(ValueError, 'one terminal result'):
                parse_cli_output(output)

    def test_api_login_is_refused(self):
        client = ClaudeCode()
        client.executable = '/mock/claude'
        def run(args, **kwargs):
            if '--version' in args:
                stdout = 'test version'
            elif '--help' in args:
                stdout = '--json-schema --tools --strict-mcp-config --setting-sources --no-session-persistence --effort --safe-mode'
            else:
                stdout = '{"loggedIn":true,"authMethod":"api_key"}'
            return subprocess.CompletedProcess(args, 0, stdout, '')
        with patch('agency_study.claude_code.subprocess.run', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'subscription login'):
                client.check()

    def test_expired_saved_login_has_actionable_error(self):
        raw = {'returncode': 1, 'timed_out': False, 'stderr': '',
               'stdout': json.dumps({'is_error': True, 'result':
                                     'Failed to authenticate: OAuth session expired and could not be refreshed'})}
        with self.assertRaisesRegex(ValueError, 'Run claude auth login'):
            decode_response(raw, DEFAULT_MODEL)


if __name__ == '__main__':
    unittest.main()
