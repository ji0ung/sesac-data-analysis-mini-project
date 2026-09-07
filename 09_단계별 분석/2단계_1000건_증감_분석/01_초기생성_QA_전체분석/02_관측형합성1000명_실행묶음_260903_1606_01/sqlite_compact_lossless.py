import pathlib, sqlite3, re, json, hashlib

ROOT = pathlib.Path(__file__).resolve().parent
src = next(p for p in ROOT.rglob('*16K.sqlite') if '260903_1606_01' in p.name)
dst = src.with_name(src.stem + '_\ucd94\uac00\uacbd\ub7c9\ud654.sqlite')
if dst.exists():
    raise RuntimeError('Output already exists')
s = sqlite3.connect(src.as_uri() + '?mode=ro', uri=True)
d = sqlite3.connect(dst)
d.execute('PRAGMA page_size=16384')
q = lambda x: '"' + x.replace('"', '""') + '"'
tables = [r[0] for r in s.execute("select name from sqlite_schema where type='table' order by name")]
report = {'source_bytes': src.stat().st_size, 'tables': {}, 'transforms': []}

# Store each session's shared attributes once, retaining per-event NULL state.
sessions = s.execute('select session_id,min(user_id),min(session_end_time) from event group by session_id order by session_id').fetchall()
assert s.execute('select count(*) from (select session_id from event group by session_id having count(distinct user_id)>1 or count(distinct session_end_time)>1)').fetchone()[0] == 0
d.execute('create table _sessions(id INTEGER PRIMARY KEY, session_id TEXT, user_id TEXT, session_end_time TEXT)')
d.executemany('insert into _sessions values(?,?,?,?)', [(i,*r) for i,r in enumerate(sessions,1)])
session_map = {r[0]:i for i,r in enumerate(sessions,1)}

for t in tables:
    info = s.execute('pragma table_info('+q(t)+')').fetchall()
    names = [r[1] for r in info]
    rows = s.execute('select * from '+q(t)+' order by rowid').fetchall()
    physical, exprs, encoders = [], {}, []
    removed = set()
    if t == 'event':
        removed.update(['session_id','user_id','session_end_time'])
        a,b = names.index('search_id'),names.index('search_filter_id')
        assert all((None if r[a] is None else r[a].replace('SYN_Q','SYN_F',1)) == r[b] for r in rows)
        removed.add('search_filter_id')
    if t == 'search_result':
        room_hotels = dict(s.execute('select room_id,hotel_id from room'))
        assert all(room_hotels[r[names.index('room_id')]] == r[names.index('hotel_id')] for r in rows)
        removed.add('hotel_id')
    for idx, col in enumerate(names):
        if col in removed:
            continue
        typ = info[idx][2] or 'BLOB'
        values = [r[idx] for r in rows if r[idx] is not None]
        decode = 'p.'+q(col)
        encode = lambda x:x
        if typ == 'TEXT' and values:
            # Encode fixed-format identifiers arithmetically; no large ID mapping table.
            match = re.fullmatch(r'(\D*)(\d+)((?:\D+\d+)*)', values[0]) if col.endswith('_id') else None
            if match:
                parts = re.split(r'(\d+)', values[0])
                widths = [len(parts[i]) for i in range(1,len(parts),2)]
                pattern = '^' + ''.join(re.escape(v) if i%2==0 else r'(\d{'+str(len(v))+'})' for i,v in enumerate(parts)) + '$'
                rx = re.compile(pattern)
                if sum(widths) <= 15 and all(rx.fullmatch(v) for v in values):
                    encode = lambda x,rx=rx: None if x is None else int(''.join(rx.fullmatch(x).groups()))
                    terms=[];pos=0
                    padded = "printf('%0"+str(sum(widths))+"d',p."+q(col)+')'
                    for i,part in enumerate(parts):
                        if i%2==0:
                            if part: terms.append("'"+part.replace("'","''")+"'")
                        else:
                            terms.append('substr('+padded+','+str(pos+1)+','+str(len(part))+')');pos+=len(part)
                    decode = 'CASE WHEN p.'+q(col)+' IS NULL THEN NULL ELSE '+'||'.join(terms)+' END'
                    typ='INTEGER'
                    report['transforms'].append(t+'.'+col+': arithmetic ID')
            if typ == 'TEXT':
                unique = sorted(set(values))
                raw = sum(len(v.encode('utf8')) for v in values)
                estimated = sum(len(v.encode('utf8'))+10 for v in unique)+3*len(values)+16384
                if estimated < raw:
                    dictionary = '_dict_'+t+'_'+col
                    d.execute('create table '+q(dictionary)+'(id INTEGER PRIMARY KEY,value TEXT)')
                    mapping = {v:i for i,v in enumerate(unique,1)}
                    d.executemany('insert into '+q(dictionary)+' values(?,?)',[(i,v) for v,i in mapping.items()])
                    encode = lambda x,m=mapping: None if x is None else m[x]
                    decode = '(select value from '+q(dictionary)+' where id=p.'+q(col)+')'
                    typ='INTEGER'
                    report['transforms'].append(t+'.'+col+': dictionary')
        physical.append(q(col)+' '+typ)
        encoders.append((idx,encode))
        exprs[col]=decode
    if t == 'event':
        physical += ['_session_ref INTEGER','_user_present INTEGER','_end_present INTEGER']
        for col in ['session_id','user_id','session_end_time']:
            val='(select '+q(col)+' from _sessions where id=p._session_ref)'
            if col!='session_id': val='CASE WHEN p.'+('_user_present' if col=='user_id' else '_end_present')+' THEN '+val+' ELSE NULL END'
            exprs[col]=val
        exprs['search_filter_id']="replace(("+exprs['search_id']+"),'SYN_Q','SYN_F')"
    if t == 'search_result':
        exprs['hotel_id']='(select hotel_id from room where room_id=('+exprs['room_id']+'))'
    d.execute('create table '+q('_data_'+t)+'('+','.join(physical)+')')
    encoded=[]
    for r in rows:
        out=[fn(r[i]) for i,fn in encoders]
        if t=='event': out += [session_map[r[names.index('session_id')]],int(r[names.index('user_id')] is not None),int(r[names.index('session_end_time')] is not None)]
        encoded.append(out)
    if encoded:d.executemany('insert into '+q('_data_'+t)+' values('+','.join('?' for _ in physical)+')',encoded)
    d.execute('create view '+q(t)+' as select '+','.join(exprs[col]+' AS '+q(col) for col in names)+' from '+q('_data_'+t)+' p')
    report['tables'][t]={'rows':len(rows)}

