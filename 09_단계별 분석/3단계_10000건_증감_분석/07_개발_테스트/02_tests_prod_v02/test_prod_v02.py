import importlib.util,sqlite3,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];sp=importlib.util.spec_from_file_location('g',HERE/'02_generator_prod_v02.py');g=importlib.util.module_from_spec(sp);sp.loader.exec_module(g)
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=g.load_config();cls.t=tempfile.TemporaryDirectory();cls.p=Path(cls.t.name)/'d.sqlite';cls.r=g.simulate_control(260601,200,cls.c,cls.p);cls.db=sqlite3.connect(cls.p)
 @classmethod
 def tearDownClass(cls):cls.db.close();cls.t.cleanup()
 def test_01_config_schema(self):self.assertEqual(self.c['generator_version'],'02.prod.2')
 def test_02_integrity_fk(self):self.assertEqual(self.db.execute('pragma integrity_check').fetchone()[0],'ok');self.assertEqual(self.db.execute('pragma foreign_key_check').fetchall(),[])
 def test_03_search_filter_1to1(self):self.assertEqual(self.db.execute('select count(*) from Search').fetchone()[0],self.db.execute('select count(*) from SearchFilter').fetchone()[0])
 def test_04_results_match(self):self.assertEqual(self.db.execute('select count(*) from Search s where total_result_count<>(select count(*) from SearchResult r where r.search_id=s.search_id)').fetchone()[0],0)
 def test_05_time(self):self.assertEqual(self.db.execute('select count(*) from SessionSummary where session_end_at<=session_start_at').fetchone()[0],0)
 def test_06_no_selection_before_exposure(self):self.assertEqual(self.db.execute("select count(*) from ActionEvent where event_type='proposal_selected'").fetchone()[0],0)
 def test_07_detail_positive_only(self):self.assertEqual(self.db.execute("select count(*) from ActionEvent e join Search s using(search_id) where e.event_type='hotel_detail_view' and s.total_result_count=0").fetchone()[0],0)
 def test_08_final_recovery(self):self.assertEqual(self.db.execute('select count(*) from SessionSummary u join Search s on s.session_id=u.session_id and s.search_seq=u.search_count where u.final_recovered<>(s.total_result_count>0 and u.experienced_zero=1)').fetchone()[0],0)
 def test_09_card_h_unique(self):self.assertEqual(self.db.execute("select sum(card_h_search_count) from SessionSummary").fetchone()[0],self.db.execute("select count(distinct search_id) from ActionEvent where event_type='hotel_detail_view'").fetchone()[0])
 def test_10_repeat_separate(self):self.assertGreaterEqual(self.db.execute('select sum(card_h_event_count-card_h_search_count) from SessionSummary').fetchone()[0],0)
 def test_11_click_not_double_counted(self):self.assertEqual(self.db.execute("select count(*) from ActionEvent where event_type='hotel_click'").fetchone()[0],0)
 def test_12_arm_config(self):self.assertEqual(g.production_plan()['control:'] if False else (self.c['n_users_control'],self.c['n_users_treatment']),(5000,5000))
 def test_13_sample_type(self):self.assertEqual(self.db.execute("select count(*) from ExperimentAssignment where sample_set_type<>'control' or sample_set_type is null").fetchone()[0],0)
 def test_14_pairs(self):
  p=g.paired_assignment_plan();self.assertEqual(len(p),5000);self.assertEqual(len({x[0] for x in p}),5000);self.assertTrue(all(x[1]!=x[2] for x in p))
 def test_15_lineage(self):self.assertEqual(self.db.execute("select count(*) from ExperimentAssignment where distribution_lineage_policy<>'row-level source lineage removed'").fetchone()[0],0)
 def test_16_exact_clone(self):self.assertEqual(self.r['full_path']['duplicate_rate'],0)
 def test_17_diversity(self):
  d=self.c['diversity_limits'];self.assertLessEqual(self.r['signature']['mode_share'],d['signature_mode_share_max']);self.assertLessEqual(self.r['behavior_path']['hhi'],d['behavior_path_hhi_max'])
 def test_18_reproducibility(self):
  r=g.simulate_control(260601,200,self.c);self.assertEqual(self.r['search_zero_rate'],r['search_zero_rate']);self.assertEqual(self.r['sessions'],r['sessions'])
 def test_19_overwrite(self):
  with self.assertRaises(FileExistsError):g.simulate_control(260601,200,self.c,self.p)
if __name__=='__main__':unittest.main(verbosity=2)
