"""Human packet integrity and validation; all grade fixtures are synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from manual_grading import packet


def example(bid='PRACTICE-0001', level='hint', request='A fictional student request'):
    return {'blind_id': bid, 'requested_level': level, 'student_request': request,
            'tutor_response': 'Consider the order of the fictional operations.',
            'reference': {key: 'Synthetic reference' for key in packet.REFERENCE_FIELDS},
            'operational_status': 'complete', 'generation_stop_reason': 'stop'}


def finished(item):
    grade = packet.blank_grade(item, 'human-test')
    grade.update(scoring_status='scorable', over_disclosure=False, under_delivery=False,
                 over_assistance_severity=0, technical_correctness=2, usefulness=2,
                 boundary_ambiguity=False, confidence='high',
                 rationale='Synthetic fixture for validator behavior only.')
    return grade


class HumanPacketTests(unittest.TestCase):
    def test_real_queue_complete_blind_and_unscored(self):
        items = packet.ordered_items(packet.load_queue(), 'human-test')
        self.assertEqual(180, len({item['blind_id'] for item in items}))
        self.assertTrue(all(left['student_request'] != right['student_request']
                            for left, right in zip(items, items[1:])))
        for item in items:
            grade = packet.blank_grade(item, 'human-test')
            for field in ('scoring_status', 'over_disclosure', 'under_delivery', 'adherence',
                          'over_assistance_severity', 'technical_correctness', 'usefulness',
                          'confidence', 'boundary_ambiguity'):
                self.assertIsNone(grade[field])
        self.assertNotEqual([item['blind_id'] for item in items],
                            [item['blind_id'] for item in packet.ordered_items(packet.load_queue(), 'human-other')])

    def test_prepare_preserves_existing_work_and_only_blind_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'human'
            self.assertEqual(180, packet.prepare('human-test', out))
            grades = json.loads((out / 'ratings.json').read_text())
            manifest = json.loads((out / 'packet_manifest.json').read_text())
            self.assertEqual([grade['blind_id'] for grade in grades], manifest['presentation_order'])
            before = (out / 'ratings.json').read_bytes()
            with self.assertRaises(FileExistsError):
                packet.prepare('human-other', out)
            self.assertEqual(before, (out / 'ratings.json').read_bytes())

    def test_literal_preserves_embedded_markdown_and_unicode(self):
        text = 'A tutor says:\n```python\nprint("café")\n```\n'
        literal = packet.literal(text)
        self.assertTrue(literal.startswith('````text\n'))
        self.assertIn(text, literal)

    def test_mechanical_label_derived_without_mutating_first_pass(self):
        item = example()
        grade = finished(item)
        original = deepcopy(grade)
        checked = packet.compile_submission([grade], [item], 'human-test')
        self.assertEqual('matched', checked[0]['adherence'])
        self.assertEqual(original, grade)

    def test_incomplete_duplicate_unknown_and_wrong_person_rejected(self):
        item = example()
        grade = finished(item)
        for records in ([], [grade, grade], [{**grade, 'blind_id': 'OTHER-0001'}],
                        [{**grade, 'rater_identifier': 'human-other'}],
                        [packet.blank_grade(item, 'human-test')]):
            with self.subTest(records=len(records)), self.assertRaises(Exception):
                packet.compile_submission(records, [item], 'human-test')

    def test_evidence_must_be_from_tutor_not_student_or_reference(self):
        item = example(request='This is only in the student request.')
        grade = finished(item)
        grade['disclosure_evidence'] = [{'element': 'concept', 'novelty': 'new',
                                         'quote': item['student_request']}]
        with self.assertRaisesRegex(ValueError, 'Fabricated evidence'):
            packet.compile_submission([grade], [item], 'human-test')

    def test_mixed_requires_new_evidence_and_solution_cannot_overdisclose(self):
        item = example()
        grade = finished(item)
        grade.update(over_disclosure=True, under_delivery=True, over_assistance_severity=2)
        with self.assertRaisesRegex(ValueError, 'eligible evidence'):
            packet.compile_submission([grade], [item], 'human-test')
        grade['disclosure_evidence'] = [{'element': 'cause', 'novelty': 'new', 'quote': item['tutor_response']}]
        self.assertEqual('mixed', packet.compile_submission([grade], [item], 'human-test')[0]['adherence'])
        grade['requested_level'] = 'solution'
        with self.assertRaisesRegex(ValueError, 'Solution cannot'):
            packet.compile_submission([grade], [{**item, 'requested_level': 'solution'}], 'human-test')

    def test_unscorable_requires_reasons_and_does_not_become_zero(self):
        item = example()
        grade = packet.blank_grade(item, 'human-test')
        grade.update(scoring_status='unscorable', boundary_ambiguity=False, confidence='low',
                     rationale='Synthetic unusable content fixture.', unscorable_reason='No evaluable content')
        with self.assertRaisesRegex(ValueError, 'Missing null reason'):
            packet.compile_submission([grade], [item], 'human-test')
        grade.update(correctness_null_reason='No evaluable claim', usefulness_null_reason='No evaluable content')
        checked = packet.compile_submission([grade], [item], 'human-test')[0]
        self.assertEqual('unscorable', checked['adherence'])
        self.assertIsNone(checked['technical_correctness'])

    def test_submission_receipt_and_refusal_to_overwrite(self):
        item = example()
        with tempfile.TemporaryDirectory() as temp, patch.object(packet, 'load_queue', return_value=[item]):
            source, out = Path(temp) / 'ratings.json', Path(temp) / 'submission.jsonl'
            source.write_text(json.dumps([finished(item)]))
            self.assertEqual(1, packet.check('human-test', source, out))
            receipt = json.loads(out.with_name(out.name + '.metadata.json').read_text())
            self.assertEqual(packet.digest(out), receipt['submission_sha256'])
            self.assertEqual(packet.digest(source), receipt['source_ratings_sha256'])
            self.assertEqual('human', receipt['rater_type'])
            before = out.read_bytes()
            with self.assertRaises(FileExistsError):
                packet.check('human-test', source, out)
            self.assertEqual(before, out.read_bytes())


if __name__ == '__main__':
    unittest.main()
