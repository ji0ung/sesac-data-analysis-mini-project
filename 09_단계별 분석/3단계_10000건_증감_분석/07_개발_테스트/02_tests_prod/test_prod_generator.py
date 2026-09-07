import importlib.util, json, sqlite3, tempfile, unittest
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("prodgen",HERE/"02_generator_prod.py")
g=importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
CONFIG=HERE/"02_base_config_prod.yaml"

class ProductionReadinessTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.t=tempfile.TemporaryDirectory(); cls.out=Path(cls.t.name)/"dry.sqlite"
  cls.result=g.generate(CONFIG,cls.out,dry_run_users=200); cls.db=sqlite3.connect(cls.out)
 @classmethod
 def tearDownClass(cls): cls.db.close(); cls.t.cleanup()
 def test_01_config_schema_validation(self): self.assertEqual(g.load_config(CONFIG)["execution_mode"],"production")
 def test_02_dry_run_200(self): self.assertEqual(self.result["users"],200)
 def test_03_production_config_prevalidation(self): g.validate_production_config(g.load_config(CONFIG))
 def test_04_total_calculation(self):
  c=g.load_config(CONFIG); self.assertEqual(c["n_users_total"],c["n_users_control"]+c["n_users_treatment"]); self.assertEqual(c["n_users_total"],10000)
 def test_05_arm_calculation(self):
  c=g.load_config(CONFIG); self.assertEqual((c["n_users_control"],c["n_users_treatment"]),(5000,5000))
 def test_06_sample_set_allowed(self): self.assertEqual(self.db.execute("SELECT count(*) FROM ExperimentAssignment WHERE sample_set_type NOT IN('control','treatment') OR sample_set_type IS NULL").fetchone()[0],0)
 def test_07_required_fields_not_null(self):
  cols="user_id pair_id sample_set_type sample_stratum intent_segment intent_assignment_prob intent_version simulation_run_id random_seed scenario_type treatment_policy template_cluster_id".split()
  self.assertTrue(all(self.db.execute(f'SELECT count(*) FROM ExperimentAssignment WHERE "{x}" IS NULL').fetchone()[0]==0 for x in cols))
 def test_08_pair_completeness(self): self.assertEqual(self.db.execute("SELECT count(*) FROM (SELECT pair_id FROM ExperimentAssignment GROUP BY pair_id HAVING count(*)<>2 OR count(DISTINCT sample_set_type)<>2)").fetchone()[0],0)
 def test_09_pk_fk_orphans(self): self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(),[]); self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
 def test_10_time_order(self):
  self.assertEqual(self.db.execute("SELECT count(*) FROM SessionSummary WHERE session_end_at<=session_start_at").fetchone()[0],0)
  self.assertEqual(self.db.execute("SELECT count(*) FROM SearchTransition WHERE interarrival_seconds<=0").fetchone()[0],0)
 def test_11_no_exact_row_clone(self):
  # No duplicate complete logical search row; the only intentional repeat is the paired pre-profile.
  self.assertEqual(self.db.execute("SELECT count(*) FROM (SELECT user_id,search_seq,search_at,condition_signature,total_result_count,count(*) n FROM Search GROUP BY 1,2,3,4,5 HAVING n>1)").fetchone()[0],0)
 def test_12_session_path_concentration(self):
  paths=[r[0] for r in self.db.execute("SELECT group_concat(total_result_count||':'||query_variant,'>') FROM Search GROUP BY user_id")]
  self.assertLessEqual(max(Counter(paths).values())/len(paths),.20)
 def test_13_no_source_session_id(self):
  names=[r[1].lower() for t in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'") for r in self.db.execute(f"PRAGMA table_info('{t[0]}')")]
  self.assertNotIn("source_session_id",names)
 def test_14_overwrite_prevention(self):
  with self.assertRaises(FileExistsError): g.generate(CONFIG,self.out,dry_run_users=200)
 def test_15_unapproved_output_folder(self):
  c=g.load_config(CONFIG)
  with self.assertRaises(PermissionError): g.validate_execution(c,CONFIG,None,True,g.sha256(CONFIG),Path(self.t.name)/"x.sqlite")
 def test_16_confirm_required(self):
  c=g.load_config(CONFIG); approved=Path(c["approved_output_dir"])/"03_ab10000_base.sqlite"
  with self.assertRaises(PermissionError): g.validate_execution(c,CONFIG,None,False,g.sha256(CONFIG),approved)
 def test_17_config_hash_guard(self):
  c=g.load_config(CONFIG); approved=Path(c["approved_output_dir"])/"03_ab10000_base.sqlite"
  with self.assertRaises(PermissionError): g.validate_execution(c,CONFIG,None,True,"0"*64,approved)

if __name__=="__main__": unittest.main(verbosity=2)
