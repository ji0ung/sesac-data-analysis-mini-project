"""Read-only, fresh-process query benchmarks. No generation code is executed."""
import gc, hashlib, json, os, pathlib, platform, random, sqlite3, statistics, subprocess, sys, threading, time
import psutil

OUT=pathlib.Path(__file__).resolve().parent
Q=lambda x:'"'+x.replace('"','""')+'"'

def connect(path):
    c=sqlite3.connect(pathlib.Path(path).as_uri()+'?mode=ro',uri=True)
    for pragma in ['query_only=on','cache_size=-8192','mmap_size=0','temp_store=MEMORY','threads=1','automatic_index=on']:
        c.execute('pragma '+pragma)
    return c

def definitions():
    a=json.loads((OUT/'audit_raw.json').read_text(encoding='utf-8'))
    profiles=[x for x in a['profiles'] if x['db']=='plain']
    tables=list(a['logical_equality'])
    queries={
      'event_type_group':{'sql':['select event_type,count(*) from event group by event_type order by event_type'],'mode':'stream'},
      'event_id_lookup':{'sql':["select event_id,event_type,hotel_id from event where event_id='SYN_E0500_00001'"],'mode':'stream'},
      'session_search':{'sql':["select search_id,total_result_count from search where session_id='SYN_S0500' order by search_time,search_id"],'mode':'stream'},
      'search_result_join':{'sql':["select r.result_rank,h.hotel_name from search_result r join hotel h on r.hotel_id=h.hotel_id where r.search_id=(select search_id from search where total_result_count>0 order by search_id limit 1) order by r.result_rank,h.hotel_name"],'mode':'stream'},
    }
    for name,textonly,mode in [('all_text_stream',True,'stream'),('all_columns_stream',False,'stream'),('all_columns_materialize',False,'materialize')]:
        queries[name]={'sql':[],'original_sql':[],'mode':mode}
        for t in tables:
            cols=[x for x in profiles if x['table']==t and (not textonly or x['declared_type']=='TEXT')]
            if not cols:continue
            expr=[Q(x['column']) for x in cols]
            orig=[('replace('+Q(x['column'])+",' KST','') AS "+Q(x['column'])) if (t,x['column']) in [('event','event_at'),('event','session_end_time'),('search','search_time'),('user','signup_at')] else Q(x['column']) for x in cols]
            queries[name]['sql'].append('select '+','.join(expr)+' from '+Q(t))
            queries[name]['original_sql'].append('select '+','.join(orig)+' from '+Q(t))
    return queries

def worker(label,name):
    inputs=json.loads((OUT/'inputs.json').read_text(encoding='utf-8'))
    defs=json.loads((OUT/'benchmark_queries.json').read_text(encoding='utf-8'))
    spec=defs[name];sqls=spec.get('original_sql',spec['sql']) if label=='original' else spec['sql']
    c=connect(inputs[label]);proc=psutil.Process();gc.collect()
    baseline=proc.memory_info().rss;peak=[baseline];stop=threading.Event()
    def sample():
        while not stop.wait(0.002):peak[0]=max(peak[0],proc.memory_info().rss)
    thread=threading.Thread(target=sample);thread.start()
    begin=time.perf_counter();cpu=time.process_time();rows=0;kept=[];timed_out=False
    c.set_progress_handler(lambda:int(time.perf_counter()-begin>30),10000)
    try:
        for sql in sqls:
            cur=c.execute(sql)
            if spec['mode']=='materialize':
                data=cur.fetchall();rows+=len(data);kept.append(data)
            else:
                while True:
                    batch=cur.fetchmany(5000)
                    if not batch:break
                    rows+=len(batch)
            peak[0]=max(peak[0],proc.memory_info().rss)
    except sqlite3.OperationalError as exc:
        if str(exc)!='interrupted':raise
        timed_out=True
    elapsed=time.perf_counter()-begin;cpu=time.process_time()-cpu
    peak[0]=max(peak[0],proc.memory_info().rss);stop.set();thread.join()
    # Result equivalence checked separately without adding hash cost to timed sections.
    c.close()
    print(json.dumps(dict(db=label,query=name,seconds=elapsed,cpu_seconds=cpu,rows=rows,rss_baseline=baseline,rss_peak=peak[0],rss_increment=peak[0]-baseline,timeout=timed_out)))

