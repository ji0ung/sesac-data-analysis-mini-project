#!/usr/bin/env python3
import importlib.util,json,sqlite3
from pathlib import Path
def load(path,name):
 if not Path(path).is_file():raise FileNotFoundError(path)
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def gate(db,reference,contract,metric_module,clone_adapter,approved_clone):
 try:
  mm=load(metric_module,'metric_contract');cm=load(clone_adapter,'clone_adapter')
  metrics=mm.calculate(db,contract,'synthetic')
  clones=cm.audit(db,reference,approved_clone)
  c=sqlite3.connect('file:'+Path(db).resolve().as_posix()+'?mode=ro',uri=True);c.execute('pragma query_only=on')
  relational={'integrity':c.execute('pragma integrity_check').fetchone()[0],
   'foreign_keys':len(c.execute('pragma foreign_key_check').fetchall()),
   'time_inversion':c.execute('with x as(select session_id,search_time,lag(search_time)over(partition by session_id order by search_sequence)p from Search)select count(*) from x where search_time<p').fetchone()[0],
   'event_after_end':c.execute('select count(*) from ActionEvent e join SessionSynthetic s using(session_id) where e.event_at>s.ended_at').fetchone()[0]}
  c.close()
  clone_fail=any(clones[k]!=0 for k in ('clone_a_rows','control_clone_b','treatment_clone_b','control_clone_c','treatment_clone_c','reference_exact_session_clone','reference_exact_relative_path_clone','reference_exact_delay_vector_clone'))
  ok=relational=={'integrity':'ok','foreign_keys':0,'time_inversion':0,'event_after_end':0} and not clone_fail
  return {'status':'PASS' if ok else 'FAIL','metrics_source':'contract_executed','metrics':metrics,'clones':clones,'relational':relational}
 except Exception as e:return {'status':'ERROR','error':type(e).__name__+': '+str(e),'metrics':None,'clones':'NOT_RUN','relational':'NOT_RUN'}
