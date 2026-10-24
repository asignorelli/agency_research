"""Network-free regression tests for restarts, ambiguous outcomes and preservation."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agency_study.core import canonical, connect, docs, get_config, initialize, sha, tutor_settings, verify_db_sources
from agency_study.providers import ProviderError, build_request, conservative_reservation, cost_usd, parse_response
from agency_study.recovery import collection_lock, ensure_recovery_schema, prepare_resume, progress, queue_order
from agency_study.runner import append_archive, freeze_candidates, import_student_messages, run_tutors, store_attempt_start


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'main.sqlite';self.archive=self.root/'raw.jsonl'
        self.c=get_config();initialize(self.c,self.db)
        import_student_messages(self.c,self.db);freeze_candidates(self.c,self.db,True)
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(patch('urllib.request.urlopen',side_effect=AssertionError('Live HTTP is forbidden in recovery tests')))

    def response(self,provider,payload,**kwargs):
        raw={'id':'mock-response','model':payload['model'],
             'choices':[{'message':{'content':'A saved mock tutor response.'},'finish_reason':'stop'}],
             'usage':{'prompt_tokens':100,'completion_tokens':20}}
        return parse_response(provider,raw)

    def snapshot(self):
        con=connect(self.db)
        try:
            return {r['run_id']:dict(r) for r in con.execute("SELECT * FROM runs WHERE response_text IS NOT NULL")}
        finally:con.close()

    def first_request(self):
        con=connect(self.db);ensure_recovery_schema(con)
        rid=queue_order(con,self.c['randomization_seed'])[0]
        row=con.execute('''SELECT r.condition,s.request_text FROM runs r
            JOIN student_requests s USING(request_id) WHERE r.run_id=?''',(rid,)).fetchone()
        prompts,_=docs(self.c);settings=tutor_settings(self.c)
        payload=build_request(self.c['tutor']['provider'],self.c['tutor']['model'],prompts[row[0]],
            row[1],settings['max_output_tokens'],temperature=settings['temperature'])
        return con,rid,payload

    def test_timeout_continues_and_restart_does_not_repeat_saved_or_ambiguous(self):
        calls=0
        def flaky(provider,payload,**kwargs):
            nonlocal calls
            calls+=1
            if calls==1:raise ProviderError('AMBIGUOUS_NETWORK_FAILURE: timeout')
            return self.response(provider,payload)
        with patch('agency_study.runner.invoke',side_effect=flaky):
            self.assertEqual(run_tutors(self.c,self.db,self.archive,True,1,3),2)
        saved=self.snapshot()
        with patch('agency_study.runner.invoke',side_effect=self.response) as provider:
            self.assertEqual(run_tutors(self.c,self.db,self.archive,True,1,2),2)
            self.assertEqual(provider.call_count,2)
        for rid,record in saved.items():self.assertEqual(self.snapshot()[rid],record)
        con=connect(self.db)
        state=progress(con);order=json.loads(con.execute("SELECT value_json FROM metadata WHERE key='tutor_run_order'").fetchone()[0])
        self.assertEqual(state['status_counts'],{'blocked_ambiguous':1,'complete':4,'planned':175})
        self.assertEqual(con.execute('SELECT COUNT(*) FROM attempts WHERE object_id=?',(order[0],)).fetchone()[0],1)
        self.assertEqual(state['next_pending_run'],order[5]);con.close()
        checkpoint=json.loads(Path(str(self.db)+'.progress.json').read_text())
        self.assertEqual(checkpoint['status_counts'],state['status_counts'])

    def test_explicit_retry_keeps_old_failure_and_records_authorization(self):
        with patch('agency_study.runner.invoke',side_effect=ProviderError('AMBIGUOUS_NETWORK_FAILURE: timeout')):
            run_tutors(self.c,self.db,self.archive,True,1,1)
        with patch('agency_study.runner.invoke',side_effect=self.response) as provider:
            run_tutors(self.c,self.db,self.archive,True,1,1,retry_ambiguous=True,timeout_seconds=300)
            self.assertEqual(provider.call_count,1)
            self.assertEqual(provider.call_args.kwargs['timeout'],300)
        con=connect(self.db)
        attempts=list(con.execute('SELECT object_id,number,status,error_json FROM attempts ORDER BY number'))
        self.assertEqual(len({r[0] for r in attempts}),1)
        self.assertEqual([r[2] for r in attempts],['ambiguous','success'])
        self.assertIn('timeout',attempts[0][3])
        self.assertEqual(con.execute("SELECT COUNT(*) FROM recovery_events WHERE action='retry_authorized'").fetchone()[0],1)
        self.assertEqual(progress(con)['unknown_charge_attempts'],1);con.close()

    def test_archived_success_restored_after_crash_without_any_provider_call(self):
        con,rid,payload=self.first_request()
        con.execute("UPDATE runs SET status='in_flight' WHERE run_id=?",(rid,));con.commit()
        aid=store_attempt_start(con,'tutor',rid,payload)
        output=self.response('deepinfra',payload)
        append_archive(self.archive,{'event':'provider_success','stage':'tutor','object':rid,
            'attempt_id':aid,'request':payload,'response':output['raw'],'created_utc':'2026-10-24T00:00:00+00:00'})
        with patch('agency_study.runner.invoke') as provider:
            recovered=prepare_resume(self.c,con,self.archive)
            provider.assert_not_called()
        self.assertEqual(recovered['restored'],[rid])
        row=con.execute('SELECT * FROM runs WHERE run_id=?',(rid,)).fetchone()
        self.assertEqual(row['status'],'complete');self.assertEqual(row['response_text'],output['text'])
        self.assertEqual(con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],1)
        self.assertEqual(con.execute('SELECT status FROM attempts').fetchone()[0],'success');con.close()
        with patch('agency_study.runner.invoke',side_effect=self.response):
            run_tutors(self.c,self.db,self.archive,True,1,1)
        self.assertEqual(self.snapshot()[rid],dict(row))

    def test_successful_attempt_restored_when_run_finalization_was_interrupted(self):
        con,rid,payload=self.first_request();aid=store_attempt_start(con,'tutor',rid,payload)
        output=self.response('deepinfra',payload)
        con.execute("UPDATE runs SET status='in_flight' WHERE run_id=?",(rid,))
        con.execute("UPDATE attempts SET status='success',raw_response_json=?,input_tokens=100,output_tokens=20,cost_usd=? WHERE attempt_id=?",
                    (canonical(output['raw']),cost_usd(100,20,self.c['tutor']),aid));con.commit()
        self.assertEqual(prepare_resume(self.c,con,self.archive)['restored'],[rid]);con.close()

    def test_authentication_failure_halts_and_can_be_resumed_after_key_fix(self):
        with patch('agency_study.runner.invoke',side_effect=ProviderError('HTTP 401: invalid_api_key',status=401)) as provider:
            with self.assertRaises(ProviderError):run_tutors(self.c,self.db,self.archive,True,1,3)
            self.assertEqual(provider.call_count,1)
        with patch('agency_study.runner.invoke',side_effect=self.response):
            run_tutors(self.c,self.db,self.archive,True,1,1)
        con=connect(self.db)
        self.assertEqual([r[0] for r in con.execute('SELECT status FROM attempts ORDER BY number')],['terminal_error','success'])
        self.assertEqual(con.execute("SELECT COUNT(*) FROM recovery_events WHERE action='safe_requeue'").fetchone()[0],1);con.close()

    def test_keyboard_interrupt_is_checkpointed_and_not_silently_resent(self):
        with patch('agency_study.runner.invoke',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):run_tutors(self.c,self.db,self.archive,True,1,3)
        con=connect(self.db);old=con.execute('SELECT object_id FROM attempts').fetchone()[0];con.close()
        with patch('agency_study.runner.invoke',side_effect=self.response):
            run_tutors(self.c,self.db,self.archive,True,1,1)
        con=connect(self.db)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM attempts WHERE object_id=?',(old,)).fetchone()[0],1)
        self.assertEqual(con.execute('SELECT status FROM attempts WHERE object_id=?',(old,)).fetchone()[0],'ambiguous');con.close()

    def test_order_is_stable_across_restarts(self):
        con=connect(self.db);ensure_recovery_schema(con);original=queue_order(con,self.c['randomization_seed']);con.close()
        for count in [3,2]:
            with patch('agency_study.runner.invoke',side_effect=self.response):
                run_tutors(self.c,self.db,self.archive,True,1,count)
        con=connect(self.db)
        attempted=[r[0] for r in con.execute('SELECT object_id FROM attempts ORDER BY started_utc')]
        self.assertEqual(attempted,original[:5]);con.close()

    def test_fail_fast_preserves_checkpoint(self):
        with patch('agency_study.runner.invoke',side_effect=ProviderError('AMBIGUOUS_NETWORK_FAILURE: timeout')) as provider:
            with self.assertRaises(ProviderError):
                run_tutors(self.c,self.db,self.archive,True,1,3,continue_on_error=False)
            self.assertEqual(provider.call_count,1)
        self.assertEqual(json.loads(Path(str(self.db)+'.progress.json').read_text())['status_counts'],
                         {'blocked_ambiguous':1,'planned':179})

    def test_second_collector_cannot_start(self):
        with collection_lock(self.db):
            with patch('agency_study.runner.invoke') as provider:
                with self.assertRaisesRegex(ValueError,'Another collector'):
                    run_tutors(self.c,self.db,self.archive,True,1,1)
                provider.assert_not_called()

    def test_budget_rejection_does_not_leave_a_request_in_flight(self):
        with patch('agency_study.runner.invoke') as provider:
            with self.assertRaisesRegex(ValueError,'Spending guard'):
                run_tutors(self.c,self.db,self.archive,True,0.00000001,1)
            provider.assert_not_called()
        con=connect(self.db)
        self.assertEqual(progress(con)['status_counts'],{'planned':180})
        self.assertEqual(con.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0);con.close()

    def test_archive_request_mismatch_blocks_recovery(self):
        con,rid,payload=self.first_request();aid=store_attempt_start(con,'tutor',rid,payload)
        con.execute("UPDATE runs SET status='in_flight' WHERE run_id=?",(rid,));con.commit()
        append_archive(self.archive,{'event':'provider_success','stage':'tutor','object':rid,
            'attempt_id':aid,'request':{**payload,'temperature':1.0},'response':self.response('deepinfra',payload)['raw']})
        with self.assertRaisesRegex(ValueError,'Archive/request mismatch'):prepare_resume(self.c,con,self.archive)
        con.close()

    def test_truncated_response_is_preserved_instead_of_regenerated(self):
        def truncated(provider,payload,**kwargs):
            result=self.response(provider,payload);result['stop_reason']='length'
            result['raw']['choices'][0]['finish_reason']='length';return result
        with patch('agency_study.runner.invoke',side_effect=truncated):run_tutors(self.c,self.db,self.archive,True,1,1)
        saved=self.snapshot()
        with patch('agency_study.runner.invoke',side_effect=self.response):
            run_tutors(self.c,self.db,self.archive,True,1,1,retry_ambiguous=True)
        for rid,record in saved.items():self.assertEqual(self.snapshot()[rid],record)

    def test_status_can_inspect_a_legacy_database_without_migrating_it(self):
        con=connect(self.db)
        before=list(con.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        state=progress(con)
        self.assertEqual(state['pending'],180)
        self.assertEqual(before,list(con.execute("SELECT name FROM sqlite_master WHERE type='table'")));con.close()

    def test_budget_reserves_unknown_attempt_cost_instead_of_assuming_free(self):
        with patch('agency_study.runner.invoke',side_effect=ProviderError('AMBIGUOUS_NETWORK_FAILURE: timeout')):
            run_tutors(self.c,self.db,self.archive,True,1,1)
        con=connect(self.db)
        payload=json.loads(con.execute('SELECT raw_request_json FROM attempts').fetchone()[0]);con.close()
        cap=conservative_reservation(payload,self.c['tutor'])*1.1
        with patch('agency_study.runner.invoke') as provider:
            with self.assertRaisesRegex(ValueError,'reserved uncertain usage'):
                run_tutors(self.c,self.db,self.archive,True,cap,1,retry_ambiguous=True)
            provider.assert_not_called()

    def test_resume_cli_accepts_runtime_flags_and_passes_timeout(self):
        from agency_study.cli import main
        import sys
        argv=['agency_study','--config',str(Path(self.c['_root'])/'config.json'),
              '--db',str(self.db),'--archive',str(self.archive),'resume-tutors',
              '--live','--max-usd','1','--limit','1','--timeout-seconds','240','--retry-ambiguous']
        with patch.object(sys,'argv',argv),patch('agency_study.runner.invoke',side_effect=self.response) as provider:
            main()
            self.assertEqual(provider.call_count,1)
            self.assertEqual(provider.call_args.kwargs['timeout'],240)

    def test_corrupt_archive_halts_without_issuing_a_provider_request(self):
        self.archive.write_text('{"incomplete":')
        with patch('agency_study.runner.invoke') as provider:
            with self.assertRaisesRegex(ValueError,'invalid JSON record'):
                run_tutors(self.c,self.db,self.archive,True,1,1)
            provider.assert_not_called()

    def test_manually_requeued_ambiguous_request_still_needs_audited_retry(self):
        with patch('agency_study.runner.invoke',side_effect=ProviderError('AMBIGUOUS_NETWORK_FAILURE: timeout')):
            run_tutors(self.c,self.db,self.archive,True,1,1)
        con=connect(self.db)
        old=con.execute('SELECT object_id FROM attempts').fetchone()[0]
        con.execute("UPDATE runs SET status='planned' WHERE run_id=?",(old,));con.commit();con.close()
        with patch('agency_study.runner.invoke',side_effect=self.response):
            run_tutors(self.c,self.db,self.archive,True,1,1)
        con=connect(self.db)
        self.assertEqual(con.execute('SELECT status FROM runs WHERE run_id=?',(old,)).fetchone()[0],'blocked_ambiguous')
        self.assertEqual(con.execute('SELECT COUNT(*) FROM attempts WHERE object_id=?',(old,)).fetchone()[0],1);con.close()


if __name__=='__main__':unittest.main()
