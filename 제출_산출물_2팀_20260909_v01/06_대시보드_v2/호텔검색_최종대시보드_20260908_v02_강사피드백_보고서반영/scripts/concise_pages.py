"""Concise A/B evidence and fixed relative-improvement scenarios."""
import json
from visual_analysis import card,bars,svg

def ab_page(root):
 d=json.loads((root/'data/exploratory_10000.json').read_text());o=json.loads((root/'data/overview_10000.json').read_text());effects=d['effects']
 wanted=[dict(effects[i]) for i in [0,2,4,6]]
 wanted[-1]['metric']='상세 진입률'
 plot=bars([(r['metric'],[(r['control_n'],r['control_d']),(r['treatment_n'],r['treatment_d'])]) for r in wanted],['대조군 C','실험군 T'])
 content='<div class="label">03 · 합성 A/B 비교</div><h1>실패는 줄었고,<br>상세 진입도 좋아졌을까?</h1><p class="lead">C/T 각 5,000명 · 같은 사전 프로필 5,000쌍 · 2028-02-01~07 UTC. 합성 탐색 결과이며 실제 사용자 A/B는 아닙니다.</p>'
 content+=card('핵심 지표 4개 · 대조군과 실험군',plot,'분모: 0건률=전체 검색 / 즉시 회복=0건 후속 검색 / 최종 회복=0건 경험 세션 / 상세 진입=결과 있음 검색','report-summary')
 content+=card('이 A/B는 어떤 가설을 확인하나?','<div class="scroll"><table><thead><tr><th>연결 가설</th><th>비교 대상</th><th>확인하려는 효과</th><th>현재 판단</th></tr></thead><tbody><tr><th>H1 · 전체 회복 개선</th><td>전체 C/T 각 5,000명</td><td>복합 개입이 0건 후 즉시 회복률을 높이는가?</td><td>16.90% → 22.02% · +5.12%p. 합성 개입의 개선 확인, 조건 완화 단독 효과는 미분리.</td></tr><tr><th>H2 · 조건별 효과 차이</th><td>첫 검색의 가격 설정 여부·옵션 0/1/2/3개</td><td>각 조건군 안의 회복률 차이 Δ=T−C와 군 사이 Δ의 차이 비교</td><td>아래 조건별 합성 비교 가능. 군 간 차이의 통계적 검증과 실제 의도군 효과는 별도.</td></tr><tr><th>H5 · 일본 지역 확대</th><td>일본 도시·세부지역별 제안 대상 C/T</td><td>지역 확대 제안의 선택·회복 효과</td><td>현재 합성 DB에 일본 도시·제안 로그가 없어 미검증. 일반 지역 코드 비교는 대체 증거가 아님.</td></tr></tbody></table></div><p class="meta">01의 행동 추정군은 재검색 후 배정된 설명용 군입니다. 이 A/B의 H2에는 첫 검색 가격·옵션 조건을 사용합니다. 가격 설정은 예산 유연성과 같지 않습니다.</p>','가설 → 세그먼트 → 지표 → 판정','ab-hypothesis-map')
 for dim in ['가격 조건','옵션 수']:
  subset=[r for r in o['ab_conditions'] if r['dimension']==dim];levels=list(dict.fromkeys(r['segment'] for r in subset));rows=[];deltas=[]
  for level in levels:
   c,t=[next(r for r in subset if r['segment']==level and r['arm']==arm) for arm in ['control','treatment']]
   label=level+'개' if dim=='옵션 수' else level
   rows.append((label,[(c['recovered'],c['followup']),(t['recovered'],t['followup'])]));deltas.append((label,(t['recovered']/t['followup']-c['recovered']/c['followup'])*100))
  differences=' · '.join(f'{label} {value:+.2f}%p' for label,value in deltas)
  spread=max(v for _,v in deltas)-min(v for _,v in deltas)
  content+=card('H2 · '+dim+'에 따라 회복 개선 폭이 다른가?',bars(rows,['대조군 C','실험군 T'])+f'<p><b>군별 즉시 회복률 차이(T−C): {differences}.</b> 최대·최소 개선 폭의 차이는 {spread:.2f}%p입니다.</p><p class="meta">확인 목적: 어떤 초기 조건에서 회복 개선이 더 크게 나타나는지 탐색합니다. 군별 막대의 높이 자체보다 C/T 간격을 비교합니다. 위 차이는 기술통계이며 군×처치 상호작용의 신뢰구간·검정은 아직 산출하지 않아 차이의 유의성이나 우선순위를 확정하지 않습니다.</p>','첫 검색 조건으로 분류 · 합성 10,000명 · 2028-02-01~07 UTC · 즉시 회복 / 0건 후속 검색','ab-h2-'+('price' if dim=='가격 조건' else 'options'))
 s=''
 for v in [0,25,50,75,100]:
  y=300-v*2.4;s+=f'<line x1="60" x2="950" y1="{y}" y2="{y}" stroke="#e3e9ef"/><text x="48" y="{y+4}" text-anchor="end" font-size="13">{v}%</text>'
 days=sorted({r['day'] for r in o['ab_daily']})
 for j,arm in enumerate(['control','treatment']):
  rows=[r for r in o['ab_daily'] if r['arm']==arm];points=[];color=['#4569df','#219a87'][j]
  for r in rows:
   x=60+days.index(r['day'])*890/(len(days)-1);q=r['zero']/r['searches']*100;y=300-q*2.4;points.append(f'{x},{y}');s+=f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"><title>{r["day"]} {arm}: {r["zero"]}/{r["searches"]} · {q:.2f}%</title></circle>'
  s+=f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3"/>'
 for i,day in enumerate(days):s+=f'<text x="{60+i*890/(len(days)-1)}" y="330" text-anchor="middle" font-size="13">{day[5:]}</text>'
 daily_pairs=[]
 for day in days:
  c,t=[next(r for r in o['ab_daily'] if r['day']==day and r['arm']==arm) for arm in ['control','treatment']]
  daily_pairs.append((day,(t['zero']/t['searches']-c['zero']/c['searches'])*100))
 full=[v for day,v in daily_pairs if day!=days[-1]]
 daily_read=f'<p><b>무엇을 확인하나?</b> 전체 0건률 차이가 특정 하루에만 집중되는지, 날짜별로도 같은 방향인지 점검하는 H1 보조 진단입니다.</p><p><b>관측 결과:</b> {len(days)}개 날짜 중 {sum(v<0 for day,v in daily_pairs)}개에서 T의 0건률이 C보다 낮습니다. 마지막 부분 날짜를 제외한 일별 T−C 차이는 {min(full):+.2f}~{max(full):+.2f}%p입니다. 마지막 날짜({days[-1]})는 {daily_pairs[-1][1]:+.2f}%p로 방향이 반대이며, 일부 시간만 포함한 구성 차이를 함께 확인해야 합니다.</p><p class="meta">이는 합성 실행 안에서 방향이 얼마나 일관적인지 보여줍니다. 학습 효과·요일 효과·실제 운영 안정성의 증거는 아닙니다. 일별 사용자 구성과 반복 검색량이 달라 날짜를 독립 실험처럼 세지 않습니다. H1의 주 판단은 전체 즉시 회복률과 조건부 구간으로 합니다.</p>'
 content+=card('일별 검색 0건률 · C/T 추이','<div class="path-legend"><span><i style="background:#4569df"></i>대조군 C</span><span><i style="background:#219a87"></i>실험군 T</span></div>'+svg(s)+'<p class="meta">분모: 각 날짜·집단의 전체 검색. 점에 마우스를 올리면 분자·분모를 확인합니다. 마지막 날은 03:47 UTC까지이며 합성 시간축으로 실제 서비스 추이를 뜻하지 않습니다.</p>'+daily_read,'2028-02-01~07 UTC · 동일 날짜의 C/T 비교','ab-daily')
 summary='<div class="scroll"><table><thead><tr><th>지표</th><th>T − C</th><th>조건부 95% 구간</th><th>해석</th></tr></thead><tbody>'
 for i,r in enumerate(wanted):
  summary+=f'<tr><td>{r["metric"]}</td><td>{r["difference"]*100:+.2f}%p</td><td>[{r["ci_low"]*100:+.2f}, {r["ci_high"]*100:+.2f}]%p</td><td>{"개선 근거 부족 · 구간에 0 포함" if i==3 else "합성 시나리오에서 개선 방향"}</td></tr>'
 content+=card('결과 해석',summary+'</tbody></table></div><p>지역 변경 + 회복 확률 증가를 함께 적용한 시뮬레이션입니다. 개별 기능의 효과는 분리되지 않았습니다. 전수 관계 QA는 PASS지만 기준선 교정은 strict HOLD(16/20)이므로 실제 효과의 검증으로 결론 내리지 않습니다.</p>','expected · seed 2434815518 · 조건부 구간은 합성 생성 가정에 의존','ab-verdict')
 return content

