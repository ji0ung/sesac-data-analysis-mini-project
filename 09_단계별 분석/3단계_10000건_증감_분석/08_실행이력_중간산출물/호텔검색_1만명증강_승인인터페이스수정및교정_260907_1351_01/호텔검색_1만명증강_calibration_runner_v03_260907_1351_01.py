#!/usr/bin/env python3
import argparse,hashlib,importlib.util,json
from pathlib import Path
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def run(args):
 wrapper=load(args.wrapper,'authorized_generator')
 db=wrapper.generate(args.generator,args.config,args.output,args.authorization,'calibration',args.users,args.seed,args.scenario)
 gate=load(args.integration_gate,'integration_gate')
 result=gate.gate(db,args.reference,args.contract,args.metric_calculator,args.clone_adapter,args.clone_audit)
 if result['status']!='PASS':raise RuntimeError('integrated gate failed: '+result['status'])
 side=Path(args.sidecar)
 if side.exists():raise FileExistsError(side)
 payload={'seed':args.seed,'scenario':args.scenario,'users':args.users,'db_path':str(Path(db).resolve()),'db_sha256':hashlib.sha256(Path(db).read_bytes()).hexdigest(),'gate':result}
 side.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8');return payload
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for x in ['wrapper','generator','config','output','authorization','scenario','reference','contract','metric_calculator','clone_adapter','clone_audit','integration_gate','sidecar']:p.add_argument('--'+x.replace('_','-'),dest=x,required=True)
 p.add_argument('--users',type=int,required=True);p.add_argument('--seed',type=int,required=True);run(p.parse_args())
