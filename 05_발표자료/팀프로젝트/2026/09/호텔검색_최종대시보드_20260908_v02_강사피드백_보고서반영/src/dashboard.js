
'use strict';const PACK={{DATA_PACK}};let D=PACK.slices['ALL|ALL'];const $=s=>document.querySelector(s);const fmt=n=>Number(n).toLocaleString('ko-KR');const rate=(n,d)=>d?n/d*100:0;const pct=(n,d)=>d?rate(n,d).toFixed(1):'—';const colors=['#176858','#a9c7b8','#b88b51','#d8cabb'];
let chartSeq=0;let chartRegistry={};const chartBaselines={};
function periodLabel(data=D){return data.period&&data.period.start?data.period.start.slice(0,10)+' ~ '+data.period.end.slice(0,10)+' · 합성 검색 시간':'해당 기간 데이터 없음';}
function periodHTML(data=D){return '<div class="analysis-period">분석 기간 '+periodLabel(data)+' · 선택 '+fmt(data.counts.sessions)+'세션</div>';}
function signed(n){return (n>0?'+':'')+n.toFixed(1);}
function verticalBars(rows){return `<div class="vchart-scroll"><div class="vchart" style="--cols:${rows.length}" role="img" aria-label="집단별 비율 세로 막대, 0~100%"><div class="vaxis"><span>100%</span><span>50%</span><span>0%</span></div><div class="vplot">${rows.map((r,i)=>`<div class="vcolumn"><div class="vwell"><div class="vbar" style="height:${rate(r.n,r.d)}%;background:${colors[i%4]}"><strong>${pct(r.n,r.d)}%</strong></div></div><div class="vlabel">${r.name}</div><div class="vcount">${fmt(r.n)} / ${fmt(r.d)}</div></div>`).join('')}</div></div></div>`;}
function choiceControl(rows,key,selected,metric){return `<span class="meta">${rows.length>1?'비교 기준: '+(rows[selected]?.name||'—'):'비교 집단 없음'}</span>`;}
function comparisonHTML(rows,key,metric){const preferred=rows.findIndex(r=>r.name==='조건 완화');let baseline=rows.findIndex(r=>r.name===chartBaselines[key]);if(baseline<0)baseline=preferred>=0?preferred:0;const b=rows[baseline];return periodHTML()+`<div class="chart-controls"><span class="badge gray">${metric} · 관측 비교</span>${choiceControl(rows,key,baseline,metric)}</div>`+verticalBars(rows)+`<div class="scroll"><table class="lift-table"><thead><tr><th>집단</th><th>${metric}</th><th>차이</th><th>상대 변화</th><th>유의성</th></tr></thead><tbody>${rows.map((r,i)=>{const valid=r.d>0&&b&&b.d>0;const diff=valid?rate(r.n,r.d)-rate(b.n,b.d):null;const lift=valid&&b.n>0?diff/rate(b.n,b.d)*100:null;return `<tr><td>${r.name}${i===baseline?' · 기준':''}</td><td>${pct(r.n,r.d)}%</td><td>${rows.length<2||i===baseline?'—':diff===null?'—':signed(diff)+'%p'}</td><td>${rows.length<2||i===baseline?'—':lift===null?'—':signed(lift)+'%'}</td><td>미산출</td></tr>`}).join('')}</tbody></table></div><details class="metric-notes"><summary>지표 정의·해석</summary><p class="chart-method">차이(%p)는 비교군 비율 − 기준군 비율입니다. 상대 변화(관측 업리프트, %)는 차이 ÷ 기준군 비율 × 100입니다. 기준군이 0%이면 상대 변화는 —입니다. 합성·반복 관측 자료이며 A/B 배정 정보 미연결로 p값·신뢰구간은 미산출입니다. 양수는 수치 증가를 뜻하며 개선 여부는 지표에 따라 다릅니다.</p></details>`;}
function bars(rows,metric='전환율'){if(metric==='구성비')return periodHTML()+verticalBars(rows)+'<details class="metric-notes"><summary>지표 정의·해석</summary><p class="chart-method">성과군 구성비입니다. 전환율·처치 업리프트와 구분합니다.</p></details>';const key='metric-'+chartSeq++;chartRegistry[key]={rows,metric};return `<div id="${key}">${comparisonHTML(rows,key,metric)}</div>`;}
function selectBaseline(key,value,focus=false){const x=chartRegistry[key];if(!x||!x.rows[value])return;chartBaselines[key]=x.rows[value].name;$('#'+key).innerHTML=comparisonHTML(x.rows,key,x.metric);if(focus)$('#'+key).querySelector('[role="radio"][aria-checked="true"]')?.focus({preventScroll:true});}
document.addEventListener('change',event=>{const key=event.target.dataset.chartBaseline;if(key)selectBaseline(key,Number(event.target.value));});
document.addEventListener('click',event=>{const b=event.target.closest('[data-choice-key]');if(b)selectBaseline(b.dataset.choiceKey,Number(b.dataset.choiceValue),true);});
document.addEventListener('keydown',event=>{const b=event.target.closest('[data-choice-key]');if(!b)return;const key=b.dataset.choiceKey,n=chartRegistry[key].rows.length;let index=Number(b.dataset.choiceValue);if(['ArrowRight','ArrowDown'].includes(event.key))index=(index+1)%n;else if(['ArrowLeft','ArrowUp'].includes(event.key))index=(index+n-1)%n;else if(event.key==='Home')index=0;else if(event.key==='End')index=n-1;else return;event.preventDefault();selectBaseline(key,index,true);});


