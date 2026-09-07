"""New diagnostic only. Existing DBs and generation scripts are never written."""
import collections, csv, hashlib, json, os, pathlib, platform, re, sqlite3, sys, time

OUT = pathlib.Path(__file__).resolve().parent
ROOT = OUT.parents[1]
q = lambda s: '"' + s.replace('"', '""') + '"'

def ro(path):
    c = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    c.execute('pragma query_only=on')
    return c

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def paths():
    found=list(ROOT.rglob('*16K_*.sqlite'))
    found=[p for p in found if '260903_1606_01' in p.name]
    assert len(found)==1, found
    compact=found[0]
    plain=next(compact.parent.glob('*16K.sqlite'))
    original=next(p for p in compact.parent.glob('*260903_1606_01.sqlite') if not p.name.startswith('._'))
    return {'original':original,'plain':plain,'compact':compact}

def profile(c,t,kind,label):
    n=c.execute('select count(*) from '+q(t)).fetchone()[0]
    out=[]
    for col in c.execute('pragma table_xinfo('+q(t)+')').fetchall():
        name=col[1];x=q(name)
        a=c.execute('select count('+x+'),count(distinct '+x+'),'
            'count(case when typeof('+x+")='text' then 1 end),"
            'avg(case when typeof('+x+")='text' then length("+x+') end),'
            'max(case when typeof('+x+")='text' then length("+x+') end),'
            'sum(case when typeof('+x+")='text' then length(cast("+x+' as blob)) else 0 end),'
            'avg(case when typeof('+x+")='text' then length(cast("+x+' as blob)) end) '
            'from '+q(t)).fetchone()
        types=dict(c.execute('select typeof('+x+'),count(*) from '+q(t)+' group by typeof('+x+')'))
        out.append(dict(db=label,object_type=kind,table=t,column=name,declared_type=col[2],pk_order=col[5],not_null=bool(col[3]),default=col[4],rows=n,non_null=a[0],distinct=a[1],unique_ratio=a[1]/n if n else None,unique_nonnull_ratio=a[1]/a[0] if a[0] else None,null_ratio=(n-a[0])/n if n else None,text_rows=a[2],avg_text_chars=a[3],max_text_chars=a[4],text_utf8_bytes=a[5] or 0,avg_text_utf8_bytes=a[6],runtime_types=types))
    return out

def btree_sizes(path,c):
    ps=c.execute('pragma page_size').fetchone()[0]
    f=path.open('rb')
    def tree(root):
        todo=[root];seen=set()
        while todo:
            n=todo.pop()
            if n in seen:continue
            seen.add(n);f.seek((n-1)*ps);b=f.read(ps);o=100 if n==1 else 0
            kind=b[o];cnt=int.from_bytes(b[o+3:o+5],'big')
            if kind in (2,5):
                todo.append(int.from_bytes(b[o+8:o+12],'big'))
                for i in range(cnt):
                    pos=int.from_bytes(b[o+12+2*i:o+14+2*i],'big')
                    todo.append(int.from_bytes(b[pos:pos+4],'big'))
        return len(seen)*ps
    sizes={name:tree(root) for name,root in c.execute('select name,rootpage from sqlite_schema where rootpage>0')}
    sizes['sqlite_schema']=tree(1)
    f.close()
    # Only claim exact coverage when reachable btrees account for the entire file.
    return {'bytes':sizes,'accounted_bytes':sum(sizes.values()),'file_bytes':path.stat().st_size,'complete':sum(sizes.values())==path.stat().st_size}

