from pathlib import Path
import sqlite3,json,hashlib,collections
root=Path.cwd();dest=root/'05_발표자료/팀프로젝트/2026/09/호텔검색_최종대시보드_20260908_v02_강사피드백_보고서반영'
db=next((root/'09_단계별 분석/3단계_10000건_증감_분석/02_증강_데이터').rglob('*탐색용AB10000*.sqlite'))
source_path=str(db.relative_to(root))
if db.stat().st_size<1024:
 db=root/'.git/lfs/objects/f6/de/f6de5834ea326bb165efdd16e73ba4b1ff3939d1c8ecce27b3517d55b2a5819a'
assert db.stat().st_size==790736896
sha=hashlib.file_digest(db.open('rb'),'sha256').hexdigest();assert sha=='f6de5834ea326bb165efdd16e73ba4b1ff3939d1c8ecce27b3517d55b2a5819a'
c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('pragma query_only=ON')
sessions={r['session_id']:dict(r) for r in c.execute('SELECT x.session_id,x.user_id,x.started_at,x.ended_at,u.sample_stratum FROM SessionSynthetic x JOIN UserSynthetic u USING(user_id)')}
clicked={r[0] for r in c.execute("SELECT DISTINCT session_id FROM ActionEvent WHERE event_type='hotel_click'")}
searches=[dict(r) for r in c.execute('SELECT s.*, f.price,f.amenity_count FROM Search s JOIN SearchFilter f USING(search_id) ORDER BY session_id,search_sequence')]
by=collections.defaultdict(list)
for r in searches:by[r['session_id']].append(r)
for sid,ss in sessions.items():
 rows=by[sid];ss['searches']=len(rows);ss['zero']=sum(r['total_result_count']==0 for r in rows);ss['final_positive']=rows[-1]['total_result_count']>0;ss['first_zero']=rows[0]['total_result_count']==0;ss['clicked']=sid in clicked;ss['profile']=dict(x.split('=',1) for x in ss['sample_stratum'].split('|'))
 ss['experience']=('처음 0건·이후 회복' if any(r['total_result_count']>0 for r in rows) else '처음 0건·끝까지 미회복') if ss['first_zero'] else ('첫 결과 있음·클릭' if ss['clicked'] else '첫 결과 있음·미클릭')
start=min(r['search_time'] for r in searches);end=max(r['search_time'] for r in searches)
days={r['search_time'][:10] for r in searches};grain='월' if len(days)>45 else '일' if len(days)>1 else '시간';cut={'월':7,'일':10,'시간':13}[grain]
trend={}
for r in searches:
 k=r['search_time'][:cut];g=trend.setdefault(k,{'label':k,'searches':0,'zero':0,'users':set(),'entries':0});g['searches']+=1;g['zero']+=r['total_result_count']==0;g['users'].add(sessions[r['session_id']]['user_id'])
for ss in sessions.values():
 k=ss['started_at'][:cut];g=trend.setdefault(k,{'label':k,'searches':0,'zero':0,'users':set(),'entries':0});g['entries']+=1
for v in trend.values():v['users']=len(v['users'])
def group_sessions(key):
 out=[]
 for name in dict.fromkeys(key(x) for x in sessions.values()):
  a=[x for x in sessions.values() if key(x)==name];n=len(a);q=sum(x['searches'] for x in a);z=sum(x['zero'] for x in a);ez=sum(x['zero']>0 for x in a)
  out.append({'label':name,'users':n,'share':n/len(sessions)*100,'searches':q,'avg':q/n,'zero':z,'zero_rate':z/q*100,'zero_users':ez,'recovered_users':sum(x['zero']>0 and x['final_positive'] for x in a),'clicked':sum(x['clicked'] for x in a)})
 return out
exp=group_sessions(lambda x:x['experience']);profiles={dim:group_sessions(lambda x:x['profile'][dim]) for dim in ['price','opt','region']}
filters={}
for r in searches:
 label=('가격+옵션' if r['amenity_count']>0 else '가격만') if r['price'] is not None else ('옵션만' if r['amenity_count']>0 else '둘 다 미설정')
 g=filters.setdefault(label,{'label':label,'searches':0,'zero':0});g['searches']+=1;g['zero']+=r['total_result_count']==0
for g in filters.values():g['zero_rate']=g['zero']/g['searches']*100
seq=[]
for i in range(1,max(len(v) for v in by.values())+1):
 a=[v[i-1] for v in by.values() if len(v)>=i];seq.append({'label':str(i),'users':len(a),'zero':sum(r['total_result_count']==0 for r in a)})
