#!/usr/bin/env python3
"""Sequential Z/P/END revision. Reuses approved v02 materialization and v03 authorization."""
import argparse,hashlib,importlib.util,json,random
from pathlib import Path
V02_SHA='150b7bae317809c0007335311b41bdff663e7f81d4b9fbab1083bdfc01fcbd56'
AUTH_SHA='40192ea7fe212cec7b98206be51c8be4175af8a7c0396541b946e81726087edc'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(path,name,expected):
 if sha(path)!=expected:raise RuntimeError(name+' SHA mismatch')
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sequential_plan(rng,c,profile,force=None,arm='control',scenario='expected'):
 t=c['sequential_transition'];force=force or {};first_zero=force.get('first_zero',rng.random()<t['first_zero_probability'])
 states=['FIRST_SEARCH_ZERO' if first_zero else 'FIRST_SEARCH_POSITIVE'];current='Z' if first_zero else 'P';ever=first_zero
 while len(states)<c['state_machine']['max_searches']:
  if current=='Z':
   zp=t['z_to_p']+(t['treatment_recovery_uplift'][scenario] if arm=='treatment' else 0);zz=t['z_to_z'];scale=(1-t['z_to_end'])/(zz+zp);zz*=scale;zp*=scale
   u=rng.random()
   if u<t['z_to_end']:break
   nxt='Z' if u<t['z_to_end']+zz else 'P'
  else:
   u=rng.random()
   if u<t['p_to_end']:break
   nxt='Z' if u<t['p_to_end']+t['p_to_z'] else 'P'
  if current=='Z' and nxt=='P':state='IMMEDIATE_RECOVERY'
  elif nxt=='Z':state='FOLLOWUP_ZERO'
  else:state='CONTINUED_SEARCH'
  states.append(state);current=nxt;ever=ever or nxt=='Z'
 outcome='SG1' if not ever else ('SG3' if current=='P' else 'SG4')
 return states,outcome
def stored_signature(plan):
 clean=[]
 for x in plan:
  if isinstance(x,tuple) and len(x)==9:clean.append(x[:-1])
  else:clean.append(x)
 return json.dumps(clean,sort_keys=True,default=str)
def generate(v02_generator,authorized_wrapper,schema,config,out,authorization,mode,n,seed,scenario):
 auth=load(authorized_wrapper,'authorized_wrapper',AUTH_SHA);auth.validate_authorization(authorization,mode,n,seed,scenario,out,config)
 base=load(v02_generator,'approved_v02',V02_SHA);base.SCHEMA=Path(schema);base.state_plan=sequential_plan;base.business_signature=stored_signature
 def guard(c,m,nn,s,o):auth.validate_authorization(authorization,m,nn,s,scenario,o,config)
 base.guard=guard;return base.generate(config,out,mode,n,seed)
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for x in ['v02-generator','authorized-wrapper','schema','config','output','authorization','mode','scenario']:p.add_argument('--'+x,required=True)
 p.add_argument('--users',type=int,required=True);p.add_argument('--seed',type=int,required=True);a=p.parse_args();generate(a.v02_generator,a.authorized_wrapper,a.schema,a.config,a.output,a.authorization,a.mode,a.users,a.seed,a.scenario)
