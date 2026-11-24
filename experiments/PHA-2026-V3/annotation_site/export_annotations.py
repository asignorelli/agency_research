"""Coordinator-only: download every saved annotation from the website's database.

Run from experiments/PHA-2026-V3/ (standard library only):

    python3 annotation_site/export_annotations.py

You will be asked for the coordinator code. It is never stored. The script writes
a new folder (it refuses to overwrite one) containing:

  events.jsonl                     every save, in order, exactly as stored (the audit trail)
  <rater>/ratings_latest.json      each person's latest answer per response (180-record array)
  <rater>/ratings_first.json       each person's first-pass answer per response
  <rater>/practice_latest.json     practice answers (not study data)
  summary.json                     counts, hashes and export time

A complete ratings file can then go through the existing checker and import:

    .venv/bin/python manual_grading/packet.py check --rater human-alyssa \
        --file <export>/human-alyssa/ratings_latest.json --out workspace/human-alyssa-submission.jsonl
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = Path(__file__).resolve().parent
STUDY = SITE.parent


def read_config(path):
    text = Path(path).read_text(encoding='utf-8')
    match = re.search(r'window\.PHA_CONFIG\s*=\s*(\{.*?\})\s*;', text, flags=re.S)
    if not match:
        raise SystemExit(f'Could not read PHA_CONFIG from {path}')
    config = json.loads(match.group(1))
    if not config.get('supabaseUrl') or not config.get('supabaseKey'):
        raise SystemExit('config.js has no supabaseUrl/supabaseKey yet')
    return config


def call(config, name, params):
    key = config['supabaseKey']
    headers = {'Content-Type': 'application/json', 'apikey': key, 'User-Agent': 'pha-annotation-export'}
    if key.startswith('eyJ'):
        headers['Authorization'] = 'Bearer ' + key
    request = urllib.request.Request(config['supabaseUrl'].rstrip('/') + '/rest/v1/rpc/' + name,
                                     data=json.dumps(params).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', 'replace')
        try:
            body = json.loads(body).get('message', body)
        except ValueError:
            pass
        raise SystemExit(f'Database refused the export ({error.code}): {body}') from None


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', default=SITE / 'config.js', type=Path)
    parser.add_argument('--out', type=Path, help='new folder to create (default: workspace/annotation_export/<UTC time>)')
    args = parser.parse_args()

    config = read_config(args.config)
    code = os.environ.get('PHA_COORDINATOR_CODE') or getpass.getpass('Coordinator code: ')
    events = call(config, 'pha_export', {'p_coordinator_code': code})

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = args.out or STUDY / 'workspace/annotation_export' / stamp
    out.mkdir(parents=True, exist_ok=False)

    encoded = ''.join(json.dumps(e, ensure_ascii=False, sort_keys=True) + '\n' for e in events)
    with (out / 'events.jsonl').open('x', encoding='utf-8') as handle:
        handle.write(encoded)

    orders = json.loads((SITE / 'data/orders.json').read_text(encoding='utf-8'))
    manifest = json.loads((SITE / 'data/manifest.json').read_text(encoding='utf-8'))
    raters = sorted({e['rater_identifier'] for e in events} | set(orders))
    summary = {'exported_utc': datetime.now(timezone.utc).isoformat(), 'events': len(events),
               'events_sha256': hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
               'site_manifest': manifest, 'raters': {}}
    print(f'{len(events)} saved events')
    print(f'{"rater":<16} {"done":>8} {"revised":>8} {"practice":>9}')
    for rater in raters:
        mine = [e for e in events if e['rater_identifier'] == rater]
        main = {}
        for e in mine:
            if e['kind'] == 'main':
                main.setdefault(e['item_id'], []).append(e)
        practice = {}
        for e in mine:
            if e['kind'] == 'practice':
                practice[e['item_id']] = e  # events are sorted by revision, so the last one wins
        order = orders.get(rater) or sorted(main)
        first = [sorted(main[i], key=lambda e: e['revision'])[0]['record'] for i in order if i in main]
        latest = [sorted(main[i], key=lambda e: e['revision'])[-1]['record'] for i in order if i in main]
        revised = sum(1 for versions in main.values() if len(versions) > 1)
        if mine:
            dump(out / rater / 'ratings_first.json', first)
            dump(out / rater / 'ratings_latest.json', latest)
            dump(out / rater / 'practice_latest.json', [practice[k]['record'] for k in sorted(practice)])
        summary['raters'][rater] = {'responses_saved': len(main), 'responses_expected': len(order),
                                    'responses_revised': revised, 'practice_saved': len(practice)}
        print(f'{rater:<16} {len(main):>4}/{len(order):<3} {revised:>8} {len(practice):>6}/18')
    dump(out / 'summary.json', summary)
    print(f'\nWrote {out}')
    complete = [r for r, s in summary['raters'].items() if s['responses_saved'] == s['responses_expected'] > 0]
    if complete:
        print('Complete sets can be validated with manual_grading/packet.py check, e.g.:')
        r = complete[0]
        print(f'  .venv/bin/python manual_grading/packet.py check --rater {r} '
              f'--file {out / r / "ratings_latest.json"} --out workspace/{r}-submission.jsonl')


if __name__ == '__main__':
    sys.exit(main())
