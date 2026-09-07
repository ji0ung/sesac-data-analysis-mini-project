"""Conditional scale calculations and scalar/read-only probes; creates no augmented DB."""
import ast, collections, hashlib, json, pathlib, re, sqlite3, statistics, sys, time
import pandas as pd

OUT=pathlib.Path(__file__).resolve().parent
ROOT=OUT.parents[1]
Q=lambda x:'"'+x.replace('"','""')+'"'

def main():
    a=json.loads((OUT/'audit_raw.json').read_text(encoding='utf-8'))
    p=pathlib.Path(a['sources']['plain']['path']);c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);c.execute('pragma query_only=on')
    profiles={(r['table'],r['column']):r for r in a['profiles'] if r['db']=='plain'}
    effects=a['dictionary_effects'];out={'assumption':'Conditional: 1000 users/sessions to 10000 users/sessions, same per-session behavior frequency, fixed hotel/room catalogs; not an approved generation specification.'}
    dynamic=['user','search','search_filter','search_result','event']
    out['row_scenario']={t:{'now':v['rows'],'x10_users':v['rows']*(10 if t in dynamic else 1)} for t,v in a['logical_equality'].items()}
    scenarios=[]
    for e in effects:
        x=profiles[(e['table'],e['column'])];factor=10 if e['table'] in dynamic else 1
        n=e['rows_nonnull']*factor;d=e['distinct'];L=e['dictionary_text_bytes']/d
        ds={'same_vocabulary':d,'same_unique_ratio':min(n,d*factor),'all_new_values':n}
        one={'table':e['table'],'column':e['column'],'dictionary':e['dictionary'],'N_nonnull_10k':n,'mean_dictionary_text_bytes':L,'cases':{}}
        for name,D in ds.items():
            width=1 if D<=127 else 2 if D<=32767 else 3 if D<=8388607 else 4
            # Approximate table overhead 10 bytes/entry plus 16 KiB root, not measured file size.
            dictionary=D*(L+10)+16384
            text=n*x['avg_text_utf8_bytes']
            one['cases'][name]={'distinct':D,'dictionary_bytes_estimate':dictionary,'code_bytes_upper':n*width,'net_bytes_estimate':text-dictionary-n*width,'code_width_upper':width}
        scenarios.append(one)
    out['dictionary_scenarios']=scenarios
    sizes={k:v['btree']['bytes'] for k,v in a['sources'].items()}
    scale={}
    for label,b in sizes.items():
        total=0
        for name,value in b.items():
            if label=='compact':
                mult=10 if name in ['_data_'+t for t in dynamic]+['_sessions','_dict_event_event_at'] else 1
            else:
                mult=10 if name in dynamic or any(name=='sqlite_autoindex_'+t+'_1' for t in dynamic) or name.startswith('idx_syn_') else 1
            total+=value*mult
        scale[label]={'page_linear_estimate_bytes':total,'method':'Current object page bytes times 10 for behavioral objects; static catalog and stable dictionaries fixed. compact event_at dictionary grows 10x. No output file generated.'}
    out['db_scale']=scale
    timestamp=next(e for e in scenarios if e['column']=='event_at')
    out['compact_all_unique_timestamp_estimate_bytes']=scale['compact']['page_linear_estimate_bytes']+timestamp['cases']['all_new_values']['dictionary_bytes_estimate']-timestamp['cases']['same_unique_ratio']['dictionary_bytes_estimate']
    out['temporal_qa']={'search_rows':c.execute('select count(*) from search').fetchone()[0],'checkin_before_search_date':c.execute('select count(*) from search where date(checkin_date)<date(search_time)').fetchone()[0]}
    # Directly demonstrate the generator's table-only source schema lookup, without executing DDL.
    cc=sqlite3.connect(pathlib.Path(a['sources']['compact']['path']).as_uri()+'?mode=ro',uri=True)
    try:cc.execute("select sql from sqlite_master where type='table' and name=?",('user',)).fetchone()[0]
    except Exception as e:out['generator_schema_error']=type(e).__name__+': '+str(e)
    cc.close()
    out['source_missing_generated_columns']={t:['data_origin'] for t in ['user','search','search_filter','search_result','event'] if 'data_origin' not in [r[1] for r in c.execute('pragma table_info('+Q(t)+')')]}
    out['pandas_input_memory_bytes']={};frames={}
    for t in ['search','search_filter','search_result','event']:
        df=pd.read_sql_query('select * from '+Q(t),c);frames[t]=df
        out['pandas_input_memory_bytes'][t]=int(df.memory_usage(index=True,deep=True).sum())
    # Cost of exactly the filtering primitives visible in build(), measured on actual source frames.
    tasks=[('search_by_session','search','session_id',10000),('filter_by_search','search_filter','search_id',69000),('results_by_search','search_result','search_id',69000),('events_by_session','event','session_id',10000)]
    costs=[]
    for name,t,col,times in tasks:
        df=frames[t];keys=list(df[col].dropna().unique());keys=keys[:min(30,len(keys))]
        samples=[]
        for _ in range(5):
            begin=time.perf_counter()
            for key in keys:selection=df[df[col]==key]
            samples.append((time.perf_counter()-begin)/len(keys))
        costs.append({'operation':name,'source_rows':len(df),'keys_sampled':len(keys),'median_seconds_per_call':statistics.median(samples),'calls_scenario':times,'estimated_seconds':statistics.median(samples)*times,'element_comparisons_scenario':len(df)*times})
    # One results.isin() scan per output session in the existing exposed-set expression.
    groups=list(frames['search'].groupby('session_id'))[:30];samples=[]
    for _ in range(5):
        begin=time.perf_counter()
        for _,g in groups:selection=frames['search_result'][frames['search_result'].search_id.isin(g.search_id)]
        samples.append((time.perf_counter()-begin)/len(groups))
    costs.append({'operation':'results_isin_session_searches','source_rows':len(frames['search_result']),'keys_sampled':len(groups),'median_seconds_per_call':statistics.median(samples),'calls_scenario':10000,'estimated_seconds':statistics.median(samples)*10000,'element_comparisons_scenario':len(frames['search_result'])*10000})
    out['generator_filter_cost_model']=costs
    # Structural Python dict overhead only, excluding values, keys, lists and source frames.
    out['output_dict_shell_lower_bound_bytes']=sum(sys.getsizeof(dict.fromkeys([*frames[t].columns,'data_origin']))*out['row_scenario'][t]['x10_users'] for t in frames)
    out['id_boundary_and_rebuild']={
        'current_user_view_10000':a['boundary_tests'][0],
        'mixed_width_encoder_accepts':all(re.fullmatch(r'SYN_Q\d{4}_\d{3}',v) for v in ['SYN_Q0001_001','SYN_Q10000_001']),
        'hardcoded_result_view_if_search_id_stored_as_text':c.execute("select printf('SYN_Q%04d_%03d',?/1000,?%1000)",('SYN_Q10000_001','SYN_Q10000_001')).fetchone()[0],
        'existing_user_ids_reused_if_i_restarts_at_one':c.execute("select count(*) from user where user_id between 'SYN_U0001' and 'SYN_U1000'").fetchone()[0],
    }
    c.close()
    out['protected_files_unchanged']={path:hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()==sha for path,sha in a['protected_files'].items()}
    (OUT/'augmentation_risk_model.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=True))

if __name__=='__main__':main()
