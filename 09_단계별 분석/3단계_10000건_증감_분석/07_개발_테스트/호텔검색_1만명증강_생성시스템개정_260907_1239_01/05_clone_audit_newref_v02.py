#!/usr/bin/env python3
"""Clone audit v02. Clone identity excludes IDs/absolute time/lineage, never business values."""
import argparse,collections,hashlib,json,math,sqlite3

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def session_records(db):
 c=sqlite3.connect(db); c.row_factory=sqlite3.Row
 sessions=c.execute("""select s.session_id,u.sample_set_type arm,s.outcome_segment
 from SessionSynthetic s join UserSynthetic u on u.user_id=s.user_id""").fetchall()
 out=[]
 for ss in sessions:
  searches=c.execute("""select search_id,search_sequence,search_time,total_result_count,
   query_text,destination,action_type from Search where session_id=? order by search_sequence""",
   (ss['session_id'],)).fetchall()
  if not searches: continue
  t0=searches[0]['search_time']; import datetime
  origin=datetime.datetime.fromisoformat(t0)
  business=[]; exact=[]; abstract=[]
  for q in searches:
   qt=datetime.datetime.fromisoformat(q['search_time']); rel=(qt-origin).total_seconds()
   filt=c.execute("""select price,amenity_count,region,property_type,property_grade
    from SearchFilter where search_id=? order by search_filter_id""",(q['search_id'],)).fetchall()
   results=c.execute("""select hotel_id,room_id,result_rank from SearchResult
    where search_id=? order by result_rank,search_result_id""",(q['search_id'],)).fetchall()
   events=c.execute("""select event_type,hotel_id,event_at from ActionEvent
    where search_id=? order by event_at,event_id""",(q['search_id'],)).fetchall()
   ev=[(e['event_type'],e['hotel_id'],round((datetime.datetime.fromisoformat(e['event_at'])-qt).total_seconds())) for e in events]
   row=(q['search_sequence'],q['total_result_count'],q['query_text'],q['destination'],q['action_type'],
        [tuple(x) for x in filt],[tuple(x) for x in results],ev)
   business.append(row+(round(rel/5)*5,))
   exact.append(row+(rel,))
   abstract.append(('ZERO' if q['total_result_count']==0 else 'POSITIVE',q['action_type']))
  out.append({'session_id':ss['session_id'],'arm':ss['arm'],'clone_b':digest((business,ss['outcome_segment'])),
   'clone_c':digest((exact,ss['outcome_segment'])),'diversity_path':digest((abstract,ss['outcome_segment']))})
 c.close(); return out

def repeated_count(rows,key,arm=None):
 xs=[r[key] for r in rows if arm is None or r['arm']==arm]; f=collections.Counter(xs)
 return sum(v for v in f.values() if v>1),sum(1 for v in f.values() if v>1),f

def audit(db):
 rows=session_records(db); result={'database':str(db),'sessions':len(rows),
  'definitions':{'CLONE_A':'duplicate stored rows including identifiers','CLONE_B':'all business values equal after excluding IDs, absolute timestamps, lineage; relative delays bucketed to 5s','CLONE_C':'CLONE-B with exact relative delays','DIVERSITY_PATH':'abstract outcome/action token repetition; allowed'}}
 c=sqlite3.connect(db); a=0
 for (t,) in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"):
  cols=[x[1] for x in c.execute('pragma table_info("'+t.replace('"','""')+'")')]
  if cols:
   names=','.join('"'+x.replace('"','""')+'"' for x in cols)
   q='select coalesce(sum(n-1),0) from (select count(*) n from "'+t.replace('"','""')+'" group by '+names+' having count(*)>1)'
   a+=c.execute(q).fetchone()[0]
 c.close();result['clone_a_rows']=a
 for arm in ('control','treatment'):
  b,_,_=repeated_count(rows,'clone_b',arm); cc,_,_=repeated_count(rows,'clone_c',arm); d,groups,f=repeated_count(rows,'diversity_path',arm)
  n=sum(r['arm']==arm for r in rows); probs=[v/n for v in f.values()] if n else []
  result[arm]={'clone_b_sessions':b,'clone_c_sessions':cc,'diversity_path_repeated_sessions':d,
   'diversity_unique':len(f),'diversity_top_share':max(probs,default=0),'diversity_hhi':sum(x*x for x in probs),
   'diversity_shannon':-sum(x*math.log(x) for x in probs if x)}
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('database');p.add_argument('--output');a=p.parse_args();r=audit(a.database);s=json.dumps(r,ensure_ascii=False,indent=2)
 if a.output:
  from pathlib import Path
  q=Path(a.output)
  if q.exists():raise FileExistsError(q)
  q.write_text(s,encoding='utf8')
 print(s)
