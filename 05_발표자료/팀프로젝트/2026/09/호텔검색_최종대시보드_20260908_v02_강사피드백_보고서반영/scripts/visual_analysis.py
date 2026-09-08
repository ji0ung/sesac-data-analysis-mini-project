"""Purpose-specific charts; all rates retain their own explicit denominators."""
import json,math
from html import escape as E
COLORS=['#4569df','#219a87','#b4864b','#8a6bc1','#7898b6','#9aa7b7']
def data(root):return json.loads((root/'data/overview_10000.json').read_text())
def card(title,body,basis,id=''):
 return f'<article class="analytics-chart visual-analysis" id="{id}"><span class="analytics-kicker">분포와 전환 · 근거를 함께 읽기</span><h3>{title}</h3><p class="analytics-meta">{basis}</p>{body}</article>'
def svg(body,h=370):return f'<div class="analytics-plot"><svg viewBox="0 0 1000 {h}" role="img">{body}</svg></div>'
def bars(rows,series):
 # rows label and (numerator, denominator) values; fixed 0–100% axis.
 s=''
 peak=max([n/d*100 for _,vals in rows for n,d in vals if d]+[1]);maximum=min(100,max(10,math.ceil(peak/10)*10));scale=215/maximum
 for v in [maximum*j/4 for j in range(5)]:
  y=285-v*scale;s+=f'<line x1="65" x2="970" y1="{y}" y2="{y}" stroke="#e3e9ef"/><text x="55" y="{y+4}" text-anchor="end" font-size="13">{v:g}%</text>'
 table='<div class="scroll"><table><thead><tr><th>비교군</th>'+''.join(f'<th>{E(x)}</th>' for x in series)+'</tr></thead><tbody>'
 for i,(label,values) in enumerate(rows):
  x=65+(i+.5)*905/len(rows);table+=f'<tr><td>{E(label)}</td>'
  for j,(n,d) in enumerate(values):
   rate=n/d*100 if d else 0;cx=x+(j-(len(series)-1)/2)*48
   value=f'{n:,}/{d:,} · {rate:.2f}%' if d else '— · 분모 없음'
   s+=f'<rect x="{cx-19}" y="{285-rate*scale}" width="38" height="{rate*scale}" rx="4" fill="{COLORS[j]}"><title>{E(label)} · {E(series[j])}: {value}</title></rect><text x="{cx}" y="{275-rate*scale}" text-anchor="middle" font-size="12">{rate:.1f}%</text>' if d else f'<text x="{cx}" y="275" text-anchor="middle">—</text>'
   table+=f'<td>{value}</td>'
  s+=f'<text x="{x}" y="316" text-anchor="middle" font-size="14">{E(label)}</text>';table+='</tr>'
 legend='<div class="path-legend">'+''.join(f'<span><i style="background:{COLORS[i]}"></i>{E(n)}</span>' for i,n in enumerate(series))+'</div>'
 return legend+svg(s,345)+table+'</tbody></table></div>'
def behavior_chart(d):
 groups=d['behavior_groups'];active=[g for g in groups if g['searches']]
 short={'budget_flexible':'예산 조정','option_count_flexible':'옵션 감소','location_flexible':'위치 변경','condition_keeper':'유지·강화','rapid_resolver':'복합 변경'}
 distribution='<div class="scroll"><table><thead><tr><th>보고서 의도군에 대응한 추정</th><th>사용자 / 전체 10,000명</th><th>배정 규칙</th></tr></thead><tbody>'+''.join(f'<tr><th>{g["label"]}</th><td>{g["users"]:,}명 · {g["users"]/100:.2f}%</td><td>{g["rule"]}</td></tr>' for g in groups)+'</tbody></table></div>'
 body=bars([(short[g['code']],[(g['detail'],g['searches']),(g['detail'],g['positive'])]) for g in active],['전체 후속 검색 → 상세','결과 있음 후속 검색 → 상세'])
 return card('행동 기반 의도군 추정 · 상세 진입 전환',body+distribution+'<p><b>사용자당 첫 검색 → 두 번째 검색의 조건 변경으로 1개 군만 배정</b>합니다. 2개 이상 조건 변경은 복합 변경을 우선하고, 단일 변경은 예산·옵션·위치·표현 규칙을 적용합니다. 결과·클릭·회복 여부는 배정에 쓰지 않습니다.</p><p class="meta">집계는 배정이 가능해진 두 번째 검색부터 세션 종료까지입니다. 첫 검색 10,000건은 전환율 분모에서 제외합니다. 미분류 2,186명은 재검색이 없어 후속 전환율을 계산하지 않습니다. 표현 수정형 0명은 생성 접미사를 제외한 실제 검색어 변화가 없다는 뜻이며 실제 모집단에 해당 의도가 없다는 뜻이 아닙니다.</p><p class="meta">보고서의 확률 배정식을 재현한 결과가 아닌 명시적 행동 규칙 v1입니다. 복합 변경형은 보고서 빠른 해결형의 대체 신호이나 해결 속도는 측정하지 않습니다. 가격 조건 상향·해제를 예산 유연성의 신호로 가정합니다. 사후·처치 후 행동일 수 있어 이 군으로 C/T를 나눈 차이를 인과효과로 해석하지 않습니다.</p>', '합성 10,000명 · 2028-02-01~07 UTC · 후속 검색 55,355건 · 실제 의도 응답이 아닌 행동 추정','behavior-detail')