def run():
    defs=definitions();(OUT/'benchmark_queries.json').write_text(json.dumps(defs,indent=2),encoding='utf-8')
    inputs=json.loads((OUT/'inputs.json').read_text(encoding='utf-8'))
    # Prime OS file cache for all files equally, without altering DB or connection cache.
    for path in inputs.values():
        with open(path,'rb') as f:
            while f.read(1<<20):pass
    plans={};equality={}
    for label,path in inputs.items():
        c=connect(path);plans[label]={}
        for name,spec in defs.items():
            sqls=spec.get('original_sql',spec['sql']) if label=='original' else spec['sql']
            plans[label][name]=[c.execute('explain query plan '+sql).fetchall() for sql in sqls]
            if name not in ('all_columns_materialize',):
                hashes=[]
                for sql in sqls:
                    # Sort serialized row hashes, not query results: equivalence independent of storage order.
                    rh=[]
                    for row in c.execute(sql):rh.append(hashlib.sha256(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode()).digest())
                    hashes.append(hashlib.sha256(b''.join(sorted(rh))).hexdigest())
                equality.setdefault(name,{})[label]=hashes
        c.close()
    for name,dbs in equality.items():
        assert len(set(tuple(v) for v in dbs.values()))==1,(name,'result mismatch')
    (OUT/'benchmark_plans_and_equality.json').write_text(json.dumps({'plans':plans,'equality':equality},indent=2),encoding='utf-8')
    results=[];rng=random.Random(20260907)
    for name in defs:
        for trial in range(5):
            order=list(inputs);rng.shuffle(order)
            for label in order:
                r=subprocess.run([sys.executable,__file__,'--worker',label,name],capture_output=True,text=True,check=True,timeout=45)
                value=json.loads(r.stdout);value['trial']=trial+1;results.append(value)
        print('benchmark complete',name,flush=True)
        (OUT/'benchmark_trials.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    summary=[]
    for name in defs:
        for label in inputs:
            rr=[r for r in results if r['query']==name and r['db']==label]
            summary.append(dict(db=label,query=name,rows=rr[0]['rows'],seconds_median=statistics.median(r['seconds'] for r in rr),seconds_min=min(r['seconds'] for r in rr),seconds_max=max(r['seconds'] for r in rr),cpu_median=statistics.median(r['cpu_seconds'] for r in rr),rss_peak_median=statistics.median(r['rss_peak'] for r in rr),rss_increment_median=statistics.median(r['rss_increment'] for r in rr),timeouts=sum(r['timeout'] for r in rr)))
    env=dict(python=sys.version,sqlite=sqlite3.sqlite_version,platform=platform.platform(),ram_bytes=psutil.virtual_memory().total,logical_cpu_count=psutil.cpu_count(),runs=5,cache='OS cache primed; fresh SQLite connection in fresh process per run; no cold-cache claim',settings={'cache_size':-8192,'mmap_size':0,'temp_store':'MEMORY','threads':1,'automatic_index':1},rss='process RSS sampled every 2 ms plus final sample; baseline excluded in increment; Python interpreter included in absolute peak',timing='query execution plus fetching; excludes process startup, connect and result hashes')
    (OUT/'benchmark_summary.json').write_text(json.dumps({'environment':env,'summary':summary},indent=2),encoding='utf-8')
    print('BENCHMARK DONE',flush=True)

if __name__=='__main__':
    if len(sys.argv)>1:worker(sys.argv[2],sys.argv[3])
    else:run()
