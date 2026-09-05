#!/usr/bin/env python3
"""Generate and QA only the S0 observed-like 1,000-user pilot."""
from __future__ import annotations
import argparse, hashlib, json, platform, sqlite3, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from openpyxl import Workbook
from docx import Document

KST=ZoneInfo("Asia/Seoul")
TABLES=["user","hotel","room","search","search_filter","search_result","event","booking"]
BEHAVIOR=["user","search","search_filter","search_result","event"]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def dt(v):
 s=str(v).replace(' KST','+09:00'); return datetime.fromisoformat(s)
def ts(v): return v.astimezone(KST).strftime('%Y-%m-%d %H:%M:%S KST')
def ro(db):
 c=sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True); c.row_factory=sqlite3.Row;c.execute('pragma query_only=on');return c
def args():
 p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);return p.parse_args()
def create_schema(src,dst):
 for t in TABLES:
  sql=src.execute("select sql from sqlite_master where type='table' and name=?",(t,)).fetchone()[0]
  dst.execute(sql)
 dst.execute('create table _generation_metadata(key text primary key,value text)')
def insert_rows(c,t,rows):
 if not rows:return
 cols=list(rows[0]);q=','.join('?'*len(cols))
 c.executemany(f'insert into "{t}"({",".join(cols)}) values({q})',[[r.get(x) for x in cols] for r in rows])
