#!/usr/bin/env python3
"""State-transition v02 generator; synthetic scenario data, never observed A/B."""
from __future__ import annotations
import hashlib,json,math,random,sqlite3
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
import jsonschema,yaml
HERE=Path(__file__).resolve().parent
CONFIG_SCHEMA=HERE/'02_config_schema_prod_v02.json'; SQL=HERE/'02_schema_prod_v02.sql'
APPROVED_CONFIG_SHA256='d15219bbe085b5177ef02345ab1865cf50cfb47bb0a23e14a97cdf93ceb1443b'
ACTIONS=['same','region','price_relax','option_relax','query','mixed']
INTENTS=['condition_keeper','location_flexible','budget_flexible','option_count_flexible','query_reframer','rapid_resolver']
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def load_config(p=HERE/'02_base_config_prod_v02.yaml'):
 p=Path(p).resolve();c=yaml.safe_load(p.read_text(encoding='utf-8'));jsonschema.Draft202012Validator(json.loads(CONFIG_SCHEMA.read_text(encoding='utf-8'))).validate(c)
 if c['n_users_total']!=10000 or c['n_users_control']!=5000 or c['n_users_treatment']!=5000 or len(c['calibration_seeds'])!=20:raise ValueError('fixed design violation')
 for key,hkey in [('observed_db','observed_db_sha256'),('reference_1000_db','reference_1000_db_sha256'),('revision_spec','revision_spec_sha256')]:
  q=(p.parent/c['source'][key]).resolve()
  if sha(q)!=c['source'][hkey]:raise RuntimeError(f'{key} SHA-256 mismatch')
 return c
def production_plan(config_path=HERE/'02_base_config_prod_v02.yaml'):
 c=load_config(config_path)
 return {'total':c['n_users_total'],'control':c['n_users_control'],'treatment':c['n_users_treatment'],'pairs':c['n_users_control'],'paired':c['n_users_control']==c['n_users_treatment']}
def validate_production_output(output,confirm,approved_config_sha256,config_path=HERE/'02_base_config_prod_v02.yaml'):
 c=load_config(config_path);out=Path(output).resolve();approved=Path(c['approved_output_dir']).resolve()
 if not confirm:raise PermissionError('--confirm-production required')
 if approved_config_sha256!=sha(config_path) or sha(config_path)!=APPROVED_CONFIG_SHA256:raise PermissionError('config SHA-256 mismatch')
 if out.parent!=approved:raise PermissionError('unapproved output directory')
 if not approved.is_dir() or any(approved.iterdir()):raise FileExistsError('approved directory must exist and remain empty')
 if out.exists():raise FileExistsError(out)
 return production_plan(config_path)
def paired_assignment_plan(n_pairs=5000):
 return [(f'P{i:05d}',f'U{i:05d}C',f'U{i:05d}T') for i in range(1,n_pairs+1)]
def poisson(rng,lam):
 L=math.exp(-lam);k=0;p=1
 while p>L:k+=1;p*=rng.random()
 return k-1
def diversity(values):
 f=Counter(values);n=len(values);ps=[v/n for v in f.values()]
 return {'unique':len(f),'unique_ratio':len(f)/n,'mode_share':max(ps),'hhi':sum(x*x for x in ps),'shannon':-sum(x*math.log(x) for x in ps),'duplicate_rate':sum(v-1 for v in f.values())/n}