counts={'users':len({s['user_id'] for s in sessions.values()}),'sessions':len(sessions),'searches':len(searches),'zero':sum(r['total_result_count']==0 for r in searches),'clicked_users':len(clicked),'zero_users':sum(s['zero']>0 for s in sessions.values()),'final_recovered':sum(s['zero']>0 and s['final_positive'] for s in sessions.values()),'first_zero':sum(s['first_zero'] for s in sessions.values())}
assert counts['users']==10000 and counts['searches']==65355 and counts['zero']==30614 and counts['final_recovered']==4936
assert sum(r['searches'] for r in trend.values())==65355 and sum(r['users'] for r in exp)==10000
keyword_rows=[dict(r) for r in c.execute('SELECT query_text label,COUNT(*) n FROM Search WHERE search_sequence=1 GROUP BY query_text ORDER BY n DESC,query_text')]
clicked_searches={r[0] for r in c.execute("SELECT DISTINCT search_id FROM ActionEvent WHERE event_type='hotel_click' AND search_id IS NOT NULL")}
funnel={'zero':counts['zero'],'followup':0,'recovered':0,'recovered_click':0}
for rows in by.values():
 for current,nxt in zip(rows,rows[1:]):
  if current['total_result_count']==0:
   funnel['followup']+=1
   if nxt['total_result_count']>0:
    funnel['recovered']+=1;funnel['recovered_click']+=nxt['search_id'] in clicked_searches
assert sum(x['n'] for x in keyword_rows)==10000
assert funnel['followup']==29184 and funnel['recovered']==5611
# Cohorts describe observed synthetic search paths, not randomized treatment groups.
cohort_names=['첫 검색 결과 있음','첫 0건·재시도 후 회복','첫 0건·재시도 후 미회복','첫 0건·재시도 없이 종료']
cohort_rows=[]
for label in cohort_names:
 selected=[]
 for sid,ss in sessions.items():
  rows=by[sid]
  group='첫 검색 결과 있음' if not ss['first_zero'] else ('첫 0건·재시도 없이 종료' if len(rows)==1 else ('첫 0건·재시도 후 회복' if any(r['total_result_count']>0 for r in rows[1:]) else '첫 0건·재시도 후 미회복'))
  if group==label:selected.append(rows)
 steps=[]
 for i in range(31):
  active=[r for r in selected if len(r)>i];has_next=[r for r in active if len(r)>i+1];zero_next=[r for r in has_next if r[i]['total_result_count']==0]
  recovered=sum(r[i+1]['total_result_count']>0 for r in zero_next)
  steps.append({'step':i+1,'reach':{'n':len(active),'d':len(selected)},'end':{'n':len(active)-len(has_next),'d':len(active)},'retry':{'n':len(has_next),'d':len(active)},'recovery':{'n':recovered,'d':len(zero_next)}})
 cohort_rows.append({'label':label,'users':len(selected),'steps':steps})
assert sum(x['users'] for x in cohort_rows)==10000
for g in cohort_rows:
 assert sum(x['end']['n'] for x in g['steps'])==g['users']
 for x in g['steps']:assert x['end']['n']+x['retry']['n']==x['end']['d']
positive_detail=c.execute("SELECT COUNT(DISTINCT e.search_id) FROM ActionEvent e JOIN Search s USING(search_id) WHERE e.event_type='hotel_detail_view' AND s.total_result_count>0").fetchone()[0]
assert positive_detail==6834
positive_detail_ids={r[0] for r in c.execute("SELECT DISTINCT e.search_id FROM ActionEvent e JOIN Search s USING(search_id) WHERE e.event_type='hotel_detail_view' AND s.total_result_count>0")}
assert positive_detail_ids=={r['search_id'] for r in searches if r['total_result_count']>0 and r['search_id'] in clicked_searches}
kpi_baseline={'searches':len(searches),'positive_searches':len(searches)-counts['zero'],'zero_searches':counts['zero'],'detail_searches':positive_detail,'sessions':len(sessions),'booking_rows':c.execute('SELECT COUNT(*) FROM Booking').fetchone()[0]}
# Exact initial options, keyword-topic conversion and within-session search continuation.
import statistics,csv
for sid,ss in sessions.items():
 ss['initial_options']=by[sid][0]['amenity_count']
 ss['topic']={'business':'업무·출장 표현','family':'가족 표현','weekend':'주말 표현','hotel':'일반 숙소 탐색','stay':'일반 숙소 탐색'}[by[sid][0]['query_text']]
profiles['opt']=sorted(group_sessions(lambda x:str(x['initial_options'])),key=lambda x:int(x['label']))
def distribution(values):
 values=sorted(values);q=statistics.quantiles(values,n=4,method='inclusive')
 return dict(min=values[0],q1=q[0],median=statistics.median(values),q3=q[2],max=values[-1],mean=statistics.mean(values))
