#!/usr/bin/env python3
"""newref_v02 explicit terminal-first state-machine simulator; synthetic scenario, not observed A/B."""
import argparse,hashlib,json,math,random,sqlite3
from datetime import datetime,timedelta,timezone
from pathlib import Path
import jsonschema,yaml
HERE=Path(__file__).resolve().parent;SCHEMA=HERE/'05_config_schema_newref_v02.json';SQL=HERE/'05_schema_newref_v02.sql';PRODSEED=2434815518
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def seedof(*x):return int.from_bytes(hashlib.sha256('|'.join(map(str,x)).encode()).digest()[:8],'big')
def load_config(p):
 p=Path(p).resolve();c=yaml.safe_load(p.read_text(encoding='utf8'));jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text())).validate(c);r=(p.parent/c['reference']['path']).resolve()
 if sha(r)!=c['reference']['sha256']:raise RuntimeError('reference SHA mismatch')
 return c,r
def guard(c,mode,n,seed,out):
 if seed==PRODSEED:raise PermissionError('production seed prohibited in revision stage')
 if mode=='unit_test' and n>c['safety']['unit_test_max_users']:raise PermissionError('unit limit')
 if mode=='smoke_test' and n>c['safety']['smoke_test_max_users']:raise PermissionError('smoke limit')
 if mode in ('calibration','production'):raise PermissionError(f'{mode} blocked')
 root=(HERE/c['output']['allowed_test_root']).resolve();p=Path(out).resolve()
 if root not in p.parents:raise PermissionError('output outside tests');
 if p.exists():raise FileExistsError(p)
def posterior(c,name,scenario):
 x=c['treatment_posteriors'][name];a=x['prior_alpha']+x['success'];b=x['prior_beta']+x['n']-x['success'];m=a/(a+b);sd=math.sqrt(a*b/((a+b)**2*(a+b+1)));return max(.001,min(.999,m+{'conservative':-1,'expected':0,'optimistic':1}[scenario]*sd))
def draw_interval(rng,t):
 if rng.random()<t['same_timestamp_probability']:return 0,'simultaneous'
 if rng.random()<t['tail_probability']:return min(t['maximum_seconds'],max(t['body_cap_seconds']+1,round(rng.lognormvariate(t['tail_log_mu'],t['tail_log_sigma'])))),'tail'
 return min(t['body_cap_seconds'],max(1,round(rng.lognormvariate(t['body_log_mu'],t['body_log_sigma'])))),'body'
def zero_hazard(c,order,previous_zero,cumulative_zero,strategy,price_present,option_bucket,treatment_exposed):
 h=c['search_hazard'];p=h['base_zero']-h['order_decay']*max(0,order-1)
 p+=h['previous_zero_increment']*bool(previous_zero)+h['cumulative_zero_increment']*cumulative_zero
 p+=h['price_constraint_increment']*bool(price_present)+h['option_2plus_increment']*(option_bucket=='2+')
 p-=h['region_change_decrement']*(strategy=='region_change')+h['treatment_exposure_decrement']*bool(treatment_exposed)
 return max(.001,min(.999,p))
def reference_profile(ref):
 c=sqlite3.connect('file:'+ref.as_posix()+'?mode=ro',uri=True);rows=c.execute('''with x as(select session_id,total_result_count,row_number()over(partition by session_id order by search_time,search_id)first_rn,row_number()over(partition by session_id order by search_time desc,search_id desc)last_rn,count(*)over(partition by session_id)n,max(total_result_count=0)over(partition by session_id)z from search)select session_id,max(n),max(z),max(case when first_rn=1 then total_result_count=0 end),max(case when last_rn=1 then total_result_count>0 end),sum(total_result_count=0)from x group by session_id''').fetchall();src=[x[0] for x in rows];lengths={'nozero':[],'recovered':[],'persistent':[]}
 for _,n,z,f,r,k in rows:lengths['nozero' if not z else ('recovered' if r else 'persistent')].append(n)
 positive_counts=[x[0] for x in c.execute('select total_result_count from search where total_result_count>0')];c.close();return {'sources':src,'lengths':lengths,'positive_counts':positive_counts}
