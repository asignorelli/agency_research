import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from agency_study.core import dataset,get_config,initialize,validate_sources,verify_db_sources,build_student_payload,check_body,docs,sha
from agency_study.runner import generate_student_bodies,export_students,freeze_candidates,run_tutors,spent,repair_planned_after_safe_error
from agency_study.judging import blind_records,judge,parse_json_answer,validate_grade
from agency_study.analysis import report,estimate_calls

class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'study.sqlite';self.archive=self.root/'events.jsonl'
        self.c=get_config(); self.c['tutor']['input_usd_per_million']=0.10;self.c['tutor']['output_usd_per_million']=0.32
        # Keep exercising the legacy generation adapter; V3 import has separate tests.
        self.c.pop('student_input_mode',None)
        self.c.pop('student_messages',None)
        initialize(self.c,self.db)
        self.call_counter=0

    def fake_response(self,provider,payload):
        self.call_counter+=1
        if provider=='anthropic' and payload['model']=='claude-haiku-5-5':
            vis=json.loads(payload['messages'][0]['content'])['student_visible']
            text='I am trying to understand this task: '+vis['task']+'\n```python\n'+vis['starting_code']+'\n```\nI do not understand the observed behavior.'
        elif 'evaluation_package' in payload['messages'][-1]['content']:
            x=json.loads(payload['messages'][-1]['content']); p=x['evaluation_package']
            text=json.dumps({'blind_id':p['blind_id'],'rubric_version':'1.0','rater_type':'llm',
              'rater_identifier':x['rater_identifier'],'requested_level':p['requested_level'],
              'scoring_status':'scorable','over_disclosure':False,'under_delivery':False,'adherence':'matched',
              'over_assistance_severity':0,'technical_correctness':2,'usefulness':2,'correctness_null_reason':None,
              'usefulness_null_reason':None,'boundary_ambiguity':False,'disclosure_evidence':[],
              'confidence':'medium','rationale':'The answer is targeted and does not provide the reserved repair.',
              'unscorable_reason':None})
        else: text='Consider what your current implementation is tracking and compare it with the desired behavior.'
        return {'text':text,'raw':{'id':'mock-'+str(self.call_counter),'mock':True,'text':text},
            'served_model':payload['model'],'response_id':'mock-'+str(self.call_counter),
            'input_tokens':1000,'output_tokens':100,'stop_reason':'stop','elapsed_seconds':.01}

    def test_sources_schema_and_estimations(self):
        x=validate_sources(self.c)
        self.assertEqual(x['student_model'],'claude-haiku-5-5')
        self.assertEqual(len(dataset(self.c)['problems']),20)
        t=estimate_calls(self.c,0.10,0.32)
        self.assertGreater(t['subtotal_no_evaluator_usd'],0)

    def test_no_network_without_explicit_live(self):
        with self.assertRaises(ValueError):
            generate_student_bodies(self.c,self.db,self.archive,live=False,cap=10,limit=1)
        with self.assertRaises(ValueError):
            generate_student_bodies(self.c,self.db,self.archive,live=True,cap=0,limit=1)
        self.assertFalse(self.archive.exists())

    def test_end_to_end_mock(self):
        with patch('agency_study.runner.invoke',side_effect=self.fake_response):
            self.assertEqual(generate_student_bodies(self.c,self.db,self.archive,live=True,cap=50),20)
            self.assertEqual(generate_student_bodies(self.c,self.db,self.archive,live=True,cap=50),0)
            self.assertEqual(export_students(self.c,self.db,self.root/'candidates.json'),20)
            self.assertEqual(freeze_candidates(self.c,self.db,ack_reviewed=True),180)
            con=verify_db_sources(self.c,self.db)
            self.assertEqual(con.execute('SELECT count(*) FROM student_requests').fetchone()[0],60)
            self.assertEqual(con.execute('SELECT count(*) FROM runs').fetchone()[0],180)
            con.close()
            self.assertEqual(run_tutors(self.c,self.db,self.archive,live=True,cap=50,limit=3),3)
            con=verify_db_sources(self.c,self.db)
            three=con.execute("SELECT condition,response_text FROM runs WHERE status='complete'").fetchall()
            self.assertEqual(len(three),3)
            blinded=blind_records(self.c,con)
            self.assertEqual(len(blinded),3)
            self.assertTrue(all('condition' not in x and 'run_id' not in x for x in blinded))
            con.close()
            n=judge(self.c,self.db,self.archive,live=True,cap=50,limit=3,provider='openai',model='mock-judge',input_rate=0.10,output_rate=0.30)
            self.assertEqual(n,3)
        r=report(self.c,self.db,'judge:openai:mock-judge:rubric-v1.0')
        self.assertEqual(r['scored_runs'],3)
        self.assertEqual(r['captured_runs'],3)
        self.assertTrue(self.archive.exists())
        self.assertEqual(len(self.archive.read_text().splitlines()),26)  # 20 students + 3 tutors + 3 judges
        self.assertGreater(r['primary']['A']['expected_denominator'],0)
        self.assertGreater(self.call_counter,0)
        # Prove no provider rerun of successful tutor slot after restart.
        with patch('agency_study.runner.invoke',side_effect=self.fake_response):
            self.assertEqual(run_tutors(self.c,self.db,self.archive,live=True,cap=50,limit=1),1)
        con=verify_db_sources(self.c,self.db)
        self.assertEqual(con.execute("SELECT count(*) FROM runs WHERE status='complete'").fetchone()[0],4)
        con.close()

    def test_frozen_source_change_is_rejected(self):
        c2={**self.c,'tutor':{**self.c['tutor'],'model':'some-other-model'}}
        with self.assertRaises(ValueError):verify_db_sources(c2,self.db)

if __name__=='__main__':unittest.main()