def kpi_page(root):
 o=json.loads((root/'data/overview_10000.json').read_text());b=o['kpi_baseline'];S=b['searches'];z=b['zero_searches']/S;d=b['detail_searches']/b['positive_searches'];base=b['detail_searches']
 rows=[];table='<div class="scroll"><table><thead><tr><th>0건률 상대 감소</th><th>예상 0건률</th><th>검색 → 상세</th><th>예상 상세 검색</th><th>현재 대비</th></tr></thead><tbody>'
 for improvement in [0,.05,.10,.15]:
  target=z*(1-improvement);details=S*(1-target)*d;label='현재' if improvement==0 else f'{improvement*100:.0f}% 감소'
  rows.append((label,[(target*100,100),((1-target)*d*100,100)]))
  table+=f'<tr><th>{label}</th><td>{target*100:.2f}% <small>({(target-z)*100:+.2f}%p)</small></td><td>{details/S*100:.2f}%</td><td>{details:,.1f}건</td><td>{details-base:+,.1f}건 · {(details/base-1)*100:+.2f}%</td></tr>'
 body='<section aria-labelledby="tab-5" class="page" hidden id="page-5" role="tabpanel"><div class="label">05 · 고정 개선율 시뮬레이션</div><h1>검색 0건률을 낮추면,<br>상세 진입은 얼마나 늘어날까?</h1><p class="lead">검색량 65,355건과 결과 있음 → 상세 진입률 '+f'{d*100:.2f}'+'%를 현재 수준으로 고정하고, 0건률만 상대적으로 5%·10%·15% 낮춰 계산했습니다.</p>'
 body+=card('현재와 3개 개선 시나리오',bars(rows,['검색 0건률','검색 → 상세 진입률']).split('<div class="scroll">')[0]+'<p class="meta">5% 감소는 5%p 감소가 아닙니다. 현재 0건률에 0.95를 곱하는 상대 감소입니다. 그래프는 가정에 따른 산술 시뮬레이션으로 실제 A/B 결과나 승인된 목표가 아닙니다.</p>','기준: 합성 10,000명 · 2028-02-01~07 UTC · 검색량·조건부 상세 진입률 고정','fixed-scenarios')
 body+=card('상세 진입 증가 규모',table+'</tbody></table></div><p>목표 0건률 = 현재 0건률 × (1 − 감소율)<br>예상 상세 검색 = 65,355 × (1 − 목표 0건률) × 현재 결과 있음 대비 상세 진입률</p><p class="meta">소수 건수는 기대값입니다. 결과가 늘어도 상세 진입 품질이 유지된다는 가정이 깨지면 이 기대값에 도달하지 못합니다.</p>','현재 상세 진입 6,834검색 · 모든 시나리오의 검색량 동일','scenario-counts')
 body+=card('목표와 함께 지킬 기준','<ul><li>결과 있음 → 상세 진입률: 현재 '+f'{d*100:.2f}'+'% 이상 유지</li><li>검색 → 상세 진입률: 현재 '+f'{base/S*100:.2f}'+'%보다 증가</li><li>세션당 검색 횟수: 현재 '+f'{S/b["sessions"]:.2f}'+'회보다 늘어나지 않는지 확인</li></ul><p>반복 검색 횟수는 이 산술 모형으로 예측하지 않습니다. 실제 실험에서 별도로 관측해야 합니다.</p>','보호 기준 · 품질 유지와 검색 부담을 함께 확인','scenario-guards')
 groups=o['behavior_groups'];group_table='<div class="scroll"><table><thead><tr><th>행동 추정군</th><th>현재 후속 검색 → 상세</th><th>0건률 상대 10% 감소 시</th><th>예상 추가 상세 검색</th></tr></thead><tbody>'
 for g in groups:
  if not g['positive']:
   group_table+=f'<tr><th>{g["label"]}</th><td colspan="3">계산 불가 · 후속 검색 분모 없음</td></tr>';continue
  expected=(g['positive']+g['zero']*.1)*g['detail']/g['positive']
  group_table+=f'<tr><th>{g["label"]}</th><td>{g["detail"]:,}/{g["searches"]:,} · {g["detail"]/g["searches"]*100:.2f}%</td><td>{expected/g["searches"]*100:.2f}% · {expected:,.1f}건</td><td>{expected-g["detail"]:+,.1f}건</td></tr>'
 body+=card('행동 추정군별 · 같은 10% 감소 가정 비교',group_table+'</tbody></table></div><p class="meta">01의 첫 재검색 행동 규칙과 같은 배정입니다. 사용자 의도를 직접 측정한 값이 아닙니다. 각 군의 후속 검색량과 결과 있음 대비 상세 진입률을 고정합니다. 예상 상세 = (현재 결과 있음 + 현재 0건 × 0.1) × 현재 조건부 상세 진입률. 첫 검색이 제외된 55,355검색 기준이므로 위 전체65,355검색 시나리오와 합산하지 않습니다.</p>','행동 규칙 v1 · 두 번째 검색부터 집계 · 의도군별 효과 검증 아님','behavior-scenarios')
 return body+'<details class="speaker-notes"><summary>발표 설명</summary><p>전체 검색량을 고정하고 실패율이 상대적으로 5, 10, 15퍼센트 감소할 때 상세 진입의 기대값을 비교합니다. 조건부 상세 진입률 유지가 전제이며 실제 검증 결과와 구분합니다.</p></details></section>'
