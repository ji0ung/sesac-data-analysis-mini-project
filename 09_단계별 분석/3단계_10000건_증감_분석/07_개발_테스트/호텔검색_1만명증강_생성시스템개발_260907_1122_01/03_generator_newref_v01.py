#!/usr/bin/env python3
"""newref_v01 paired A/B simulator. Output is synthetic scenario data, not observed A/B."""
from __future__ import annotations
import argparse,hashlib,json,math,random,sqlite3
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
import jsonschema,yaml
HERE=Path(__file__).resolve().parent; SCHEMA=HERE/'03_config_schema_newref_v01.json'; SQL=HERE/'03_schema_newref_v01.sql'; VERSION='newref_v01'
SCENARIOS=('conservative','expected','optimistic'); ACTIONS=('region_change','constraint_relax','query_change','same_condition')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def seedof(*parts):return int.from_bytes(hashlib.sha256('|'.join(map(str,parts)).encode()).digest()[:8],'big')
def load_config(path):
 p=Path(path).resolve();cfg=yaml.safe_load(p.read_text(encoding='utf-8'));jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding='utf-8'))).validate(cfg)
 ref=(p.parent/cfg['reference']['path']).resolve()
 if sha(ref)!=cfg['reference']['sha256']:raise RuntimeError('reference DB SHA-256 mismatch')
 return cfg,ref
def guard(cfg,mode,n,out,config_path,approval=None):
 if mode=='unit_test' and n>cfg['safety']['unit_test_max_users']:raise PermissionError('unit_test maximum is 40')
 if mode=='smoke_test' and n>cfg['safety']['smoke_test_max_users']:raise PermissionError('smoke_test maximum is 200')
 if mode=='calibration':raise PermissionError('calibration blocked until STEP 2.10')
 if mode=='production':
  if n!=10000 or not approval:raise PermissionError('production requires exactly 10000 and approval manifest')
  a=json.loads(Path(approval).read_text(encoding='utf-8'))
  if not a.get('execution_authorized'):raise PermissionError('production execution_authorized is not true')
  required=['generator_sha256','config_sha256','schema_sha256','config_schema_sha256','metric_definitions_sha256','calibration_results_sha256','reference_db_sha256','step_2_10_manifest_sha256','approved_output_dir']
  if any(k not in a for k in required):raise PermissionError('production approval manifest is incomplete')
  actual={'generator_sha256':sha(__file__),'config_sha256':sha(config_path),'schema_sha256':sha(SQL),'config_schema_sha256':sha(SCHEMA),'metric_definitions_sha256':sha(HERE/'03_metric_definitions_newref_v01.yaml'),'reference_db_sha256':cfg['reference']['sha256']}
  if any(a[k]!=v for k,v in actual.items()):raise PermissionError('production approved artifact SHA mismatch')
  if any(len(a[k])!=64 or any(x not in '0123456789abcdef' for x in a[k]) for k in required if k.endswith('sha256')):raise PermissionError('invalid approval SHA format')
  prod=(HERE/cfg['output']['production_root']).resolve()
  if Path(a['approved_output_dir']).resolve()!=prod or Path(out).resolve().parent!=prod:raise PermissionError('unapproved production output path')
  if not prod.is_dir() or any(prod.iterdir()):raise FileExistsError('approved production folder must exist and be empty')
 root=(HERE/cfg['output']['allowed_test_root']).resolve();o=Path(out).resolve()
 if mode in ('unit_test','smoke_test') and root not in o.parents:raise PermissionError('test output outside allowed root')
 if o.exists():raise FileExistsError(o)
def posterior(cfg,name,scenario):
 x=cfg['treatment_posteriors'][name];a=x['prior_alpha']+x['raw_success'];b=x['prior_beta']+x['raw_n']-x['raw_success'];mean=a/(a+b);sd=math.sqrt(a*b/((a+b)**2*(a+b+1)));z={'conservative':-1,'expected':0,'optimistic':1}[scenario]
 return max(.001,min(.999,mean+z*sd)),a,b
def poisson(rng,lam):
 L=math.exp(-lam);p=1;k=0
 while p>L:k+=1;p*=rng.random()
 return k-1
