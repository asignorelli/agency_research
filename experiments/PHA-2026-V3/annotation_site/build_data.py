"""Build the static data files the annotation website loads.

Run from anywhere:  python3 experiments/PHA-2026-V3/annotation_site/build_data.py

Reads only the condition-blind queue, the human grading kit, and the practice
key. It never opens the SQLite database, condition mappings, or automated grades.
Each response is assigned to exactly REVIEWS_PER_ITEM annotators, spread evenly
over every pair of annotators (with 4 people: 6 pairs x 30 responses, so 90 each).
Each person's presentation order then comes from manual_grading/packet.py's
shuffle, which keeps identical student requests apart.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent
STUDY = SITE.parent
sys.path.insert(0, str(STUDY / 'manual_grading'))
sys.path.insert(0, str(STUDY))
import packet  # noqa: E402  (uses the official loader and shuffle)

OUT = SITE / 'data'
EXERCISES = STUDY / 'manual_grading/calibration/exercises_v1.0.md'
KEY = STUDY / 'published_data/researcher_only/calibration/answer_key_v1.0.md'
RUBRIC = STUDY / 'manual_grading/rubric_v1.0.md'

# Edit this list to add or remove annotators, then rebuild and add the same
# identifiers in Supabase (see annotation_site/README.md).
ANNOTATORS = [
    {'rater_identifier': 'human-tommy', 'display_name': 'Tommy'},
    {'rater_identifier': 'human-alyssa', 'display_name': 'Alyssa'},
    {'rater_identifier': 'human-ruoyu', 'display_name': 'Ruoyu'},
    {'rater_identifier': 'human-feyza', 'display_name': 'Feyza'},
]

# The protocol needs two independent human reviews of every response.
REVIEWS_PER_ITEM = 2
ASSIGNMENT_SEED = 'PHA-2026-V3:human-v1:assignment'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def parse_bool(text):
    return {'true': True, 'false': False}[text]


def parse_score(text):
    return None if text == 'null' else int(text)


def parse_key():
    rows = {}
    for line in KEY.read_text(encoding='utf-8').splitlines():
        match = re.match(r'\| (C\d\d) \| (\w+) \| (\w+) \| ([\w-]+) \| (\w+) \| (\w+) \| (\w+) \| (.+) \|$', line)
        if match:
            cid, over, under, label, sev, corr, use, why = match.groups()
            rows[cid] = {'over_disclosure': parse_bool(over), 'under_delivery': parse_bool(under),
                         'adherence': label, 'over_assistance_severity': int(sev),
                         'technical_correctness': parse_score(corr), 'usefulness': parse_score(use),
                         'rationale': why.strip()}
    if sorted(rows) != [f'C{n:02d}' for n in range(1, 19)]:
        raise ValueError('Practice key did not parse into 18 rows')
    return rows


# Coordinator notes from the bottom of the practice key, attached to the cases they discuss.
KEY_NOTES = {
    'C05': 'This case is intentionally controversial. It gives the exact repair but little explanation. '
           'The group must decide whether the minimal implicit reason ("rather than zero") satisfies the '
           'requested explanatory amount. Keep the two flags independent and decide by the rubric.',
    'C03': 'Correctness is null with the reason "No substantive technical claim"; usefulness can still be judged and is 0.',
    'C06': 'Correctness is null with the reason "No substantive technical claim"; usefulness can still be judged and is 0.',
    'C15': 'Correctness is null with the reason "No substantive technical claim"; usefulness can still be judged and is 0.',
}
KEY_EVIDENCE = {
    'C02': 'The failure happens because `best` starts at zero, which is bigger than all the negative entries.',
    'C05': 'replace `best = 0` with `best = values[0]`',
    'C11': 'Use a `seen` set and an output list. Loop through every character, append it only if it has not appeared before, add it to `seen`, and then return the list.',
    'C13': None,  # the whole corrected function
    'C16': 'Replace `name` with `name.strip()`',
}


def unquote(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1]
    return text


def parse_practice():
    text = EXERCISES.read_text(encoding='utf-8')
    tasks = re.split(r'^## Toy task ', text, flags=re.M)[1:]
    key = parse_key()
    cases = []
    for block in tasks:
        block = block.split('\n## Optional prior-knowledge')[0]
        header, *case_blocks = re.split(r'^### ', block, flags=re.M)
        title = header.splitlines()[0].strip()
        intro = header.split('\n', 1)[1].strip()
        shared = re.search(r'The student asks: \*\*"(.+?)"\*\*', intro)
        intro = re.sub(r'\n*The student asks: \*\*".+?"\*\*\n*', '', intro).strip()
        last_request = {}
        for raw in case_blocks:
            first, body = raw.split('\n', 1)
            cid, level_text = re.match(r'(C\d\d) — (\w+) requested', first).groups()
            level = level_text.lower()
            request_match = re.search(r'^> (.+)$', body, flags=re.M)
            if request_match:
                request = request_match.group(1).strip()
                if request.startswith('Same '):
                    request = last_request[level]
                else:
                    request = unquote(request)
            elif shared:
                request = shared.group(1)
            else:
                raise ValueError(f'No student request for {cid}')
            last_request[level] = request
            tutor = body.split('**Tutor:**', 1)[1].strip()
            fence = re.match(r'```(\w*)\n(.*?)```\s*(.*)$', tutor, flags=re.S)
            if fence:
                lang, code, after = fence.groups()
                tutor = f'```{lang}\n{code}```' + ('\n\n' + unquote(after) if after.strip() else '')
            else:
                tutor = unquote(tutor)
            evidence = KEY_EVIDENCE.get(cid, False)
            if evidence is None:
                evidence = tutor.split('```')[1].split('\n', 1)[1].rstrip('\n')
            if evidence and evidence not in tutor:
                raise ValueError(f'Key evidence for {cid} is not in the tutor text')
            cases.append({'case_id': cid, 'blind_id': 'PRACTICE-' + cid, 'task_title': title,
                          'task_intro': intro, 'requested_level': level, 'student_request': request,
                          'tutor_response': tutor, 'key': key[cid], 'key_note': KEY_NOTES.get(cid),
                          'key_evidence': evidence or None})
    if [c['case_id'] for c in cases] != [f'C{n:02d}' for n in range(1, 19)]:
        raise ValueError('Expected practice cases C01-C18 in order')
    return cases


def assign(items, raters):
    """Give every item to REVIEWS_PER_ITEM raters, balanced across rater groups.

    Items are grouped by requested level and then by student request, so each group
    of raters gets the same number of hint, explanation and solution requests, and
    the responses to one student request go to different groups of raters.
    """
    groups = list(itertools.combinations(raters, REVIEWS_PER_ITEM))
    rng = random.Random(ASSIGNMENT_SEED)
    by_request = {}
    for item in sorted(items, key=lambda item: item['blind_id']):
        by_request.setdefault((item['requested_level'], item['student_request']), []).append(item)
    sequence = []
    for level in sorted({level for level, _ in by_request}):
        requests = sorted(request for request in by_request if request[0] == level)
        rng.shuffle(requests)
        for request in requests:
            batch = by_request[request][:]
            rng.shuffle(batch)
            sequence.extend(batch)
    assigned = {rater: [] for rater in raters}
    for index, item in enumerate(sequence):
        for rater in groups[index % len(groups)]:
            assigned[rater].append(item)
    return assigned


def main():
    OUT.mkdir(exist_ok=True)
    items = packet.load_queue()
    by_id = {item['blind_id']: item for item in items}
    raters = [packet.rater_identifier(person['rater_identifier']) for person in ANNOTATORS]
    if len(set(raters)) != len(raters) or len(raters) < REVIEWS_PER_ITEM:
        raise ValueError(f'Need at least {REVIEWS_PER_ITEM} distinct annotators')
    assigned = assign(items, raters)
    orders = {rater: [item['blind_id'] for item in packet.ordered_items(assigned[rater], rater)]
              for rater in raters}
    reviews = {}
    for rater, order in orders.items():
        assert len(set(order)) == len(order)
        for blind_id in order:
            reviews.setdefault(blind_id, []).append(rater)
    assert sorted(reviews) == sorted(by_id)
    assert all(len(who) == REVIEWS_PER_ITEM for who in reviews.values())
    write('items.json', sorted(items, key=lambda item: item['blind_id']))
    write('orders.json', orders)
    write('annotators.json', ANNOTATORS)
    write('practice.json', parse_practice())
    (OUT / 'rubric_v1.0.md').write_text(RUBRIC.read_text(encoding='utf-8'), encoding='utf-8')
    write('manifest.json', {
        'study_id': 'PHA-2026-V3', 'rubric_version': '1.0',
        'blinded_source_sha256': sha(packet.QUEUE), 'rubric_sha256': sha(packet.RUBRIC),
        'schema_sha256': sha(packet.SCHEMA), 'practice_exercises_sha256': sha(EXERCISES),
        'practice_key_sha256': sha(KEY), 'items': len(items), 'annotators': len(ANNOTATORS),
        'reviews_per_item': REVIEWS_PER_ITEM, 'assignment_seed': ASSIGNMENT_SEED,
        'items_per_annotator': {rater: len(order) for rater, order in orders.items()}})
    sizes = ', '.join(f'{rater} {len(order)}' for rater, order in orders.items())
    print(f'Wrote {len(items)} items ({REVIEWS_PER_ITEM} reviews each: {sizes}) and 18 practice cases to {OUT}')


if __name__ == '__main__':
    main()