def state_plan(rng,c,profile,force=None,arm='control',scenario='expected'):
 s=c['state_machine'];force=force or {};ever=force.get('ever_zero',rng.random()<s['ever_zero_probability'])
 if not ever:return ['FIRST_SEARCH_POSITIVE']+['CONTINUED_SEARCH']*(rng.choice(profile['lengths']['nozero'])-1),'SG1'
 first=force.get('first_zero',rng.random()<s['first_zero_given_ever_zero']);follow=force.get('follow',rng.random()<s['zero_followup_probability'])
 if not follow:return (['FIRST_SEARCH_ZERO'] if first else ['FIRST_SEARCH_POSITIVE','FOLLOWUP_ZERO']),'SG4'
 immediate_p=s['immediate_recovery_probability']
 if arm=='treatment':
  immediate_p=max(immediate_p,posterior(c,'region_change',scenario))
 immediate=force.get('immediate',rng.random()<immediate_p)
 if immediate:
  states=['FIRST_SEARCH_ZERO','IMMEDIATE_RECOVERY'] if first else ['FIRST_SEARCH_POSITIVE','FOLLOWUP_ZERO','IMMEDIATE_RECOVERY'];return states,'SG3'
 target=s['terminal_recovery_probability'];p=s['zero_followup_probability'];i=immediate_p;late=max(0,min(1,(target-p*i)/(p*(1-i)))) if p*(1-i)>0 else 0
 if arm=='treatment':late=max(late,posterior(c,'constraint_relax',scenario))
 recover=force.get('late',rng.random()<late)
 terminal='recovered' if recover else 'persistent';n=max(3 if recover else 2,rng.choice(profile['lengths'][terminal]));states=['FIRST_SEARCH_ZERO' if first else 'FIRST_SEARCH_POSITIVE'];zero_seen=first
 while len(states)<n-1:
  hz=zero_hazard(c,len(states)+1,bool(states and 'ZERO' in states[-1]),sum('ZERO' in x for x in states),'same_condition',False,'0',arm=='treatment')
  if not zero_seen or rng.random()<hz:states.append('FOLLOWUP_ZERO');zero_seen=True
  else:states.append('CONTINUED_SEARCH')
 states.append('LATE_RECOVERY' if recover else 'PERSISTENT_FAILURE');return states,'SG3' if recover else 'SG4'
