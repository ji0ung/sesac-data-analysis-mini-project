#!/usr/bin/env python3
import hashlib,importlib.util,json
from pathlib import Path
V04_SHA='823a7bc7241f6670093b5f8224fe00547be44d3b26e37a675a3c96dfbf427b24'
def load(p):
 if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=V04_SHA:raise RuntimeError('v04 SHA mismatch')
 s=importlib.util.spec_from_file_location('v04',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def sequential_plan(rng,c,profile,force=None,arm='control',scenario='expected'):
 t=c['sequential_transition'];force=force or {};first_zero=force.get('first_zero',rng.random()<t['first_zero_probability']);states=['FIRST_SEARCH_ZERO' if first_zero else 'FIRST_SEARCH_POSITIVE'];current='Z' if first_zero else 'P';ever=first_zero
 while len(states)<c['state_machine']['max_searches']:
  u=rng.random()
  if current=='Z':
   zend=t['z_to_end'];zp=t['z_to_p']+(t['treatment_recovery_uplift'][scenario] if arm=='treatment' else 0);zz=1-zend-zp
   if u<zend:break
   nxt='Z' if u<zend+zz else 'P'
  else:
   pend=t['p_to_end'];pz=t['p_to_z_after_zero'] if ever else t['p_to_z_before_zero'];pp=1-pend-pz
   if u<pend:break
   nxt='Z' if u<pend+pz else 'P'
  states.append('IMMEDIATE_RECOVERY' if current=='Z' and nxt=='P' else ('FOLLOWUP_ZERO' if nxt=='Z' else 'CONTINUED_SEARCH'));current=nxt;ever=ever or nxt=='Z'
 return states,('SG1' if not ever else ('SG3' if current=='P' else 'SG4'))
def generate(v04_generator,*args):
 m=load(v04_generator);m.sequential_plan=sequential_plan;return m.generate(*args)
