import copy,importlib.util,json,math,random,sqlite3,tempfile,unittest
from pathlib import Path
import jsonschema,yaml
ROOT=Path(__file__).resolve().parents[1];CFG=ROOT/'05_base_config_newref_v02.yaml';SMOKE=ROOT/'tests'/'smoke_200_approved_v03.sqlite'
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
gen=load('gen','05_generator_newref_v02.py'); quality=load('quality','05_quality_gate_newref_v02.py'); clone=load('clone','05_clone_audit_newref_v02.py')
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cfg=yaml.safe_load(CFG.read_text(encoding='utf8'));cls.c=sqlite3.connect(SMOKE);cls.q=quality.audit(SMOKE);cls.cl=clone.audit(SMOKE);cls.prof=gen.reference_profile(gen.load_config(CFG)[1])
 @classmethod
 def tearDownClass(cls):cls.c.close()
 def test_01_sha(self):self.assertEqual(gen.load_config(CFG)[0]['reference']['sha256'],'9120561ee85705141a92eae74c5015fb2c9a20f0c8d1f6df4d99893952fd1e9f')
 def test_02_schema(self):jsonschema.validate(self.cfg,json.loads((ROOT/'05_config_schema_newref_v02.json').read_text()))
 def test_03_users(self):self.assertEqual(self.c.execute('select count(*) from UserSynthetic').fetchone()[0],200)
 def test_04_arms(self):self.assertEqual(dict(self.q['metrics']['arms']),{'control':100,'treatment':100})
 def test_05_pairs(self):self.assertEqual(self.q['metrics']['pairs'],100)
 def test_06_required(self):self.assertEqual(self.c.execute('select count(*) from UserSynthetic where sample_set_type is null or sample_stratum is null or simulation_run_id is null or random_seed is null or source_session_id is null').fetchone()[0],0)
 def test_07_pair_pre(self):
  q='''select count(*) from UserSynthetic c join UserSynthetic t using(pair_id) join SessionSynthetic cs on cs.user_id=c.user_id join SessionSynthetic ts on ts.user_id=t.user_id join Search cq on cq.session_id=cs.session_id and cq.search_sequence=1 join Search tq on tq.session_id=ts.session_id and tq.search_sequence=1 join SearchFilter cf on cf.search_id=cq.search_id join SearchFilter tf on tf.search_id=tq.search_id where c.sample_set_type='control' and t.sample_set_type='treatment' and(c.sample_stratum<>t.sample_stratum or cq.total_result_count<>tq.total_result_count or cq.query_text<>tq.query_text or coalesce(cf.price,-1)<>coalesce(tf.price,-1) or cf.amenity_count<>tf.amenity_count)''';self.assertEqual(self.c.execute(q).fetchone()[0],0)
 def test_08_quality(self):self.assertTrue(self.q['pass'])
 def test_09_booking(self):self.assertEqual(self.c.execute("select count(*) from Booking").fetchone()[0],0)
 def test_10_clone_a(self):self.assertEqual(self.cl['clone_a_rows'],0)
 def test_11_clone_b(self):self.assertEqual(sum(self.cl[a]['clone_b_sessions'] for a in ('control','treatment')),0)
 def test_12_clone_c(self):self.assertEqual(sum(self.cl[a]['clone_c_sessions'] for a in ('control','treatment')),0)
 def test_13_diversity_separate(self):self.assertGreater(sum(self.cl[a]['diversity_path_repeated_sessions'] for a in ('control','treatment')),0)
 def test_14_follow_zero(self):
  x=copy.deepcopy(self.cfg);x['state_machine']['zero_followup_probability']=0
  for i in range(100):self.assertLessEqual(len(gen.state_plan(random.Random(i),x,self.prof,{'ever_zero':True,'first_zero':True})[0]),1)
 def test_15_follow_one(self):
  x=copy.deepcopy(self.cfg);x['state_machine']['zero_followup_probability']=1
  for i in range(100):self.assertGreaterEqual(len(gen.state_plan(random.Random(i),x,self.prof,{'ever_zero':True,'first_zero':True})[0]),2)
 def test_16_immediate_zero(self):
  x=copy.deepcopy(self.cfg);x['state_machine']['immediate_recovery_probability']=0
  for i in range(100):self.assertNotIn('IMMEDIATE_RECOVERY',gen.state_plan(random.Random(i),x,self.prof,{'ever_zero':True,'first_zero':True,'follow':True})[0])
 def test_17_immediate_one(self):
  x=copy.deepcopy(self.cfg);x['state_machine']['immediate_recovery_probability']=1
  for i in range(100):self.assertIn('IMMEDIATE_RECOVERY',gen.state_plan(random.Random(i),x,self.prof,{'ever_zero':True,'first_zero':True,'follow':True})[0])
 def test_18_late_one(self):
  x=copy.deepcopy(self.cfg);x['state_machine']['terminal_recovery_probability']=1;x['state_machine']['immediate_recovery_probability']=0
  self.assertEqual(gen.state_plan(random.Random(1),x,self.prof,{'ever_zero':True,'first_zero':True,'follow':True,'immediate':False})[1],'SG3')
 def test_19_persistent(self):
  p,o=gen.state_plan(random.Random(1),self.cfg,self.prof,{'ever_zero':True,'first_zero':True,'follow':True,'immediate':False,'late':False});self.assertEqual((o,p[-1]),('SG4','PERSISTENT_FAILURE'))
 def test_20_terminal_positive(self):
  p,o=gen.state_plan(random.Random(1),self.cfg,self.prof,{'ever_zero':True,'first_zero':True,'follow':True,'immediate':False,'late':True});self.assertEqual((o,p[-1]),('SG3','LATE_RECOVERY'))
 def test_21_body(self):
  x=copy.deepcopy(self.cfg['time_mixture']);x['same_timestamp_probability']=0;x['tail_probability']=0
  self.assertTrue(all(gen.draw_interval(random.Random(i),x)[1]=='body' for i in range(30)))
 def test_22_tail(self):
  x=copy.deepcopy(self.cfg['time_mixture']);x['same_timestamp_probability']=0;x['tail_probability']=1
  self.assertTrue(all(gen.draw_interval(random.Random(i),x)[1]=='tail' for i in range(30)))
 def test_23_nonnegative_time(self):self.assertTrue(all(gen.draw_interval(random.Random(i),self.cfg['time_mixture'])[0]>=0 for i in range(1000)))
 def test_24_tail_exists(self):self.assertTrue(any(gen.draw_interval(random.Random(i),self.cfg['time_mixture'])[1]=='tail' for i in range(1000)))
 def test_25_cardh_convergence(self):
  r=random.Random(991);n=200000;p=self.cfg['card_h']['search_probability'];v=sum(r.random()<p for _ in range(n))/n;self.assertLess(abs(v-p),5*math.sqrt(p*(1-p)/n))
 def test_26_follow_convergence(self):
  r=random.Random(992);n=100000;p=self.cfg['state_machine']['zero_followup_probability'];v=sum(r.random()<p for _ in range(n))/n;self.assertLess(abs(v-p),5*math.sqrt(p*(1-p)/n))
 def test_27_immediate_convergence(self):
  r=random.Random(993);n=100000;p=self.cfg['state_machine']['immediate_recovery_probability'];v=sum(r.random()<p for _ in range(n))/n;self.assertLess(abs(v-p),5*math.sqrt(p*(1-p)/n))
 def test_28_tail_convergence(self):
  r=random.Random(994);n=100000;p=self.cfg['time_mixture']['tail_probability'];v=sum(r.random()<p for _ in range(n))/n;self.assertLess(abs(v-p),5*math.sqrt(p*(1-p)/n))
 def test_29_scenario_monotonic(self):self.assertLessEqual(gen.posterior(self.cfg,'region_change','conservative'),gen.posterior(self.cfg,'region_change','expected'));self.assertLessEqual(gen.posterior(self.cfg,'region_change','expected'),gen.posterior(self.cfg,'region_change','optimistic'))
 def test_30_smoke_201(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:self.assertRaises(PermissionError,gen.generate,CFG,Path(d)/'x', 'smoke_test',202,1)
 def test_31_calibration_block(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:self.assertRaises(PermissionError,gen.generate,CFG,Path(d)/'x','calibration',40,1)
 def test_32_production_block(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:self.assertRaises(PermissionError,gen.generate,CFG,Path(d)/'x','production',40,1)
 def test_33_prodseed_block(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:self.assertRaises(PermissionError,gen.generate,CFG,Path(d)/'x','unit_test',40,2434815518)
 def test_34_outside_block(self):self.assertRaises(PermissionError,gen.generate,CFG,ROOT/'x.sqlite','unit_test',40,1)
 def test_35_overwrite(self):self.assertRaises(FileExistsError,gen.generate,CFG,SMOKE,'smoke_test',200,1)
 def test_36_fk(self):self.assertEqual(self.c.execute('pragma foreign_key_check').fetchall(),[])
 def test_37_result_count(self):self.assertEqual(next(x['value'] for x in self.q['checks'] if x['check']=='result_count'),0)
 def test_38_no_reverse(self):self.assertEqual(next(x['value'] for x in self.q['checks'] if x['check']=='time_inversion'),0)
 def test_39_cardh_grain(self):self.assertEqual(len(self.q['metrics']['card_h_search']),2)
 def test_40_event_separate(self):self.assertIsInstance(self.q['metrics']['card_h_event'],int)
 def test_41_hazard_order(self):self.assertGreater(gen.zero_hazard(self.cfg,1,0,0,'same_condition',0,'0',0),gen.zero_hazard(self.cfg,5,0,0,'same_condition',0,'0',0))
 def test_42_hazard_treatment(self):self.assertGreater(gen.zero_hazard(self.cfg,2,1,1,'same_condition',1,'2+',0),gen.zero_hazard(self.cfg,2,1,1,'region_change',1,'2+',1))
if __name__=='__main__':unittest.main()