def generate(config_path,out,mode=None,n=None,seed=None,approval=None):
 cfg,ref=load_config(config_path);mode=mode or cfg['mode'];n=n or cfg['n_users'];seed=cfg['seed'] if seed is None else seed
 if n%2:raise ValueError('paired design requires even n_users')
 if cfg['scenario'] not in SCENARIOS:raise ValueError('invalid scenario')
 guard(cfg,mode,n,out,Path(config_path).resolve(),approval);source=[r[0] for r in sqlite3.connect('file:'+ref.as_posix()+'?mode=ro',uri=True).execute('select distinct session_id from search order by session_id')]
 db=sqlite3.connect(out);db.execute('pragma foreign_keys=on');db.executescript(SQL.read_text(encoding='utf-8'));run=f'RUN-{seed}-{n}';now=datetime.now(timezone.utc).isoformat();db.execute('insert into SimulationRun values(?,?,?,?,?,?)',(run,seed,mode,cfg['scenario'],now,'synthetic scenario simulation; not observed A/B'))
 for i in range(1,301):db.execute('insert into Hotel values(?,?)',(f'H{i:04d}',f'Synthetic Hotel {i:04d}'));db.execute('insert into Room values(?,?)',(f'R{i:04d}',f'H{i:04d}'))
 for pidx in range(n//2):
  cr=random.Random(seedof(seed,pidx,'common')); region=cr.choice(['metro','coastal','inland','island']);price=cr.choice([None,80000,120000,180000]);amenity=cr.choice([0,1,2,3]);difficulty=cr.choice(['low','medium','high']);latent=cr.random();source_sid=source[cr.randrange(len(source))];initial_zero=cr.random()<cfg['model']['search_zero_probability'];initial_count=0 if initial_zero else 1+cr.randrange(5);base_len=min(cfg['model']['max_searches'],1+int(cr.expovariate(1/5)))
  pair=f'P{pidx+1:05d}';first_query=f'{region}-{difficulty}-{cr.randrange(100000):05d}';check_date=cr.randrange(1,29)
  for arm in ('control','treatment'):
   ar=random.Random(seedof(seed,pidx,arm,'outcome'));tr=random.Random(seedof(seed,pidx,arm,'time'));uid=f'U{pidx+1:05d}{arm[0].upper()}';sid=f'S{pidx+1:05d}{arm[0].upper()}';scenario='none' if arm=='control' else cfg['scenario'];stratum=f'price={int(price is not None)}|options={"2+" if amenity>=2 else amenity}|region={region}|risk={difficulty}'
   db.execute('insert into UserSynthetic values(?,?,?,?,?,?,?,?,?,?)',(uid,pair,arm,stratum,run,seed,source_sid,scenario,VERSION,None));start=datetime(2028,1,1,tzinfo=timezone.utc)+timedelta(seconds=pidx*97+(0 if arm=='control' else 31));db.execute('insert into SessionSynthetic values(?,?,?,?,?,?,?)',(sid,uid,pair,start.isoformat(),start.isoformat(),'SG2',0));t=start;last_event=start;zero=initial_zero;experienced=zero;exposed=0;searches=[];length=base_len
   if not initial_zero:length=max(1,min(length,4))
   for seq in range(1,length+1):
    if seq>1:
     delay=0 if tr.random()<.0078 else max(1,round(tr.lognormvariate(cfg['model']['interarrival_log_mu'],cfg['model']['interarrival_log_sigma'])));t+=timedelta(seconds=delay)
    action='initial';recover=False
    if seq>1:
     if not zero and ar.random()>.35:break
     if zero:
      if arm=='treatment':
       exposed=1;eligible=[]
       if price is not None or amenity>0:eligible.append('constraint_relax')
       eligible+=['region_change','query_change'];action=ar.choice(eligible);prob,_,_=posterior(cfg,action,cfg['scenario']);recover=ar.random()<prob
      else:action=ar.choice(ACTIONS);recover=ar.random()<cfg['model']['immediate_recovery_probability']
      zero=not recover
     else:zero=ar.random()<.12
    count=initial_count if seq==1 else (0 if zero else 1+ar.randrange(5));qid=f'Q{pidx+1:05d}{arm[0].upper()}{seq:02d}';qtext=first_query if seq==1 else f'{first_query}-{action}-{ar.randrange(10000):04d}';dest=region if action!='region_change' else ar.choice([x for x in ['metro','coastal','inland','island'] if x!=region])
    db.execute('insert into Search values(?,?,?,?,?,?,?,?)',(qid,sid,seq,t.isoformat(),count,qtext,dest,action));fid=f'F-{qid}';db.execute('insert into SearchFilter values(?,?,?,?,?,?,?)',(fid,qid,price if action!='constraint_relax' else None,max(0,amenity-(1 if action=='constraint_relax' else 0)),dest,None,None));db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{qid}-S',uid,sid,qid,None,'search_submit',t.isoformat(),None,None))
    hotels=[]
    for rank in range(1,count+1):
     h=1+((pidx*17+seq*13+rank*7+ar.randrange(300))%300);hid=f'H{h:04d}'
     while hid in hotels:h=1+(h%300);hid=f'H{h:04d}'
     rid=f'R{h:04d}';hotels.append(hid);db.execute('insert into SearchResult values(?,?,?,?,?)',(f'Z-{qid}-{rank}',qid,hid,rid,rank));db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{qid}-I{rank}',uid,sid,qid,hid,'hotel_impression',(t+timedelta(seconds=rank)).isoformat(),None,None))
    if count and ar.random()<cfg['model']['card_h_search_probability']:
     rep=max(1,1+poisson(ar,cfg['model']['detail_repeat_mean']-1));base_delay=max(1,round(tr.lognormvariate(math.log(152),.55)));hid=hotels[0]
     for k in range(rep):
      ct=t+timedelta(seconds=base_delay+k*max(0,round(tr.lognormvariate(0,.5))));detail_at=ct+timedelta(seconds=0 if tr.random()<.3388 else max(1,round(tr.lognormvariate(0,.6))));last_event=max(last_event,detail_at);db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{qid}-C{k}',uid,sid,qid,hid,'hotel_click',ct.isoformat(),None,None));db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{qid}-D{k}',uid,sid,qid,hid,'hotel_detail_view',detail_at.isoformat(),None,None))
    if searches:db.execute('insert into SearchTransition values(?,?,?,?,?,?)',(f'T-{qid}',sid,searches[-1][0],qid,action,int(searches[-1][1] and not zero)))
    searches.append((qid,zero))
   final_zero=searches[-1][1];outcome='SG4' if experienced and final_zero else ('SG3' if experienced else ('SG1' if any(not x[1] for x in searches) else 'SG2'));end=max(t+timedelta(seconds=300),last_event+timedelta(seconds=1));db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{sid}-END',uid,sid,None,None,'session_end',end.isoformat(),None,None));db.execute('update SessionSynthetic set ended_at=?,outcome_segment=?,treatment_exposed=? where session_id=?',(end.isoformat(),outcome,exposed,sid))
 for name in cfg['treatment_posteriors']:
  for sc in SCENARIOS:
   prob,a,b=posterior(cfg,name,sc);db.execute('insert into _generation_metadata values(?,?)',(f'posterior.{name}.{sc}',json.dumps({'raw':cfg['treatment_posteriors'][name],'posterior_alpha':a,'posterior_beta':b,'used_probability':prob})))
 db.execute("insert into _generation_metadata values('reference_sha256',?)",(cfg['reference']['sha256'],));db.execute("insert into _generation_metadata values('disclaimer','synthetic scenario simulation; not observed A/B')");db.commit();db.close();return Path(out)
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',default=str(HERE/'03_base_config_newref_v01.yaml'));p.add_argument('--output',required=True);p.add_argument('--mode');p.add_argument('--users',type=int);p.add_argument('--seed',type=int);p.add_argument('--approval-manifest');a=p.parse_args();generate(a.config,a.output,a.mode,a.users,a.seed,a.approval_manifest)
if __name__=='__main__':main()