def cities(d):
 s=''
 def split(items,x,y,w,h):
  nonlocal s
  if len(items)==1:
   i,r=items[0]
   s+=f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{COLORS[i]}" stroke="white" stroke-width="3"><title>{r["label"]} {r["n"]}/296검색</title></rect><text x="{x+w/2}" y="{y+h/2-18}" text-anchor="middle" fill="white" font-size="18">{r["label"]}</text><text x="{x+w/2}" y="{y+h/2+12}" text-anchor="middle" fill="white" font-size="16">{r["n"]}건 · {r["n"]/296*100:.1f}%</text>'
   return
  total=sum(r['n'] for i,r in items);k=min(range(1,len(items)),key=lambda k:abs(sum(r['n'] for i,r in items[:k])-total/2));ratio=sum(r['n'] for i,r in items[:k])/total
  if w>=h:split(items[:k],x,y,w*ratio,h);split(items[k:],x+w*ratio,y,w*(1-ratio),h)
  else:split(items[:k],x,y,w,h*ratio);split(items[k:],x,y+h*ratio,w,h*(1-ratio))
 split([(i,r) for i,r in enumerate(d['cities']) if r['n']],0,0,1000,390)
 return card('일본 5개 도시 · 어디를 검색했나?',svg(s,410)+'<p>도쿄 · 오사카 · 교토 · 후쿠오카 · 삿포로를 기준으로 세부 지역을 묶었습니다. 지역 미설정도 별도 보존합니다.</p><p class="meta">면적 = 검색 비중. 원본 v03 296검색이며 1만 명 합성 집계와 합산하지 않습니다. 최신 생성 DB의 일반 지역 코드는 일본 도시와 연결되지 않아 이 영역에 쓰지 않았습니다. 지역 확대 제안은 선택 도시 안의 세부 지역 범위 확대를 먼저 검토하고, 도시 변경은 별도 선택으로 구분합니다.</p>', '원본 v03 · '+ ' ~ '.join(x[:19] for x in d['original_period'])+' KST · 분모 296검색 · 숙박일 역전 9건도 검색 행동 분석에 유지.','japan-cities')
