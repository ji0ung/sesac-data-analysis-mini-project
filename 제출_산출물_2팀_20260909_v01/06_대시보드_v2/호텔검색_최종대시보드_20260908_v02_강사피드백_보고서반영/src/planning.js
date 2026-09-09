// Descriptive search-path controls.
(()=>{
const data=JSON.parse(document.querySelector('#overview-data').textContent);
const el=id=>document.getElementById(id);
const cohorts=data.cohort_patterns,colors=['#4569df','#219a87','#b4864b','#8a6bc1'];
const metrics={reach:['검색 지속','해당 순번까지 검색한 사용자 / 해당 세그먼트 전체 사용자'],end:['검색 후 종료','해당 검색 이후 다음 검색 없음 / 해당 순번까지 도달한 사용자'],retry:['다시 검색','해당 검색 이후 다음 검색 있음 / 해당 순번까지 도달한 사용자'],recovery:['0건 후 회복','해당 순번이 0건이고 다음 검색에서 회복 / 해당 순번이 0건이고 다음 검색 있음']};
let selected='reach';
function renderPaths(){
 const [title,definition]=metrics[selected];el('path-basis').textContent=definition;
 document.querySelectorAll('[data-path-metric]').forEach(e=>e.setAttribute('aria-pressed',String(e.dataset.pathMetric===selected)));
 let svg='';const W=1120,left=65,right=1085,top=35,bottom=330;
 [0,25,50,75,100].forEach(v=>{const y=bottom-v/100*(bottom-top);svg+=`<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" stroke="#e3e9ef"/><text x="${left-12}" y="${y+4}" text-anchor="end" font-size="12" fill="#68788a">${v}%</text>`;});
 [1,5,10,15,20,25,31].forEach(step=>{const x=left+(step-1)/30*(right-left);svg+=`<text x="${x}" y="362" text-anchor="middle" font-size="12" fill="#68788a">${step}번째</text>`;});
 cohorts.forEach((g,gi)=>{let chunks=[],points=[];g.steps.forEach(s=>{const q=s[selected];if(!q.d){if(points.length)chunks.push(points);points=[];return;}const value=q.n/q.d*100,x=left+(s.step-1)/30*(right-left),y=bottom-value/100*(bottom-top);points.push([x,y]);});if(points.length)chunks.push(points);chunks.forEach(points=>{svg+=`<polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="${colors[gi]}" stroke-width="3" ${gi===3?'stroke-dasharray="7 4"':''}/>`;});g.steps.forEach(s=>{const q=s[selected];if(!q.d)return;const value=q.n/q.d*100,x=left+(s.step-1)/30*(right-left),y=bottom-value/100*(bottom-top);svg+=`<circle cx="${x}" cy="${y}" r="4" fill="${colors[gi]}" tabindex="0"><title>${g.label} · ${s.step}번째 · ${q.n}/${q.d} = ${value.toFixed(2)}%</title></circle>`;});});
 el('path-plot').innerHTML=`<svg viewBox="0 0 ${W} 390" role="img" aria-label="세그먼트별 ${title}: 각 점의 상세값은 아래 표에서 확인">${svg}</svg>`;
 el('path-values').innerHTML='<div class="scroll"><table><thead><tr><th>검색 순번</th>'+cohorts.map(g=>`<th>${g.label}</th>`).join('')+'</tr></thead><tbody>'+Array.from({length:31},(_,i)=>'<tr><td>'+(i+1)+'번째</td>'+cohorts.map(g=>{const q=g.steps[i][selected];return '<td>'+(q.d?`${q.n.toLocaleString()} / ${q.d.toLocaleString()} · ${(q.n/q.d*100).toFixed(2)}%`:'— · 분모 없음')+'</td>';}).join('')+'</tr>').join('')+'</tbody></table></div>';
}
document.querySelectorAll('[data-path-metric]').forEach(e=>e.onclick=()=>{selected=e.dataset.pathMetric;renderPaths();});renderPaths();
if(location.hash==='#kpi-planner'){page(5);window.scrollTo(0,0);}
})();
