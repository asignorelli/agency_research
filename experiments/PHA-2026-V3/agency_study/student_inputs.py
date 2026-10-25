"""Parse standardized student openings without importing researcher notes."""
from __future__ import annotations

import re
from pathlib import Path


def parse_student_messages(text):
    """Accept the 20-section corpus, including a whole-document Markdown fence."""
    text = text.replace('\r\n', '\n').replace('\r', '\n').strip()
    lines = text.splitlines()
    outer = re.fullmatch(r'(`{4,}|~{4,})(?:markdown|md)?\s*', lines[0]) if lines else None
    if outer:
        if len(lines) < 2 or lines[-1].strip() != outer[1]:
            raise ValueError('Unclosed whole-document Markdown fence')
        text = '\n'.join(lines[1:-1]).strip()
    begin, end = '<!-- BEGIN STUDENT MESSAGES -->', '<!-- END STUDENT MESSAGES -->'
    if begin in text or end in text:
        if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) >= text.index(end):
            raise ValueError('Student-message section markers must occur once, in order')
        text = text.split(begin, 1)[1].split(end, 1)[0].strip()

    lines = text.splitlines()
    headings = []
    fence = None
    for index, line in enumerate(lines):
        marker = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if fence is not None:
            continue
        heading = re.fullmatch(r'## (\d{2})\. (.+?)\s*', line)
        if heading:
            headings.append((index, int(heading[1]), heading[2]))
        elif headings and re.match(r'^#{1,6}\s+', line):
            raise ValueError('Unexpected non-scenario section; isolate the student-message corpus')
    if fence is not None:
        raise ValueError('Unclosed code fence in student messages')
    if [sid for _, sid, _ in headings] != list(range(1, 21)):
        raise ValueError('Need exactly 20 numbered student sections in order, 01 through 20')
    result = {}
    for number, (start, sid, title) in enumerate(headings):
        stop = headings[number + 1][0] if number + 1 < len(headings) else len(lines)
        body = '\n'.join(lines[start + 1:stop]).strip()
        body = re.sub(r'\n---\s*$', '', body).strip()
        if not body:
            raise ValueError(f'Empty student message for scenario {sid}')
        result[sid] = {'title': title, 'body': body}
    return result


def configured_student_messages(config):
    source = config.get('student_messages')
    if not source:
        raise ValueError('Configure student_messages for standardized input import')
    return parse_student_messages((Path(config['_root']) / source).read_text(encoding='utf-8'))