def business_signature(plan):return json.dumps(plan,sort_keys=True,default=str)
def generate(config,out,mode=None,n=None,seed=None):
 c,ref=load_config(config);mode=mode or c['mode'];n=n or c['n_users'];seed=c['seed'] if seed is None else seed;guard(c,mode,n,seed,out);profile=reference_profile(ref);db=sqlite3.connect(out);db.execute('pragma foreign_keys=on');db.executescript(SQL.read_text());run=f'V02-{seed}-{n}';db.execute('insert into SimulationRun values(?,?,?,?,?,?)',(run,seed,mode,c['scenario'],datetime.now(timezone.utc).isoformat(),'synthetic A/B scenario; not observed causal effect'))
 for x in range(1,1001):db.execute('insert into Hotel values(?,?)',(f'H{x:04d}',f'Hotel {x:04d}'));db.execute('insert into Room values(?,?)',(f'R{x:04d}',f'H{x:04d}'))
 seen={'control':set(),'treatment':set()};tail_count=0
 for pi in range(n//2):
  common=random.Random(seedof(seed,pi,'common'));pair=f'P{pi+1:05d}';region=common.choice(['metro','coastal','inland','island']);price=common.choice([None,80000,120000,180000]);amenity=common.choice([0,1,2,3]);risk=common.choice(['low','medium','high']);source=common.choice(profile['sources']);first_query=common.choice(['hotel','stay','weekend','family','business']);first_date=common.randrange(1,29);common_ever=common.random()<c['state_machine']['ever_zero_probability'];common_first=common.random()<c['state_machine']['first_zero_given_ever_zero'] if common_ever else False;common_first_count=0 if common_first else common.choice(profile['positive_counts']);common_first_hotels=tuple(common.sample(range(1,1001),common_first_count))
  for arm in ('control','treatment'):
   for attempt in range(c['clone']['max_redraw_attempts']):
    rng=random.Random(seedof(seed,pi,arm,attempt,'state'));plan,outcome=state_plan(rng,c,profile,{'ever_zero':common_ever,'first_zero':common_first},arm,c['scenario']);actions=[];vals=[]
    for j,state in enumerate(plan):
     action='initial' if j==0 else ('region_change' if arm=='treatment' and 'ZERO' in plan[j-1] else rng.choice(['same_condition','constraint_relax','query_change','region_change']));count=common_first_count if j==0 else (0 if state in ('FIRST_SEARCH_ZERO','FOLLOWUP_ZERO','PERSISTENT_FAILURE') else rng.choice(profile['positive_counts']));hotels=common_first_hotels if j==0 else tuple(rng.sample(range(1,1001),count));vals.append((state,action,count,hotels,region,price,amenity,first_query,first_date));actions.append(action)
    sig=business_signature(vals+[outcome]);
    if sig not in seen[arm]:seen[arm].add(sig);break
   else:raise RuntimeError('clone redraw attempts exceeded')
   uid=f'U{pi+1:05d}{arm[0].upper()}';sid=f'S{pi+1:05d}{arm[0].upper()}';scenario='none' if arm=='control' else c['scenario'];stratum=f'price={int(price is not None)}|opt={amenity if amenity<2 else "2+"}|region={region}|risk={risk}';db.execute('insert into UserSynthetic values(?,?,?,?,?,?,?,?,?,?)',(uid,pair,arm,stratum,run,seed,source,scenario,'newref_v02',None));start=datetime(2028,2,1,tzinfo=timezone.utc)+timedelta(seconds=pi*101+(31 if arm=='treatment' else 0));db.execute('insert into SessionSynthetic values(?,?,?,?,?,?,?)',(sid,uid,pair,start.isoformat(),start.isoformat(),outcome,0));t=start;last=t;prev=None;exposed=0
   for j,(state,action,count,hotels,_,_,_,_,_) in enumerate(vals,1):
    if j>1:d,component=draw_interval(rng,c['time_mixture']);tail_count+=component=='tail';t+=timedelta(seconds=d)
    if arm=='treatment' and j>1 and 'ZERO' in plan[j-2]:exposed=1;prob=posterior(c,action if action in c['treatment_posteriors'] else 'same_condition',c['scenario'])
    qid=f'Q{pi+1:05d}{arm[0].upper()}{j:02d}';qtext=first_query if j==1 else f'{first_query}-{action}-{rng.randrange(1000):03d}';dest=region if action!='region_change' else rng.choice([x for x in ['metro','coastal','inland','island'] if x!=region]);db.execute('insert into Search values(?,?,?,?,?,?,?,?)',(qid,sid,j,t.isoformat(),count,qtext,dest,action));fid=f'F-{qid}';db.execute('insert into SearchFilter values(?,?,?,?,?,?,?)',(fid,qid,None if action=='constraint_relax' else price,max(0,amenity-(action=='constraint_relax')),dest,None,None));db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{qid}-S',uid,sid,qid,None,'search_submit',t.isoformat(),None,None))
    for rank,h in enumerate(hotels,1):hid=f'H{h:04d}';db.execute('insert into SearchResult values(?,?,?,?,?)',(f'Z-{qid}-{rank}',qid,hid,f'R{h:04d}',rank));db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{qid}-I{rank}',uid,sid,qid,hid,'hotel_impression',(t+timedelta(seconds=rank)).isoformat(),None,None));last=max(last,t+timedelta(seconds=rank))
    if count and rng.random()<c['card_h']['search_probability']:
     rep=max(1,round(rng.expovariate(1/c['card_h']['repeat_mean'])));hid=f'H{hotels[0]:04d}';base=t+timedelta(seconds=max(1,round(rng.lognormvariate(math.log(152),.5))))
     for k in range(rep):ct=base+timedelta(seconds=k);dt=ct+timedelta(seconds=0 if rng.random()<.3388 else 1);db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{qid}-C{k}',uid,sid,qid,hid,'hotel_click',ct.isoformat(),None,None));db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{qid}-D{k}',uid,sid,qid,hid,'hotel_detail_view',dt.isoformat(),None,None));last=max(last,dt)
    if prev:db.execute('insert into SearchTransition values(?,?,?,?,?,?)',(f'T-{qid}',sid,prev,qid,action,int(count>0 and vals[j-2][2]==0)))
    prev=qid
   end=max(t+timedelta(seconds=60),last+timedelta(seconds=1));db.execute('insert into ActionEvent values(?,?,?,?,?,?,?,?,?)',(f'E-{sid}-END',uid,sid,None,None,'session_end',end.isoformat(),None,None));db.execute('update SessionSynthetic set ended_at=?,treatment_exposed=? where session_id=?',(end.isoformat(),exposed,sid))
 db.execute("insert into _generation_metadata values('state_machine','terminal_outcome_first')");db.execute("insert into _generation_metadata values('tail_component_count',?)",(str(tail_count),));db.commit();db.close();return Path(out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',default=str(HERE/'05_base_config_newref_v02.yaml'));p.add_argument('--output',required=True);p.add_argument('--mode');p.add_argument('--users',type=int);p.add_argument('--seed',type=int);a=p.parse_args();generate(a.config,a.output,a.mode,a.users,a.seed)
