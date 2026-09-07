
'use strict';const PACK={{DATA_PACK}};let D=PACK.slices['ALL|ALL'];const $=s=>document.querySelector(s);const fmt=n=>Number(n).toLocaleString('ko-KR');const rate=(n,d)=>d?n/d*100:0;const pct=(n,d)=>d?rate(n,d).toFixed(1):'—';const colors=['#176858','#a9c7b8','#b88b51','#d8cabb'];
let chartSeq=0;let chartRegistry={};const chartBaselines={};
function periodLabel(data=D){return data.period&&data.period.start?data.period.start.slice(0,10)+' ~ '+data.period.end.slice(0,10)+' · 합성 검색 시간':'해당 기간 데이터 없음';}
function periodHTML(data=D){return '<div class="analysis-period">분석 기간 '+periodLabel(data)+' · 선택 '+fmt(data.counts.sessions)+'세션</div>';}
function signed(n){return (n>0?'+':'')+n.toFixed(1);}
function verticalBars(rows){return `<div class="vchart-scroll"><div class="vchart" style="--cols:${rows.length}" role="img" aria-label="집단별 비율 세로 막대, 0~100%"><div class="vaxis"><span>100%</span><span>50%</span><span>0%</span></div><div class="vplot">${rows.map((r,i)=>`<div class="vcolumn"><div class="vwell"><div class="vbar" style="height:${rate(r.n,r.d)}%;background:${colors[i%4]}"><strong>${pct(r.n,r.d)}%</strong></div></div><div class="vlabel">${r.name}</div><div class="vcount">${fmt(r.n)} / ${fmt(r.d)}</div></div>`).join('')}</div></div></div>`;}
function choiceControl(rows,key,selected,metric){const name=rows[selected]?.name||'항목 없음';const label=metric+' 비교 기준군';if(rows.length<=1)return `<span class="choice-control" data-selected-label="${name}">비교 항목: ${name} · 비교 집단 없음</span>`;if(rows.length<5)return `<div class="choice-control choice-buttons" data-selected-label="${name}"><span class="meta">비교 기준군</span><div role="radiogroup" aria-label="${label}">${rows.map((r,i)=>`<button type="button" role="radio" aria-checked="${i===selected}" tabindex="${i===selected?0:-1}" data-choice-key="${key}" data-choice-value="${i}">${r.name}</button>`).join('')}</div></div>`;return `<label class="choice-control" data-selected-label="${name}">비교 기준군<select data-chart-baseline="${key}" aria-label="${label}">${rows.map((r,i)=>`<option value="${i}" ${i===selected?'selected':''}>${r.name}</option>`).join('')}</select></label>`;}
function comparisonHTML(rows,key,metric){const preferred=rows.findIndex(r=>r.name==='조건 완화');let baseline=rows.findIndex(r=>r.name===chartBaselines[key]);if(baseline<0)baseline=preferred>=0?preferred:0;const b=rows[baseline];return periodHTML()+`<div class="chart-controls"><span class="badge gray">${metric} · 관측 비교</span>${choiceControl(rows,key,baseline,metric)}</div>`+verticalBars(rows)+`<div class="scroll"><table class="lift-table"><thead><tr><th>집단</th><th>${metric}</th><th>차이</th><th>상대 변화</th><th>유의성</th></tr></thead><tbody>${rows.map((r,i)=>{const valid=r.d>0&&b&&b.d>0;const diff=valid?rate(r.n,r.d)-rate(b.n,b.d):null;const lift=valid&&b.n>0?diff/rate(b.n,b.d)*100:null;return `<tr><td>${r.name}${i===baseline?' · 기준':''}</td><td>${pct(r.n,r.d)}%</td><td>${rows.length<2||i===baseline?'—':diff===null?'—':signed(diff)+'%p'}</td><td>${rows.length<2||i===baseline?'—':lift===null?'—':signed(lift)+'%'}</td><td>미산출</td></tr>`}).join('')}</tbody></table></div><details class="metric-notes"><summary>지표 정의·해석</summary><p class="chart-method">차이(%p)는 비교군 비율 − 기준군 비율입니다. 상대 변화(관측 업리프트, %)는 차이 ÷ 기준군 비율 × 100입니다. 기준군이 0%이면 상대 변화는 —입니다. 합성·반복 관측 자료이며 A/B 배정 정보 미연결로 p값·신뢰구간은 미산출입니다. 양수는 수치 증가를 뜻하며 개선 여부는 지표에 따라 다릅니다.</p></details>`;}
function bars(rows,metric='전환율'){if(metric==='구성비')return periodHTML()+verticalBars(rows)+'<details class="metric-notes"><summary>지표 정의·해석</summary><p class="chart-method">성과군 구성비입니다. 전환율·처치 업리프트와 구분합니다.</p></details>';const key='metric-'+chartSeq++;chartRegistry[key]={rows,metric};return `<div id="${key}">${comparisonHTML(rows,key,metric)}</div>`;}
function selectBaseline(key,value,focus=false){const x=chartRegistry[key];if(!x||!x.rows[value])return;chartBaselines[key]=x.rows[value].name;$('#'+key).innerHTML=comparisonHTML(x.rows,key,x.metric);if(focus)$('#'+key).querySelector('[role="radio"][aria-checked="true"]')?.focus({preventScroll:true});}
document.addEventListener('change',event=>{const key=event.target.dataset.chartBaseline;if(key)selectBaseline(key,Number(event.target.value));});
document.addEventListener('click',event=>{const b=event.target.closest('[data-choice-key]');if(b)selectBaseline(b.dataset.choiceKey,Number(b.dataset.choiceValue),true);});
document.addEventListener('keydown',event=>{const b=event.target.closest('[data-choice-key]');if(!b)return;const key=b.dataset.choiceKey,n=chartRegistry[key].rows.length;let index=Number(b.dataset.choiceValue);if(['ArrowRight','ArrowDown'].includes(event.key))index=(index+1)%n;else if(['ArrowLeft','ArrowUp'].includes(event.key))index=(index+n-1)%n;else if(event.key==='Home')index=0;else if(event.key==='End')index=n-1;else return;event.preventDefault();selectBaseline(key,index,true);});