function page(i){document.querySelectorAll('.page').forEach(e=>e.hidden=e.id!=='page-'+i);document.querySelectorAll('nav button').forEach(e=>{const active=+e.dataset.page===i;e.setAttribute('aria-selected',active);e.tabIndex=active?0:-1});$('#slide-position').textContent=([4,0,1,2,3,5].indexOf(i)+1)+' / 6';window.scrollTo(0,0)}
document.querySelectorAll('[data-page]').forEach(e=>e.onclick=()=>page(+e.dataset.page));document.querySelectorAll('nav button').forEach((e,i)=>e.onkeydown=x=>{if(['ArrowRight','ArrowLeft'].includes(x.key)){x.preventDefault();const tabs=[...document.querySelectorAll('nav button')];let n=(i+(x.key==='ArrowRight'?1:tabs.length-1))%tabs.length;tabs[n].click();tabs[n].focus()}});
function recoveryHTML(data){const c=data.counts;
const funnelStages=[['결과 없음',c.zero,'시작 기준'],['후속 검색 기록 있음',c.followup,'직전 단계 대비'],['다음 검색에서 회복',c.recovered,'직전 단계 대비'],['회복한 검색에 클릭',data.recovered_click.n,'직전 단계 대비']];
const sideNotes=['',`후속 검색 기록 없음 ${fmt(c.zero-c.followup)}건 · ${pct(c.zero-c.followup,c.zero)}%`,`즉시 미회복 ${fmt(c.followup-c.recovered)}건 · ${pct(c.followup-c.recovered,c.followup)}%`,`회복한 검색에 클릭 기록 없음 ${fmt(c.recovered-data.recovered_click.n)}건 · ${pct(c.recovered-data.recovered_click.n,c.recovered)}%`];
return periodHTML(data)+`<div class="funnel-extra"><div><span>0건 검색 → 즉시 회복</span><strong>${pct(c.recovered,c.zero)}%</strong><span>${fmt(c.recovered)} / ${fmt(c.zero)} · 0건 검색 기준</span></div><div><span>0건 검색 → 회복 후 클릭</span><strong>${pct(data.recovered_click.n,c.zero)}%</strong><span>${fmt(data.recovered_click.n)} / ${fmt(c.zero)} · 0건 검색 기준</span></div><div><span>후속 검색 기록 없음</span><strong>${fmt(c.zero-c.followup)}건</strong><span>${pct(c.zero-c.followup,c.zero)}% · 이탈로 단정하지 않음</span></div></div>`+funnelStages.map(([name,n,note],i)=>`<div class="funnel-step"><div class="funnel-row"><div class="funnel-label"><span class="meta">0${i+1}</span> ${name}</div><div class="funnel-track"><div class="funnel-bar" style="width:${rate(n,c.zero)}%;background:${['#91b5a5','#5c9881','#176858','#b88b51'][i]}"></div></div><div class="funnel-count"><strong>${fmt(n)}건</strong><span class="meta">${i?pct(n,funnelStages[i-1][1])+'% · '+note:(c.zero?'100%':'—')+' · '+note}</span><span class="meta">0건 검색 대비 ${pct(n,c.zero)}%</span></div></div>${i?`<p class="funnel-side">↳ ${sideNotes[i]}</p>`:''}</div>`).join('')+'<details class="metric-notes"><summary>지표 정의·해석</summary><p class="chart-method">통계적 유의성 미산출 · 관측 퍼널입니다. 서로 다른 단계의 전환율 차이를 A/B 업리프트로 해석하지 않습니다.</p></details>';
}

