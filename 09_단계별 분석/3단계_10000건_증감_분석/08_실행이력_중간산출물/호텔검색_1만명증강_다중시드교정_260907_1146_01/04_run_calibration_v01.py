#!/usr/bin/env python3
"""Authorized STEP 2.10 adapter; does not modify the approved generator."""
import concurrent.futures,hashlib,importlib.util,json,sys,time
from pathlib import Path
import yaml
OUT=Path(__file__).resolve().parent; ROOT=OUT.parents[3]; DEV=OUT.parent/'호텔검색_1만명증강_생성시스템개발_260907_1122_01'; GEN=DEV/'03_generator_newref_v01.py'; BASE=DEV/'03_base_config_newref_v01.yaml'; AUTH=OUT/'04_calibration_authorization_v01.json'; PRODSEED=2434815518
RUNS=[('expected',x) for x in range(260701,260721)]+[('conservative',x) for x in range(260721,260726)]+[('optimistic',x) for x in range(260726,260731)]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def worker(item):
 scenario,seed=item
 if seed==PRODSEED:raise RuntimeError('production seed prohibited')
 auth=json.loads(AUTH.read_text(encoding='utf8'))
 if not auth['calibration_authorized'] or auth['production_authorized'] or seed not in auth[f'{scenario}_seeds'] or auth['generator_sha256']!=sha(GEN):raise PermissionError('invalid calibration authorization')
 spec=importlib.util.spec_from_file_location('approved_generator',GEN);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
 cfg=yaml.safe_load(BASE.read_text(encoding='utf8'));cfg['mode']='calibration';cfg['n_users']=2000;cfg['seed']=seed;cfg['scenario']=scenario;cfg['reference']['path']=str((DEV/cfg['reference']['path']).resolve());cfg['output']['allowed_test_root']=str((OUT/'calibration_dbs').resolve());cp=OUT/f'config_{scenario}_{seed}.yaml';cp.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False),encoding='utf8')
 target=OUT/'calibration_dbs'/f'calibration_{scenario}_{seed}.sqlite'
 def calibration_guard(c,mode,n,out,config_path,approval=None):
  p=Path(out).resolve();root=(OUT/'calibration_dbs').resolve()
  if mode!='calibration' or n!=2000 or root not in p.parents or p.exists():raise PermissionError('calibration boundary violation')
 g.guard=calibration_guard;t=time.time();g.generate(cp,target,'calibration',2000,seed,str(AUTH));elapsed=time.time()-t
 manifest={'scenario':scenario,'seed':seed,'users':2000,'control':1000,'treatment':1000,'pairs':1000,'db_path':str(target.resolve()),'db_bytes':target.stat().st_size,'db_sha256':sha(target),'config_sha256':sha(cp),'generator_sha256':sha(GEN),'production_mode':False,'production_seed_used':False,'elapsed_seconds':elapsed}
 (OUT/'seed_manifests'/f'manifest_{scenario}_{seed}.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');return manifest
if __name__=='__main__':
 if any((OUT/'calibration_dbs'/f'calibration_{s}_{x}.sqlite').exists() for s,x in RUNS):raise FileExistsError('calibration output already exists')
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as ex:
  results=[]
  for r in ex.map(worker,RUNS):results.append(r);print(f"DONE {r['scenario']} {r['seed']} {r['elapsed_seconds']:.2f}s",flush=True)
 (OUT/'04_calibration_execution_results.json').write_text(json.dumps(results,indent=2),encoding='utf8')