def simulate_control(seed,n,c=None,materialize=None):
 c=c or load_config();m=c['model'];rng=random.Random(seed);sessions=[];searches=[];trans=[];events=[];results=[]
 for i in range(n):
  uid=f'U{seed}-{i:05d}';sid=f'S{seed}-{i:05d}';intent=INTENTS[i%6];region=['metro','coastal','inland','island'][(i//6)%4];latent=rng.betavariate(2,2)
  # prospective latent exploration length; no outcome-count backfilling.
  length=min(m['max_searches'],2+int(math.log(max(1e-12,1-rng.random()))/math.log(0.83)))
  experienced=rng.random()<m['experienced_zero_probability'];final_recover=experienced and rng.random()<m['final_recovery_probability']
  first_zero=experienced and rng.random()<(m['first_zero_probability']/m['experienced_zero_probability'])
  zero=[]
  for seq in range(1,length+1):
   if not experienced:z=False
   elif seq==1:z=first_zero
   elif seq==length:z=not final_recover
   else:z=rng.random()<0.98
   zero.append(z)
  if experienced and not any(zero):zero[max(0,length-2)]=True
  if final_recover:zero[-1]=False
  elif experienced:zero[-1]=True
  acts=[];last=None;run=0
  for seq in range(1,length):
   weights={'same':.18,'region':.17,'price_relax':.18,'option_relax':.15,'query':.17,'mixed':.15}
   preferred={'condition_keeper':'same','location_flexible':'region','budget_flexible':'price_relax','option_count_flexible':'option_relax','query_reframer':'query','rapid_resolver':'mixed'}[intent];weights[preferred]+=.12*latent
   if last and run>=m['max_same_action_run']:weights[last]=0
   choices=list(weights);x=rng.random()*sum(weights.values());acc=0
   for a in choices:
    acc+=weights[a]
    if x<=acc:break
   run=run+1 if a==last else 1;last=a;acts.append(a)
  h_search=0;h_event=0;start=datetime(2026,9,7,tzinfo=timezone.utc)+timedelta(seconds=i*40);t=start
  sigs=[];condition_steps=[];full_steps=[]
  for j,z in enumerate(zero,1):
   if j>1:t+=timedelta(seconds=max(1,int(rng.lognormvariate(3.2,.6))))
   action='start' if j==1 else acts[j-2]; pref=min(1,max(0,latent+rng.uniform(-.025,.025)));signature=f'{region}|{intent}|{action}|{j}|{pref:.4f}|{i%997}'
   count=0 if z else 1+rng.randrange(5);qid=f'Q{seed}-{i:05d}-{j:02d}';sigs.append(signature)
   searches.append({'search_id':qid,'user_id':uid,'session_id':sid,'seq':j,'at':t.isoformat(),'count':count,'sig':signature,'action':None if j==1 else action,'region':region,'price':100000 if intent=='budget_flexible' else None,'options':2 if intent=='option_count_flexible' else 0,'query':'related' if action=='query' else 'base','pref':pref});condition_steps.append(signature+f'|result={int(count>0)}')
   hotels=[]
   for rank in range(1,count+1):
    hotel=1+(i*13+j*7+rank)%120;results.append((f'R-{qid}-{rank}',qid,hotel,hotel,rank));hotels.append(f'{rank}:{hotel}')
   full_steps.append(condition_steps[-1]+'|'+','.join(hotels))
   events.append((f'E-{qid}-S',uid,qid,'search_submit',t.isoformat(),None,0))
   if count and rng.random()<m['card_h_search_probability']:
    h_search+=1;repeat=1+poisson(rng,m['detail_repeat_mean']-1);h_event+=repeat;hotel=1+(i*13+j*7+1)%120
    for k in range(repeat):events.append((f'E-{qid}-D{k}',uid,qid,'hotel_detail_view',(t+timedelta(seconds=2+k)).isoformat(),hotel,0))
   if j>1:trans.append((f'T-{qid}',uid,f'Q{seed}-{i:05d}-{j-1:02d}',qid,action,int(zero[j-2] and not z),int((t-datetime.fromisoformat(searches[-2]['at'])).total_seconds())))
  events.append((f'E-{sid}-END',uid,None,'session_end',(t+timedelta(seconds=3)).isoformat(),None,0))
  sessions.append({'uid':uid,'sid':sid,'intent':intent,'region':region,'cluster':f'TC-{intent[:3]}-{region[:2]}-{i%211:03d}','length':length,'experienced':int(any(zero)),'recovered':int(any(zero) and not zero[-1]),'h_search':h_search,'h_event':h_event,'start':start.isoformat(),'end':(t+timedelta(seconds=3)).isoformat(),'behavior_path':f'{intent[:2]}:{region[:2]}:'+'>'.join(acts),'condition_path':'>'.join(condition_steps),'full_path':'>'.join(full_steps)})
 if materialize:write_db(Path(materialize),seed,sessions,searches,trans,events,results,c)
 search_by_id={x['search_id']:x for x in searches};zero_n=sum(x['count']==0 for x in searches);zero_follow=sum(1 for t in trans if search_by_id[t[2]]['count']==0);immediate=sum(t[5] for t in trans if search_by_id[t[2]]['count']==0);exp=sum(x['experienced'] for x in sessions);rec=sum(x['recovered'] for x in sessions);pos=sum(x['count']>0 for x in searches);hs=sum(x['h_search'] for x in sessions);he=sum(x['h_event'] for x in sessions)
 return {'seed':seed,'users':n,'search_zero_rate':zero_n/len(searches),'zero_followup_rate':zero_follow/zero_n,'immediate_recovery_rate':immediate/zero_follow if zero_follow else 0,'final_recovery_rate':rec/exp,'card_h_search_rate':hs/pos,'repeat_events_per_detail_search':he/hs if hs else 0,'searches_per_session':len(searches)/n,'signature':diversity([x['sig'] for x in searches]),'condition_path':diversity([x['condition_path'] for x in sessions]),'behavior_path':diversity([x['behavior_path'] for x in sessions]),'full_path':diversity([x['full_path'] for x in sessions]),'template':diversity([x['cluster'] for x in sessions]),'sessions':sessions,'searches':searches}
def write_db(path,seed,sessions,searches,trans,events,results,c):
 if path.exists():raise FileExistsError(path)
 db=sqlite3.connect(path);db.executescript(SQL.read_text(encoding='utf-8'));run=f'CAL-{seed}';db.execute("insert into SimulationRun values(?,?,?,?,?)",(run,seed,'dry_run','base','synthetic_calibration_not_observed_ab'))
 for h in range(1,121):db.execute('insert into HotelDimension values(?,?)',(h,f'HC{h:03d}'));db.execute('insert into RoomDimension values(?,?,?)',(h,h,'standard'))
 for x in sessions:
  db.execute('insert into ExperimentAssignment values(?,?,?,?,?,?,?,?,?,?,?)',(x['uid'],None,'control',x['intent']+'|'+x['region'],x['intent'],'none',x['cluster'],run,seed,'base','row-level source lineage removed'))
  outcome='SG1' if not x['experienced'] else ('SG2' if x['recovered'] and x['h_search'] else ('SG3' if x['recovered'] else 'SG4'))
  db.execute('insert into SessionSummary values(?,?,?,?,?,?,?,?,?,?)',(x['sid'],x['uid'],x['length'],x['experienced'],x['recovered'],x['h_search'],x['h_event'],x['start'],x['end'],outcome))
 for x in searches:
  db.execute('insert into Search values(?,?,?,?,?,?,?,?)',(x['search_id'],x['user_id'],x['session_id'],x['seq'],x['at'],x['count'],x['sig'],x['action']));db.execute('insert into SearchFilter values(?,?,?,?,?,?)',(x['search_id'],x['region'],x['price'],x['options'],x['query'],x['pref']))
 db.executemany('insert into SearchResult values(?,?,?,?,?)',results);db.executemany('insert into ActionEvent values(?,?,?,?,?,?,?)',events);db.executemany('insert into SearchTransition values(?,?,?,?,?,?,?)',trans);db.execute("insert into _generation_metadata values('detail_event_policy','detail_only')");db.commit();db.close()
