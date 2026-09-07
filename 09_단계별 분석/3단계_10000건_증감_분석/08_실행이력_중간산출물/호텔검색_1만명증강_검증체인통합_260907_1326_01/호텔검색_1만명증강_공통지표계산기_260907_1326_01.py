#!/usr/bin/env python3
import argparse,hashlib,json,sqlite3
from pathlib import Path
import yaml
SUPPORTED='newref_v03_20260907'
def sha_text(s):return hashlib.sha256(s.encode()).hexdigest()
def load_contract(path):
 p=Path(path)
 if not p.is_file():raise FileNotFoundError(p)
 c=yaml.safe_load(p.read_text(encoding='utf8'))
 if c.get('definition_version')!=SUPPORTED:raise ValueError('unsupported definition version')
 if not isinstance(c.get('metrics'),dict):raise ValueError('metrics missing')
 return c
def calculate(db,contract,kind,metric_ids=None):
 cdef=load_contract(contract)
 ids=metric_ids or list(cdef['metrics'])
 unknown=set(ids)-set(cdef['metrics'])
 if unknown:raise KeyError('unsupported metric_id: '+','.join(sorted(unknown)))
 con=sqlite3.connect('file:'+Path(db).resolve().as_posix()+'?mode=ro',uri=True);con.execute('pragma query_only=on')
 out=[]
 for mid in ids:
  m=cdef['metrics'][mid];key='sql_'+kind
  if key not in m:raise KeyError(f'{mid} does not support {kind}')
  sql=m[key];row=con.execute(sql).fetchone();num=row[0] or 0;den=row[1]
  value=None if den in (None,0) else num/den
  out.append({'metric_id':mid,'definition_version':cdef['definition_version'],'grain':m['grain'],
   'numerator':num,'denominator':den,'value':value,'sql':sql,'sql_sha256':sha_text(sql)})
 con.close();return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--contract',required=True);p.add_argument('--kind',choices=['reference','synthetic'],required=True);p.add_argument('--output');a=p.parse_args()
 r=calculate(a.db,a.contract,a.kind);s=json.dumps(r,ensure_ascii=False,indent=2)
 if a.output:
  o=Path(a.output)
  if o.exists():raise FileExistsError(o)
  o.write_text(s,encoding='utf8')
 print(s)