function renderDashboard(){chartSeq=0;chartRegistry={};const c=D.counts;
$('#overview-counts').textContent=fmt(c.sessions)+' sessions / '+fmt(c.searches)+' searches';
$('#overview-title').textContent=c.searches?'전체 검색의 결과 없음 '+pct(c.zero,c.searches)+'%, 다음 검색 회복 '+pct(c.recovered,c.followup)+'%':'선택 조건에 해당하는 세션이 없습니다.';
$('#overview-scope').textContent=fmt(c.sessions)+'세션 · 검색 '+fmt(c.searches)+'건 · 합성 데이터';
const fullScope='전체 기간 · 전체 성과군 · '+fmt(c.sessions)+'세션 · '+fmt(c.searches)+'검색';
const noteBase=PACK.slices['ALL|ALL'];$('#funnel-summary').textContent='기본 퍼널은 전체 기간·전체 성과군 기준입니다. '+fmt(noteBase.counts.zero)+'건의 0건 검색 중 '+fmt(noteBase.counts.followup)+'건('+pct(noteBase.counts.followup,noteBase.counts.zero)+'%)에 후속 검색이 있습니다. 성과군별 여정은 별도 영역에 모두 펼쳐 표시합니다.';
$('#kpis').innerHTML=[['결과 없음',c.zero,c.searches,'전체 검색'],['0건 이후 후속 검색',c.followup,c.zero,'0건 검색'],['다음 검색에서 회복',c.recovered,c.followup,'후속 검색 전환'],['세션 마지막 검색 회복',c.final_recovered,c.zero_sessions,'0건 경험 세션']].map(([name,n,d,unit])=>`<article class="card"><div class="eyebrow">${name}</div><div class="value">${pct(n,d)}<em>%</em></div><p>${fmt(n)} / ${fmt(d)} · ${unit}</p></article>`).join('');
const activeSegment='ALL';const funnelBase=PACK.slices['ALL|ALL'];const baseCounts=funnelBase.counts;
$('#funnel-filter-note').textContent='기본 퍼널: 전체 기간 · 전체 성과군';
$('#search-branches').innerHTML=periodHTML(funnelBase)+`<div class="funnel-extra"><div><span>전체 검색</span><strong>${fmt(baseCounts.searches)}건</strong><span>분기 기준 100%</span></div><div><span>결과 있음</span><strong>${fmt(baseCounts.searches-baseCounts.zero)}건</strong><span>${pct(baseCounts.searches-baseCounts.zero,baseCounts.searches)}% · 전체 검색 기준</span></div><div><span>결과 없음 → 아래 회복 퍼널</span><strong>${fmt(baseCounts.zero)}건</strong><span>${pct(baseCounts.zero,baseCounts.searches)}% · 전체 검색 기준</span></div></div><div style="display:flex;height:28px;border-radius:6px;overflow:hidden;background:#eff1ec" role="img" aria-label="결과 있음 ${fmt(baseCounts.searches-baseCounts.zero)}건, 결과 없음 ${fmt(baseCounts.zero)}건"><div style="width:${rate(baseCounts.searches-baseCounts.zero,baseCounts.searches)}%;background:#176858"></div><div style="width:${rate(baseCounts.zero,baseCounts.searches)}%;background:#b88b51"></div></div><div class="legend" style="margin-top:8px"><span>● 결과 있음</span><span style="color:#a16624">● 결과 없음</span></div>`;
$('#recovery-funnel').innerHTML=recoveryHTML(funnelBase);
$('#funnel-comparison').hidden=activeSegment==='ALL';$('#comparison-funnel').innerHTML=activeSegment==='ALL'?'':recoveryHTML(D);$('#comparison-funnel-title').textContent='선택 성과군 비교 · '+activeSegment;

const methods=[...D.methods].sort((a,b)=>rate(b.n,b.d)-rate(a.n,a.d));$('#method-bars').innerHTML=bars(methods,'즉시 회복률');
$('#segment-donut').innerHTML=bars(D.segments,'구성비');
const points=D.months.map((r,i)=>[60+i*(840/Math.max(D.months.length-1,1)),190-rate(r.n,r.d)*1.5]);$('#timeline').innerHTML=periodHTML()+`<svg class="chartsvg" viewBox="0 0 960 245" role="img" aria-label="합성 데이터 월별 결과 없음 비율">${[0,50,100].map(v=>`<line x1="60" x2="910" y1="${190-v*1.5}" y2="${190-v*1.5}" stroke="#dedfd7"/><text x="12" y="${195-v*1.5}" font-size="12" fill="#63716f">${v}%</text>`).join('')}<polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#176858" stroke-width="3"/>${D.months.map((r,i)=>`<circle cx="${points[i][0]}" cy="${points[i][1]}" r="4" fill="#176858"/><text x="${points[i][0]}" y="${points[i][1]-13}" text-anchor="middle" font-size="12" fill="#16302e">${pct(r.n,r.d)}%</text><text x="${points[i][0]}" y="214" text-anchor="middle" font-size="12" fill="#63716f">${r.name.slice(5)}월</text><text x="${points[i][0]}" y="233" text-anchor="middle" font-size="10" fill="#63716f">${r.n}/${r.d}</text>`).join('')}</svg>`;
$('#hyp-overview').innerHTML=[['H1 · A-1 전체 효과','0건 후 후속 검색의 회복률'],['H2 · A-1 의도별 차이','예산·옵션 수 의도군 안의 A/B 회복률'],['H5 · D-1 지역 확대','지역 변경 후속 검색 회복률·지역 선택률']].map(([title,metric])=>`<tr><td>${title}</td><td>${metric}</td><td>문서의 대조군·실험군 비교</td><td>${title.startsWith("H1")?"복합 개입 +5.12%p · 단독 효과 미식별":title.startsWith("H2")?"intent_segment 없음 · 조건별 탐색 결과 연결":"지역군별 비교 연결 · 노출/선택 로그 없음"}</td></tr>`).join('');


const intents=[['예산 유연형','A-1 가격 범위 확대','H1/H2'],['옵션 유연형','A-1 필요한 옵션 수 감소','H1/H2'],['위치 유연형','D-1 인접지역 제안','H5'],['조건 고수형','F-1 반복 안내','추가 검토'],['표현 수정형','D-2 연관 검색어 제안','추가 검토'],['빠른 해결형','C-1 단계별 안내','추가 검토']];
const intentDefinitions=[
['budget_flexible','가격 상한을 높이는 등 예산 조건을 조정할 수 있는 사용자','행동 신호: 최대가격 상향 또는 가격 필터 해제. 가격을 바꿨다는 이유만으로 이 의도군에 자동 배정하지 않음.'],
['option_count_flexible','필수로 요구하는 옵션 수를 줄일 수 있는 사용자','행동 신호: 요구 옵션 수 감소. 편의시설 종류별 해제가 아니라 옵션 개수 기준.'],
['location_flexible','원래 지역 대신 인접·대체 지역도 고려할 수 있는 사용자','행동 신호: 인접·대체 지역 선택. 지역 변경의 실제 회복 여부는 의도 판정에 사용하지 않음.'],
['condition_keeper','현재 검색 조건을 유지하려는 사용자','행동 신호: 동일 조건 반복 또는 조건 강화 경향. 반복 횟수 임계값은 현재 연결 자료에 없음.'],
['query_reframer','검색어 또는 표현을 바꿔 다시 찾으려는 사용자','행동 신호: 검색어 수정 또는 연관어 선택. 지역·조건 동시 변경 시 단일 의도 우선순위는 확인되지 않음.'],
['rapid_resolver','빠르게 결과를 찾는 것을 우선하는 사용자','행동 신호: 지역·가격·필터 복합 변경. 빠름을 판정하는 시간 임계값은 현재 연결 자료에 없음.']
];
$('#intent-cards').innerHTML=intents.map((x,i)=>`<article class="segment-card"><span class="label">${intentDefinitions[i][0]}</span><h3>${x[0]}</h3><p class="criterion"><b>의도 정의 · 배정값 미연결</b>${intentDefinitions[i][1]}</p><p>${intentDefinitions[i][2]}</p><p class="mapping">연결 개선안: ${x[1]}<br>연결 가설: ${x[2]}</p></article>`).join('');
const outcomeDefinitions=[
'첫 검색 결과가 1개 이상이고, 같은 세션에 호텔 클릭이 1회 이상 있음. 첫 검색에서의 클릭이나 예약 성공을 뜻하지 않음',
'첫 검색 결과가 1개 이상이지만, 같은 세션에 호텔 클릭이 없음',
'첫 검색 결과가 0개이고, 이후 검색 중 결과가 1개 이상 나온 검색이 있음. 바로 다음 검색일 필요는 없고 클릭도 필수 조건이 아님',
'첫 검색 결과가 0개이고, 이후에도 결과가 1개 이상 나온 검색이 없음. 후속 검색 기록 자체가 없는 세션도 포함'
];
$('#outcome-cards').innerHTML=D.segments.map((r,i)=>`<article class="segment-card outcome" style="--segment-color:${colors[i]}"><span class="label">SG${i+1} · 검색 후 성과군</span><h3>${r.name}</h3><div class="value">${fmt(r.n)}<span>세션 · ${pct(r.n,r.d)}%</span></div><p class="criterion"><b>분류 기준 · 실제 집계</b>${outcomeDefinitions[i]}</p><p class="mapping">분모: 전체 ${fmt(r.d)}세션<br>한 세션은 한 성과군에만 포함</p></article>`).join('');
['#journey-scope-a','#journey-scope-b'].forEach(id=>$(id).textContent=fullScope);
const journeySteps=steps=>'<ol class="journey-steps">'+steps.map(([title,body])=>`<li><strong>${title}</strong><span>${body}</span></li>`).join('')+'</ol>';
const outcomePaths=[
[['첫 검색 · 결과 있음','노출 결과 1개 이상'],['같은 세션의 탐색','추가 검색·0건 검색이 있어도 첫 결과 기준 유지'],['호텔 클릭 있음','첫 검색의 클릭일 필요 없음 · 예약 성공 아님']],
[['첫 검색 · 결과 있음','노출 결과 1개 이상'],['같은 세션의 탐색','추가 검색이나 비교 과정의 상세 순서는 미집계'],['호텔 클릭 없음','관측된 클릭 없음 · 이탈로 단정하지 않음']],
[['첫 검색 · 결과 없음','0건에서 출발'],['후속 검색 · 결과 회복','이후 한 번이라도 결과 1개 이상 · 즉시 회복과 구분'],['세션 내 클릭 여부','회복 여부와 별도로 클릭한 세션을 집계']],
[['첫 검색 · 결과 없음','0건에서 출발'],['후속 검색 없음 또는 미회복','두 경로의 세션 수는 현재 집계에 분리돼 있지 않음'],['관측 기록 끝까지 회복 없음','예약 실패·이탈을 의미하지 않음']]
];
const journeyCard=(r,i)=>`<article class="journey-card ${r.n?'':'empty-journey'}"><div class="journey-heading"><span class="label">SG${i+1} · ${r.name}</span><strong>${fmt(r.n)}세션 <small>· ${pct(r.n,r.d)}%</small></strong></div>${journeySteps(outcomePaths[i])}<div class="journey-stat">세션 내 클릭 ${fmt(r.click)} / ${fmt(r.n)} · ${pct(r.click,r.n)}%<br>세션당 평균 검색 ${r.n?Number(r.search_mean).toFixed(2)+'회':'—'}</div><details class="metric-notes"><summary>분모·해석</summary><p>구성비 분모는 선택한 ${fmt(r.d)}세션, 클릭 비율 분모는 이 성과군의 ${fmt(r.n)}세션입니다. 클릭 100% 또는 0%가 분류 조건인 SG1·SG2는 개선 효과가 아닙니다. 화살표마다 새로운 전환율을 계산한 퍼널이 아닙니다.</p></details></article>`;
$('#outcome-paths-a').innerHTML=D.segments.slice(0,2).map((r,i)=>journeyCard(r,i)).join('');
$('#outcome-paths-b').innerHTML=D.segments.slice(2).map((r,i)=>journeyCard(r,i+2)).join('');
const intentPaths=[
[['예산을 조정할 의향','사용자 의도 배정값 연결 필요'],['0건이면 가격 대안 제안','최대가격 상향·가격 필터 해제 선택지'],['사용자 선택 후 확인','다시 검색 → 결과 회복·클릭 검증']],
[['요구 옵션 수 조정 의향','사용자 의도 배정값 연결 필요'],['0건이면 옵션 수 완화 제안','필수 요구 개수를 줄일 선택지'],['사용자 선택 후 확인','다시 검색 → 결과 회복·클릭 검증']],
[['위치를 바꿀 의향','사용자 의도 배정값 연결 필요'],['0건이면 인접 지역 제안','인접·대체 지역의 대안 제시'],['사용자 선택 후 확인','다시 검색 → 결과 회복·클릭 검증']],
[['조건을 유지하려는 성향','사용자 의도 배정값 연결 필요'],['반복 상황에서 대안 비교','조건 유지와 완화의 차이를 안내'],['사용자 선택 후 확인','유지·변경 후 반복률·회복률 검증']],
[['표현을 수정하려는 성향','사용자 의도 배정값 연결 필요'],['0건이면 연관 검색어 제안','검색어 수정·자동완성 선택지'],['사용자 선택 후 확인','다시 검색 → 회복·상세진입 검증']],
[['여러 조건을 바꿔 해결','사용자 의도 배정값 연결 필요'],['0건이면 단계별 대안 제안','지역·가격·필터 대안을 순서대로 안내'],['사용자 선택 후 확인','단계별 선택 → 즉시·최종 회복 검증']]
];
const intentJourney=(i)=>`<article class="journey-card proposed-journey"><div class="journey-heading"><span class="label">제안 흐름 · ${intents[i][2]}</span><h3>${intents[i][0]}</h3></div>${journeySteps(intentPaths[i])}<p class="meta">미수용·미회복도 가능 · 제안 노출·선택 로그 없음</p></article>`;
$('#intent-paths-a').innerHTML=[0,1,2].map(intentJourney).join('');$('#intent-paths-b').innerHTML=[3,4,5].map(intentJourney).join('');

const region=D.methods.find(r=>r.name==='지역 변경'),relax=D.methods.find(r=>r.name==='조건 완화'),repeat=D.methods.find(r=>r.name==='동일조건 반복');
$('#findings').innerHTML=[['전체 세션의 즉시 회복',`회복 ${fmt(c.recovered)}/${fmt(c.followup)} = ${pct(c.recovered,c.followup)}%. 세션 마지막 검색 회복은 ${fmt(c.final_recovered)}/${fmt(c.zero_sessions)} = ${pct(c.final_recovered,c.zero_sessions)}%로 별도 지표입니다.`,'합성 복합 개입과 구분해 조건 완화 단독 실험'],['전체 방법별 회복 비교',`지역 변경 ${fmt(region.n)}/${fmt(region.d)} = ${pct(region.n,region.d)}%, 조건 완화 ${fmt(relax.n)}/${fmt(relax.d)} = ${pct(relax.n,relax.d)}%. 관측된 행동 차이입니다.`,'사전 지역군 비교 참고 · 제안 노출/선택 계측'],['전체 동일 조건 반복',`동일 조건 반복의 회복 ${fmt(repeat.n)}/${fmt(repeat.d)} = ${pct(repeat.n,repeat.d)}%. 분모가 0이면 해당 전환이 없는 경우입니다.`,'반복 안내 후 반복률·회복률 확인']].map((x,i)=>`<article class="decision"><div class="big">0${i+1}</div><div><h2>${x[0]}</h2><p>${x[1]}</p></div><div class="next"><strong>연결할 판단</strong><p>${x[2]}</p></div></article>`).join('');
$('#source').innerHTML=`<p>${D.meta.type}</p><p class="mono">${D.meta.file}</p><p class="mono">SHA-256: ${D.meta.sha256}</p><p>파일 크기 ${fmt(D.meta.size)} bytes. SQLite integrity_check: ${D.meta.integrity}. 원본 읽기 전용 집계.</p>`;$('#download').onclick=()=>{let u=URL.createObjectURL(new Blob([JSON.stringify(!$('#page-0').hidden?JSON.parse($('#overview-data').textContent):D,null,2)],{type:'application/json'}));let a=document.createElement('a');a.href=u;a.download=!$('#page-0').hidden?'Hotel_Search_10000_Overview.json':'Hotel_Search_1000_Data.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
}

renderDashboard();page(4);
const abProtocol=[...document.querySelectorAll('#page-2 article.panel')].find(x=>x.querySelector('h2')?.textContent.includes('기존 A/B 연결 정보'));if(abProtocol)abProtocol.id='ab-protocol';
const OV=JSON.parse($('#overview-data').textContent);const KC={...OV.counts,followup:OV.funnel.followup,recovered:OV.funnel.recovered,zero_sessions:OV.counts.zero_users};const K={recovered_click:{n:OV.funnel.recovered_click,d:OV.funnel.recovered}};
function formulaCard(title,numerator,denominator,n,d,role,primary=false){return `<article class="formula-card ${primary?'primary':''}"><span class="badge ${primary?'':'gray'}">${role}</span><h3>${title}</h3><div class="formula-expression"><span class="fraction"><span class="numerator">${numerator}</span><span class="denominator">${denominator}</span></span><span>× 100</span></div><div class="formula-value">${pct(n,d)}%<small>${fmt(n)} / ${fmt(d)}</small></div></article>`;}

const slides=[
['재검색은 이어지지만, 즉시 회복은 17.1%',4,['#template-story-topic']],
['왜 검색 회복에 주목했는가?',4,['#template-story-problem']],
['전체 검색 참여 현황 · 10,000명',0,['#overview-top']],
['기간별 검색량 · 합성 시간축',0,['#overview-trends .analytics-chart']],
['사용자는 어떤 검색 경험을 했나?',0,['#overview-experience .analytics-chart']],
['가설 1 · 조건 완화가 즉시 회복률을 높이는가?',1,['#template-hypothesis-1']],
['가설 2 · 조건 완화 효과는 검색의도별로 다른가?',1,['#template-hypothesis-2']],
['가설 3 · 지역 확대 제안이 결과 회복으로 이어지는가?',1,['#template-hypothesis-3']],
['검색의도 · 무엇을 바꿀 수 있나?',0,['#template-story-intents']],
['의도별 개선안 · 바꿀 수 있는 조건부터',2,['#template-story-proposals']],
['1만 명 합성 A/B · 회복과 상세진입',2,['#report-summary']],
['다음 의사결정 · 실제 효과를 확인하기',3,['#template-story-decisions']],
['사용한 데이터',4,['#template-data-summary']],
['시행착오 및 한계',4,['#template-data-limits']],
['[부록] 고정 개선율 시뮬레이션',5,['#fixed-scenarios']],
['[부록] StayTrace · 데이터를 수집한 과정',4,['#template-site_entry']],
['부록 · 팀원 구성 및 논문·데이터셋',4,['#template-team','#template-research']]
];let slideIndex=0;
const agendaGroups=[['기획과 배경',0,2],['전체 현황과 검색 흐름',2,5],['가설과 검증',5,8],['검색의도와 개선안',8,10],['합성 A/B와 결론',10,12],['데이터와 한계',12,14],['부록',14,17]];
const agendaHTML=agendaGroups.map(([name,start,end])=>`<section><h3>${name} · ${start+1}~${end}장</h3><ol start="${start+1}">${slides.slice(start,end).map(([title],i)=>`<li><button type="button" data-slide-jump="${start+i}">${title}</button></li>`).join('')}</ol></section>`).join('');
['#dashboard-agenda','#presentation-agenda'].forEach(id=>$(id).innerHTML=agendaHTML);
document.querySelectorAll('[data-slide-jump]').forEach(button=>button.onclick=()=>{document.body.classList.add('presenting');$('#presentation-mode').setAttribute('aria-pressed','true');$('#presentation-mode').textContent='대시보드로 돌아가기';document.querySelectorAll('details').forEach(d=>d.open=false);slideIndex=Number(button.dataset.slideJump);renderSlide();$('#slide-title').focus({preventScroll:true});});
function cloneForSlide(selector){const source=$(selector);if(!source||source.hidden)return document.createElement('div');const el=source.cloneNode(true);el.removeAttribute('id');el.querySelectorAll('[id]').forEach(x=>x.removeAttribute('id'));el.querySelectorAll('details').forEach(x=>x.open=false);el.querySelectorAll('.choice-control').forEach(x=>{const label=document.createElement('span');label.className='badge gray';label.textContent='비교 기준군: '+x.dataset.selectedLabel;x.replaceWith(label);});el.querySelectorAll('select').forEach(x=>{const label=document.createElement('span');label.className='badge gray';label.textContent=x.selectedOptions[0]?.textContent||'';x.replaceWith(label);});el.querySelectorAll('input').forEach(x=>{const text=document.createElement('span');text.className='badge gray';text.textContent=x.value?x.value+'%':'목표 미설정';x.replaceWith(text);});el.querySelectorAll('button').forEach(x=>x.remove());return el;}
function renderSlide(){const [title,n,selectors]=slides[slideIndex];$('#slide-title').textContent=title;$('#slide-counter').textContent=(slideIndex+1)+' / '+slides.length;$('#slide-position').textContent=(slideIndex+1)+' / '+slides.length;$('#slide-stage').replaceChildren(...selectors.map(cloneForSlide));addFirstUseTermNotes();$('#slide-script').replaceChildren(cloneForSlide('#page-'+n+' > .speaker-notes'));if(selectors.includes('#primary-kpi')){const extra=document.createElement('p');extra.textContent='주 KPI는 0건 이후 후속 검색에서 결과를 찾은 비율입니다. 현재 10,000명 전체 집계는 5,611/29,184 = 약 19.23%입니다. 모든 0건 검색을 분모로 하면 5,611/30,614 = 18.33%이므로 두 지표를 구분합니다.';$('#slide-script .speaker-notes').append(extra);}if(selectors[0].startsWith('#template-'))$('#slide-script').replaceChildren();if(selectors.includes('#template-segments'))$('#slide-script').replaceChildren(cloneForSlide('#segment-presentation-notes'));if(selectors.includes('#template-after-search'))$('#slide-script').replaceChildren(cloneForSlide('#after-search-notes'));if(selectors.includes('#template-data-summary'))$('#slide-script').replaceChildren(cloneForSlide('#data-summary-notes'));if(selectors.includes('#template-data-limits'))$('#slide-script').replaceChildren(cloneForSlide('#data-limits-notes'));for(const key of ['topic','problem','overview','funnel','intents','proposals','decisions']){if(selectors.includes('#template-story-'+key))$('#slide-script').replaceChildren(cloneForSlide('#story-'+key+'-notes'));}for(let h=1;h<=3;h++){if(selectors.includes('#template-hypothesis-'+h))$('#slide-script').replaceChildren(cloneForSlide('#hypothesis-'+h+'-notes'));}$('#prev-slide').disabled=slideIndex===0;$('#next-slide').disabled=slideIndex===slides.length-1;window.scrollTo(0,0);}
function moveSlide(step){slideIndex=Math.max(0,Math.min(slides.length-1,slideIndex+step));renderSlide();}
$('#prev-slide').onclick=()=>moveSlide(-1);$('#next-slide').onclick=()=>moveSlide(1);$('#presentation-mode').textContent='슬라이드 모드';$('#presentation-mode').onclick=()=>{const on=document.body.classList.toggle('presenting');$('#presentation-mode').setAttribute('aria-pressed',on);$('#presentation-mode').textContent=on?'대시보드로 돌아가기':'슬라이드 모드';document.querySelectorAll('details').forEach(d=>d.open=false);if(on){slideIndex=0;renderSlide();}else window.scrollTo(0,0);};document.addEventListener('keydown',e=>{if(!document.body.classList.contains('presenting')||['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName))return;if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();moveSlide(e.key==='ArrowRight'?1:-1);}});
// Show each definition only on the first slide whose visible content uses it.
const slideTermDefinitions=[
{terms:['세션'],label:'세션',text:'이어진 검색·행동의 묶음. 검색 1건은 요청 한 번.'},
{terms:['결과 없음','결과가 없','0건'],label:'결과 없음',text:'검색 결과가 0개인 상태.'},
{terms:['후속 검색','후속검색'],label:'후속 검색',text:'같은 세션에서 이어지는 검색. 즉시 회복에서는 바로 다음 검색을 뜻함.'},
{terms:['즉시 회복'],label:'즉시 회복',text:'0건 직후 다음 검색에서 결과를 1개 이상 찾음.'},
{terms:['의도군','검색의도','6가지 의도'],label:'검색의도',text:'제안 전에 바꿀 수 있는 조건과 해결 선호로 나눈 사용자 기준.'},
{terms:['성과 세그먼트','4가지 성과'],label:'성과 세그먼트',text:'첫 검색 결과와 이후 회복·클릭으로 나눈 세션 기준.'},
{terms:['전환율'],label:'전환율',text:'해당 단계에 도달한 건수 ÷ 그 단계의 대상 건수 × 100.'},
{terms:['%p'],label:'%p',text:'두 비율의 차이. 20%에서 25%는 +5%p.'},
{terms:['상대 변화','상대 개선','상대값'],label:'상대 변화',text:'비율 차이 ÷ 기준 비율 × 100. 20%에서 25%는 +25%.'},
{terms:['유의성','신뢰구간'],label:'유의성·신뢰구간',text:'통계적 판단과 추정의 불확실성 범위. 합성 A/B는 고정 모형의 조건부 구간이며 실제 효과는 미검증.'},
{terms:['A-1'],label:'A-1',text:'조건 완화 검증. 회복률의 분모는 0건 이후 후속 검색.'},
{terms:['D-1'],label:'D-1',text:'지역 확대 검증. 회복률의 분모는 지역 변경 후속 검색.'},
{terms:['지역 선택률','수용률'],label:'지역 선택률',text:'지역 확대 제안 선택 ÷ 제안 노출 × 100.'},
{terms:['예산 유연형','budget_flexible'],label:'예산 유연형',text:'가격 범위를 넓힐 의향이 있는 사용자.'},
{terms:['옵션 유연형','옵션 수 유연형','option_count_flexible'],label:'옵션 수 유연형',text:'필요한 옵션 개수를 줄일 의향이 있는 사용자.'},
{terms:['위치 유연형','location_flexible'],label:'위치 유연형',text:'인접·대체 지역을 고려할 의향이 있는 사용자.'},
{terms:['A/B','대조군','실험군','제안군'],label:'A/B',text:'기존 검색을 쓰는 대조군과 맞춤 제안을 받는 실험군을 비교.'},
{terms:['arm'],label:'arm',text:'실험의 비교 집단. 문서의 5,000명/arm은 설계값이며 실측 표본이 아님.'},
{terms:['합성','확장본'],label:'합성 확장본',text:'원본을 바탕으로 생성한 데이터. 추가 모집한 관측 표본이 아님.'},
{terms:['KPI'],label:'KPI',text:'목표 달성 정도를 확인하는 핵심 지표.'},
{terms:['HOLD'],label:'HOLD',text:'검증 조건 미충족으로 정식 판정을 보류한 상태.'},
{terms:['퍼널'],label:'퍼널',text:'단계별로 다음 행동·결과에 이어지는 규모를 보여주는 그림.'}
];
function addFirstUseTermNotes(){
 const seen=new Set();
 let current=[];
 for(let i=0;i<=slideIndex;i++){
  const [title,,selectors]=slides[i];
  const content=selectors.map(selector=>{const node=cloneForSlide(selector);node.querySelectorAll('details').forEach(el=>el.remove());return node.textContent;}).join(' ');
  const visible=title+' '+content;
  current=slideTermDefinitions.filter((entry,index)=>{if(seen.has(index)||!entry.terms.some(term=>visible.includes(term)))return false;seen.add(index);return true;});
 }
 if(!current.length)return;
 const notes=document.createElement('aside');notes.className='slide-term-notes';notes.setAttribute('aria-label','처음 나오는 용어 풀이');
 current.forEach(entry=>{const item=document.createElement('span');const label=document.createElement('b');label.textContent=entry.label+' ';item.append(label,document.createTextNode(entry.text));notes.append(item);});
 $('#slide-stage').append(notes);
}

if(location.hash==='#report-results'){page(2);}

if(location.hash==="#exploratory-all-metrics"){page(2);document.querySelector("#exploratory-all-metrics").scrollIntoView();}

if(location.hash==="#overview-charts"){page(0);document.querySelector("#overview-top").scrollIntoView();}