def main():
    ps=paths();report={'sources':{},'profiles':[],'schema':{},'relations':[]}
    scripts=[ROOT/'sqlite_compact_lossless.py',*ps['compact'].parent.glob('*260903_1606_01.py'),*ps['compact'].parent.glob('*260903_1606_01.json')]
    report['protected_files']={str(p):digest(p) for p in [*ps.values(),*scripts]}
    for label,path in ps.items():
        c=ro(path)
        report['sources'][label]={'path':str(path),'bytes':path.stat().st_size,'sha256':digest(path),'pragmas':{k:c.execute('pragma '+k).fetchall() for k in ['page_size','page_count','freelist_count','integrity_check','encoding','foreign_keys']},'btree':btree_sizes(path,c)}
        schema=[]
        for kind,t,sql in c.execute("select type,name,sql from sqlite_schema order by type,name").fetchall():
            obj={'type':kind,'name':t,'sql':sql}
            if kind in ('table','view'):
                obj['columns']=c.execute('pragma table_xinfo('+q(t)+')').fetchall()
                obj['foreign_keys']=c.execute('pragma foreign_key_list('+q(t)+')').fetchall()
                obj['indexes']=c.execute('pragma index_list('+q(t)+')').fetchall()
                report['profiles'].extend(profile(c,t,kind,label))
            schema.append(obj)
        report['schema'][label]=schema
        c.close()
        print('profile complete',label,flush=True)
    c=ro(ps['compact']);p=ro(ps['plain'])
    logical=[x['name'] for x in report['schema']['compact'] if x['type']=='view']
    verified={}
    for t in logical:
        ca=p.execute('select * from '+q(t)+' order by rowid');cb=c.execute('select * from '+q(t));n=0;h=hashlib.sha256()
        while True:
            a=ca.fetchmany(5000);b=cb.fetchmany(5000)
            if a!=b:raise AssertionError((t,n,'logical values differ'))
            for row in a:h.update((json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode())
            n+=len(a)
            if not a:break
        verified[t]={'rows':n,'sha256_rows':h.hexdigest(),'exact':True}
    report['logical_equality']=verified
    mapping=[]
    for obj in report['schema']['compact']:
        if obj['type']!='view':continue
        for dictionary,column in re.findall(r'\(select value from "(_dict_[^"]+)" where id=p\."([^"]+)"\)',obj['sql']):
            mapping.append((obj['name'],column,dictionary))
    report['dictionary_effects']=[]
    def intbytes(v):
        if v in (0,1):return 0
        for n in [1,2,3,4,6,8]:
            if -(1<<(8*n-1))<=v<(1<<(8*n-1)):return n
    for t,col,di in mapping:
        physical='_data_'+t
        n,orphans=c.execute('select count(*),sum(case when d.id is null then 1 else 0 end) from '+q(physical)+' p left join '+q(di)+' d on p.'+q(col)+'=d.id where p.'+q(col)+' is not null').fetchone()
        codes=c.execute('select '+q(col)+',count(*) from '+q(physical)+' where '+q(col)+' is not null group by '+q(col)).fetchall()
        raw=next(x for x in report['profiles'] if x['db']=='plain' and x['table']==t and x['column']==col)
        dirows=c.execute('select id,value from '+q(di)).fetchall()
        codebytes=sum(intbytes(k)*v for k,v in codes)
        dictionarybytes=report['sources']['compact']['btree']['bytes'][di]
        report['dictionary_effects'].append({'table':t,'column':col,'dictionary':di,'rows_nonnull':n,'distinct':len(dirows),'raw_text_bytes':raw['text_utf8_bytes'],'code_payload_bytes':codebytes,'dictionary_page_bytes':dictionarybytes,'estimated_net_payload_saving':raw['text_utf8_bytes']-codebytes-dictionarybytes,'dictionary_text_bytes':sum(len(v.encode()) for _,v in dirows),'orphans':orphans or 0,'duplicate_values':len(dirows)-len(set(v for _,v in dirows))})
        report['relations'].append(dict(source_table=physical,source_column=col,target_table=di,target_column='id',evidence='view SQL',declared_fk=False,non_null=n,orphans=orphans or 0))
    # Business relations verified on identical decoded values, using bounded parent sets.
    relations=[('room','hotel_id','hotel','hotel_id'),('search_filter','search_id','search','search_id'),('search_result','search_id','search','search_id'),('search_result','hotel_id','hotel','hotel_id'),('search_result','room_id','room','room_id'),('event','user_id','user','user_id'),('event','hotel_id','hotel','hotel_id'),('event','search_id','search','search_id'),('event','search_filter_id','search_filter','search_filter_id'),('event','session_id','search','session_id'),('booking','user_id','user','user_id'),('booking','hotel_id','hotel','hotel_id'),('booking','room_id','room','room_id')]
    for st,sc,tt,tc in relations:
        parents={r[0] for r in p.execute('select distinct '+q(tc)+' from '+q(tt)) if r[0] is not None}
        counts=p.execute('select '+q(sc)+',count(*) from '+q(st)+' where '+q(sc)+' is not null group by '+q(sc)).fetchall()
        report['relations'].append(dict(source_table=st,source_column=sc,target_table=tt,target_column=tc,evidence='generator code + values; logical relation, not declared FK',declared_fk=False,non_null=sum(n for _,n in counts),orphans=sum(n for v,n in counts if v not in parents)))
    report['relations'].append(dict(source_table='_data_event',source_column='_session_ref',target_table='_sessions',target_column='id',evidence='view SQL',declared_fk=False,non_null=c.execute('select count(_session_ref) from _data_event').fetchone()[0],orphans=c.execute('select count(*) from _data_event e left join _sessions s on e._session_ref=s.id where e._session_ref is not null and s.id is null').fetchone()[0]))
    report['generator_schema_lookup']={label:{t:conn.execute("select sql from sqlite_master where type='table' and name=?",(t,)).fetchone() is not None for t in logical} for label,conn in [('plain',p),('compact',c)]}
    report['date_ranges']={t+'.'+col:p.execute('select min('+q(col)+'),max('+q(col)+') from '+q(t)).fetchone() for t,col in [('event','event_at'),('event','session_end_time'),('search','search_time'),('search','checkin_date'),('search','checkout_date'),('user','signup_at')]}
    # Evaluate existing view expressions against scalar boundary values using SELECT only.
    tests=[('user',10000,"'SYN_U'||substr(printf('%04d',?),1,4)",'SYN_U10000'),('event',1000000001,"'SYN_E'||substr(printf('%09d',?),1,4)||'_'||substr(printf('%09d',?),5,5)",'SYN_E10000_00001'),('search',10000001,"'SYN_Q'||substr(printf('%07d',?),1,4)||'_'||substr(printf('%07d',?),5,3)",'SYN_Q10000_001'),('room',25210,"'R'||substr(printf('%05d',?),1,4)||'_'||substr(printf('%05d',?),5,1)",'R0252_10')]
    report['boundary_tests']=[]
    for t,n,expr,want in tests:
        actual=c.execute('select '+expr,[n]*expr.count('?')).fetchone()[0]
        report['boundary_tests'].append(dict(object=t,integer=n,expected=want,actual=actual,pass_test=actual==want))
    report['format_change']={'SYN_U10000_matches_current_4digit_regex':bool(re.fullmatch(r'SYN_U\d{4}','SYN_U10000'))}
    report['uniqueness']={t:p.execute('select count(*),count('+q(t+'_id')+'),count(distinct '+q(t+'_id')+') from '+q(t)).fetchone() for t in logical}
    report['constraints']={'session_conflicts':p.execute('select count(*) from (select session_id from event group by session_id having count(distinct user_id)>1 or count(distinct session_end_time)>1)').fetchone()[0],'filter_search_distinct':p.execute('select count(*),count(distinct search_id) from search_filter').fetchone(),'time_null_flags':c.execute('select _end_present,count(*) from _data_event group by _end_present').fetchall()}
    c.close();p.close()
    report['protected_files_unchanged']={name:digest(pathlib.Path(name))==before for name,before in report['protected_files'].items()}
    (OUT/'audit_raw.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'inputs.json').write_text(json.dumps({k:str(v.resolve()) for k,v in ps.items()},ensure_ascii=False,indent=2),encoding='utf-8')
    print('DONE',len(report['profiles']),'column profiles',flush=True)

if __name__=='__main__':main()
