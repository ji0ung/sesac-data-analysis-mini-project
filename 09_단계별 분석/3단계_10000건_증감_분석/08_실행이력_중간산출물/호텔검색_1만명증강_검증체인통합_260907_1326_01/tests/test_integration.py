import importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];V02=ROOT.parent/'호텔검색_1만명증강_생성시스템개정_260907_1239_01'
def module(pattern,name):
 p=next(ROOT.glob(pattern));s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m,p
metric,MP=module('*공통지표계산기*.py','metric');gate,GP=module('*통합품질검증기*.py','gate');entry,EP=module('*calibration진입점*.py','entry')
CONTRACT=next(ROOT.glob('*지표정의*.yaml'));SMOKE=V02/'tests'/'smoke_200_approved_v03.sqlite';REF=(V02/__import__('yaml').safe_load((V02/'05_base_config_newref_v02.yaml').read_text(encoding='utf8'))['reference']['path']).resolve();CA=V02/'05_clone_audit_newref_v02.py';AD=next(ROOT.glob('*clone연결기*.py'))
class Integration(unittest.TestCase):
 def fixture(self,p):
  c=sqlite3.connect(p);c.executescript('''create table Search(search_id text,session_id text,search_sequence int,search_time text,total_result_count int);create table SearchResult(search_result_id text,search_id text,hotel_id text,room_id text,result_rank int);create table ActionEvent(event_id text,search_id text,hotel_id text,event_type text,event_at text);''')
  rows=[('a','S1',1,'2020-01-01T00:00:00',0),('b','S1',2,'2020-01-01T00:00:01',0),('c','S1',3,'2020-01-01T00:00:02',1),('d','S1',4,'2020-01-01T00:00:03',0),('e','S1',5,'2020-01-01T00:00:04',1),('f','S2',1,'2020-01-01T00:00:00',0)];c.executemany('insert into Search values(?,?,?,?,?)',rows);c.commit();c.close()
 def test_fixture_metrics(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'f.db';self.fixture(p);r={x['metric_id']:(x['numerator'],x['denominator']) for x in metric.calculate(p,CONTRACT,'synthetic',['zero_followup_rate','immediate_recovery_transition_rate','first_zero_immediate_recovery_rate','final_recovery_rate'])};self.assertEqual(r,{'zero_followup_rate':(3,4),'immediate_recovery_transition_rate':(2,3),'first_zero_immediate_recovery_rate':(0,1),'final_recovery_rate':(1,2)})
 def test_missing_contract(self):self.assertRaises(FileNotFoundError,metric.calculate,SMOKE,ROOT/'none.yaml','synthetic')
 def test_unknown_metric(self):self.assertRaises(KeyError,metric.calculate,SMOKE,CONTRACT,'synthetic',['unknown'])
 def test_reference_values(self):
  r={x['metric_id']:(x['numerator'],x['denominator']) for x in metric.calculate(REF,CONTRACT,'reference')};self.assertEqual(r['immediate_recovery_transition_rate'],(558,3271));self.assertEqual(r['first_zero_immediate_recovery_rate'],(69,628))
 def test_smoke_gate(self):self.assertEqual(gate.gate(SMOKE,REF,CONTRACT,MP,AD,CA)['status'],'PASS')
 def test_audit_missing_is_error(self):self.assertEqual(gate.gate(SMOKE,REF,CONTRACT,MP,AD,ROOT/'none.py')['status'],'ERROR')
 def test_authorization_missing(self):self.assertRaises(PermissionError,entry.require_authorization,ROOT/'none.json')
 def test_generator_calibration_conflict(self):self.assertIn("mode in ('calibration','production')",(V02/'05_generator_newref_v02.py').read_text(encoding='utf8'))
if __name__=='__main__':unittest.main()