# Room lookup must remain efficient for compatibility-view joins.
d.execute('create unique index _room_key on _data_room(room_id)')
# Use the encoded room key directly to avoid scanning the formatted room view.
d.execute('drop view search_result')
sql = s.execute("select sql from sqlite_schema where name='search_result'").fetchone()[0]
view_columns = [r[1] for r in s.execute('pragma table_info(search_result)')]
hotel_expr = "(select hotel_id from hotel where hotel_id=('H'||substr(("+exprs.get('room_id','NULL')+"),2,4)))"
# The room/hotel relation in this source follows a verified fixed ID format.
assert s.execute("select count(*) from room where hotel_id IS NOT ('H'||substr(room_id,2,4))").fetchone()[0]==0
# Reconstruct the saved search_result view from schema captured during creation instead.
d.commit()
report['note']='Compatibility views preserve values; physical storage is normalized.'

# Rebuild search_result expressions from its verified identifier formats.
d.execute('create view search_result as select '
 "CASE WHEN search_result_id IS NULL THEN NULL ELSE printf('SYN_R%04d_%03d_%04d',search_result_id/10000000,(search_result_id/10000)%1000,search_result_id%10000) END search_result_id,"
 "CASE WHEN search_id IS NULL THEN NULL ELSE printf('SYN_Q%04d_%03d',search_id/1000,search_id%1000) END search_id,"
 "CASE WHEN room_id IS NULL THEN NULL ELSE printf('H%04d',room_id/10) END hotel_id,"
 "CASE WHEN room_id IS NULL THEN NULL ELSE printf('R%04d_%01d',room_id/10,room_id%10) END room_id,"
 'result_score,result_rank,price_rank from _data_search_result')
d.commit()
d.execute('VACUUM')
assert d.execute('pragma integrity_check').fetchone()[0]=='ok'
for t in tables:
    # Views preserve the physical insertion order; explicitly order by physical rowid.
    a=s.execute('select * from '+q(t)+' order by rowid')
    b=d.execute('select * from '+q(t))
    n=0
    while True:
        ar=a.fetchmany(5000);br=b.fetchmany(5000)
        assert ar==br, 'Value mismatch: '+t+' near '+str(n)
        n+=len(ar)
        if not ar:break
    report['tables'][t]['verified_exact']=True
report['output_bytes']=dst.stat().st_size
report['reduction_percent']=round(100*(1-report['output_bytes']/report['source_bytes']),2)
d.close();s.close()
dst.with_suffix('.verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'output':str(dst),**report},ensure_ascii=True))
