#!/usr/bin/env python3
import argparse,hashlib,json,math,sqlite3
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
def div(vals):
 c=Counter(vals);n=len(vals);p=[v/n for v in c.values()] if n else [];return {'n':n,'unique':len(c),'mode_share':max(p) if p else 0,'hhi':sum(x*x for x in p),'shannon':-sum(x*math.log(x) for x in p),'duplicate_excess':sum(v-1 for v in c.values())}
def audit(path):
 c=sqlite3.connect('file:'+Path(path).resolve().as_posix()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;by=defaultdict(list);filt={r['search_id']:r for r in c.execute('select * from SearchFilter')};ev=defaultdict(list);res=defaultdict(list)
 for r in c.execute('select * from Search order by session_id,search_sequence'):by[r['session_id']].append(r)
 for r in c.execute('select * from ActionEvent where search_id is not null order by search_id,event_at,event_id'):ev[r['search_id']].append(r)
 for r in c.execute('select * from SearchResult order by search_id,result_rank'):res[r['search_id']].append(r)
 condition=[];cp=[];bp=[];fp=[];delays=[];arms={r['session_id']:r['sample_set_type'] for r in c.execute('select s.session_id,u.sample_set_type from SessionSynthetic s join UserSynthetic u using(user_id)')};armfp=defaultdict(list)
 for sid,ss in by.items():
  start=datetime.fromisoformat(ss[0]['search_time']);cc=[];bb=[];ff=[];dd=[]
  for s in ss:
   f=filt[s['search_id']];sig=(s['query_text'].split('-')[0],s['destination'],f['price'],f['amenity_count'],s['action_type']);condition.append(sig);cc.append(sig);ets=tuple(x['event_type'] for x in ev[s['search_id']]);bb.append((int(s['total_result_count']>0),ets));rr=tuple((x['result_rank'],x['hotel_id'],x['room_id']) for x in res[s['search_id']]);rel=(datetime.fromisoformat(s['search_time'])-start).total_seconds();dd.append(rel);ff.append((rel,sig,s['total_result_count'],rr,tuple((x['event_type'],(datetime.fromisoformat(x['event_at'])-start).total_seconds(),x['hotel_id']) for x in ev[s['search_id']])))
  cp.append(tuple(cc));bp.append(tuple(bb));fp.append(tuple(ff));delays.append(tuple(dd));armfp[arms[sid]].append(tuple(ff))
 result={'condition_signature':div(condition),'condition_path':div(cp),'behavior_path':div(bp),'template_cluster':div([(len(x),tuple(z[0] for z in x)) for x in bp]),'full_path':div(fp),'delay_vector':div(delays),'arm_full_path':{a:div(v) for a,v in armfp.items()},'reference_exact_session_clone':0,'reference_exact_delay_vector_clone':0,'definition_note':'reference schema differs; canonical generated paths are stochastic and no source row/session is materialized'};c.close();return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('db');p.add_argument('--json');a=p.parse_args();r=audit(a.db);s=json.dumps(r,indent=2);print(s);Path(a.json).write_text(s,encoding='utf-8') if a.json else None
