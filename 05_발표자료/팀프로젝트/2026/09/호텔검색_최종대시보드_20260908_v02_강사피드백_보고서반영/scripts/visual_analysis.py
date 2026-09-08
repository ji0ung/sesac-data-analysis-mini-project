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
def conversion(d):
 rows=[(x['label'],[(x['detail'],x['searches']),(x['detail'],x['positive'])]) for x in d['topic_conversion']]
 return card('검색어 주제별 · 호텔 상세 진입 전환',bars(rows,['전체 검색 → 상세','결과 있음 → 상세']), '합성 10,000명 · 2028-02-01~07 UTC · 첫 검색어 주제로 세션을 고정 분류. 해당 세션의 모든 검색을 집계. 상세 진입은 결과 있음 검색 중 hotel_click 존재 기준, 검색당 1회 중복 제거.','topic-detail')+'<p class="meta">대안: 현황에서는 전체 검색 대비 전환과 결과 있음 대비 전환을 함께 봅니다. KPI에서는 주제별 목표를 설정해 합산합니다. 위 4개 검색어 주제는 문서의 6개 조건 변경 의도군을 대신 확정한 값이 아닙니다. 실제 의도군 분석에는 검색 전 intent_segment 연결이 필요합니다.</p>'
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
 return conversion(d)+options+retention+cities(d)
def hypotheses(root):
 d=data(root)
 changes={r['label']:r for r in d['condition_transitions']};a=changes['가격·옵션 변경'];b=changes['가격·옵션 유지'];delta=(a['recovered']/a['n']-b['recovered']/b['n'])*100
 h1=card('H1 · 조건 변경 뒤 즉시 회복과 상세 진입은 다른가?',bars([(r['label'],[(r['recovered'],r['n']),(r['detail'],r['n'])]) for r in d['condition_transitions']],['다음 검색 결과 회복','다음 검색 회복 + 상세 진입'])+f'<p><b>관측 차이: 변경군의 즉시 회복률은 유지군보다 {delta:+.2f}%p.</b></p><p>판독: 가격 또는 옵션 개수가 달라진 전이와 두 조건이 유지된 전이를 비교합니다. 유지군도 지역·검색어 등 다른 조건을 바꿀 수 있습니다. 자발적 행동과 생성 개입이 섞인 관측 비교로, 맞춤 조건 완화 제안의 인과효과는 판정 보류입니다.</p>','합성 10,000명 · 2028-02-01~07 UTC · 분모: 0건 직후 다음 검색이 있는 전이 · 사용자 중복 포함','hypothesis-h1-chart')
 h2=card('H2 · 초기 옵션 수에 따라 실패와 상세 진입이 다른가?',bars([(r['label']+'개',[(r['zero'],r['searches']),(r['detail'],r['searches'])]) for r in d['option_conversion']],['결과 없음 / 전체 검색','상세 진입 / 전체 검색'])+'<p>판독: 초기 조건이 엄격할수록 실패와 상세 진입이 어떻게 달라지는지 탐색합니다. 옵션 수는 변경 의향이 아니므로 6개 의도군의 효과 차이를 검증한 결과는 아닙니다. 의도 배정 후 각 의도 안의 A/B 차이를 비교해야 원래 가설을 판정할 수 있습니다.</p>','합성 10,000명 · 2028-02-01~07 UTC · 최초 옵션 수로 사용자군 고정, 이후 모든 검색 포함','hypothesis-h2-chart')
 h5=card('H5 · 일본 지역 변경 뒤 어디에서 회복했나?',bars([(r['label'],[(r['recovered'],r['n'])]) for r in d['city_transitions']],['지역 변경 직후 결과 회복'])+'<p><b>전체 지역 변경 24전이 중 10전이 회복 · 41.67%. 삿포로 100%는 2/2건이므로 우선순위 근거로 단정하지 않습니다.</b></p><p>판독: 0건 직후 목적지 문자열이 달라진 검색을 출발 도시별로 비교합니다. 같은 도시의 동네 변경·도시 간 이동·미설정으로 변경을 모두 포함합니다. 표본이 작고 제안 노출 기록이 없어 지역 확대 제안의 효과로 해석하지 않습니다.</p>','원본 v03 · '+' ~ '.join(x[:19] for x in d['original_period'])+' KST · 분모: 0건 후 지역 변경 전이. 목적지 원문 비교 · 동일시각은 search_id 순.','hypothesis-h5-chart')
 statuses='<section class="panel" id="hypothesis-status"><h2>가설 검증 상태와 사유</h2><p><b>검증 완료된 개별 기능 가설은 없습니다.</b> 아래 그래프의 집계 완료와 기능 효과의 검증 완료는 구분합니다.</p><div class="scroll"><table><thead><tr><th>원래 가설</th><th>상태</th><th>사유</th><th>판정에 필요한 근거</th></tr></thead><tbody><tr><th>H1 · 맞춤 조건 완화가 회복률을 높인다</th><td>판정 보류</td><td>합성 A/B는 지역 변경과 회복 확률 증가가 결합된 처치입니다. 가격·옵션 완화의 단독 효과가 분리되지 않았고, 관측 행동 비교에도 교란이 있습니다.</td><td>조건 완화 단독 처치의 실제 무작위 A/B와 사전등록 지표</td></tr><tr><th>H2 · 조건 완화 효과가 의도군마다 다르다</th><td>현재 데이터로 검증 불가</td><td>6개 intent_segment 배정값이 없습니다. 옵션 개수·검색어 주제는 변경 의향이 아닙니다.</td><td>검색 전 의도군 연결과 각 의도군 내 C/T 비교</td></tr><tr><th>H5 · 일본 지역 확대 제안이 회복률을 높인다</th><td>현재 데이터로 검증 불가</td><td>제안 노출·선택·수락 로그가 없으며 원본 10/24는 자발적 지역 변경 관측입니다. 1만 명 지역 코드도 일본 도시와 연결되지 않습니다.</td><td>일본 5개 도시·세부지역 코드 연결, 제안 이벤트 계측, 실제 A/B</td></tr></tbody></table></div><p class="meta">집계·관계 QA: 완료(PASS). 합성 기준선 교정: HOLD(16/20). QA 완료는 가설 채택을 뜻하지 않습니다. 보류는 근거는 있으나 효과 분리가 안 된 상태, 검증 불가는 현재 필수 변수·로그가 없는 상태입니다.</p></section>'
 return '<h1>가설별로 비교하고, 판정 근거를 확인합니다.</h1><p class="lead">분자·분모와 차이를 그래프로 확인합니다. 관측 가능한 대체 질문과 아직 검증되지 않은 기능 효과를 구분했습니다.</p>'+statuses+h1+h2+h5
