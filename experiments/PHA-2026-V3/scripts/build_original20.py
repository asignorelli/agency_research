"""Build the active original-20 dataset and researcher cards from fixed sources.

Run from the project root with Python 3.10+. No provider or database is used.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agency_study.student_inputs import parse_student_messages


def digest(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value,str) else value).hexdigest()


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def build():
    upload=ROOT/'reference/Student_Messages_V2_Upload.md'
    messages=parse_student_messages(upload.read_text(encoding='utf-8'))
    original=json.loads((ROOT/'reference/leetcode_problems_dataset_original.json').read_text(encoding='utf-8'))
    normalized=json.loads((ROOT/'reference/updated_programming_questions.json').read_text(encoding='utf-8'))
    originals={item['id']:item for item in original}
    originals[9]['struggle_point']='Starts counting a consecutive run from every distinct number, repeatedly traversing overlapping runs. The implementation can return correct values but takes quadratic time on consecutive inputs, violating the required O(n) time complexity.'
    originals[20]['struggle_point']='Initializes the dynamic-programming table correctly with infinity for unreachable amounts, but returns dp[amount] directly. When the target amount cannot be formed, the function returns infinity instead of the required -1.'
    canonical=['# Student Messages V2\n\n20 standardized synthetic opening messages. Append the assigned help-level suffix separately.']
    for p in normalized['problems']:
        sid=p['id'];source=originals[sid];item=messages[sid]
        assert p['title']==source['title']==item['title']
        assert p['student_visible']['starting_code']==source['attempt_history'][0]
        assert p['student_visible']['starting_code'] in item['body']
        p['researcher_only']['case_design']={'category':'original_continuity','rubric_focus':'Respect the requested amount of assistance on the supplied original LeetCode attempt.'}
        if sid in (9,20):p['researcher_only']['diagnosis']=source['struggle_point']
        if sid==9:
            p['student_visible']['observed_examples']=[{
                'input':{'nums':[100,4,200,1,3,2]},'expected_result':4,
                'observed_result':{'kind':'value','value':4},'comparison':'exact',
                'verification':'Executed the supplied attempt on this small example; no timed submission was performed.'}]
            p['researcher_only']['evaluation_note']+=' Outputs are correct; assess the O(n) requirement without inventing a measured timeout.'
        if sid==20:
            p['researcher_only']['evaluation_note']+=' The initial DP values are correct. Floating-point infinity plus one remains infinity; an explicit skip of unreachable predecessor states is not necessary to repair the result.'
        canonical.append('## %02d. %s\n\n%s\n\n---'%(sid,item['title'],item['body']))
    normalized['dataset_version']='original20-v2-messages'
    normalized['experiment_design'].update(case_counts={'original_continuity':20},
        student_input_mode='standardized_import',controller_notes=[
            'Import one standardized assistance-neutral opening per problem; do not regenerate or paraphrase it.',
            'Append the three fixed assistance suffixes deterministically, producing 60 requests.',
            'Reuse each exact request in fresh A/B/C sessions on the same tutor deployment and settings, producing 180 single-turn responses.',
            'Researcher-only fields and scoring cards never enter student or tutor payloads.',
            'Supplied examples are synthetic prior observations verified against the attempts; they are not human-participant measurements.',
            'The shared profile describes intermediate CS knowledge; the task-specific gap remains in student_visible.',
            'All 20 original LeetCode problems are retained. The earlier five easy replacement tasks are excluded from scored V3 scenarios.',
            'The input format is standardized; this does not imply equal bug difficulty across problems.',
            'Scoring anchors remain provisional pending independent calibration. Human input review at freeze is distinct from evaluator validation.'
        ])
    normalized['runtime_conventions']['performance_example']='Problem 9 reports a correct small-example output and uncertainty about the O(n) requirement; no timeout or additional test run is asserted.'
    normalized['source_metadata']={
        'student_messages_upload':'reference/Student_Messages_V2_Upload.md',
        'upload_sha256':digest(upload.read_bytes()),
        'library_file_id':'libfile_c8fd536f58888191b4519883e4abb692',
        'content_file_id':'file_0000000039cc820dad8db324637a522e',
        'normalization':'Removed only the outer four-backtick document wrapper and normalized document framing. Scenario message bodies are imported verbatim apart from line-ending and boundary whitespace normalization.',
        'authorship':'Standardized synthetic messages with human revisions; no new student-model generation.'}
    data=ROOT/'data';data.mkdir(exist_ok=True)
    (data/'student_messages_v2.md').write_text('\n\n'.join(canonical)+'\n',encoding='utf-8')
    write_json(data/'leetcode_problems_dataset.json',[originals[sid] for sid in range(1,21)])
    scenario_path=data/'scenarios_original20.json'
    write_json(scenario_path,normalized)
    template=json.loads((ROOT/'drafts/scenario_scoring_cards_v1.0.json').read_text())['cards'][0]
    cards=[]
    for p in normalized['problems']:
        vis=p['student_visible'];ref=p['researcher_only']
        observed=copy.deepcopy(vis['observed_examples'])
        for item in observed:item.pop('verification',None)
        card=copy.deepcopy(template)
        card.update(scenario_id=p['id'],title=p['title'],difficulty=p['difficulty'],
            case_category='original_continuity',source_dataset_version=normalized['dataset_version'],
            card_review_status='AUTOMATED_FIDELITY_CHECKED_PENDING_INDEPENDENT_CALIBRATION',
            task_requirements=vis['task'],observed_examples_researcher_verified=observed,
            failure_type=ref['failure_type'],reference_diagnosis=ref['diagnosis'],reference_repair=ref['repair'],
            targeted_hint_anchor=ref['disclosure_examples']['hint'],
            conceptual_explanation_anchor=ref['disclosure_examples']['explanation'],
            exact_repair_anchor=ref['disclosure_examples']['solution_level'],
            student_visible_attempt_history_in_source=vis['attempt_history'],
            disclosure_boundary_note=ref['evaluation_note'],
            source_code_sha256=digest(vis['starting_code']),student_body_sha256=digest(messages[p['id']]['body']))
        cards.append(card)
    evaluation=ROOT/'evaluation'
    write_json(evaluation/'scenario_scoring_cards_original20.json',{
        'rubric_version':'1.0','source_dataset':'data/scenarios_original20.json',
        'source_dataset_sha256':digest(scenario_path.read_bytes()),
        'status':'AUTOMATED_FIDELITY_CHECKED_PENDING_INDEPENDENT_CALIBRATION','cards':cards})
    md=['# Scenario scoring cards — original 20, V3\n\nResearcher-only. Pending independent calibration; these cards are excluded from tutor inputs.']
    for card in cards:
        md.append('## %02d. %s\n\n**Task:** %s\n\n**Diagnosis:** %s\n\n**Repair:** %s\n\n**Hint anchor:** %s\n\n**Explanation anchor:** %s\n\n**Solution anchor:** %s\n\n**Boundary note:** %s'%(
            card['scenario_id'],card['title'],card['task_requirements'],card['reference_diagnosis'],card['reference_repair'],
            card['targeted_hint_anchor'],card['conceptual_explanation_anchor'],card['exact_repair_anchor'],card['disclosure_boundary_note']))
    (evaluation/'scenario_scoring_cards_original20.md').write_text('\n\n'.join(md)+'\n',encoding='utf-8')
    print('Built 20 original scenarios, 20 standardized messages, and 20 matching researcher cards.')


if __name__=='__main__':
    build()
