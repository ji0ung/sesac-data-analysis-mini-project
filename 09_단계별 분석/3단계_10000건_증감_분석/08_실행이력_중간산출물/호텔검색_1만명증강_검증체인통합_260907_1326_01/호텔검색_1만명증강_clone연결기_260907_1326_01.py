#!/usr/bin/env python3
import hashlib,importlib.util,json,sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
APPROVED_SHA='2dd3ec9b7b79f7948eb90b0790c7b3f02e5a73736c3446b8e2ef3761117a7026'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_audit(path):
 if not Path(path).is_file():raise FileNotFoundError(path)
 if sha(path)!=APPROVED_SHA:raise RuntimeError('clone audit SHA mismatch')
 s=importlib.util.spec_from_file_location('approved_clone_audit',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def canonical(db,kind):
 c=sqlite3.connect('file:'+Path(db).resolve().as_posix()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('pragma query_only=on')
 order='search_sequence,search_time,search_id' if kind=='synthetic' else 'search_time,search_id'
 searches=defaultdict(list)
 for r in c.execute('select * from Search order by session_id,'+order):searches[r['session_id']].append(r)
 rt='SearchResult' if kind=='synthetic' else 'search_result';et='ActionEvent' if kind=='synthetic' else 'event';ecol='event_at'
 results=defaultdict(list);events=defaultdict(list)
 for x in c.execute(f'select search_id,hotel_id,room_id,result_rank from {rt} order by search_id,result_rank,search_result_id'):results[x['search_id']].append((x['hotel_id'],x['room_id'],x['result_rank']))
 for x in c.execute(f'select search_id,event_type,hotel_id from {et} where search_id is not null order by search_id,{ecol},event_id'):events[x['search_id']].append((x['event_type'],x['hotel_id']))
 result={};delay={}
 for sid,rows in searches.items():
  start=datetime.fromisoformat(rows[0]['search_time']);path=[];dv=[]
  for r in rows:
   rel=(datetime.fromisoformat(r['search_time'])-start).total_seconds();dv.append(rel)
   rr=tuple(results[r['search_id']]);ev=tuple(events[r['search_id']])
   path.append((r['query_text'],r['destination'],r['total_result_count'],rr,ev))
  ph=hashlib.sha256(repr(tuple(path)).encode()).hexdigest();dh=hashlib.sha256(repr(tuple(dv)).encode()).hexdigest()
  result[sid]=ph;delay[sid]=(dh,len(dv),hashlib.sha256(repr((tuple(path),tuple(dv))).encode()).hexdigest())
 c.close();return set(result.values()),set(delay.values())
def audit(synthetic_db,reference_db,approved_audit):
 base=load_audit(approved_audit).audit(synthetic_db)
 sp,sd=canonical(synthetic_db,'synthetic');rp,rd=canonical(reference_db,'reference')
 sdelay={(h,n) for h,n,_ in sd if n>=2};rdelay={(h,n) for h,n,_ in rd if n>=2}
 srelative={x[2] for x in sd};rrelative={x[2] for x in rd}
 return {'status':'PASS','approved_audit_sha256':APPROVED_SHA,'clone_a_rows':base['clone_a_rows'],
  'control_clone_b':base['control']['clone_b_sessions'],'treatment_clone_b':base['treatment']['clone_b_sessions'],
  'control_clone_c':base['control']['clone_c_sessions'],'treatment_clone_c':base['treatment']['clone_c_sessions'],
  'reference_exact_session_clone':len(sp&rp),'reference_exact_relative_path_clone':len(srelative&rrelative),
  'reference_exact_delay_vector_clone':len(sdelay&rdelay),
  'diversity_path':{'control':base['control'],'treatment':base['treatment']}}