def overview_extras(root):
 d=data(root);o=d['option_summary']
 stats='<div class="report-metrics">'+''.join(f'<article class="report-metric"><h3>{n}</h3><strong>{v:.2f}<small>개</small></strong></article>' for n,v in [('평균',o['mean']),('중앙값',o['median']),('하위 25% 경계',o['q1']),('상위 25% 경계',o['q3'])])+'</div>'
 s=''
 for i,b in enumerate(d['option_boxes']):
  x=150+i*225;Y=lambda v:300-v/31*240
  s+=f'<line x1="{x}" x2="{x}" y1="{Y(b["min"])}" y2="{Y(b["max"])}" stroke="{COLORS[i]}" stroke-width="3"/><rect x="{x-55}" y="{Y(b["q3"])}" width="110" height="{Y(b["q1"])-Y(b["q3"])}" fill="{COLORS[i]}" fill-opacity=".25" stroke="{COLORS[i]}"/><line x1="{x-55}" x2="{x+55}" y1="{Y(b["median"])}" y2="{Y(b["median"])}" stroke="{COLORS[i]}" stroke-width="4"/><circle cx="{x}" cy="{Y(b["mean"])}" r="5" fill="#172e4a"><title>평균 {b["mean"]:.2f}회</title></circle><text x="{x}" y="326" text-anchor="middle" font-size="15">옵션 {i}개 · {b["users"]:,}명</text><text x="{x}" y="349" text-anchor="middle" font-size="13">평균 {b["mean"]:.2f} · 중앙값 {b["median"]:.1f}회</text>'
  for v in [b['min'],b['max']]:s+=f'<line x1="{x-20}" x2="{x+20}" y1="{Y(v)}" y2="{Y(v)}" stroke="{COLORS[i]}" stroke-width="2"/>'
 for v in [0,10,20,31]:s+=f'<text x="30" y="{300-v/31*240}" font-size="13">{v}회</text>'
 options=card('초기 옵션 수 · 평균과 중앙값, 이후 검색 횟수',stats+svg(s)+'<p class="meta">상자: 검색 횟수의 25~75% · 굵은 선: 중앙값 · 점: 평균 · 수염: 최소~최대(1.5 IQR 규칙 아님). 사용자별 검색 횟수이며 최대 31회 생성 제한이 있습니다. 초기 옵션은 실제 amenity_count 0·1·2·3개를 사용하고 2+로 합치지 않았습니다.</p>', '합성 10,000명 · 2028-02-01~07 UTC · 사용자별 첫 검색 옵션 수 / 같은 세션의 전체 검색 횟수','option-boxes')
 heat='<div class="scroll"><table class="retention-heat"><thead><tr><th>첫 검색일 · 사용자</th>'+''.join(f'<th>{i}번째</th>' for i in range(1,11))+'</tr></thead><tbody>'
 for r in d['retention']:
  heat+=f'<tr><th>{r["day"]}<br>{r["users"]:,}명</th>'
  for n in r['steps']:
   q=n/r['users'];heat+=f'<td style="background:rgba(69,105,223,{.08+q*.85});color:{"white" if q>.5 else "#20324b"}" title="{n}/{r["users"]}">{q*100:.1f}%<small>{n:,}명</small></td>'
  heat+='</tr>'
 heat+='</tbody></table></div>'
 retention=card('검색 지속 코호트 · 몇 번째 검색까지 남았나?',heat+'<p class="meta">색이 진할수록 같은 세션 안에서 해당 순번까지 검색한 비율이 높습니다. 분모는 행의 첫 검색일 사용자 수로 고정합니다. 사용자당 1세션이므로 일간·주간 재방문 리텐션은 측정할 수 없습니다. 마지막 날짜는 일부 시간입니다.</p>','합성 10,000명 · 첫 검색일(UTC) 기준 · 검색 단계 리텐션 / 재방문 아님','search-retention')
 return behavior_chart(d)+options+retention+cities(d)
