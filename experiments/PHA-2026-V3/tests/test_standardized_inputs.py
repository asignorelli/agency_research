"""V3 input fidelity, restored tasks, paired requests, and source isolation."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency_study.analysis import estimate_calls
from agency_study.core import (
    SUFFIXES, canonical, connect, dataset, get_config, initialize,
    sha, source_file, validate_sources, verify_db_sources,
)
from agency_study.runner import (
    freeze_candidates, generate_student_bodies, import_student_edit,
    import_student_messages,
)
from agency_study.student_inputs import configured_student_messages, parse_student_messages


class StandardizedInputsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root/'v3.sqlite'
        self.c=get_config()
        initialize(self.c,self.db)

    def test_uploaded_wrapper_preserves_all_twenty_message_bodies(self):
        upload=Path(self.c['_root'])/'reference/Student_Messages_V2_Upload.md'
        self.assertEqual(parse_student_messages(upload.read_text()),configured_student_messages(self.c))
        self.assertEqual(len(configured_student_messages(self.c)),20)

    def test_import_is_free_idempotent_and_explicit_about_origin(self):
        with patch('agency_study.runner.invoke') as provider:
            self.assertEqual(import_student_messages(self.c,self.db),20)
            self.assertEqual(import_student_messages(self.c,self.db),0)
            provider.assert_not_called()
        con=verify_db_sources(self.c,self.db)
        self.addCleanup(con.close)
        expected=configured_student_messages(self.c)
        for row in con.execute('SELECT * FROM student_candidates'):
            self.assertEqual(row['body'],expected[row['scenario_id']]['body'])
            self.assertEqual(row['provider'],'standardized_import')
            self.assertIsNone(row['served_model'])
            self.assertEqual(row['cost_usd'],0)
            self.assertFalse(json.loads(row['raw_response_json'])['human_review_attested'])
        self.assertEqual(con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM student_requests').fetchone()[0],0)

    def test_freeze_requires_review_and_builds_sixty_identical_paired_requests(self):
        import_student_messages(self.c,self.db)
        with self.assertRaisesRegex(ValueError,'ack-reviewed'):
            freeze_candidates(self.c,self.db)
        self.assertEqual(freeze_candidates(self.c,self.db,True),180)
        con=verify_db_sources(self.c,self.db)
        self.addCleanup(con.close)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM student_requests').fetchone()[0],60)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM runs').fetchone()[0],180)
        expected=configured_student_messages(self.c)
        for row in con.execute('SELECT * FROM student_requests'):
            body=expected[row['scenario_id']]['body']
            self.assertEqual(row['request_text'],body+'\n\n'+SUFFIXES[row['level']])
            self.assertEqual(row['body_sha256'],sha(body))
            self.assertEqual(row['request_sha256'],sha(row['request_text']))
        rows=con.execute('''SELECT request_id,COUNT(*) n,COUNT(DISTINCT condition) conditions
            FROM runs GROUP BY request_id''').fetchall()
        self.assertTrue(all(row['n']==3 and row['conditions']==3 for row in rows))
        self.assertTrue(all(row['status']=='planned' for row in con.execute('SELECT status FROM runs')))
        with self.assertRaisesRegex(ValueError,'already frozen'):
            import_student_messages(self.c,self.db)

    def test_generation_and_unversioned_manual_rewording_are_blocked(self):
        with patch('agency_study.runner.invoke') as provider:
            with self.assertRaisesRegex(ValueError,'imports fixed student messages'):
                generate_student_bodies(self.c,self.db,self.root/'events.jsonl',True,1)
            provider.assert_not_called()
        edit=self.root/'changed.txt'
        edit.write_text(configured_student_messages(self.c)[1]['body']+'\nNew wording.')
        with self.assertRaisesRegex(ValueError,'source-controlled'):
            import_student_edit(self.c,self.db,1,edit)

    def test_wrong_import_is_rejected_without_partial_candidates(self):
        wrong=self.root/'wrong.md'
        wrong.write_text(source_file(self.c,'student_messages').read_text().replace(
            "I'm not sure why the result isn't what I expected.",'A new diagnosis.',1))
        with self.assertRaisesRegex(ValueError,'differs'):
            import_student_messages(self.c,self.db,wrong)
        con=connect(self.db)
        self.addCleanup(con.close)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM student_candidates').fetchone()[0],0)

    def test_changed_candidate_is_not_frozen(self):
        import_student_messages(self.c,self.db)
        con=connect(self.db)
        con.execute("UPDATE student_candidates SET body=body || ' Extra content.' WHERE scenario_id=1")
        con.commit();con.close()
        with self.assertRaisesRegex(ValueError,'differs from the standardized corpus'):
            freeze_candidates(self.c,self.db,True)

    def test_researcher_sections_missing_scenarios_and_broken_fences_are_rejected(self):
        text=source_file(self.c,'student_messages').read_text()
        for bad in [text+'\n## Researcher-only\nExact answers.',
                    text.replace('## 20. Coin Change','## 19. Coin Change'),
                    text+'\n```python\nUnclosed']:
            with self.subTest(ending=bad[-60:]),self.assertRaises(ValueError):
                parse_student_messages(bad)
        marked='<!-- BEGIN STUDENT MESSAGES -->\n'+text+'\n<!-- END STUDENT MESSAGES -->\n## Researcher-only\nExact answers.'
        self.assertEqual(parse_student_messages(marked),configured_student_messages(self.c))

    def test_mismatched_cards_and_changed_source_hashes_are_rejected(self):
        content=json.loads(source_file(self.c,'cards').read_text())
        content['cards'][2]['title']='Last Character Index'
        bad=self.root/'bad_cards.json';bad.write_text(json.dumps(content))
        changed={**self.c,'cards':str(bad)}
        with self.assertRaisesRegex(ValueError,'mismatched title'):
            validate_sources(changed)
        duplicate=self.root/'messages.md'
        duplicate.write_text(source_file(self.c,'student_messages').read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Sources/config changed'):
            verify_db_sources({**self.c,'student_messages':str(duplicate)},self.db)

    def test_restored_tasks_and_corrected_metadata(self):
        problems={p['id']:p for p in dataset(self.c)['problems']}
        expected={3:'Longest Palindromic Substring',4:'3Sum',9:'Longest Consecutive Sequence',
                  11:'Search in Rotated Sorted Array',20:'Coin Change'}
        self.assertEqual({sid:problems[sid]['title'] for sid in expected},expected)
        self.assertEqual({p['difficulty'] for p in problems.values()},{'Medium'})
        self.assertEqual(dataset(self.c)['experiment_design']['case_counts'],{'original_continuity':20})
        source=json.loads(source_file(self.c,'original_dataset').read_text())
        self.assertNotIn('timeout',source[8]['struggle_point'].lower())
        self.assertIn('initializes',source[19]['struggle_point'].lower())
        self.assertNotIn('Time Limit Exceeded',source_file(self.c,'student_messages').read_text())
        estimate=estimate_calls(self.c,.10,.32)
        self.assertEqual(estimate['estimated_student_calls'],0)
        self.assertEqual(estimate['student_cost_usd'],0)
        self.assertEqual(estimate['estimated_tutor_calls'],180)

    def test_all_reported_example_results_match_the_supplied_attempts(self):
        class ListNode:
            def __init__(self,val=0,next=None):self.val,self.next=val,next
        def linked(values):
            root=ListNode();cur=root
            for value in values:cur.next=ListNode(value);cur=cur.next
            return root.next
        def encode(value):
            if isinstance(value,ListNode):
                values=[]
                while value:values.append(value.val);value=value.next
                return values
            if isinstance(value,float) and math.isinf(value):return {'special_value':'positive_infinity'}
            return value
        for problem in dataset(self.c)['problems']:
            for example in problem['student_visible']['observed_examples']:
                with self.subTest(scenario=problem['id'],input=example['input']):
                    namespace={'ListNode':ListNode}
                    exec(problem['student_visible']['starting_code'],namespace)
                    solution=namespace['Solution']()
                    method=getattr(solution,next(name for name in vars(namespace['Solution']) if not name.startswith('_')))
                    args=copy.deepcopy(example['input'])
                    if problem['id']==1:args={key:linked(value) for key,value in args.items()}
                    try:
                        value=method(**args)
                        if problem['id'] in (15,17):value=args['matrix']
                        observed={'kind':'value','value':encode(value)}
                    except Exception as error:
                        observed={'kind':'exception','exception_type':type(error).__name__}
                    self.assertEqual(observed,example['observed_result'])


if __name__=='__main__':
    unittest.main()