def build(db,out,cfg):
 rng=np.random.default_rng(cfg['random_seed']); src=ro(db); dst=sqlite3.connect(out)
 create_schema(src,dst)
 for t in ['hotel','room']:
  rows=[dict(x) for x in src.execute(f'select * from {t}')];insert_rows(dst,t,rows)
 searches=pd.read_sql_query('select * from search',src); filters=pd.read_sql_query('select * from search_filter',src)
 results=pd.read_sql_query('select * from search_result',src); events=pd.read_sql_query('select * from event',src)
 sessions=np.array(sorted(searches.session_id.unique()))
 # 소표본 43개 세션의 특정 세션이 과도하게 복제되는 부트스트랩 변동을 줄인다.
 # 세그먼트 목표비율은 강제하지 않고, 각 원본 세션을 균등 횟수 복제한 뒤 나머지만 고정 seed로 추출한다.
 q,r=divmod(cfg['n_sessions'],len(sessions)); chosen=np.tile(sessions,q)
 if r: chosen=np.concatenate([chosen,rng.choice(sessions,size=r,replace=False)])
 chosen=rng.permutation(chosen)
 users=[];out_s=[];out_f=[];out_r=[];out_e=[]
 valid_durations=[]
 for r in searches.itertuples():
  try:
   d=(datetime.fromisoformat(r.checkout_date)-datetime.fromisoformat(r.checkin_date)).days
   if d>0:valid_durations.append(d)
  except:pass
 for i,ss in enumerate(chosen,1):
  uid=f'SYN_U{i:04d}'; sid=f'SYN_S{i:04d}';base=datetime(2027,1,1,tzinfo=KST)+timedelta(days=i//4,minutes=i%4)
  users.append(dict(user_id=uid,user_name=f'합성사용자_{i:06d}',age_group=None,email=f'synthetic{i:06d}@example.invalid',signup_at=ts(base-timedelta(days=30)),data_origin='synthetic_augmentation'))
  sg=searches[searches.session_id==ss].sort_values(['search_time','search_id']); qmap={};fmap={}
  origin=min(dt(x) for x in sg.search_time)
  for j,row in enumerate(sg.itertuples(),1):
   qid=f'SYN_Q{i:04d}_{j:03d}';qmap[row.search_id]=qid
   rec=row._asdict();rec.pop('Index',None);rec['search_id']=qid;rec['session_id']=sid;rec['search_time']=ts(base+(dt(row.search_time)-origin))
   try:
    ci=datetime.fromisoformat(str(row.checkin_date));co=datetime.fromisoformat(str(row.checkout_date))
    if co<=ci:rec['checkout_date']=(ci+timedelta(days=int(rng.choice(valid_durations)))).date().isoformat()
   except:pass
   rec['data_origin']='synthetic_augmentation';out_s.append(rec)
   fr=filters[filters.search_id==row.search_id].iloc[0].to_dict();fid=f'SYN_F{i:04d}_{j:03d}';fmap[fr['search_filter_id']]=fid;fr['search_filter_id']=fid;fr['search_id']=qid;fr['data_origin']='synthetic_augmentation';out_f.append(fr)
   rr=results[results.search_id==row.search_id].sort_values('result_rank')
   for k,x in enumerate(rr.to_dict('records'),1):
    x['search_result_id']=f'SYN_R{i:04d}_{j:03d}_{k:04d}';x['search_id']=qid;x['data_origin']='synthetic_augmentation';out_r.append(x)
  exposed={(qmap.get(r.search_id),r.hotel_id) for r in results[results.search_id.isin(qmap)].itertuples()}
  eg=events[events.session_id==ss].sort_values(['event_at','event_id'])
  eorigin=min(dt(x) for x in eg.event_at)
  for k,row in enumerate(eg.itertuples(),1):
   rec=row._asdict();rec.pop('Index',None); oldq=rec['search_id'];newq=qmap.get(oldq)
   if rec['event_type'] in {'booking_start','booking_complete','booking_cancel'}:continue
   if rec['event_type'] in {'hotel_click','hotel_detail_view'} and (newq,rec['hotel_id']) not in exposed:continue
   rec['event_id']=f'SYN_E{i:04d}_{k:05d}';rec['session_id']=sid;rec['user_id']=uid;rec['search_id']=newq;rec['search_filter_id']=fmap.get(rec['search_filter_id']);rec['event_at']=ts(base+(dt(row.event_at)-eorigin))
   if rec.get('session_end_time'):
    rec['session_end_time']=ts(base+(dt(rec['session_end_time'])-eorigin))
   rec['data_origin']='synthetic_augmentation';out_e.append(rec)
 insert_rows(dst,'user',users);insert_rows(dst,'search',out_s);insert_rows(dst,'search_filter',out_f);insert_rows(dst,'search_result',out_r);insert_rows(dst,'event',out_e)
 meta={'sample_set_type':'observed_like','scenario_id':'S0','random_seed':cfg['random_seed'],'config_version':cfg['config_version'],'generation_version':cfg['approved_generation_version'],'n_users':len(users),'n_sessions':len(set(x['session_id'] for x in out_s))}
 dst.executemany('insert into _generation_metadata values(?,?)',[(k,json.dumps(v,ensure_ascii=False)) for k,v in meta.items()])
 # QA와 다음 단계 재현 쿼리의 안정적 성능을 위한 보조 인덱스다. 생성 로직과 데이터 값은 변경하지 않는다.
 dst.executescript('''
 CREATE INDEX IF NOT EXISTS idx_syn_search_session_time ON search(session_id, search_time, search_id);
 CREATE INDEX IF NOT EXISTS idx_syn_result_search_hotel ON search_result(search_id, hotel_id);
 CREATE INDEX IF NOT EXISTS idx_syn_event_search_hotel_type ON event(search_id, hotel_id, event_type);
 CREATE INDEX IF NOT EXISTS idx_syn_event_session_type ON event(session_id, event_type);
 ''')
 dst.commit();dst.close();src.close()
def qa(db):
 c=ro(db); one=lambda s:c.execute(s).fetchone()[0]; rows={t:one(f'select count(*) from "{t}"') for t in TABLES}
 checks={
 'G1_user_1000':rows['user']==1000,'G1_sessions_1000':one('select count(distinct session_id) from search')==1000,
 'G1_hotel_1000':rows['hotel']==1000,'G1_room_3000':rows['room']==3000,'G1_booking_0':rows['booking']==0,
 'G1_search_filter_1to1':one('select count(*) from search')==one('select count(*) from search_filter')==one('select count(distinct search_id) from search_filter'),
 'G1_result_sum':one('select sum(total_result_count) from search')==rows['search_result'],
 'G1_result_duplicate_0':one('select count(*) from (select search_id,hotel_id,count(*) n from search_result group by 1,2 having n>1)')==0,
 'G1_room_hotel_match':one('select count(*) from search_result r join room x on r.room_id=x.room_id where r.hotel_id<>x.hotel_id')==0,
 'G1_click_exposed':one("select count(*) from event e where event_type='hotel_click' and not exists(select 1 from search_result r where r.search_id=e.search_id and r.hotel_id=e.hotel_id)")==0,
 'G2_invalid_stay_0':one('select count(*) from search where date(checkout_date)<=date(checkin_date)')==0,
 'G2_zero_behavior_0':one("select count(*) from event e join search s on e.search_id=s.search_id where s.total_result_count=0 and e.event_type in ('hotel_impression','hotel_click','hotel_detail_view')")==0,
 'G5_origin':one("select count(*) from search where data_origin<>'synthetic_augmentation'")==0}
 integrity=one('pragma integrity_check');c.close();return rows,checks,integrity
def metrics(db):
 c=ro(db); s=pd.read_sql_query('select * from search',c); f=pd.read_sql_query('select * from search_filter',c);e=pd.read_sql_query('select * from event',c);c.close()
 s['search_time']=pd.to_datetime(s.search_time.str.replace(' KST','+09:00'));o=s.sort_values(['session_id','search_time','search_id']);o['ord']=o.groupby('session_id').cumcount();o['next']=o.groupby('session_id').search_id.shift(-1);o['zero']=o.total_result_count.eq(0)
 zero=o.zero.sum();trans=((o.zero)&o['next'].notna()).sum(); sess=o.groupby('session_id').agg(first=('total_result_count','first'),n=('search_id','size'),anyzero=('zero','max'),anypos=('total_result_count',lambda x:(x>0).any()))
 clicks=set(e.loc[e.event_type.eq('hotel_click'),'search_id']);click_sessions=set(e.loc[e.event_type.eq('hotel_click'),'session_id'])
 seg={'직접 성공':0,'결과 노출·미선택':0,'재검색 회복':0,'지속 실패':0}
 for sid,r in sess.iterrows():
  if r['first']>0:seg['직접 성공' if sid in click_sessions else '결과 노출·미선택']+=1
  else:seg['재검색 회복' if r['anypos'] else '지속 실패']+=1
 return {'searches':len(s),'sessions':len(sess),'zero_searches':int(zero),'zero_rate':zero/len(s),'zero_transitions':int(trans),'followup_zero_rate':trans/zero,'click_rate':len(clicks)/len(s),'segments':seg}
def main():
 a=args();cfg=json.loads(a.config.read_text(encoding='utf-8'));out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
 stamp=cfg['stage2_bundle_run_id'].split('_',1)[1].rsplit('_',1)[0];dbout=out/f'호텔검색_관측형합성1000명_데이터_{stamp}_01.sqlite'
 if dbout.exists():raise FileExistsError(dbout)
 before=sha(a.db);start=datetime.now(KST).isoformat();build(a.db,dbout,cfg);rows,checks,integrity=qa(dbout);met=metrics(dbout)
 payload={'rows':rows,'checks':checks,'integrity':integrity,'metrics':met}
 (out/'qa_payload.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(payload,ensure_ascii=False,indent=2));assert all(checks.values()) and integrity=='ok' and sha(a.db)==before
if __name__=='__main__':main()