def hypotheses(root):
 d=data(root)
 changes={r['label']:r for r in d['condition_transitions']};a=changes['가격·옵션 변경'];b=changes['가격·옵션 유지'];delta=(a['recovered']/a['n']-b['recovered']/b['n'])*100
 h1=card('우선순위 1 · 조건 완화가 회복을 높이는가?',bars([(r['label'],[(r['recovered'],r['n']),(r['detail'],r['n'])]) for r in d['condition_transitions']],['다음 검색 결과 회복','다음 검색 회복 + 상세 진입'])+f'<p><b>선정 이유: 제한 조건 검색의 0건률이 높고, 정적 조건 완화 UI로 먼저 시험할 수 있습니다.</b></p><p>원본에서 편의시설 3개 이상 88.2%, 최소 평점 설정 75.7%, 가격 설정 72.6%의 0건률이 관측됐고, 자발적 조건 완화 뒤 회복은 11/41=26.8%였습니다. 기대효과는 검색 범위를 넓혀 동일 조건 반복을 줄이고 즉시 회복을 높이는 것입니다. 현재 차트는 관측 비교이며 맞춤 제안의 인과효과는 판정 보류입니다.</p>','합성 10,000명 · 2028-02-01~07 UTC · 분모: 0건 직후 다음 검색이 있는 전이 · 사용자 중복 포함','hypothesis-h1-chart')
 h2=card('하위 가설 · 조건 완화를 누구에게 먼저 보여줄까?',bars([(r['label']+'개',[(r['zero'],r['searches']),(r['detail'],r['searches'])]) for r in d['option_conversion']],['결과 없음 / 전체 검색','상세 진입 / 전체 검색'])+'<p><b>선정 이유: 가격과 옵션 모두 실패와 관련됐지만, 사용자가 포기할 수 있는 조건은 다를 수 있습니다.</b></p><p>이 질문은 별도 개선 우선순위가 아니라 조건 완화의 전체 효과를 확인한 뒤 개인화 여부를 결정하는 2차 분석입니다. 기대효과는 수용 가능성이 높은 완화를 먼저 보여 불필요한 제안을 줄이는 것입니다. 실제 의도 배정값이 없어 현재 차트로 예산·옵션 의도군별 효과를 판정할 수 없습니다.</p>','합성 10,000명 · 2028-02-01~07 UTC · 최초 옵션 수로 사용자군 고정, 이후 모든 검색 포함','hypothesis-h2-chart')
 h5=card('우선순위 2 · 일본 지역 확대가 회복을 높이는가?',bars([(r['label'],[(r['recovered'],r['n'])]) for r in d['city_transitions']],['지역 변경 직후 결과 회복'])+'<p><b>선정 이유: 지역 변경 회복률 10/24=41.7%로 검색어 변경 30.0%, 조건 완화 26.8%보다 높게 관측됐습니다.</b></p><p>기대효과는 현재 5개 일본 도시 안에서 인접·대체 지역을 제시해 새로운 호텔 공급 후보를 보여주는 것입니다. 다만 같은 도시의 동네 변경·도시 간 이동·미설정 변경이 섞여 있고, 24건의 소표본과 자기선택이 있으므로 우선 파일럿 후보로만 판단합니다.</p>','원본 v03 · '+' ~ '.join(x[:19] for x in d['original_period'])+' KST · 분모: 0건 후 지역 변경 전이. 목적지 원문 비교 · 동일시각은 search_id 순.','hypothesis-h5-chart')
 statuses='<section class="panel" id="hypothesis-status"><h2>우선순위와 검증 상태</h2><p><b>검증 완료된 개별 기능 가설은 없습니다.</b> 관측 근거로 검증 순서를 정했으며, 집계 완료와 기능 효과 검증은 구분합니다.</p><div class="scroll"><table><thead><tr><th>역할</th><th>선정 이유</th><th>기대효과</th><th>현재 상태</th></tr></thead><tbody><tr><th>1순위 · 조건 완화</th><td>제한 조건의 0건률이 높고 기존 검색 UI에서 단계적 완화를 시험하기 쉬움</td><td>검색 범위 확대, 동일 조건 반복 감소, 즉시 회복 증가</td><td>조건 완화 단독 A/B 미실시</td></tr><tr><th>하위 가설 · 예산/옵션 개인화</th><td>사용자가 포기할 수 있는 조건에 따라 제안 수용이 다를 가능성</td><td>불필요한 제안 감소, 의도별 회복 효율 개선</td><td>검색 전 intent_segment 미연결</td></tr><tr><th>2순위 · 일본 지역 확대</th><td>자발적 지역 변경 회복 10/24=41.7%로 비교 방법 중 가장 높게 관측</td><td>인접·대체 지역의 새로운 호텔 후보 노출</td><td>소표본·자기선택, 제안 로그 없음</td></tr></tbody></table></div><p class="meta">집계·관계 QA: 완료(PASS). 합성 기준선 교정: HOLD(16/20). 선정은 효과 입증이 아니라 다음 검증 순서를 뜻합니다.</p></section>'
 return '<h1>왜 이 개선안을 먼저 검증하는지 설명합니다.</h1><p class="lead">문제 규모·관측 회복·실행 가능성으로 우선순위를 정하고, 각 개선안에서 기대하는 효과와 검증 상태를 함께 봅니다.</p>'+statuses+h1+h2+h5
