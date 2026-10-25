"""Use `python -m agency_study --help` in this project directory."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .core import ROOT,connect,get_config,initialize,provenance,verify_db_sources,validate_sources
from .runner import generate_student_bodies,export_students,import_student_edit,import_student_messages,freeze_candidates,run_tutors,repair_planned_after_safe_error,spent
from .judging import export_blind,judge,import_human_grades
from .analysis import report,estimate_calls
from .pilot import run_pilot
from .recovery import progress
from .agentic_grading import grade
from .claude_code import ClaudeCode,DEFAULT_MODEL


def main():
    p=argparse.ArgumentParser(description='Agency tutoring experiment. Remote work requires --live; paid API collection also requires --max-usd.')
    p.add_argument('--config',default=str(ROOT/'config.json'))
    p.add_argument('--db',default=None,help='Override the database configured for this study')
    p.add_argument('--archive',default=None,help='Override the raw archive configured for this study')
    subs=p.add_subparsers(dest='cmd',required=True)
    for name,helptext in [('validate','Check dataset, rubric reference sources and frozen prompt derivation'),('init','Initialize local SQLite study DB'),
                          ('generate-students','Generate 20 student body candidates using Haiku, no freeze'),
                          ('import-students','Import all 20 configured standardized student messages without API calls'),
                          ('export-students','Export generated candidates for factual review'),
                          ('edit-student','Replace one generated body with a reviewed local text file'),
                          ('freeze-students','Freeze reviewed candidates and build 60 requests and 180 runs'),
                          ('run-tutors','Collect queued tutor responses and checkpoint progress'),
                          ('resume-tutors','Resume saved collection, restoring received responses and safe failures'),
                          ('pilot-tutors','Preview or run a separate, held-out A/B/C tutor pilot'),
                          ('recover-safe','Requeue runs known to have failed before receiving a response'),
                          ('blind-export','Export completed responses without tutor-condition identifiers'),
                          ('evaluate','Run chosen paid LLM judge, when ready'),
                          ('grade','Preview or run blinded agentic grading through your Claude Code subscription'),
                          ('grade-status','Read agentic grading progress without calling a model'),
                          ('grade-report','Rebuild agentic grading exports and analysis without calling a model'),
                          ('grade-check','Check Claude Code installation, subscription login, and grading dependencies'),
                          ('import-human-grades','Optional future import of independently completed blinded grading JSONL'),
                          ('report','Statistical summaries from one exact evaluator identity'),
                          ('estimate','Offline, hypothetical student+tutor costs'),('status','Show progress, missingness, spending')]:
        x=subs.add_parser(name,help=helptext)
        if name in ('grade','grade-status','grade-report','grade-check'):
            x.add_argument('--model',default=DEFAULT_MODEL,help='Explicit Claude model ID; default claude-haiku-5-5')
            x.add_argument('--effort',choices=['low','medium','high'],default='medium')
        if name in ('grade','grade-report'):
            x.add_argument('--out-dir',default=None,help='Output parent directory; each pipeline gets its own subdirectory')
        if name=='grade-report':
            x.add_argument('--pipeline',default=None,help='Full saved pipeline ID, including pipelines from older grading implementations or CLI versions')
        if name=='grade':
            x.add_argument('--live',action='store_true',help='Use your Claude Code subscription; without this flag, show an offline plan')
            x.add_argument('--dry-run',action='store_true',help='Show the offline plan (cannot be combined with --live)')
            x.add_argument('--limit',type=int,default=None,help='Complete at most N additional response grades')
            x.add_argument('--max-calls',type=int,default=None,help='Cap Claude Code invocations in this run; saved partial grades resume later')
            x.add_argument('--timeout-seconds',type=float,default=300)
            x.add_argument('--retry-failed',action='store_true',help='Retry previously failed/interrupted grader stages; prior usage may have occurred')
        if name in ('generate-students','run-tutors','resume-tutors','pilot-tutors','evaluate'):
            x.add_argument('--live',action='store_true',help='Required for any paid API calls')
            x.add_argument('--max-usd',type=float,help='Spending cap in USD (estimate, not a provider guarantee)')
            x.add_argument('--limit',type=int,default=None,help='Process at most N new items')
        if name in ('run-tutors','resume-tutors','pilot-tutors'):
            x.add_argument('--timeout-seconds',type=float,default=300,help='HTTP read timeout; runtime transport setting, default 300 seconds')
            x.add_argument('--retry-ambiguous',action='store_true',help='Authorize an audited retry when an earlier provider outcome/charge is unknown')
            x.add_argument('--fail-fast',action='store_true',help='Stop on the first network failure instead of collecting other queued jobs')
        if name=='pilot-tutors':
            x.set_defaults(limit=3)
            x.add_argument('--pilot-db',default=None)
            x.add_argument('--pilot-archive',default=None)
        if name=='export-students':x.add_argument('--out',default=None)
        if name=='import-students':x.add_argument('--file',default=None,help='Optional equivalent copy of the configured Markdown corpus')
        if name=='edit-student':
            x.add_argument('--scenario',type=int,required=True)
            x.add_argument('--body-file',required=True)
        if name=='freeze-students':x.add_argument('--ack-reviewed',action='store_true',help='I personally reviewed all 20 student inputs for factual accuracy')
        if name=='blind-export':x.add_argument('--out',default=None)
        if name=='evaluate':
            x.add_argument('--judge-provider',choices=['anthropic','openai','deepinfra'],required=True)
            x.add_argument('--judge-model',required=True)
            x.add_argument('--input-rate',type=float,required=True,help='Current input rate per million tokens USD')
            x.add_argument('--output-rate',type=float,required=True,help='Current output rate per million tokens USD')
        if name=='estimate':
            x.add_argument('--tutor-input-rate',type=float,required=True)
            x.add_argument('--tutor-output-rate',type=float,required=True)
            x.add_argument('--output-fraction',type=float,default=.45)
        if name=='import-human-grades':
            x.add_argument('--file',required=True)
            x.add_argument('--rater',required=True)
        if name=='report':
            x.add_argument('--rater',required=True,help='Exact evaluator identifier, do not mix graders')
            x.add_argument('--out',default=None)
    args=p.parse_args();c=get_config(args.config)
    def configured_path(key,fallback):
        return Path(c['_root'])/c.get('paths',{}).get(key,fallback)
    db=Path(args.db) if args.db else configured_path('database','workspace/experiment_v2.sqlite')
    arch=Path(args.archive) if args.archive else configured_path('archive','workspace/raw_attempts_v2.jsonl')
    if args.cmd=='export-students' and not args.out:args.out=str(configured_path('student_export','workspace/student_candidates_to_review.json'))
    if args.cmd=='blind-export' and not args.out:args.out=str(configured_path('blind_export','workspace/blinded_review_queue.jsonl'))
    if args.cmd=='report' and not args.out:args.out=str(configured_path('analysis','workspace/analysis_summary.json'))
    try:
        if args.cmd=='validate':
            print(json.dumps({'status':'VALID','source_provenance':validate_sources(c)},indent=2));return
        if args.cmd=='estimate':
            print(json.dumps(estimate_calls(c,args.tutor_input_rate,args.tutor_output_rate,args.output_fraction),indent=2));return
        if args.cmd=='init':
            print(json.dumps({'status':'INITIALIZED','database':str(db),'source_provenance':initialize(c,db)},indent=2));return
        if args.cmd=='pilot-tutors':
            pilot_db=Path(args.pilot_db) if args.pilot_db else configured_path('pilot_database','workspace/tutor_pilot_v2.sqlite')
            pilot_archive=Path(args.pilot_archive) if args.pilot_archive else configured_path('pilot_archive','workspace/tutor_pilot_raw_attempts_v2.jsonl')
            main_paths={db.resolve(),arch.resolve(),(ROOT/'workspace/experiment.sqlite').resolve(),
                        (ROOT/'workspace/raw_attempts.jsonl').resolve(),
                        (ROOT/'workspace/experiment_v2.sqlite').resolve(),
                        (ROOT/'workspace/raw_attempts_v2.jsonl').resolve()}
            if pilot_db.resolve() in main_paths or pilot_archive.resolve() in main_paths:
                raise ValueError('Pilot files must be separate from main-study files')
            print(json.dumps(run_pilot(c,pilot_db,pilot_archive,args.live,args.max_usd,args.limit,timeout_seconds=args.timeout_seconds,continue_on_error=not args.fail_fast,retry_ambiguous=args.retry_ambiguous),indent=2));return
        if args.cmd=='grade-check':
            import jsonschema
            print(json.dumps(ClaudeCode(args.model,args.effort).check(),indent=2));return
        if not db.exists():raise ValueError('Database missing; run init')
        if args.cmd in ('grade','grade-status','grade-report'):
            if args.cmd=='grade' and args.live and args.dry_run:
                raise ValueError('Choose --live or --dry-run')
            output=(Path(args.out_dir) if getattr(args,'out_dir',None) else configured_path('grading','workspace/claude_grading'))
            result=grade(c,db,output,live=getattr(args,'live',False),
                         limit=getattr(args,'limit',None),model=args.model,effort=args.effort,
                         timeout=getattr(args,'timeout_seconds',300),max_calls=getattr(args,'max_calls',None),
                         retry_failed=getattr(args,'retry_failed',False),report_only=args.cmd=='grade-report',
                         pipeline=getattr(args,'pipeline',None))
            print(json.dumps(result,indent=2));return
        if args.cmd=='generate-students':
            if not args.live:raise ValueError('Network disabled. Supply --live --max-usd to generate paid student candidates')
            print('Generated:',generate_student_bodies(c,db,arch,args.live,args.max_usd,args.limit))
        elif args.cmd=='import-students':print('Imported:',import_student_messages(c,db,args.file))
        elif args.cmd=='export-students':print('Exported:',export_students(c,db,args.out),'to',args.out)
        elif args.cmd=='edit-student':print('Candidate saved:',import_student_edit(c,db,args.scenario,args.body_file))
        elif args.cmd=='freeze-students':print('Frozen 60 requests / planned runs:',freeze_candidates(c,db,args.ack_reviewed))
        elif args.cmd in ('run-tutors','resume-tutors'):
            if not args.live:raise ValueError('Network disabled. Supply --live --max-usd to run paid tutors')
            print('Tutor calls completed:',run_tutors(c,db,arch,args.live,args.max_usd,args.limit,timeout_seconds=args.timeout_seconds,continue_on_error=not args.fail_fast,retry_ambiguous=args.retry_ambiguous))
        elif args.cmd=='recover-safe':print('Safely requeued:',recover_ids:=repair_planned_after_safe_error(c,db))
        elif args.cmd=='blind-export':print('Blinded entries:',export_blind(c,db,args.out),'at',args.out)
        elif args.cmd=='evaluate':print('Judge labels completed:',judge(c,db,arch,args.live,args.max_usd,args.limit,args.judge_provider,args.judge_model,args.input_rate,args.output_rate))
        elif args.cmd=='import-human-grades':print('Independent human grades imported:',import_human_grades(c,db,args.file,args.rater))
        elif args.cmd=='report':print(json.dumps(report(c,db,args.rater,args.out),indent=2))
        elif args.cmd=='status':
            conn=verify_db_sources(c,db)
            result={'dataset':c['study_id'],'database':str(db),'student_input_mode':c.get('student_input_mode','generated'),
                'spend_recorded_usd':round(spent(conn),6),
                'student_candidates':[dict(r) for r in conn.execute('SELECT status,COUNT(*) n FROM student_candidates GROUP BY status')],
                'student_bodies_frozen':conn.execute('SELECT COUNT(*) FROM student_bodies').fetchone()[0],
                'requests_frozen':conn.execute('SELECT COUNT(*) FROM student_requests').fetchone()[0],
                'tutor_runs':[dict(r) for r in conn.execute('SELECT status,COUNT(*) n FROM runs GROUP BY status')],
                'blinded':conn.execute('SELECT COUNT(*) FROM blinded').fetchone()[0],
                'evaluator_labels':[dict(r) for r in conn.execute('SELECT rater_identifier,COUNT(*) n FROM evaluations GROUP BY rater_identifier')],
                'collection':progress(conn)}
            print(json.dumps(result,indent=2));conn.close()
    except KeyboardInterrupt:
        print('Stopped by user. Progress is saved; repeat the same command to resume. Failed grading stages require --retry-failed.',file=sys.stderr);sys.exit(130)
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}',file=sys.stderr);sys.exit(2)

if __name__=='__main__':main()