option_summary=distribution([x['initial_options'] for x in sessions.values()])
option_boxes=[dict(label=str(k),users=sum(x['initial_options']==k for x in sessions.values()),**distribution([x['searches'] for x in sessions.values() if x['initial_options']==k])) for k in range(4)]
def conversion_groups(key):
 result=[]
 for g in group_sessions(key):
  selected=[r for sid,ss in sessions.items() if key(ss)==g['label'] for r in by[sid]]
  g['positive']=sum(r['total_result_count']>0 for r in selected)
  g['detail']=sum(r['search_id'] in clicked_searches and r['total_result_count']>0 for r in selected)
  result.append(g)
 return result
topic_conversion=conversion_groups(lambda x:x['topic'])
option_conversion=sorted(conversion_groups(lambda x:str(x['initial_options'])),key=lambda x:int(x['label']))
retention=[]
for day in sorted({ss['started_at'][:10] for ss in sessions.values()}):
 cohort=[ss for ss in sessions.values() if ss['started_at'][:10]==day]
 retention.append(dict(day=day,users=len(cohort),steps=[sum(ss['searches']>=n for ss in cohort) for n in range(1,11)]))
transitions={}
for rows in by.values():
 for a,b in zip(rows,rows[1:]):
  if a['total_result_count']!=0:continue
  changed=a['price']!=b['price'] or a['amenity_count']!=b['amenity_count']
  key='가격·옵션 변경' if changed else '가격·옵션 유지'
  g=transitions.setdefault(key,dict(label=key,n=0,recovered=0,detail=0));g['n']+=1
  g['recovered']+=b['total_result_count']>0;g['detail']+=b['total_result_count']>0 and b['search_id'] in clicked_searches
# Original v03 Japan-city context: independent population, never relabel generated region codes.
original=list(csv.DictReader((root/'03_데이터모델링/현행데이터/search_2026-09-03_v03_비식별.csv').open(encoding='utf-8-sig')))
assert len(original)==296 and all(r['invalid_stay_date_flag'] in ['0','1'] for r in original)
assert sum(r['invalid_stay_date_flag']=='1' for r in original)==9
city_names={'Tokyo':'도쿄','Osaka':'오사카','Kyoto':'교토','Fukuoka':'후쿠오카','Sapporo':'삿포로'}
city_names['']='지역 미설정'
for r in original:r['city']=r['destination'].split(' · ')[0]
assert set(r['city'] for r in original)<=set(city_names)
cities=[]
for code,label in city_names.items():
 rows=[r for r in original if r['city']==code]
 cities.append(dict(code=code,label=label,n=len(rows),zero=sum(int(r['total_result_count'])==0 for r in rows)))
original_by=collections.defaultdict(list)
for r in original:original_by[r['session_id']].append(r)
city_transitions=[]
for code,label in city_names.items():
 pairs=[]
 for rows in original_by.values():
  rows=sorted(rows,key=lambda r:(r['search_time'],r['search_id']))
  pairs.extend((a,b) for a,b in zip(rows,rows[1:]) if a['city']==code and int(a['total_result_count'])==0 and a['destination']!=b['destination'])
 city_transitions.append(dict(label=label,n=len(pairs),recovered=sum(int(b['total_result_count'])>0 for a,b in pairs)))
original_period=[min(r['search_time'] for r in original),max(r['search_time'] for r in original)]
ab_daily=[dict(r) for r in c.execute("SELECT substr(s.search_time,1,10) day,u.sample_set_type arm,COUNT(*) searches,SUM(s.total_result_count=0) zero FROM Search s JOIN SessionSynthetic x USING(session_id) JOIN UserSynthetic u ON x.user_id=u.user_id GROUP BY 1,2 ORDER BY 1,2")]
out={'ab_daily':ab_daily,'option_summary' :option_summary,'option_boxes':option_boxes,'topic_conversion':topic_conversion,'option_conversion':option_conversion,'retention':retention,'condition_transitions':list(transitions.values()),'cities':cities,'city_transitions':city_transitions,'original_period':original_period,'source':source_path,'sha256':sha,'start':start,'end':end,'grain':grain,'counts':counts,'trend':sorted(trend.values(),key=lambda r:r['label']),'experience':exp,'profiles':profiles,'filters':list(filters.values()),'sequence':seq,'cohort_patterns':cohort_rows,'kpi_baseline':kpi_baseline,'keywords':keyword_rows,'funnel':funnel,'events':[dict(r) for r in c.execute('SELECT event_type,COUNT(*) n FROM ActionEvent GROUP BY event_type')]}
(dest/'data/overview_10000.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'period':[start,end],'grain':grain,'counts':counts,'events':out['events']},ensure_ascii=False))
