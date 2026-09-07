import importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
import jsonschema,yaml
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
 s=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
gen=load('gen','03_generator_newref_v01.py');quality=load('quality','03_quality_gate_newref_v01.py');clone=load('clone','03_clone_audit_newref_v01.py')
CFG=ROOT/'03_base_config_newref_v01.yaml';SMOKE=ROOT/'tests'/'smoke_200.sqlite'
class NewRefTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=sqlite3.connect(SMOKE);cls.c.row_factory=sqlite3.Row;cls.q=quality.audit(SMOKE);cls.cl=clone.audit(SMOKE);cls.cfg=yaml.safe_load(CFG.read_text(encoding='utf8'))
 @classmethod
 def tearDownClass(cls):cls.c.close()
 def test_01_reference_sha(self):self.assertEqual(gen.load_config(CFG)[0]['reference']['sha256'],'9120561ee85705141a92eae74c5015fb2c9a20f0c8d1f6df4d99893952fd1e9f')
 def test_02_config_schema(self):jsonschema.validate(self.cfg,json.loads((ROOT/'03_config_schema_newref_v01.json').read_text()))
 def test_03_users(self):self.assertEqual(self.c.execute('select count(*) from UserSynthetic').fetchone()[0],200)
 def test_04_balance(self):self.assertEqual(dict(self.q['metrics']['arms']),{'control':100,'treatment':100})
 def test_05_pairs(self):self.assertEqual(self.q['metrics']['pairs'],100)
 def test_06_required_fields(self):self.assertEqual(self.c.execute('select count(*) from UserSynthetic where sample_set_type is null or sample_stratum is null or simulation_run_id is null or random_seed is null or source_session_id is null or pair_id is null or treatment_scenario is null or generation_model_version is null').fetchone()[0],0)
 def test_07_source_valid(self):
  _,r=gen.load_config(CFG);rc=sqlite3.connect('file:'+r.as_posix()+'?mode=ro',uri=True);valid={x[0] for x in rc.execute('select distinct session_id from search')};rc.close();self.assertFalse({x[0] for x in self.c.execute('select distinct source_session_id from UserSynthetic')}-valid)
 def test_08_pair_pre_match(self):
  sql='''select count(*) from UserSynthetic c join UserSynthetic t using(pair_id) join SessionSynthetic cs on cs.user_id=c.user_id join SessionSynthetic ts on ts.user_id=t.user_id join Search cq on cq.session_id=cs.session_id and cq.search_sequence=1 join Search tq on tq.session_id=ts.session_id and tq.search_sequence=1 join SearchFilter cf on cf.search_id=cq.search_id join SearchFilter tf on tf.search_id=tq.search_id where c.sample_set_type='control' and t.sample_set_type='treatment' and (c.sample_stratum<>t.sample_stratum or cq.query_text<>tq.query_text or cq.destination<>tq.destination or cq.total_result_count<>tq.total_result_count or coalesce(cf.price,-1)<>coalesce(tf.price,-1) or cf.amenity_count<>tf.amenity_count)''';self.assertEqual(self.c.execute(sql).fetchone()[0],0)
 def test_09_no_outcome_leakage(self):self.assertEqual(self.c.execute("select count(*) from UserSynthetic where sample_stratum like '%SG%' or sample_stratum like '%recover%'").fetchone()[0],0)
 def test_10_relationships(self):self.assertTrue(self.q['pass'])
 def test_11_metric_outputs(self):self.assertTrue(all(k in self.q['metrics'] for k in ['search_zero','zero_followup','immediate_recovery','final_recovery','card_h_search','card_h_event','sg3','sg4']))
 def test_12_clone_detector(self):self.assertEqual(self.cl['arm_full_path']['control']['duplicate_excess'],0);self.assertEqual(self.cl['arm_full_path']['treatment']['duplicate_excess'],0)
 def test_13_diversity_outputs(self):self.assertTrue(all(k in self.cl for k in ['condition_signature','condition_path','behavior_path','template_cluster','full_path','delay_vector']))
 def test_14_scenario_reject(self):
  bad=dict(self.cfg);bad['scenario']='invalid';self.assertRaises(jsonschema.ValidationError,jsonschema.validate,bad,json.loads((ROOT/'03_config_schema_newref_v01.json').read_text()))
 def test_15_seed_missing_reject(self):
  bad=dict(self.cfg);bad.pop('seed');self.assertRaises(jsonschema.ValidationError,jsonschema.validate,bad,json.loads((ROOT/'03_config_schema_newref_v01.json').read_text()))
 def test_16_smoke_201_reject(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:self.assertRaises(PermissionError,gen.generate,CFG,Path(d)/'x.sqlite','smoke_test',202,1)
 def test_17_calibration_reject(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:self.assertRaises(PermissionError,gen.generate,CFG,Path(d)/'x.sqlite','calibration',40,1)
 def test_18_production_reject(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:self.assertRaises(PermissionError,gen.generate,CFG,Path(d)/'x.sqlite','production',10000,1)
 def test_19_outside_path_reject(self):self.assertRaises(PermissionError,gen.generate,CFG,ROOT/'outside.sqlite','smoke_test',40,1)
 def test_20_overwrite_reject(self):self.assertRaises(FileExistsError,gen.generate,CFG,SMOKE,'smoke_test',200,1)
 def test_21_determinism_and_seed_change(self):
  def fp(p):
   c=sqlite3.connect(p);h=[]
   for t in ['UserSynthetic','SessionSynthetic','Search','SearchFilter','SearchResult','ActionEvent','SearchTransition']:h.extend(c.execute(f'select * from {t} order by 1').fetchall())
   c.close();return repr(h)
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as d:
   a=Path(d)/'a.sqlite';b=Path(d)/'b.sqlite';z=Path(d)/'z.sqlite';gen.generate(CFG,a,'unit_test',40,77);gen.generate(CFG,b,'unit_test',40,77);gen.generate(CFG,z,'unit_test',40,78);self.assertEqual(fp(a),fp(b));self.assertNotEqual(fp(a),fp(z))
if __name__=='__main__':unittest.main()
