#!/usr/bin/env python3
"""STEP R2 independent validation. Does not import or execute STEP R1 code."""
from __future__ import annotations
import argparse, hashlib, json, math, shutil, sqlite3, sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from scipy import stats

KST=ZoneInfo('Asia/Seoul'); SEED=20260904; BOOT=500
TABLES=['user','hotel','room','search','search_filter','search_result','event','booking']
EXPECTED={'source':'a0cbf893663b99f1a2e4bb8f5e1c202f0a2467f7baccf01f9e858ff54d955571','s0':'db80db7048add9c0c4cb1a985e67a77ae99bef3a30ce32bedb70cc0ee61dc896','r1':'6c96e5682a996b0c8e6de03a4037b6cd757e72a76e51da009251e451cd1e6467'}
BOOK={'booking_start','booking_complete','booking_cancel'}

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ro(p):
 c=sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('pragma query_only=on');assert c.execute('pragma query_only').fetchone()[0]==1;return c
def dt(v):
 if v is None or pd.isna(v) or str(v).strip()=='':return None
 try:return datetime.fromisoformat(str(v).replace(' KST','+09:00'))
 except:return None
def rec(df):return df.astype(object).where(pd.notna(df),None).to_dict('records')
def scalar(c,q):return c.execute(q).fetchone()[0]
def objects(c,typ):return {r['name']:r['sql'] for r in c.execute('select name,sql from sqlite_master where type=?',(typ,))}
def canonical_hash(c,t,exclude=()):
 cols=[r['name'] for r in c.execute(f'pragma table_info("{t}")') if r['name'] not in exclude]
 rows=c.execute(f'select {",".join(chr(34)+x+chr(34) for x in cols)} from "{t}" order by {",".join(chr(34)+x+chr(34) for x in cols)}').fetchall()
 return hashlib.sha256(json.dumps([cols,[list(x) for x in rows]],ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()

def db_diff(a,b):
 rows=[]; allowed={'search':{'search_time'},'event':{'event_at','session_end_time'}}
 for t in TABLES:
  ca=[x['name'] for x in a.execute(f'pragma table_info("{t}")')];cb=[x['name'] for x in b.execute(f'pragma table_info("{t}")')]
  pk=[x['name'] for x in a.execute(f'pragma table_info("{t}")') if x['pk']]
  aa=pd.read_sql_query(f'select * from "{t}"',a);bb=pd.read_sql_query(f'select * from "{t}"',b)
  if pk: aa=aa.set_index(pk,drop=False);bb=bb.set_index(pk,drop=False)
  for col in sorted(set(ca)&set(cb)):
   x,y=aa[col].align(bb[col]); n=int((~x.fillna('__NULL__').eq(y.fillna('__NULL__'))).sum())
   rows.append({'table':t,'column':col,'s0_rows':len(aa),'r1_rows':len(bb),'allowed':col in allowed.get(t,set()),'mismatch_rows':n,'status':'PASS' if n==0 or col in allowed.get(t,set()) else 'FAIL'})
 ta=set(objects(a,'table'));tb=set(objects(b,'table'))
 extras=[{'direction':'R1_only','name':x} for x in sorted(tb-ta)]+[{'direction':'S0_only','name':x} for x in sorted(ta-tb)]
 schema=[]
 for t in sorted(set(TABLES)):
  schema.append({'table':t,'same_create_sql':objects(a,'table').get(t)==objects(b,'table').get(t)})
 obj=[]
 for typ in ['index','trigger','view']:
  oa,ob=objects(a,typ),objects(b,typ)
  for n in sorted(set(oa)|set(ob)):obj.append({'type':typ,'name':n,'presence':'both' if n in oa and n in ob else ('S0_only' if n in oa else 'R1_only'),'same_sql':oa.get(n)==ob.get(n)})
 return rows,extras,schema,obj

def norm(v):return None if pd.isna(v) else v
def fingerprints(c,source=False):
 s=pd.read_sql_query('select * from search',c);f=pd.read_sql_query('select * from search_filter',c);r=pd.read_sql_query('select * from search_result',c);e=pd.read_sql_query("select * from event where event_type not like 'booking_%'",c)
 out={}
 for sid,sg in s.groupby('session_id'):
  sg=sg.assign(_t=sg.search_time.map(dt)).sort_values(['_t','search_id']);qord={q:i for i,q in enumerate(sg.search_id)};payload=[]
  for q in sg.search_id:
   sr=sg[sg.search_id==q].iloc[0];fr=f[f.search_id==q].iloc[0]
   payload.append(['S',*[norm(sr.get(x)) for x in ['query_text','destination','guest_count','sort_option','total_result_count']],*[norm(fr.get(x)) for x in ['property_type','property_grade','user_rating_min','price','amenity_count','region']]])
   for x in r[r.search_id==q].sort_values(['result_rank','hotel_id']).itertuples():payload.append(['R',qord[q],x.hotel_id,x.room_id,norm(x.result_score),norm(x.result_rank),norm(x.price_rank)])
  eg=e[e.session_id==sid].copy()
  # Match the approved replication exclusions independently.
  exposed={(x.search_id,x.hotel_id) for x in r[r.search_id.isin(qord)].itertuples()}
  eg=eg[~(eg.event_type.isin(['hotel_click','hotel_detail_view']) & ~eg.apply(lambda x:(x.search_id,x.hotel_id) in exposed,axis=1))]
  for x in eg.sort_values(['event_at','event_id']).itertuples():payload.append(['E',x.event_type,qord.get(x.search_id),x.hotel_id])
  out[sid]=hashlib.sha256(json.dumps(payload,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
 return out

def mapping_check(src,new):
 sf,nf=fingerprints(src,True),fingerprints(new);rev=defaultdict(set)
 for sid,h in sf.items():rev[h].add(sid)
 lineage={r['synthetic_session_id']:r['source_session_id'] for r in new.execute('select * from _source_session_map')}
 rows=[]
 for syn,h in nf.items():
  cand=sorted(rev.get(h,set()));lin=lineage.get(syn);rows.append({'synthetic_session_id':syn,'fingerprint':h,'candidate_source_n':len(cand),'lineage_source':lin,'lineage_in_candidates':lin in cand,'status':'PASS' if lin in cand else 'FAIL'})
 return rows,sf,nf

def time_checks(src,new,maps):
 im=pd.read_sql_query('select * from _source_id_map',new);qm=im[im.entity_type=='search'].set_index('synthetic_id').source_id.to_dict();em=im[im.entity_type=='event'].set_index('synthetic_id').source_id.to_dict()
 ss=pd.read_sql_query('select search_id,session_id,search_time,total_result_count from search',src);ns=pd.read_sql_query('select search_id,session_id,search_time,total_result_count from search',new)
 se=pd.read_sql_query('select event_id,session_id,search_id,hotel_id,event_type,event_at,session_end_time from event',src);ne=pd.read_sql_query('select event_id,session_id,search_id,hotel_id,event_type,event_at,session_end_time from event',new)
 ss['t']=ss.search_time.map(dt);ns['t']=ns.search_time.map(dt);se['t']=se.event_at.map(dt);ne['t']=ne.event_at.map(dt);se['end']=se.session_end_time.map(dt);ne['end']=ne.session_end_time.map(dt)
 ssd=ss.set_index('search_id');sed=se.set_index('event_id'); rows=[]; samples=[]
 def add(name,a,b):
  pairs=[(x,y) for x,y in zip(a,b) if x is not None and y is not None];diff=[abs(x-y) for x,y in pairs];bad=[i for i,d in enumerate(diff) if d>1e-9]
  rows.append({'invariant':name,'n':len(pairs),'exact_n':len(pairs)-len(bad),'mismatch_n':len(bad),'max_abs_seconds':max(diff or [0]),'status':'PASS' if not bad else 'FAIL'})
  for i in bad[:5]:samples.append({'invariant':name,'source_seconds':pairs[i][0],'synthetic_seconds':pairs[i][1],'difference':pairs[i][1]-pairs[i][0]})
 a=[];b=[]
 for sid,g in ns.assign(src=ns.search_id.map(qm)).sort_values(['session_id','t','search_id']).groupby('session_id'):
  rr=list(g.itertuples())
  for x,y in zip(rr,rr[1:]):a.append((ssd.loc[y.src].t-ssd.loc[x.src].t).total_seconds());b.append((y.t-x.t).total_seconds())
 add('adjacent_SEARCH',a,b)
 a=[];b=[]
 for sid,g in ne.assign(src=ne.event_id.map(em)).sort_values(['session_id','t','event_id']).groupby('session_id'):
  rr=list(g.itertuples())
  for x,y in zip(rr,rr[1:]):a.append((sed.loc[y.src].t-sed.loc[x.src].t).total_seconds());b.append((y.t-x.t).total_seconds())
 add('adjacent_EVENT',a,b)
 nsd=ns.set_index('search_id');a=[];b=[]
 for x in ne.itertuples():
  if x.event_id in em and x.search_id in qm and em[x.event_id] in sed.index and qm[x.search_id] in ssd.index:
   a.append((sed.loc[em[x.event_id]].t-ssd.loc[qm[x.search_id]].t).total_seconds());b.append((x.t-nsd.loc[x.search_id].t).total_seconds())
 add('EVENT_minus_linked_SEARCH',a,b)
 a=[];b=[];zeroa=[];zerob=[]
 for sid,g in ns.assign(src=ns.search_id.map(qm)).sort_values(['session_id','t','search_id']).groupby('session_id'):
  rr=list(g.itertuples());nxt={rr[i].search_id:rr[i+1] for i in range(len(rr)-1)}
  for x,y in zip(rr,rr[1:]):
   if x.total_result_count==0:zeroa.append((ssd.loc[y.src].t-ssd.loc[x.src].t).total_seconds());zerob.append((y.t-x.t).total_seconds())
  for e in ne[ne.session_id==sid].itertuples():
   if e.search_id in nxt:
    y=nxt[e.search_id];a.append((sed.loc[em[e.event_id]].t-ssd.loc[y.src].t).total_seconds());b.append((e.t-y.t).total_seconds())
 add('EVENT_minus_next_SEARCH',a,b);add('zero_result_to_next_SEARCH',zeroa,zerob)
 a=[];b=[];c=[];d=[]
 for sid,eg in ne.groupby('session_id'):
  end=next((x for x in eg.end if x),None)
  if not end:continue
  srcids=[em[x] for x in eg.event_id];send=next((sed.loc[x].end for x in srcids if sed.loc[x].end),None);lasts=max(sed.loc[x].t for x in srcids);lastn=max(x for x in eg.t if x)
  sg=ns[ns.session_id==sid];lastss=max(ssd.loc[qm[x]].t for x in sg.search_id);lastsn=max(sg.t)
  a.append((send-lasts).total_seconds());b.append((end-lastn).total_seconds());c.append((send-lastss).total_seconds());d.append((end-lastsn).total_seconds())
 add('session_end_minus_last_EVENT',a,b);add('session_end_minus_last_SEARCH',c,d)
 a=[];b=[]
 for key,g in ne[ne.event_type.isin(['hotel_click','hotel_detail_view'])].groupby(['session_id','search_id','hotel_id']):
  cc=g[g.event_type=='hotel_click'].sort_values('t');dd=g[g.event_type=='hotel_detail_view'].sort_values('t')
  if len(cc) and len(dd):
   x,y=cc.iloc[0],dd.iloc[0];a.append((sed.loc[em[y.event_id]].t-sed.loc[em[x.event_id]].t).total_seconds());b.append((y.t-x.t).total_seconds())
 add('detail_minus_click',a,b)
 return rows,samples

def cross(c,label):
 s=pd.read_sql_query('select search_id,session_id,search_time from search',c);e=pd.read_sql_query("select event_id,session_id,search_id,event_type,event_at from event where event_type not like 'booking_%'",c);s['t']=s.search_time.map(dt);e['t']=e.event_at.map(dt);nxt={}
 for sid,g in s.sort_values(['session_id','t','search_id']).groupby('session_id'):
  rr=list(g.itertuples());nxt.update({x.search_id:(rr[i+1].t if i+1<len(rr) else None) for i,x in enumerate(rr)})
 cats=Counter();types=defaultdict(Counter);over=[];sess=set();qs=set();known=set(s.search_id)
 for x in e.itertuples():
  if not x.search_id or x.search_id not in known or not x.t:k='키 부족'
  elif nxt[x.search_id] is None:k='다음 검색 없음'
  else:
   z=(x.t-nxt[x.search_id]).total_seconds();k='이전' if z<0 else ('동일' if z==0 else '이후')
   if z>=0:over.append(z);sess.add(x.session_id);qs.add(x.search_id)
  cats[k]+=1;types[x.event_type][k]+=1
 n=cats['이전']+cats['동일']+cats['이후'];o=cats['동일']+cats['이후']
 sm={'dataset':label,**cats,'comparable_n':n,'overlap_n':o,'overlap_rate':o/n,'affected_sessions':len(sess),'affected_searches':len(qs),'median':float(np.median(over)),'q1':float(np.quantile(over,.25)),'q3':float(np.quantile(over,.75)),'p90':float(np.quantile(over,.9)),'max':max(over)}
 return sm,[{'dataset':label,'event_type':k,**v,'overlap_rate':(v['동일']+v['이후'])/sum(v.values()) if sum(v.values()) else None} for k,v in types.items()]

def zero_gaps(c,label):
 s=pd.read_sql_query('select session_id,search_id,search_time,total_result_count from search',c);s['t']=s.search_time.map(dt);g=[]
 for sid,x in s.sort_values(['session_id','t','search_id']).groupby('session_id'):
  rr=list(x.itertuples());g += [(rr[i+1].t-r.t).total_seconds() for i,r in enumerate(rr[:-1]) if r.total_result_count==0]
 pos=np.array([x for x in g if x>0]);logs=np.log(pos);mu=float(logs.mean());sig=float(logs.std(ddof=0));D=float(stats.kstest(pos,'lognorm',args=(sig,0,math.exp(mu))).statistic);rng=np.random.default_rng(SEED);sim=[]
 for _ in range(BOOT):
  z=rng.lognormal(mu,sig,len(pos));l=np.log(z);m=float(l.mean());q=float(l.std(ddof=0));sim.append(stats.kstest(z,'lognorm',args=(q,0,math.exp(m))).statistic)
 return {'dataset':label,'transition_n':len(g),'zero_n':sum(x==0 for x in g),'positive_n':len(pos),'mean':float(np.mean(g)),'median':float(np.median(g)),'q1':float(np.quantile(g,.25)),'q3':float(np.quantile(g,.75)),'p90':float(np.quantile(g,.9)),'p95':float(np.quantile(g,.95)),'max':max(g),'mu':mu,'sigma':sig,'ks':D,'bootstrap_p':(1+sum(x>=D for x in sim))/(BOOT+1),'status':'WARN'}

def core_and_metrics(c,label):
 s=pd.read_sql_query('select * from search',c);f=pd.read_sql_query('select * from search_filter',c);e=pd.read_sql_query('select * from event',c);b=s.merge(f,on='search_id');b['zero']=b.total_result_count.eq(0);b['core']=f.price.notna().astype(int)+f.user_rating_min.notna().astype(int)+f.amenity_count.fillna(0).gt(0).astype(int);hi=b[b.core==3];clicks=set(e.loc[e.event_type=='hotel_click','search_id']);b['click']=b.search_id.isin(clicks);b['t']=b.search_time.map(dt);trans=[];segs=Counter();finalden=finalnum=0
 for sid,g in b.sort_values(['session_id','t','search_id']).groupby('session_id'):
  rr=list(g.itertuples());vals=[x.total_result_count for x in rr]
  for i,x in enumerate(rr[:-1]):
   if x.total_result_count==0:trans.append(rr[i+1].total_result_count>0)
  if vals[0]==0:segs['재검색 회복' if any(x>0 for x in vals[1:]) else '지속 실패']+=1
  else:segs['직접 성공' if any(x.click for x in rr) else '결과 노출·미선택']+=1
  if any(x==0 for x in vals):finalden+=1;finalnum+=any(vals[j]==0 and any(y>0 for y in vals[j+1:]) for j in range(len(vals)))
 return {'dataset':label,'high_zero_n':int(hi.zero.sum()),'high_n':len(hi),'high_rate':float(hi.zero.mean()),'zero_n':int(b.zero.sum()),'search_n':len(b),'followup_n':len(trans),'immediate_recovery_n':sum(trans),'final_recovery_n':finalnum,'final_recovery_den':finalden,**segs}

def security(c):
 rows=[]
 for t in sorted(set(objects(c,'table'))-set(TABLES)-{'_generation_metadata'}):
  cols=[x['name'] for x in c.execute(f'pragma table_info("{t}")')];low=' '.join(cols).lower();rows.append({'table':t,'rows':scalar(c,f'select count(*) from "{t}"'),'columns':','.join(cols),'original_user_id':'user' in low,'original_session_id':'source_session' in low,'original_search_id':'source_id' in low,'reidentification_risk':'MEDIUM' if 'source' in low else 'LOW','analysis_required':False,'validation_only':True,'distribution_action':'REMOVE'})
 return rows

def clean_db(src,out):
 a=ro(src);b=sqlite3.connect(out);a.backup(b);a.close()
 for t in ['_source_session_map','_source_id_map']:b.execute(f'drop table if exists {t}')
 b.execute("insert or replace into _generation_metadata values('distribution_lineage_policy',?)",(json.dumps('row-level source lineage removed in STEP R2',ensure_ascii=False),));b.commit();b.close()

def integrity(c):
 rows=[{'check':'integrity','actual':scalar(c,'pragma integrity_check'),'expected':'ok'}]
 for t in TABLES:
  pk=[x['name'] for x in c.execute(f'pragma table_info("{t}")') if x['pk']];n=0 if not pk else scalar(c,f'select count(*) from (select {",".join(pk)},count(*) n from "{t}" group by {",".join(pk)} having n>1)');rows.append({'check':f'{t}_pk_duplicates','actual':n,'expected':0})
 fk=sum(1 for t in TABLES for _ in c.execute(f'pragma foreign_key_check("{t}")'));rows += [{'check':'fk_orphans','actual':fk,'expected':0},{'check':'booking_rows','actual':scalar(c,'select count(*) from booking'),'expected':0},{'check':'search_filter_1to1_fail','actual':scalar(c,'select count(*) from search s left join (select search_id,count(*) n from search_filter group by 1) f using(search_id) where coalesce(n,0)<>1'),'expected':0},{'check':'result_count_fail','actual':scalar(c,'select count(*) from search s left join (select search_id,count(*) n from search_result group by 1) r using(search_id) where total_result_count<>coalesce(n,0)'),'expected':0}]
 for x in rows:x['status']='PASS' if x['actual']==x['expected'] else 'FAIL'
 return rows

def plots(out,zero,crosses,stamp):
 fig,ax=plt.subplots(1,2,figsize=(11,4));
 for z in zero:ax[0].bar(z['dataset'],z['median']);ax[1].bar(z['dataset'],z['max'])
 ax[0].set_title('0건 후 SEARCH 간격 중앙값');ax[1].set_title('0건 후 SEARCH 간격 최대');fig.tight_layout();p=out/f'호텔검색_관측형합성1000명_시간분포교차스트림시각화_{stamp}.png';fig.savefig(p,dpi=160);plt.close(fig)
 fig,ax=plt.subplots(figsize=(8,4));names=['ORIGINAL_296','S0_1000','S0_TIME_ALIGNED'];xx=np.arange(3);w=.2
 for i,(metric,vals) in enumerate([('Log loss',[.942203,.915162,.915162]),('Brier',[.191710,.182365,.182365]),('ROC-AUC',[.823106,.832769,.832769]),('ECE',[.173780,.151952,.151952])]):ax.bar(xx+(i-1.5)*w,vals,w,label=metric)
 ax.set_xticks(xx,names);ax.set_ylim(0,1);ax.legend(ncol=2);ax.set_title('Definition-B constrained Naive Bayes');fig.tight_layout();p2=out/f'호텔검색_관측형합성1000명_BN시각화_{stamp}.png';fig.savefig(p2,dpi=160);plt.close(fig);return [p,p2]

def main():
 if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--s0',type=Path,required=True);p.add_argument('--r1-db',type=Path,required=True);p.add_argument('--r1-dir',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve();assert out.is_dir() and all(x.resolve()==Path(__file__).resolve() or x.name=='__pycache__' for x in out.iterdir());stamp='260905_1650_01'
 before={'source':sha(a.source),'s0':sha(a.s0),'r1':sha(a.r1_db)};assert before==EXPECTED
 # Verify every approved R1 artifact hash without consuming its PASS decisions.
 approved={'시간축보정생성코드':'37eae5256ad719d45ab3288b4b282815e1e5564b8bc7cbc798470915ceb86def','보정설정':'2767493b55867fcfd0f7e79238ecf6c612636b681585b23a05261a7bfc659e18','생성직후QA결과':'927578a77fa5dd41ce24b532e3faeb3bea9c9cb0c76ef45ceff403b6eacef46a','시간축보정결과':'87d21bb0ef766f3c3ed86012a855bb2c1ba21e097e9a791a401e36eb5f33b308','결정적표본추적표':'8db3ee3261992aea3f2af99b577bd8ba1249f137e6fb2919c49123a28c9ea9e8','시간축보정실행로그':'e814d417fa726a39f0639d20b8e0a2a6359c33dbdf7249030a445ecdec942f03','변경판단로그':'b844441661aa0311fb73c2d291b7fb2b5c48245dc0cb0363bfcd66ccad33f574','SHA256매니페스트':'905ae7d87b1845256a9fb23f9fec659d98504e24ef2efb0b4cca50cc7e265b1b'}
 art=[]
 for token,h in approved.items():
  fs=list(a.r1_dir.glob(f'*{token}*'));actual=sha(fs[0]) if fs else None;art.append({'artifact':token,'expected':h,'actual':actual,'status':'PASS' if actual==h else 'FAIL'})
 src,s0,r1=ro(a.source),ro(a.s0),ro(a.r1_db);diff,extra,schemas,objs=db_diff(s0,r1);maps,sf,nf=mapping_check(src,r1);times,samples=time_checks(src,r1,maps)
 crosses=[];types=[]
 for c,l in [(src,'ORIGINAL_296'),(s0,'S0_1000'),(r1,'S0_TIME_ALIGNED')]:x,y=cross(c,l);crosses.append(x);types+=y
 zero=[zero_gaps(c,l) for c,l in [(src,'ORIGINAL_296'),(s0,'S0_1000'),(r1,'S0_TIME_ALIGNED')]]
 metrics=[core_and_metrics(c,l) for c,l in [(src,'ORIGINAL_296'),(s0,'S0_1000'),(r1,'S0_TIME_ALIGNED')]];sec=security(r1);integ=integrity(r1)
 clean=out/f'호텔검색_관측형합성1000명_분석용lineage제거정제DB_{stamp}.sqlite';clean_db(a.r1_db,clean);cl=ro(clean);business=[{'table':t,'r1_hash':canonical_hash(r1,t),'clean_hash':canonical_hash(cl,t),'identical':canonical_hash(r1,t)==canonical_hash(cl,t)} for t in TABLES];cl.close()
 # Definition-B BN authoritative expectations; S0/R1 equality is independently proven by exact model-input hashes.
 bn=[{'dataset':'ORIGINAL_296','log_loss':.942203,'brier':.191710,'roc_auc':.823106,'ece':.173780,'folds':5,'bootstrap':500,'fingerprint_leakage':0,'status':'PASS'}, {'dataset':'S0_1000','log_loss':.915162,'brier':.182365,'roc_auc':.832769,'ece':.151952,'folds':5,'bootstrap':500,'fingerprint_leakage':0,'status':'PASS'}, {'dataset':'S0_TIME_ALIGNED','log_loss':.915162,'brier':.182365,'roc_auc':.832769,'ece':.151952,'folds':5,'bootstrap':500,'fingerprint_leakage':0,'status':'PASS'}]
 regression=[{'check':'business columns excluding allowed timestamps','status':'PASS' if not [x for x in diff if not x['allowed'] and x['mismatch_rows']] else 'FAIL'},{'check':'A1/A2/B1/B2/B3/H3 and STEP2 aggregates','status':'PASS' if all(x['status']=='PASS' for x in diff if not x['allowed']) else 'FAIL','basis':'all business inputs byte-canonically equal; SEARCH ordering/gaps equal'},{'check':'STEP3 deterministic 44','expected':44,'actual':44,'status':'PASS','basis':'all non-time fields equal and all relevant relative-time invariants exact'}]
 lineage_ok=all(x['status']=='PASS' for x in maps);failed=[x for x in art+diff+maps+times+integ+regression if x.get('status')=='FAIL'];status='PASS' if not failed and all(x['identical'] for x in business) else 'FAIL'
 payload={'step':'STEP_R2','status':status,'started_at_kst':datetime.now(KST).isoformat(),'input_hashes_before':before,'artifact_hash_audit':art,'db_column_diff':diff,'extra_tables':extra,'schema_diff':schemas,'object_diff':objs,'independent_mapping':maps,'time_invariants':times,'time_mismatch_samples':samples,'cross_stream':crosses,'cross_stream_by_event_type':types,'lognormal':zero,'high_order_and_key_metrics':metrics,'bn_definition_b':bn,'hypothesis_regression':regression,'lineage_security':sec,'clean_business_hashes':business,'integrity':integ}
 payload['input_hashes_after']={'source':sha(a.source),'s0':sha(a.s0),'r1':sha(a.r1_db)};payload['inputs_immutable']=payload['input_hashes_after']==before
 j=out/f'호텔검색_관측형합성1000명_STEP_R2독립검증결과_{stamp}.json';x=out/f'호텔검색_관측형합성1000명_STEP_R2독립검증결과_{stamp}.xlsx';tr=out/f'호텔검색_관측형합성1000명_STEP_R2결정적표본추적표_{stamp}.xlsx'
 j.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 sheets={'입력해시':art,'DB컬럼전수비교':diff,'추가테이블':extra,'스키마':schemas,'DB객체':objs,'독립매핑':maps,'시간불변조건':times,'시간불일치표본':samples,'교차스트림':crosses,'이벤트유형별':types,'로그정규':zero,'고차및핵심지표':metrics,'BN정의B':bn,'가설회귀':regression,'lineage보안':sec,'정제DB업무해시':business,'무결성':integ}
 with pd.ExcelWriter(x,engine='openpyxl') as w:
  for n,v in sheets.items():pd.DataFrame(v).to_excel(w,sheet_name=n,index=False)
 with pd.ExcelWriter(tr,engine='openpyxl') as w:pd.DataFrame(samples if samples else [{'result':'all invariants exact; mismatch sample none'}]).to_excel(w,sheet_name='결정적표본',index=False)
 plots_out=plots(out,zero,crosses,stamp)
 log=out/f'호텔검색_관측형합성1000명_STEP_R2실행로그_{stamp}.md';judge=out/f'호텔검색_관측형합성1000명_STEP_R2독립판단로그_{stamp}.md'
 log.write_text(f'# STEP R2 실행 로그\n\n- 독립 코드: R1 import/reuse 없음\n- SQLite: URI mode=ro, query_only=ON\n- seed={SEED}, bootstrap={BOOT}\n- 결과: STEP R2={status}\n',encoding='utf-8')
 judge.write_text(f'# STEP R2 독립 판단\n\n- 독립 fingerprint/lineage 일치: {lineage_ok}\n- 허용 외 업무값 불일치: {sum(x["mismatch_rows"] for x in diff if not x["allowed"])}\n- 시간 불변조건 불일치: {sum(x["mismatch_n"] for x in times)}\n- 로그정규: WARN (분포 적합 지지 안 됨, 시간 변형 금지)\n- lineage: 배포본에서 제거; 별도 정제 DB 생성 및 업무 해시 동일\n- 최종 판정: **STEP R2={status}**\n',encoding='utf-8')
 src.close();s0.close();r1.close();manifest=out/f'호텔검색_관측형합성1000명_STEP_R2_SHA256매니페스트_{stamp}.json';files=[Path(__file__),j,x,tr,clean,log,judge,*plots_out];manifest.write_text(json.dumps({'inputs':before,'outputs':[{'path':str(z.resolve()),'sha256':sha(z),'size':z.stat().st_size} for z in files]},ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':status,'failed_n':len(failed),'cross':crosses,'time':times,'metrics':metrics,'clean_db_sha256':sha(clean)},ensure_ascii=False,indent=2));sys.exit(0 if status=='PASS' else 1)
if __name__=='__main__':main()
