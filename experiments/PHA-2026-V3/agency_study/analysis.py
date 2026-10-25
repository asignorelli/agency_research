"""Paired comparisons; outputs are explicitly provisional if scored by an LLM."""
from __future__ import annotations
import csv,json,math,random
from collections import defaultdict
from pathlib import Path
from .core import LEVELS,CONDITIONS,verify_db_sources


def mcnemar_exact(n01,n10):
    n=n01+n10
    if not n:return 1.
    return min(1.,2*sum(math.comb(n,k) for k in range(min(n01,n10)+1))/2**n)

def get_grades(c,db,rater):
    con=verify_db_sources(c,db)
    rows=con.execute('''SELECT r.run_id, sr.scenario_id, sr.level, r.condition, r.status, e.result_json
    FROM runs r JOIN student_requests sr ON r.request_id=sr.request_id
    LEFT JOIN blinded b ON b.run_id=r.run_id
    LEFT JOIN evaluations e ON e.blind_id=b.blind_id AND e.rater_identifier=?
    ORDER BY sr.scenario_id,sr.level,r.condition''',(rater,)).fetchall()
    con.close()
    result=[]
    for r in rows:
        d=dict(r)
        if d['result_json']:d['grade']=json.loads(d.pop('result_json'))
        else:d.pop('result_json');d['grade']=None
        result.append(d)
    return result

def bootstrap_delta(paired,condition_a,condition_b,rep=3000,seed=514):
    """Resample scenario clusters; each scenario contributes both help levels."""
    if not paired:return None
    clusters=defaultdict(list)
    for (sid,level),row in paired.items():clusters[sid].append(row)
    rng=random.Random(seed);keys=list(clusters)
    draws=[]
    for _ in range(rep):
        rows=[r for _ in keys for r in clusters[rng.choice(keys)]]
        diff=sum(int(r[condition_b])-int(r[condition_a]) for r in rows)/len(rows)
        draws.append(diff)
    draws.sort();point=sum(int(r[condition_b])-int(r[condition_a]) for r in paired.values())/len(paired)
    return {'risk_difference_b_minus_a':round(point,4), 'cluster_bootstrap_95_percent_interval':[round(draws[int(.025*rep)],4),round(draws[int(.975*rep)],4)],'unit':'base_problem'}

def report(c,db,rater,output=None):
    records=get_grades(c,db,rater)
    summary={'study_id':c['study_id'],'rater_identifier':rater,'caution':'LLM ratings are provisional; human reliability unavailable' if rater.startswith('judge:') else 'Source of ratings should be verified',
             'expected_runs':180,'captured_runs':sum(x['status'] in ('complete','completed_unscorable') for x in records),
             'scored_runs':sum(x['grade'] is not None for x in records),'primary':{},'secondary':{},'paired':{}}
    for condition in CONDITIONS:
        rows=[r for r in records if r['condition']==condition and r['grade'] is not None and r['grade']['scoring_status']=='scorable']
        eligible=[r for r in rows if r['level'] in ('hint','explanation')]
        summary['primary'][condition]={
            'over_count':sum(bool(r['grade']['over_disclosure']) for r in eligible),
            'denominator':len(eligible),'expected_denominator':40,
            'over_rate':round(sum(bool(r['grade']['over_disclosure']) for r in eligible)/len(eligible),4) if eligible else None}
        summary['secondary'][condition]={'scored_total':len(rows),
            'adherence_count':sum(r['grade']['adherence']=='matched' for r in rows),
            'overall_adherence_rate':round(sum(r['grade']['adherence']=='matched' for r in rows)/len(rows),4) if rows else None,
            'correctness_mean':(round(sum(r['grade']['technical_correctness'] for r in rows if r['grade']['technical_correctness'] is not None)/sum(r['grade']['technical_correctness'] is not None for r in rows),3) if any(r['grade']['technical_correctness'] is not None for r in rows) else None),
            'usefulness_mean':(round(sum(r['grade']['usefulness'] for r in rows if r['grade']['usefulness'] is not None)/sum(r['grade']['usefulness'] is not None for r in rows),3) if any(r['grade']['usefulness'] is not None for r in rows) else None)}
    grouped=defaultdict(dict)
    for r in records:
        g=r['grade']
        if g and g['scoring_status']=='scorable' and r['level'] in ('hint','explanation'):
            grouped[(r['scenario_id'],r['level'])][r['condition']]=bool(g['over_disclosure'])
    for a,b in [('A','B'),('B','C'),('A','C')]:
        paired={key:rs for key,rs in grouped.items() if a in rs and b in rs}
        n01=sum(not v[a] and v[b] for v in paired.values())
        n10=sum(v[a] and not v[b] for v in paired.values())
        summary['paired'][f'{a}_vs_{b}']={'n_pairs':len(paired),'n_a_no_b_yes':n01,'n_a_yes_b_no':n10,
            'exploratory_exact_mcnemar_p':round(mcnemar_exact(n01,n10),6) if paired else None,
            'cluster_resampled_effect':bootstrap_delta(paired,a,b)}
    if output:
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary

def estimate_calls(c,tutor_input_rate,tutor_output_rate,assumed_output_fraction=.45):
    """Preflight ESTIMATE only. Uses char/3 as a planning heuristic, not tokenizer counts."""
    from .core import dataset,docs,SUFFIXES,canonical,build_student_payload
    problems=dataset(c)['problems'];prompts,student_prompt=docs(c)
    if not 0<assumed_output_fraction<=1:raise ValueError('assumed_output_fraction must be in (0,1]')
    student_in=sum((len(student_prompt)+len(canonical(build_student_payload(p))))/3 for p in problems)
    student_out=len(problems)*c['student']['max_output_tokens']*assumed_output_fraction
    imported=c.get('student_input_mode')=='standardized_import'
    bodies=None
    if imported:
        from .student_inputs import configured_student_messages
        bodies=configured_student_messages(c)
        student_in=student_out=0
    # Use full task+starting code+observation as an upper-ish proxy; actual frozen body unknown.
    req_texts=[]
    for p in problems:
        v=p['student_visible']
        s=v['task']+'\n'+v['starting_code']+'\n'+canonical(v.get('observed_examples',[]))
        if bodies is not None:s=bodies[p['id']]['body']
        for suf in SUFFIXES.values():req_texts.append(s+'\n'+suf)
    tutor_in=sum((len(prompts[k])+len(r))/3 for r in req_texts for k in prompts)
    tutor_out=180*c['tutor']['max_output_tokens']*assumed_output_fraction
    student_cost=(student_in*c['student']['input_usd_per_million']+student_out*c['student']['output_usd_per_million'])/1e6
    tutor_cost=(tutor_in*tutor_input_rate+tutor_out*tutor_output_rate)/1e6
    return {'estimated_not_billed':True,'student_input_mode':c.get('student_input_mode','generated'),
         'estimated_student_calls':0 if imported else len(problems),'estimated_tutor_calls':180,
         'estimated_student_input_tokens':round(student_in), 'estimated_student_output_tokens':round(student_out),
         'estimated_tutor_input_tokens':round(tutor_in),'estimated_tutor_output_tokens':round(tutor_out),
         'student_cost_usd':round(student_cost,4),'tutor_cost_usd':round(tutor_cost,4),'subtotal_no_evaluator_usd':round(student_cost+tutor_cost,4),
         'note':'Unverified token approximation and output fraction. Adaptive thinking, retries, provider billing and absent evaluator cost can change actual spend.'}