function page(i){document.querySelectorAll('.page').forEach(e=>e.hidden=e.id!=='page-'+i);document.querySelectorAll('nav button').forEach(e=>{const active=+e.dataset.page===i;e.setAttribute('aria-selected',active);e.tabIndex=active?0:-1});$('.slicers').hidden=i===4;$('#slide-position').textContent=([4,0,1,2,3].indexOf(i)+1)+' / 5';window.scrollTo(0,0)}
document.querySelectorAll('[data-page]').forEach(e=>e.onclick=()=>page(+e.dataset.page));document.querySelectorAll('nav button').forEach((e,i)=>e.onkeydown=x=>{if(['ArrowRight','ArrowLeft'].includes(x.key)){x.preventDefault();const tabs=[...document.querySelectorAll('nav button')];let n=(i+(x.key==='ArrowRight'?1:tabs.length-1))%tabs.length;tabs[n].click();tabs[n].focus()}});
function recoveryHTML(data){const c=data.counts;
const funnelStages=[['결과 없음',c.zero,'시작 기준'],['후속 검색 기록 있음',c.followup,'직전 단계 대비'],['다음 검색에서 회복',c.recovered,'직전 단계 대비'],['회복한 검색에 클릭',data.recovered_click.n,'직전 단계 대비']];
const sideNotes=['',`후속 검색 기록 없음 ${fmt(c.zero-c.followup)}건 · ${pct(c.zero-c.followup,c.zero)}%`,`즉시 미회복 ${fmt(c.followup-c.recovered)}건 · ${pct(c.followup-c.recovered,c.followup)}%`,`회복한 검색에 클릭 기록 없음 ${fmt(c.recovered-data.recovered_click.n)}건 · ${pct(c.recovered-data.recovered_click.n,c.recovered)}%`];
return periodHTML(data)+`<div class="funnel-extra"><div><span>0건 검색 → 즉시 회복</span><strong>${pct(c.recovered,c.zero)}%</strong><span>${fmt(c.recovered)} / ${fmt(c.zero)} · 0건 검색 기준</span></div><div><span>0건 검색 → 회복 후 클릭</span><strong>${pct(data.recovered_click.n,c.zero)}%</strong><span>${fmt(data.recovered_click.n)} / ${fmt(c.zero)} · 0건 검색 기준</span></div><div><span>후속 검색 기록 없음</span><strong>${fmt(c.zero-c.followup)}건</strong><span>${pct(c.zero-c.followup,c.zero)}% · 이탈로 단정하지 않음</span></div></div>`+funnelStages.map(([name,n,note],i)=>`<div class="funnel-step"><div class="funnel-row"><div class="funnel-label"><span class="meta">0${i+1}</span> ${name}</div><div class="funnel-track"><div class="funnel-bar" style="width:${rate(n,c.zero)}%;background:${['#91b5a5','#5c9881','#176858','#b88b51'][i]}"></div></div><div class="funnel-count"><strong>${fmt(n)}건</strong><span class="meta">${i?pct(n,funnelStages[i-1][1])+'% · '+note:(c.zero?'100%':'—')+' · '+note}</span><span class="meta">0건 검색 대비 ${pct(n,c.zero)}%</span></div></div>${i?`<p class="funnel-side">↳ ${sideNotes[i]}</p>`:''}</div>`).join('')+'<details class="metric-notes"><summary>지표 정의·해석</summary><p class="chart-method">통계적 유의성 미산출 · 관측 퍼널입니다. 서로 다른 단계의 전환율 차이를 A/B 업리프트로 해석하지 않습니다.</p></details>';
}

