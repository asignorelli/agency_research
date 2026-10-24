"""Prepare condition-blind human packets and validate human submissions offline.

Reads only the blinded queue, frozen rubric/schema, and human-provided ratings.
Does not open a database, access automated labels, or call any model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_study.core import get_config
from agency_study.judging import validate_grade

QUEUE = ROOT / 'published_data/blinded/responses.jsonl'
RUBRIC = ROOT / 'evaluation/evaluation_rubric_v1.0_original20.md'
SCHEMA = ROOT / 'drafts/evaluation_result.v1.0.schema.json'
LABELS = {(False, False): 'matched', (True, False): 'over-assisted',
          (False, True): 'under-assisted', (True, True): 'mixed'}
ITEM_FIELDS = {'blind_id', 'requested_level', 'student_request', 'tutor_response',
               'reference', 'operational_status', 'generation_stop_reason'}
REFERENCE_FIELDS = {'task_requirements', 'reference_diagnosis', 'reference_repair',
                    'disclosure_boundary_note', 'targeted_hint_anchor',
                    'conceptual_explanation_anchor'}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def rater_identifier(value):
    if not value or not value.strip() or value != value.strip() or value.startswith('judge:'):
        raise ValueError('Use a nonempty, distinct human rater identifier without surrounding spaces')
    return value


def load_queue():
    items = [json.loads(line) for line in QUEUE.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(items) != 180 or len({item['blind_id'] for item in items}) != 180:
        raise ValueError('Expected exactly 180 unique captured review items')
    for item in items:
        if set(item) != ITEM_FIELDS or set(item['reference']) != REFERENCE_FIELDS:
            raise ValueError('Unexpected review fields; stop and check the blinded source')
    return items


def ordered_items(items, rater):
    """Stable per-person shuffle, keeping identical student requests nonadjacent."""
    rng = random.Random('PHA-2026-V3:human-v1:' + rater)
    groups = {}
    for item in items:
        groups.setdefault(item['student_request'], []).append(item)
    for group in groups.values():
        rng.shuffle(group)
    result = []
    while groups:
        candidates = [request for request in groups
                      if not result or request != result[-1]['student_request']]
        if not candidates:
            raise ValueError('Cannot keep identical student requests apart in this review set')
        largest = max(len(groups[request]) for request in candidates)
        request = rng.choice([request for request in candidates if len(groups[request]) == largest])
        result.append(groups[request].pop())
        if not groups[request]:
            del groups[request]
    return result


def blank_grade(item, rater):
    return {
        'blind_id': item['blind_id'], 'rubric_version': '1.0',
        'rater_type': 'human', 'rater_identifier': rater,
        'requested_level': item['requested_level'], 'scoring_status': None,
        'over_disclosure': None, 'under_delivery': None, 'adherence': None,
        'over_assistance_severity': None, 'technical_correctness': None,
        'usefulness': None, 'correctness_null_reason': None,
        'usefulness_null_reason': None, 'boundary_ambiguity': None,
        'disclosure_evidence': [], 'confidence': None, 'rationale': '',
        'unscorable_reason': None,
    }


def literal(text):
    """A Markdown literal block whose delimiters cannot be closed by source text."""
    import re
    runs = re.findall(r'`+', text)
    fence = '`' * max(3, max((len(run) for run in runs), default=0) + 1)
    return fence + 'text\n' + text + ('\n' if not text.endswith('\n') else '') + fence + '\n'


def render_packet(items):
    parts = ['# Condition-blind human review packet\n\n',
             'Use `manual_grading/README.md`, the approved v1.0 rubric, and the blank worksheet.\n'
             'This packet contains task ground truth and tutor answers, but no automated grades\n'
             'or condition mapping. Reference facts are not automatically student knowledge.\n\n']
    for number, item in enumerate(items, 1):
        parts.append(f"## {number}. {item['blind_id']} — {item['requested_level']}\n\n")
        parts.append('### Exact student request\n\n' + literal(item['student_request']) + '\n')
        parts.append('### Exact tutor response\n\n' + literal(item['tutor_response']) + '\n')
        parts.append('### Researcher reference — grading ground truth\n\n')
        for field in ('task_requirements', 'reference_diagnosis', 'reference_repair',
                      'disclosure_boundary_note', 'targeted_hint_anchor',
                      'conceptual_explanation_anchor'):
            value = item['reference'][field]
            content = value if isinstance(value, str) else json_text(value).rstrip('\n')
            parts.append('**' + field.replace('_', ' ').capitalize() + '**\n\n' + literal(content) + '\n')
        parts.append('**Capture status:** ' + str(item['operational_status']) +
                     '; **generation stop reason:** ' + str(item['generation_stop_reason']) + '\n\n')
        parts.append('Record your own decisions on the worksheet or matching `ratings.json` record.\n\n---\n\n')
    return ''.join(parts)


def prepare(rater, out):
    rater_identifier(rater)
    items = ordered_items(load_queue(), rater)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()  # Never replace an existing packet or somebody's work.
    (out / 'responses.md').write_text(render_packet(items), encoding='utf-8')
    (out / 'ratings.json').write_text(json_text([blank_grade(item, rater) for item in items]), encoding='utf-8')
    manifest = {'study_id': 'PHA-2026-V3', 'rater_identifier': rater,
                'rubric_version': '1.0', 'created_utc': timestamp(),
                'rubric_sha256': digest(RUBRIC), 'schema_sha256': digest(SCHEMA),
                'blinded_source_sha256': digest(QUEUE),
                'presentation_order': [item['blind_id'] for item in items]}
    (out / 'packet_manifest.json').write_text(json_text(manifest), encoding='utf-8')
    return len(items)


def compile_submission(records, items, rater):
    """Validate completed records, deriving only the mechanical adherence label."""
    rater_identifier(rater)
    expected = {item['blind_id']: item for item in items}
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError('Ratings must be a JSON array of grade objects or one grade object per JSONL line')
    ids = [record.get('blind_id') for record in records]
    if any(not isinstance(bid, str) for bid in ids) or len(set(ids)) != len(ids):
        raise ValueError('Missing or duplicate blind ID in human ratings')
    if set(ids) != set(expected):
        raise ValueError('Submission must contain exactly one completed review for every captured response')
    result = []
    config = get_config(ROOT / 'config.json')
    for original in records:
        record = dict(original)
        if record.get('adherence') is None:
            if record.get('scoring_status') == 'unscorable':
                record['adherence'] = 'unscorable'
            elif (record.get('scoring_status') == 'scorable' and
                  type(record.get('over_disclosure')) is bool and
                  type(record.get('under_delivery')) is bool):
                record['adherence'] = LABELS[(record['over_disclosure'], record['under_delivery'])]
        validate_grade(config, record, expected[record['blind_id']], rater, rater_type='human')
        result.append(record)
    return result


def check(rater, file, out):
    file, out = Path(file), Path(out)
    receipt = out.with_name(out.name + '.metadata.json')
    if out.exists() or receipt.exists():
        raise FileExistsError('Submission or receipt already exists; preserve the original and choose a new path')
    text = file.read_text(encoding='utf-8')
    records = json.loads(text) if text.lstrip().startswith('[') else [json.loads(line) for line in text.splitlines() if line.strip()]
    grades = compile_submission(records, load_queue(), rater)
    encoded = ''.join(json.dumps(grade, ensure_ascii=False, separators=(',', ':')) + '\n' for grade in grades)
    metadata = {'study_id': 'PHA-2026-V3', 'rater_identifier': rater, 'rater_type': 'human',
                'rubric_version': '1.0', 'submitted_utc': timestamp(), 'records': len(grades),
                'source_ratings_sha256': digest(file),
                'submission_sha256': hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
                'rubric_sha256': digest(RUBRIC), 'schema_sha256': digest(SCHEMA),
                'blinded_source_sha256': digest(QUEUE)}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf-8') as handle:
        handle.write(encoded)
    with receipt.open('x', encoding='utf-8') as handle:
        handle.write(json_text(metadata))
    return len(grades)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare', help='Create a randomized 180-item human packet with blank ratings')
    prepare_parser.add_argument('--rater', required=True)
    prepare_parser.add_argument('--out', type=Path, required=True)
    check_parser = commands.add_parser('check', help='Validate all completed human ratings and write a new JSONL submission')
    check_parser.add_argument('--rater', required=True)
    check_parser.add_argument('--file', type=Path, required=True)
    check_parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        count = prepare(args.rater, args.out) if args.command == 'prepare' else check(args.rater, args.file, args.out)
    except Exception as error:
        parser.exit(1, f'ERROR: {error}\n')
    print(f'{count} human review records: ' + ('blank packet prepared' if args.command == 'prepare' else 'validated; submission and receipt saved'))


if __name__ == '__main__':
    main()
