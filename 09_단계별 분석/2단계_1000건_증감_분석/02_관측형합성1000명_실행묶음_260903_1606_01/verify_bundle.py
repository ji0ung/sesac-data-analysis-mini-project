from pathlib import Path
import sys,json,hashlib,sqlite3
b=Path(sys.argv[1]);mp=next(b.glob('*매니페스트*.json'));m=json.loads(mp.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
bad=[x['path'] for x in m['artifacts'] if sha(b/x['path'])!=x['sha256']]
db=b/next(x['path'] for x in m['artifacts'] if x['role']=='synthetic SQLite')
c=sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True)
print('manifest_hash_mismatches=',bad)
print('integrity=',c.execute('pragma integrity_check').fetchone()[0])
print('rows=',{t:c.execute(f'select count(*) from "{t}"').fetchone()[0] for t in ['user','hotel','room','search','search_filter','search_result','event','booking']})
print('metadata=',dict(c.execute('select key,value from _generation_metadata')))
print('non_synthetic_email_domains=',c.execute("select count(*) from user where email not like ?",('%@example.invalid',)).fetchone()[0])
c.close();print('qa=',m['final_qa_status'],m['expansion_allowed'],m['G1_G5']);print('bundle_files=',len(list(b.iterdir())))
