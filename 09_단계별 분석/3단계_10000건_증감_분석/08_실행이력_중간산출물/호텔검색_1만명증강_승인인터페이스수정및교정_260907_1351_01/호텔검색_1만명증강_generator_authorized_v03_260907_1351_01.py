#!/usr/bin/env python3
"""Authorization-aware wrapper; delegates all business generation to immutable approved v02."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
PROD_SEED=2434815518
APPROVED_GENERATOR_SHA='150b7bae317809c0007335311b41bdff663e7f81d4b9fbab1083bdfc01fcbd56'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_json(p):return json.loads(Path(p).read_text(encoding='utf8'))
def validate_authorization(auth_path,mode,n,seed,scenario,out,config):
 if not auth_path:raise PermissionError('authorization required')
 a=load_json(auth_path)
 if a.get('allowed_mode')!='calibration' or mode!='calibration':raise PermissionError('mode not authorized')
 if a.get('production_execution_authorized') is not False:raise PermissionError('production flag invalid')
 skey=str(seed)
 if seed==PROD_SEED or skey not in a.get('allowed_seeds',{}):raise PermissionError('seed not authorized')
 if a['allowed_seeds'][skey]!=scenario:raise PermissionError('scenario not authorized')
 if n>a['max_users'] or n!=a['users_per_db'] or n//2!=a['users_per_arm'] or n//2!=a['pairs_per_db']:raise PermissionError('population scope mismatch')
 if sha(config) not in a['allowed_config_sha256']:raise PermissionError('config SHA not authorized')
 root=Path(a['allowed_output_directory']).resolve();target=Path(out).resolve()
 if root not in target.parents or target.parent!=root:raise PermissionError('output path not authorized')
 if target.exists():raise FileExistsError(target)
 manifest=Path(a['execution_manifest_path'])
 if sha(manifest)!=a['execution_manifest_sha256']:raise PermissionError('execution manifest SHA mismatch')
 m=load_json(manifest)
 for role,x in m['files'].items():
  if sha(x['path'])!=x['sha256']:raise PermissionError('frozen dependency changed: '+role)
 return a
def load_generator(path):
 if sha(path)!=APPROVED_GENERATOR_SHA:raise RuntimeError('approved generator SHA mismatch')
 s=importlib.util.spec_from_file_location('approved_v02_generator',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def generate(generator_path,config,out,authorization,mode,n,seed,scenario):
 validate_authorization(authorization,mode,n,seed,scenario,out,config)
 base=load_generator(generator_path)
 # Only the execution guard is replaced. State machine, probabilities, time and treatment code remain the approved module.
 def authorized_guard(c,called_mode,called_n,called_seed,called_out):
  validate_authorization(authorization,called_mode,called_n,called_seed,scenario,called_out,config)
 base.guard=authorized_guard
 return base.generate(config,out,mode,n,seed)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--generator',required=True);p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--authorization',required=True);p.add_argument('--mode',required=True);p.add_argument('--users',type=int,required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--scenario',required=True);a=p.parse_args()
 generate(a.generator,a.config,a.output,a.authorization,a.mode,a.users,a.seed,a.scenario)
