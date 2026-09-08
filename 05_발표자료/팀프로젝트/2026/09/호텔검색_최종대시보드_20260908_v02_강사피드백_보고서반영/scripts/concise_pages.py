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
 content+=card('일별 검색 0건률 · C/T 추이','<div class="path-legend"><span><i style="background:#4569df"></i>대조군 C</span><span><i style="background:#219a87"></i>실험군 T</span></div>'+svg(s)+'<p class="meta">분모: 각 날짜·집단의 전체 검색. 점에 마우스를 올리면 분자·분모를 확인합니다. 마지막 날은 03:47 UTC까지이며 합성 시간축으로 실제 서비스 추이를 뜻하지 않습니다.</p>','2028-02-01~07 UTC · 동일 날짜의 C/T 비교','ab-daily')
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
 return body+'<details class="speaker-notes"><summary>발표 설명</summary><p>전체 검색량을 고정하고 실패율이 상대적으로 5, 10, 15퍼센트 감소할 때 상세 진입의 기대값을 비교합니다. 조건부 상세 진입률 유지가 전제이며 실제 검증 결과와 구분합니다.</p></details></section>'
