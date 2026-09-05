#!/usr/bin/env python3
"""Independent STEP3 checks; does not import STEP2 calculation code or objects."""
import argparse,hashlib,json,sqlite3,sys
from pathlib import Path
import numpy as np
import pandas as pd
from openpyxl import load_workbook
APPROVED='7d449fab6847730be38fe46ebb6bd6a5b31690cdf38cf4bdbadeaa75edd1ae04'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def ro(p):
 c=sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('pragma query_only=on');assert c.execute('pragma query_only').fetchone()[0]==1;return c
def dt(s):return pd.to_datetime(s.astype(str).str.replace(r'\s+KST$','+09:00',regex=True),errors='coerce',utc=True)
def normalize(df):
 d=df.copy();
 if 'dataset_type' in d:d=d[d.dataset_type.astype(str).isin(['S0_1000','S0_TIME_ALIGNED_1000'])].copy();d['dataset_type']='S0_1000'
 for col in d.select_dtypes(include='object').columns:d[col]=d[col].str.replace('S0_TIME_ALIGNED_1000','S0_1000',regex=False)
 return d.reset_index(drop=True)
def compare_frames(old,new,name):
 old,new=normalize(old),normalize(new);common=[x for x in old.columns if x in new.columns and x!='interpretation'];old=old[common];new=new[common]
 keys=[x for x in common if x not in ['rate','p_value','statistic','effect_size','ci_95_low','ci_95_high','odds_ratio','risk_difference_pp','interpretation','decision']]
 if keys:
  old=old.sort_values(keys,na_position='first').reset_index(drop=True);new=new.sort_values(keys,na_position='first').reset_index(drop=True)
 mismatch=abs(len(old)-len(new));cols=[]
 if len(old)==len(new):
  for c in common:
   a,b=old[c],new[c]
   if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):n=int((~np.isclose(pd.to_numeric(a,errors='coerce'),pd.to_numeric(b,errors='coerce'),equal_nan=True,rtol=0,atol=1e-12)).sum())
   else:n=int((~a.fillna('__NULL__').astype(str).eq(b.fillna('__NULL__').astype(str))).sum())
   mismatch+=n;cols.append({'table':name,'column':c,'mismatch_n':n})
 return {'table':name,'old_rows':len(old),'new_rows':len(new),'mismatch_n':mismatch,'status':'PASS' if mismatch==0 else 'FAIL'},cols
def independent(c):
 s=pd.read_sql_query('select * from search',c);f=pd.read_sql_query('select * from search_filter',c);e=pd.read_sql_query('select * from event',c);s['t']=dt(s.search_time);click=set(e.loc[e.event_type=='hotel_click','search_id']);s['click']=s.search_id.isin(click);zero=int((s.total_result_count==0).sum());follow=imm=0;seg={'직접 성공':0,'결과 노출·미선택':0,'재검색 회복':0,'지속 실패':0};final_num=final_den=0
 for _,g in s.sort_values(['session_id','t','search_id']).groupby('session_id'):
  rr=list(g.itertuples());v=[x.total_result_count for x in rr]
  for i,x in enumerate(rr[:-1]):
   if x.total_result_count==0:follow+=1;imm+=rr[i+1].total_result_count>0
  if any(x==0 for x in v):final_den+=1;final_num+=any(v[i]==0 and any(y>0 for y in v[i+1:]) for i in range(len(v)))
  if v[0]==0:seg['재검색 회복' if any(x>0 for x in v[1:]) else '지속 실패']+=1
  else:seg['직접 성공' if any(x.click for x in rr) else '결과 노출·미선택']+=1
 b=s.merge(f,on='search_id');hi=b[b.price.notna()&b.user_rating_min.notna()&b.amenity_count.fillna(0).gt(0)]
 return {'zero_n':zero,'search_n':len(s),'followup_n':follow,'immediate_recovery_n':imm,'final_recovery_n':final_num,'final_recovery_den':final_den,'high_zero_n':int((hi.total_result_count==0).sum()),'high_n':len(hi),**seg}
def integrity(c):
 q=lambda z:c.execute(z).fetchone()[0];rows=[('integrity_check','ok',q('pragma integrity_check')),('booking_0',0,q('select count(*) from booking')),('filter_1to1_fail',0,q('select count(*) from search s left join(select search_id,count(*) n from search_filter group by 1)f using(search_id)where coalesce(n,0)<>1')),('result_count_fail',0,q('select count(*) from search s left join(select search_id,count(*) n from search_result group by 1)r using(search_id)where total_result_count<>coalesce(n,0)'))]
 for t in ['user','hotel','room','search','search_filter','search_result','event','booking']:
  pk=[x['name'] for x in c.execute(f'pragma table_info("{t}")') if x['pk']];n=0 if not pk else q(f'select count(*) from(select {",".join(pk)},count(*) n from "{t}" group by {",".join(pk)} having n>1)');rows.append((f'{t}_pk_duplicate',0,n))
 rows.append(('fk_orphan',0,sum(1 for _ in c.execute('pragma foreign_key_check'))));return [{'check':n,'expected':e,'actual':a,'status':'PASS' if e==a else 'FAIL'} for n,e,a in rows]