function renderDashboard(){chartSeq=0;chartRegistry={};const c=D.counts;
$('#overview-counts').textContent=fmt(c.sessions)+' sessions / '+fmt(c.searches)+' searches';
$('#overview-title').textContent=c.searches?'선택한 검색의 결과 없음 '+pct(c.zero,c.searches)+'%, 다음 검색 회복 '+pct(c.recovered,c.followup)+'%':'선택 조건에 해당하는 세션이 없습니다.';
$('#overview-scope').textContent=fmt(c.sessions)+'세션 · 검색 '+fmt(c.searches)+'건 · 합성 데이터';
$('#filter-summary').textContent=($('#month-slicer').value==='ALL'?'전체 월':$('#month-slicer').value)+' / '+($('#segment-slicer').value==='ALL'?'전체 성과군':$('#segment-slicer').value)+' · '+fmt(c.sessions)+'세션 · '+fmt(c.searches)+'검색';
const noteBase=PACK.slices[$('#month-slicer').value+'|ALL'];$('#funnel-summary').textContent='기본 퍼널은 기간 기준 전체입니다. '+fmt(noteBase.counts.zero)+'건의 0건 검색 중 '+fmt(noteBase.counts.followup)+'건('+pct(noteBase.counts.followup,noteBase.counts.zero)+'%)에 후속 검색이 있습니다. 성과군을 선택하면 그 집단은 아래 별도 비교로 표시합니다.';
$('#kpis').innerHTML=[['결과 없음',c.zero,c.searches,'전체 검색'],['0건 이후 후속 검색',c.followup,c.zero,'0건 검색'],['다음 검색에서 회복',c.recovered,c.followup,'후속 검색 전환'],['세션 마지막 검색 회복',c.final_recovered,c.zero_sessions,'0건 경험 세션']].map(([name,n,d,unit])=>`<article class="card"><div class="eyebrow">${name}</div><div class="value">${pct(n,d)}<em>%</em></div><p>${fmt(n)} / ${fmt(d)} · ${unit}</p></article>`).join('');
const activeSegment=$('#segment-slicer').value;const funnelBase=PACK.slices[$('#month-slicer').value+'|ALL'];const baseCounts=funnelBase.counts;
$('#funnel-filter-note').textContent='기본 퍼널: 선택 기간의 전체 성과군 · 성과 세그먼트 필터 미적용';
$('#search-branches').innerHTML=periodHTML(funnelBase)+`<div class="funnel-extra"><div><span>전체 검색</span><strong>${fmt(baseCounts.searches)}건</strong><span>분기 기준 100%</span></div><div><span>결과 있음</span><strong>${fmt(baseCounts.searches-baseCounts.zero)}건</strong><span>${pct(baseCounts.searches-baseCounts.zero,baseCounts.searches)}% · 전체 검색 기준</span></div><div><span>결과 없음 → 아래 회복 퍼널</span><strong>${fmt(baseCounts.zero)}건</strong><span>${pct(baseCounts.zero,baseCounts.searches)}% · 전체 검색 기준</span></div></div><div style="display:flex;height:28px;border-radius:6px;overflow:hidden;background:#eff1ec" role="img" aria-label="결과 있음 ${fmt(baseCounts.searches-baseCounts.zero)}건, 결과 없음 ${fmt(baseCounts.zero)}건"><div style="width:${rate(baseCounts.searches-baseCounts.zero,baseCounts.searches)}%;background:#176858"></div><div style="width:${rate(baseCounts.zero,baseCounts.searches)}%;background:#b88b51"></div></div><div class="legend" style="margin-top:8px"><span>● 결과 있음</span><span style="color:#a16624">● 결과 없음</span></div>`;
$('#recovery-funnel').innerHTML=recoveryHTML(funnelBase);
$('#funnel-comparison').hidden=activeSegment==='ALL';$('#comparison-funnel').innerHTML=activeSegment==='ALL'?'':recoveryHTML(D);$('#comparison-funnel-title').textContent='선택 성과군 비교 · '+activeSegment;

const methods=[...D.methods].sort((a,b)=>rate(b.n,b.d)-rate(a.n,a.d));$('#method-bars').innerHTML=bars(methods,'즉시 회복률');$('#segment-bars').innerHTML=bars(D.segments,'구성비');$('#zero-bars').innerHTML=bars(D.zero_compare,'클릭 세션 전환율');$('#zero-delta').textContent=D.zero_compare.every(r=>r.d)?'0건 경험 − 미경험 클릭 비율 차이: '+(rate(D.zero_compare[1].n,D.zero_compare[1].d)-rate(D.zero_compare[0].n,D.zero_compare[0].d)).toFixed(1)+'%p':'비교할 집단의 분모가 0이므로 차이를 표시하지 않습니다.';
$('#segment-donut').innerHTML=bars(D.segments,'구성비');
const points=D.months.map((r,i)=>[60+i*(840/Math.max(D.months.length-1,1)),190-rate(r.n,r.d)*1.5]);$('#timeline').innerHTML=periodHTML()+`<svg class="chartsvg" viewBox="0 0 960 245" role="img" aria-label="합성 데이터 월별 결과 없음 비율">${[0,50,100].map(v=>`<line x1="60" x2="910" y1="${190-v*1.5}" y2="${190-v*1.5}" stroke="#dedfd7"/><text x="12" y="${195-v*1.5}" font-size="12" fill="#63716f">${v}%</text>`).join('')}<polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#176858" stroke-width="3"/>${D.months.map((r,i)=>`<circle cx="${points[i][0]}" cy="${points[i][1]}" r="4" fill="#176858"/><text x="${points[i][0]}" y="${points[i][1]-13}" text-anchor="middle" font-size="12" fill="#16302e">${pct(r.n,r.d)}%</text><text x="${points[i][0]}" y="214" text-anchor="middle" font-size="12" fill="#63716f">${r.name.slice(5)}월</text><text x="${points[i][0]}" y="233" text-anchor="middle" font-size="10" fill="#63716f">${r.n}/${r.d}</text>`).join('')}</svg>`;
const H={H1:['전체 회복','전체 의도군 · 회복률','B − A 회복률 증가','어떤 조건에서 결과가 없었나?',D.filters,'선택된 조건별 검색의 0건 비율을 비교합니다. 조건 완화 제안의 효과와는 구분합니다.'],H5:['지역 확대','위치 유연형 · 회복률','B − A 회복률 증가','지역 변경과 다른 방법의 회복률',methods.filter(x=>['지역 변경','검색어 수정','조건 완화'].includes(x.name)),'선택된 방법별 회복률입니다. 스스로 선택한 행동의 차이이므로 지역 제안의 인과효과로 단정하지 않습니다.'],H4:['반복 방지','조건 고수형 · 반복률','B − A 반복률 감소','같은 조건 반복과 변경 후 회복',D.methods.filter(x=>['동일조건 반복','조건 완화','조건 강화'].includes(x.name)),'선택된 동일 조건 반복 전환의 회복률입니다. 반복 안내 효과와는 구분합니다.']};
$('#hyp-overview').innerHTML=Object.entries(H).map(([id,h])=>`<tr><td><button class="rowlink" data-hyp="${id}">${id} · ${h[0]}</button></td><td>${h[1]}</td><td>${h[2]}<br><span class="meta">기존 판정 문턱 연결 필요</span></td><td><span class="badge">관측 집계 완료</span><br><span class="meta">A/B 판정 미연결</span></td></tr>`).join('');
function showHyp(id){selectedHyp=id;let h=H[id];$('#hyp-selector').innerHTML=Object.entries(H).map(([key,x])=>`<button data-select="${key}" aria-pressed="${key===id}">${key} · ${x[0]}</button>`).join('');document.querySelectorAll('[data-select]').forEach(e=>e.onclick=()=>showHyp(e.dataset.select));let delta=h[4].length>=2&&h[4][0].d&&h[4][1].d?(h[4][0].n/h[4][0].d*100-h[4][1].n/h[4][1].d*100).toFixed(1):null;$('#hyp-content').innerHTML=`<div class="grid"><article class="panel"><span class="badge">${id} · 관측 근거</span><h2 class="hyp-title">${h[3]}</h2>${bars(h[4],id==='H2'?'구성비':id==='H1'?'결과 없음 비율':id==='H3'?'회복 후 클릭률':'즉시 회복률')}<div class="callout">${h[5]}</div></article><article class="panel"><h2>${id} · ${h[0]} 검증</h2><dl><div class="definition"><dt>대상·지표</dt><dd>${h[1]}</dd></div><div class="definition"><dt>판정 방향</dt><dd>${h[2]}</dd></div><div class="definition"><dt>현재 차이</dt><dd>${delta!==null&&id!=='H2'?h[4][0].name+' − '+h[4][1].name+': '+delta+'%p (관측 차이)':'대조군·실험군 효과 차이 미연결'}</dd></div><div class="definition"><dt>불확실성</dt><dd>신뢰구간·검정 미산출. 합성 생성 구조와 세션 내 반복 관측을 고려해야 합니다.</dd></div><div class="definition"><dt>현재 판정</dt><dd>관측 근거 집계 완료. 기존 A/B 판정 자료 미연결</dd></div></dl><button class="linkbutton" id="to-ab">세그먼트·A/B 확인 →</button></article><article class="panel wide"><h2>분자·분모·표본을 함께 확인</h2><div class="scroll"><table><thead><tr><th>관측 집단</th><th>분자</th><th>분모</th><th>포함 세션 수</th><th>비율</th></tr></thead><tbody>${h[4].map(r=>`<tr><td>${r.name}</td><td>${fmt(r.n)}</td><td>${fmt(r.d)}</td><td>${r.users!==undefined?fmt(r.users):id==='H2'?fmt(r.n):'이 집계표에서 별도 미산출'}</td><td>${pct(r.n,r.d)}%</td></tr>`).join('')}</tbody></table></div><p class="foot">H1 관측 그래프의 분모는 조건별 검색 수, H4·H5 관측 그래프의 분모는 해당 후속 검색 전환 수입니다. H4의 반복률 효과는 별도 A/B 집계가 필요합니다. 집단별 포함 세션 수는 합산하지 않습니다.</p></article></div>`;$('#to-ab').onclick=()=>{page(2)}}
document.querySelectorAll('[data-hyp]').forEach(e=>e.onclick=()=>{showHyp(e.dataset.hyp);page(1)});showHyp(selectedHyp);
const intents=[['예산 유연형','A-1 가격 범위 확대','H1'],['옵션 유연형','A-1 필요한 옵션 수 감소','H1'],['위치 유연형','D-1 인접지역 제안','H5'],['조건 고수형','F-1 반복 안내','H4'],['표현 수정형','D-2 연관 검색어 제안','추가 검토 · 발표 가설 제외'],['빠른 해결형','C-1 단계별 안내','추가 검토 · 발표 가설 제외']];const savedIntent=$('#intent').value;$('#intent').innerHTML=intents.map((x,i)=>`<option value="${i}">${x[0]}</option>`).join('');function intent(){let x=intents[+$('#intent').value];$('#intent-content').innerHTML=`<div class="divider"></div><h3>${x[1]}</h3><p>연결 가설: ${x[2]}</p><p class="meta">문서의 개선안 매핑입니다. 이 경량 DB에는 의도군별 A/B 배정값이 포함되어 있지 않습니다.</p>`}$('#intent').value=savedIntent||'0';$('#intent').onchange=intent;intent();

const intentDefinitions=[
['budget_flexible','가격 상한을 높이는 등 예산 조건을 조정할 수 있는 사용자','행동 신호: 최대가격 상향 또는 가격 필터 해제. 가격을 바꿨다는 이유만으로 이 의도군에 자동 배정하지 않음.'],
['option_count_flexible','필수로 요구하는 옵션 수를 줄일 수 있는 사용자','행동 신호: 요구 옵션 수 감소. 편의시설 종류별 해제가 아니라 옵션 개수 기준.'],
['location_flexible','원래 지역 대신 인접·대체 지역도 고려할 수 있는 사용자','행동 신호: 인접·대체 지역 선택. 지역 변경의 실제 회복 여부는 의도 판정에 사용하지 않음.'],
['condition_keeper','현재 검색 조건을 유지하려는 사용자','행동 신호: 동일 조건 반복 또는 조건 강화 경향. 반복 횟수 임계값은 현재 연결 자료에 없음.'],
['query_reframer','검색어 또는 표현을 바꿔 다시 찾으려는 사용자','행동 신호: 검색어 수정 또는 연관어 선택. 지역·조건 동시 변경 시 단일 의도 우선순위는 확인되지 않음.'],
['rapid_resolver','빠르게 결과를 찾는 것을 우선하는 사용자','행동 신호: 지역·가격·필터 복합 변경. 빠름을 판정하는 시간 임계값은 현재 연결 자료에 없음.']
];
$('#intent-cards').innerHTML=intents.map((x,i)=>`<article class="segment-card"><span class="label">${intentDefinitions[i][0]}</span><h3>${x[0]}</h3><p class="criterion"><b>의도 정의 · 배정값 미연결</b>${intentDefinitions[i][1]}</p><p>${intentDefinitions[i][2]}</p><p class="mapping">연결 개선안: ${x[1]}<br>연결 가설: ${x[2]}</p><button data-intent-card="${i}">이 의도군의 A/B 연결 보기 →</button></article>`).join('');
const outcomeDefinitions=[
'첫 검색 결과가 1개 이상이고, 같은 세션에 호텔 클릭이 1회 이상 있음. 첫 검색에서의 클릭이나 예약 성공을 뜻하지 않음',
'첫 검색 결과가 1개 이상이지만, 같은 세션에 호텔 클릭이 없음',
'첫 검색 결과가 0개이고, 이후 검색 중 결과가 1개 이상 나온 검색이 있음. 바로 다음 검색일 필요는 없고 클릭도 필수 조건이 아님',
'첫 검색 결과가 0개이고, 이후에도 결과가 1개 이상 나온 검색이 없음. 후속 검색 기록 자체가 없는 세션도 포함'
];
$('#outcome-cards').innerHTML=D.segments.map((r,i)=>`<article class="segment-card outcome" style="--segment-color:${colors[i]}"><span class="label">SG${i+1} · 검색 후 성과군</span><h3>${r.name}</h3><div class="value">${fmt(r.n)}<span>세션 · ${pct(r.n,r.d)}%</span></div><p class="criterion"><b>분류 기준 · 실제 집계</b>${outcomeDefinitions[i]}</p><p class="mapping">분모: 선택한 ${fmt(r.d)}세션<br>한 세션은 한 성과군에만 포함</p></article>`).join('');
['#journey-scope-a','#journey-scope-b'].forEach(id=>$(id).textContent=$('#filter-summary').textContent);
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
const intentJourney=(i)=>`<article class="journey-card proposed-journey"><div class="journey-heading"><span class="label">제안 흐름 · ${intents[i][2]}</span><h3>${intents[i][0]}</h3></div>${journeySteps(intentPaths[i])}<p class="meta">미수용·미회복도 가능 · 실제 결과 미연결</p></article>`;
$('#intent-paths-a').innerHTML=[0,1,2].map(intentJourney).join('');$('#intent-paths-b').innerHTML=[3,4,5].map(intentJourney).join('');
document.querySelectorAll('[data-intent-card]').forEach(b=>b.onclick=()=>{page(2);$('#intent').value=b.dataset.intentCard;intent();$('#intent').scrollIntoView({block:'center'});$('#intent').focus({preventScroll:true})});

const region=D.methods.find(r=>r.name==='지역 변경'),relax=D.methods.find(r=>r.name==='조건 완화'),repeat=D.methods.find(r=>r.name==='동일조건 반복');
$('#findings').innerHTML=[['선택한 세션의 즉시 회복',`회복 ${fmt(c.recovered)}/${fmt(c.followup)} = ${pct(c.recovered,c.followup)}%. 세션 마지막 검색 회복은 ${fmt(c.final_recovered)}/${fmt(c.zero_sessions)} = ${pct(c.final_recovered,c.zero_sessions)}%로 별도 지표입니다.`,'조건 완화의 기존 A/B 결과 확인'],['선택한 방법별 회복 비교',`지역 변경 ${fmt(region.n)}/${fmt(region.d)} = ${pct(region.n,region.d)}%, 조건 완화 ${fmt(relax.n)}/${fmt(relax.d)} = ${pct(relax.n,relax.d)}%. 관측된 행동 차이입니다.`,'위치 유연형의 제안 효과와 대조'],['선택한 동일 조건 반복',`동일 조건 반복의 회복 ${fmt(repeat.n)}/${fmt(repeat.d)} = ${pct(repeat.n,repeat.d)}%. 분모가 0이면 해당 전환이 없는 경우입니다.`,'반복 안내 후 반복률·회복률 확인']].map((x,i)=>`<article class="decision"><div class="big">0${i+1}</div><div><h2>${x[0]}</h2><p>${x[1]}</p></div><div class="next"><strong>연결할 판단</strong><p>${x[2]}</p></div></article>`).join('');
$('#source').innerHTML=`<p>${D.meta.type}</p><p class="mono">${D.meta.file}</p><p class="mono">SHA-256: ${D.meta.sha256}</p><p>파일 크기 ${fmt(D.meta.size)} bytes. SQLite integrity_check: ${D.meta.integrity}. 원본 읽기 전용 집계.</p>`;$('#download').onclick=()=>{let u=URL.createObjectURL(new Blob([JSON.stringify(D,null,2)],{type:'application/json'}));let a=document.createElement('a');a.href=u;a.download='Hotel_Search_1000_Data.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
}
let selectedHyp='H1';
$('#month-slicer').innerHTML='<option value="ALL">전체 월</option>'+PACK.months.map(m=>`<option value="${m}">${m}</option>`).join('');
$('#segment-slicer').innerHTML='<option value="ALL">전체 성과 세그먼트</option>'+PACK.segments.map(m=>`<option value="${m}">${m}</option>`).join('');
function applySlicers(){D=PACK.slices[$('#month-slicer').value+'|'+$('#segment-slicer').value];renderDashboard();}
$('#month-slicer').onchange=applySlicers;$('#segment-slicer').onchange=applySlicers;$('#reset-slicers').onclick=()=>{Object.keys(chartBaselines).forEach(k=>delete chartBaselines[k]);$('#month-slicer').value='ALL';$('#segment-slicer').value='ALL';applySlicers();};applySlicers();page(4);
const abProtocol=[...document.querySelectorAll('#page-2 article.panel')].find(x=>x.querySelector('h2')?.textContent.includes('기존 A/B 연결 정보'));if(abProtocol)abProtocol.id='ab-protocol';
const K=PACK.slices['ALL|ALL'],KC=K.counts;
function formulaCard(title,numerator,denominator,n,d,role,primary=false){return `<article class="formula-card ${primary?'primary':''}"><span class="badge ${primary?'':'gray'}">${role}</span><h3>${title}</h3><div class="formula-expression"><span class="fraction"><span class="numerator">${numerator}</span><span class="denominator">${denominator}</span></span><span>× 100</span></div><div class="formula-value">${pct(n,d)}%<small>${fmt(n)} / ${fmt(d)}</small></div></article>`;}
$('#primary-kpi').innerHTML=formulaCard('주 KPI · 후속 검색의 즉시 회복률','0건 직후 다음 검색에서 결과가 나온 건수','0건 이후 후속 검색이 있는 건수',KC.recovered,KC.followup,'목표 방향 ↑ · H1',true);
$('#supporting-kpis').innerHTML=[
['결과 없음 비율','검색 결과가 0개인 검색 수','전체 검색 수',KC.zero,KC.searches,'문제 규모 · 감소 방향'],
['0건 이후 후속 검색률','0건 이후 다음 검색이 있는 건수','모든 0건 검색 수',KC.followup,KC.zero,'진단 지표 · 회복률과 함께 해석'],
['모든 0건 검색 기준 즉시 회복률','0건 직후 다음 검색에서 결과가 나온 건수','모든 0건 검색 수',KC.recovered,KC.zero,'보조 지표 · 후속 검색 없는 경우 포함'],
['세션 마지막 검색 회복률','마지막 검색 결과가 1개 이상인 0건 경험 세션','0건을 한 번 이상 경험한 세션',KC.final_recovered,KC.zero_sessions,'보조 지표 · 세션 기준'],
['회복 후 클릭률','회복한 검색에 hotel_click이 있는 전환 수','즉시 회복한 전환 수',K.recovered_click.n,K.recovered_click.d,'보조 지표 · 회복 이후 클릭 참고']
].map(x=>formulaCard(...x)).join('');
function renderGoal(){const input=$('#goal-rate'),raw=input.value.trim(),target=Number(raw);$('#goal-error').textContent='';if(input.validity.badInput||raw!==''&&(!Number.isFinite(target)||target<0||target>100)){$('#goal-error').textContent='목표 회복률은 0~100% 사이로 입력하세요.';$('#goal-results').textContent='올바른 목표값을 입력하면 계산합니다.';return;}if(raw===''){$('#goal-results').innerHTML='<span class="badge gray">목표 미설정</span><p class="meta">현재 기준값은 '+pct(KC.recovered,KC.followup)+'%입니다. 목표를 입력하면 필요한 회복 건수를 계산합니다.</p>';return;}const exact=target/100*KC.followup,needed=Math.ceil(exact),extra=Math.max(0,needed-KC.recovered),base=rate(KC.recovered,KC.followup),delta=target-base,lift=base?delta/base*100:null;$('#goal-results').innerHTML=`<div class="goal-result-grid"><div><span>목표 회복 건수</span><strong>${fmt(needed)}건</strong><span>후속 검색 ${fmt(KC.followup)}건 고정</span></div><div><span>추가 필요 회복</span><strong>${fmt(extra)}건</strong><span>현재 ${fmt(KC.recovered)}건 대비</span></div><div><span>목표 차이</span><strong>${signed(delta)}%p</strong><span>반올림 전 현재 비율 기준</span></div><div><span>목표 상대 개선율</span><strong>${lift===null?'—':signed(lift)+'%'}</strong><span>예상 효과·검정 결과 아님</span></div></div><p class="meta">${delta<=0?'입력 목표는 현재 수준 이하입니다. 추가 개선 목표로 해석하지 않습니다.':'현재와 같은 후속 검색 수를 가정한 목표 환산입니다.'}</p>`;}
$('#goal-rate').oninput=renderGoal;$('#clear-goal').onclick=()=>{$('#goal-rate').value='';renderGoal();};renderGoal();

const slides=[
['프로젝트 주제와 분석 범위',4,['#template-topic']],
['팀원 구성 · 작성 템플릿',4,['#template-team']],
['주제 선정 의도와 기획',4,['#template-intent']],
['논문·데이터셋 · 자료 연결 대기',4,['#template-research']],
['가상 사이트와 행동 데이터 수집',4,['#template-survey']],
['StayTrace · 참여자 경험과 수집 과정',4,['#template-site_entry']],
['데이터 콘솔 · 캡처 시점의 수집 현황',4,['#template-site_console']],
['사이트의 옵션 일치·불일치 실험',4,['#template-site_experiment']],
['발표 핵심 가설 3개 · H1·H5·H4',4,['#template-hypotheses']],
['왜 호텔 검색 회복을 분석했는가?',4,['#page-4 .intro-kpis','#page-4 .callout']],
['발표에서 사용할 핵심 용어',4,['#term-definitions .scroll']],
['원시데이터에서 1,000명 확장본까지',4,['#page-4 .origin-flow','#page-4 .origin-details .scroll']],
['시행착오 · 작성 템플릿',4,['#template-lessons']],
['데이터 증강 방식 · 작성 템플릿',4,['#template-augmentation']],
['데이터 한계 · 작성 템플릿',4,['#template-limitations']],
['10,000명 시뮬레이션 · 사용 범위와 HOLD',4,['#template-simulation_scope']],
['기준선 재현 차이와 Seed별 판정',4,['#template-simulation_calibration']],
['10,000명 확장 · 영향과 대응',4,['#template-simulation_impacts']],
['용량 줄이기 · 작성 템플릿',4,['#template-optimization']],
['주 KPI와 보조 지표의 공식',4,['#primary-kpi','#supporting-kpis']],
['목표 회복률을 건수로 환산하기',4,['#kpi-goal']],
['선택한 데이터의 전체 현황',0,['#kpis','#search-branches']],
['결과 없음 이후의 회복 퍼널',0,['#funnel-filter-note','#recovery-funnel','#funnel-comparison']],
['어떤 변경 뒤에 결과를 찾았는가?',1,['#method-bars']],
['세그먼트를 나눈 기준',0,['#segment-rules']],
['검색의도에 따른 6개 세그먼트',0,['#intent-cards']],
['검색결과에 따른 4개 성과 세그먼트',0,['#outcome-cards','#segment-donut']],
['성과군 여정 · 첫 검색 결과 있음',0,['#outcome-journeys-a']],
['성과군 여정 · 첫 검색 결과 없음',0,['#outcome-journeys-b']],
['의도별 제안 여정 · 조건 변경',0,['#intent-journeys-a']],
['의도별 제안 여정 · 탐색 방식',0,['#intent-journeys-b']],
['기간별 검색 결과 없음 추세',0,['#timeline']],
['기존 A/B와 연결할 개선안',2,['#intent-content','#ab-protocol .scroll']],
['핵심 발견과 다음 의사결정',3,['#findings']]
];let slideIndex=0;
const agendaGroups=[['기획과 수집',0,9],['데이터와 한계',9,19],['지표와 검증',19,25],['세그먼트와 여정',25,31],['해석과 의사결정',31,34]];
const agendaHTML=agendaGroups.map(([name,start,end])=>`<section><h3>${name} · ${start+1}~${end}장</h3><ol start="${start+1}">${slides.slice(start,end).map(([title],i)=>`<li><button type="button" data-slide-jump="${start+i}">${title}</button></li>`).join('')}</ol></section>`).join('');
['#dashboard-agenda','#presentation-agenda'].forEach(id=>$(id).innerHTML=agendaHTML);
document.querySelectorAll('[data-slide-jump]').forEach(button=>button.onclick=()=>{document.body.classList.add('presenting');$('#presentation-mode').setAttribute('aria-pressed','true');$('#presentation-mode').textContent='대시보드로 돌아가기';document.querySelectorAll('details').forEach(d=>d.open=false);slideIndex=Number(button.dataset.slideJump);renderSlide();$('#slide-title').focus({preventScroll:true});});
function cloneForSlide(selector){const source=$(selector);if(!source||source.hidden)return document.createElement('div');const el=source.cloneNode(true);el.removeAttribute('id');el.querySelectorAll('[id]').forEach(x=>x.removeAttribute('id'));el.querySelectorAll('details').forEach(x=>x.open=false);el.querySelectorAll('.choice-control').forEach(x=>{const label=document.createElement('span');label.className='badge gray';label.textContent='비교 기준군: '+x.dataset.selectedLabel;x.replaceWith(label);});el.querySelectorAll('select').forEach(x=>{const label=document.createElement('span');label.className='badge gray';label.textContent=x.selectedOptions[0]?.textContent||'';x.replaceWith(label);});el.querySelectorAll('input').forEach(x=>{const text=document.createElement('span');text.className='badge gray';text.textContent=x.value?x.value+'%':'목표 미설정';x.replaceWith(text);});el.querySelectorAll('button').forEach(x=>x.remove());return el;}
function renderSlide(){const [title,n,selectors]=slides[slideIndex];$('#slide-title').textContent=title;$('#slide-counter').textContent=(slideIndex+1)+' / '+slides.length;$('#slide-position').textContent=(slideIndex+1)+' / '+slides.length;$('#slide-stage').replaceChildren(...selectors.map(cloneForSlide));$('#slide-script').replaceChildren(cloneForSlide('#page-'+n+' > .speaker-notes'));if(selectors.includes('#primary-kpi')||selectors.includes('#kpi-goal')){const extra=document.createElement('p');extra.textContent='주 KPI는 0건 이후 후속 검색에서 결과를 찾은 비율입니다. 현재 확장본 기준 558/3,271 = 약 17.1%입니다. 모든 0건 검색을 분모로 하면 558/3,434 = 16.2%이므로 두 지표를 구분합니다. 목표 입력 계산은 후속 검색 수를 고정한 건수 환산이며 예측 효과나 실험 표본 수가 아닙니다. 목표값은 별도로 정해야 합니다.';$('#slide-script .speaker-notes').append(extra);}if(selectors[0].startsWith('#template-'))$('#slide-script').replaceChildren();$('#prev-slide').disabled=slideIndex===0;$('#next-slide').disabled=slideIndex===slides.length-1;window.scrollTo(0,0);}
function moveSlide(step){slideIndex=Math.max(0,Math.min(slides.length-1,slideIndex+step));renderSlide();}
$('#prev-slide').onclick=()=>moveSlide(-1);$('#next-slide').onclick=()=>moveSlide(1);$('#presentation-mode').textContent='슬라이드 모드';$('#presentation-mode').onclick=()=>{const on=document.body.classList.toggle('presenting');$('#presentation-mode').setAttribute('aria-pressed',on);$('#presentation-mode').textContent=on?'대시보드로 돌아가기':'슬라이드 모드';document.querySelectorAll('details').forEach(d=>d.open=false);if(on){slideIndex=0;renderSlide();}else window.scrollTo(0,0);};document.addEventListener('keydown',e=>{if(!document.body.classList.contains('presenting')||['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName))return;if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();moveSlide(e.key==='ArrowRight'?1:-1);}});