def main():
 if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
 p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--step2-xlsx',type=Path,required=True);p.add_argument('--old-step2-xlsx',type=Path,required=True);p.add_argument('--old-step3-xlsx',type=Path,required=True);p.add_argument('--r2-json',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir;before=sha(a.db);assert before==APPROVED;c=ro(a.db);new=pd.ExcelFile(a.step2_xlsx);old=pd.ExcelFile(a.old_step2_xlsx);pairs=[('G3_core_metrics','G3_core_metrics'),('A1_filters','A1_filters'),('A2_region_intent','A2_region_intent'),('B1_followup','B1_followup'),('B2_search_count','B2_search_count'),('B3_recovery','B3_recovery'),('session_segments','session_segments'),('H3_transitions','H3_transitions'),('raw_contingency_tables','raw_contingency')];summary=[];columns=[]
 for o,n in pairs:
  z,cc=compare_frames(pd.read_excel(old,sheet_name=o),pd.read_excel(new,sheet_name=n),o);summary.append(z);columns+=cc
 metric=independent(c);expected={'zero_n':3434,'search_n':6900,'followup_n':3271,'immediate_recovery_n':558,'final_recovery_n':488,'final_recovery_den':651,'high_zero_n':2125,'high_n':2425,'직접 성공':630,'결과 노출·미선택':231,'재검색 회복':92,'지속 실패':47};recalc=[{'metric':k,'expected':v,'actual':metric[k],'status':'PASS' if v==metric[k] else 'FAIL'} for k,v in expected.items()]
 oldtr=pd.read_excel(a.old_step3_xlsx,sheet_name='deterministic_traces');ids=set(pd.read_sql_query('select search_id from search',c).search_id);tr=oldtr.copy();aggregate=tr.match_status.eq('AGGREGATE_CONFIRMED');tr['current_present']=aggregate|tr.current_search_id.isna()|tr.current_search_id.isin(ids);tr['next_present']=aggregate|tr.next_search_id.isna()|tr.next_search_id.isin(ids);tr['r2_5_status']=np.where(tr.current_present&tr.next_present&(tr.match_status.isin(['PASS','AGGREGATE_CONFIRMED'])),'PASS','FAIL')
 r2=json.loads(a.r2_json.read_text(encoding='utf-8'));extra=[{'check':'BN S0 equals approved R2','mismatch_n':0 if any(x['dataset']=='S0_TIME_ALIGNED' and abs(x['log_loss']-.915162)<1e-12 for x in r2['bn_definition_b']) else 1},{'check':'time invariant mismatches','mismatch_n':sum(x['mismatch_n'] for x in r2['time_invariants'])},{'check':'cross overlap','mismatch_n':0 if any(x['dataset']=='S0_TIME_ALIGNED' and x['overlap_n']==1474 for x in r2['cross_stream']) else 1}]
 integ=integrity(c);c.close();failed=sum(x['mismatch_n'] for x in summary)+sum(x['mismatch_n'] for x in extra)+sum(x['status']=='FAIL' for x in recalc+integ)+int((tr.r2_5_status=='FAIL').sum());status='PASS' if failed==0 and sha(a.db)==before else 'FAIL';stamp='260905_1801_01';x=out/f'호텔검색_관측형합성1000명_STEP3독립검수결과_{stamp}.xlsx';t=out/f'호텔검색_관측형합성1000명_STEP3결정적표본추적표_{stamp}.xlsx'
 with pd.ExcelWriter(x,engine='openpyxl') as w:
  for n,d in [('전체표대조',summary),('컬럼대조',columns),('독립재계산',recalc),('보완검증',extra),('무결성',integ)]:pd.DataFrame(d).to_excel(w,sheet_name=n,index=False)
 with pd.ExcelWriter(t,engine='openpyxl') as w:tr.to_excel(w,sheet_name='결정적표본44건',index=False)
 payload={'step':'STEP3','status':status,'input_before':before,'input_after':sha(a.db),'workbook_comparison':summary,'independent_recalculation':recalc,'supplemental_checks':extra,'deterministic_trace_n':len(tr),'deterministic_trace_fail_n':int((tr.r2_5_status=='FAIL').sum()),'integrity':integ,'total_mismatch_n':failed};(out/f'호텔검색_관측형합성1000명_STEP3독립검수결과_{stamp}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(payload,ensure_ascii=False,indent=2));raise SystemExit(0 if status=='PASS' else 1)
if __name__=='__main__':main()
