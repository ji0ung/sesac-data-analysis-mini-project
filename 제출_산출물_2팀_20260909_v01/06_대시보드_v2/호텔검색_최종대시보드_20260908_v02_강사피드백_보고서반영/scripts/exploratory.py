from html import escape
import json

def render_exploratory(root):
    d=json.loads((root/'data/exploratory_10000.json').read_text())
    effects=d['effects'];segments=d['segments']
    pct=lambda x:f'{x*100:.2f}%'
    delta=lambda x:f'{x*100:+.2f}%p'
    badge='<p class="meta">合成</p>'.replace('合成','합성 탐색 시뮬레이션 · 실제 A/B 아님 · seed 2434815518 · strict HOLD 16/20')
    def table(head,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+x+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'

    def chart(title, groups, denominator, unit='%', maximum=100):
        # Values are supplied from the versioned aggregate snapshot. Axes always start at zero.
        width=max(660,len(groups)*250);height=400;top=45;bottom=285;left=55;plotwidth=width-left-20
        svg=[]
        for i in range(5):
            value=maximum*i/4;y=bottom-(bottom-top)*i/4
            svg.append(f'<line x1="{left}" y1="{y}" x2="{width-20}" y2="{y}" stroke="#e3e9ef"/><text x="{left-9}" y="{y+4}" text-anchor="end" fill="#68788a" font-size="12">{value:g}{unit}</text>')
        for i,(name,c,t,cn,tn) in enumerate(groups):
            cx=left+plotwidth*(i+.5)/len(groups);barwidth=min(65,plotwidth/len(groups)/4)
            for j,(value,label,color) in enumerate([(c,cn,'#9caec7'),(t,tn,'#4569df')]):
                x=cx+(j-1)*barwidth+(j*10)-5;y=bottom-(bottom-top)*value/maximum
                svg.append(f'<rect x="{x}" y="{y}" width="{barwidth}" height="{bottom-y}" rx="5" fill="{color}"/><text x="{x+barwidth/2}" y="{y-12}" text-anchor="middle" font-size="16" font-weight="700" fill="#20324b">{value:.2f}{unit}</text>')
            svg.append(f'<text x="{cx}" y="315" text-anchor="middle" font-size="14" font-weight="600" fill="#20324b">{escape(name)}</text><text x="{cx}" y="341" text-anchor="middle" font-size="12" fill="#68788a">C {escape(cn)}</text><text x="{cx}" y="361" text-anchor="middle" font-size="12" fill="#68788a">T {escape(tn)}</text>')
        aria=escape(title+'; '+'; '.join(f'{name}: C {c:.2f}{unit}, T {t:.2f}{unit}' for name,c,t,cn,tn in groups))
        return '<article class="analytics-chart"><div class="analytics-chart-head"><div><span class="analytics-kicker">10,000명 합성 A/B</span><h3>'+escape(title)+'</h3></div><span class="badge gray">기준군 C · 차이 T − C</span></div><div class="analytics-meta"><span>기간: 2028.02.01~02.07 UTC · 합성 시간축</span><span>비교군: C 5,000명 / T 5,000명</span><span>집계 기준: '+escape(denominator)+'</span></div><div class="analytics-legend"><span><i></i>대조군 C</span><span><i></i>실험군 T</span></div><div class="analytics-plot"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+str(width)+' '+str(height)+'" role="img" aria-label="'+aria+'">'+''.join(svg)+'</svg></div><p class="analytics-foot">0부터 시작하는 공통 축 · 막대 위 값 / 아래 건수·분모 · 최신 DB에서 확인한 합성 기간 · 실제 관측 기간 아님</p></article>'
    definitions=['0건 검색 / 전체 검색','후속검색 있는 0건 검색 / 0건 검색','회복 전이 / 0건 후속검색','첫 0건 후 회복 세션 / 첫 0건 후속검색 세션','최종 회복 세션 / 0건 경험 세션','0건 경험 세션 / 전체 세션','1위 상세진입 고유 검색 / 결과 존재 검색','검색 건수 / 세션 수']
    def metric_chart(e):
        idx=effects.index(e);is_count=e['metric']=='세션당 검색 수';scale=1 if is_count else 100
        return chart(e['metric'],[('전체 배정군',e['control']*scale,e['treatment']*scale,f"{e['control_n']:,} / {e['control_d']:,}",f"{e['treatment_n']:,} / {e['treatment_d']:,}")],definitions[idx],unit='회' if is_count else '%',maximum=10 if is_count else 100)

    rows=[]
    for e in effects:
        count=e['metric']=='세션당 검색 수';scale=1 if count else 100;unit='회' if count else '%';diffunit='회' if count else '%p'
        rows.append([e['metric'],f"{e['control_n']:,} / {e['control_d']:,}<br>{e['control']*scale:.4f}{unit}",f"{e['treatment_n']:,} / {e['treatment_d']:,}<br>{e['treatment']*scale:.4f}{unit}",f"{e['difference']*scale:+.4f}{diffunit}",f"[{e['ci_low']*scale:+.3f}, {e['ci_high']*scale:+.3f}]{diffunit}"])
    full='<section id="exploratory-all-metrics"><h2>전체 A/B 지표 · 8개</h2>'+badge+'<div class="analytics-grid">'+''.join(metric_chart(e) for e in effects)+'</div><details><summary>지표 전체표 · 분자·분모·차이·불확실성</summary>'+table(['지표','대조군 C · 분자/분모','실험군 T · 분자/분모','T − C','조건부 95% 구간'],rows)+'<p class="meta">pair bootstrap 2,000회 · 고정 모형 조건부 구간. 실제 모집단·모형오류 불확실성은 포함하지 않습니다. 후속검색률은 참여 진단 지표이며 높을수록 좋다는 판정은 하지 않습니다.</p></details></section>'
    full+='<details><summary>단위와 분모 정의</summary><p>검색 0건률: 0건 검색 / 전체 검색. 후속검색률: 다음 검색이 있는 0건 검색 / 0건 검색. 즉시 회복: 다음 결과가 양수인 0건 전이 / 후속검색이 있는 0건 전이. 첫 Z 회복: 세션 첫 0건 이후 회복 / 첫 0건 이후 후속검색 존재 세션.</p><p>최종 회복: 마지막 검색 결과가 양수인 0건 경험 세션 / 0건 경험 세션. Z 경험 세션률: 0건 경험 세션 / 전체 세션. Card H: 1위 상세진입 고유 검색 / 결과 존재 검색. 세션당 검색 수: 검색 건수 / 세션 수.</p><p>Card H-EVENT는 C 13,016행 / T 13,671행이며 반복 상세진입 이벤트의 보조량입니다. 클릭·상세 이벤트를 독립 퍼널 단계로 중복 집계하지 않습니다.</p></details>'
    refs=[x for x in d['metrics'] if x['source']=='reference' and x['value'] is not None]
    baseline=[]
    for r in refs:
        arms=[next(x for x in d['metrics'] if x['arm']==a and x['metric']==r['metric']) for a in ['control','treatment']]
        label={'search_zero_rate':'검색 0건률','zero_followup_rate':'0건 후속검색률','immediate_recovery_transition_rate':'즉시 회복','first_zero_immediate_recovery_rate':'첫 Z 즉시 회복','final_recovery_rate':'최종 회복','card_h_search_rate':'Card H-SEARCH'}[r['metric']]
        baseline.append([label,f"{r['numerator']:,}/{r['denominator']:,} · {pct(r['value'])}",pct(arms[0]['value']),delta(arms[0]['value']-r['value']),pct(arms[1]['value'])])
    full+='<details><summary>1,000명 기준선 ↔ 10,000명 C/T 비교</summary>'+table(['지표','1,000명 기준','C','C − 기준','T'],baseline)+'<p class="meta">기준 DB는 합성 1,000명. 기준선 재현 비교이며 실제 개선 전후 비교가 아닙니다.</p></details>'
    blocks=''
    for dim in dict.fromkeys(x['dimension'] for x in segments):
        rows=[]
        for x in segments:
            if x['dimension']!=dim:continue
            rows.append([escape(x['segment']),f"{x['pairs']:,}",f"{x['control_searches']:,} / {x['treatment_searches']:,}",pct(x['control_zero'])+' → '+pct(x['treatment_zero']),delta(x['zero_diff']),f"[{x['zero_ci_low']*100:+.2f}, {x['zero_ci_high']*100:+.2f}]%p",f"{x['control_final_den']:,} / {x['treatment_final_den']:,}",delta(x['final_diff'])])
        selected=[x for x in segments if x['dimension']==dim]
        labels={'coastal':'생성 코드 coastal','inland':'생성 코드 inland','island':'생성 코드 island','metro':'생성 코드 metro','high':'높음','medium':'중간','low':'낮음'}
        groups=[(labels.get(x['segment'],x['segment']),x['control_zero']*100,x['treatment_zero']*100,f"검색 {x['control_searches']:,}건",f"검색 {x['treatment_searches']:,}건") for x in selected]
        blocks+=chart(dim+'별 검색 0건률',groups,'각 사전 조건군의 0건 검색 / 전체 검색')
        blocks+='<details><summary>'+dim+' · 분모·차이·조건부 구간 상세</summary>'+table(['조건','pair 수','검색 수 C/T','0건률 C → T','차이','조건부 95% 구간','최종회복 분모 C/T','최종회복 차이'],rows)+'</details>'
    seg='<section id="exploratory-segments"><h2>사전 조건별 합성 A/B · 14개 세그먼트</h2>'+badge+'<p>가격 설정·옵션 수·지역군·위험층·첫 검색 상태 기준입니다. 예산 유연형 등 6개 검색의도군과 다르며, 개별 제안 기능의 효과 순위가 아닙니다.</p>'+blocks+'<p class="meta">원본 조건별 표본·독립 seed별 세그먼트 범위는 이 집계 파일에 없습니다. 모든 셀은 탐색적으로 해석하며 합성 표본 수로 실제 신뢰성을 주장하지 않습니다. 차원별 합계는 각각 5,000쌍이고 차원 사이의 사용자는 중복됩니다.</p></section>'
    flow='<section id="exploratory-flow"><h2>0건 이후 흐름 · 대조군과 실험군</h2>'+badge+table(['단계 / 단위','대조군 C','실험군 T'],[['전체 검색','33,572','31,783'],['결과 없음 · 검색','16,761','13,853'],['0건 후속검색 · 전이','15,935','13,249'],['바로 회복 Z→P · 전이','2,693','2,918'],['0건 반복 Z→Z · 전이','13,242','10,331'],['후속검색 없음 Z→END','826','604']])+'<p class="meta">각 집단에서 Z→P + Z→Z + Z→END = 0건 검색입니다. 후속검색 없음은 실제 이탈 로그가 아닙니다. 이 흐름은 모든 0건 검색 기준이며 지역 변경 후속검색만의 D-1 회복률이 아닙니다.</p></section>'
    h1='<div class="callout"><strong>연결된 근거 · 복합 회복 개입의 합성 비교</strong><p>C 2,693 / 15,935 = 16.90% → T 2,918 / 13,249 = 22.02% · +5.12%p</p><p>조건부 95% 구간 [+4.331, +5.970]%p. 지역 변경과 회복 확률 +0.06을 결합한 결과로, 가격·옵션 조건 완화 단독 효과는 검증하지 못합니다.</p></div>'
    h2='<div class="callout"><strong>검색의도군별 효과는 산출 불가 · intent_segment 없음</strong><p>대신 사전 가격 조건별 검색 0건률 차이는 미설정 −8.93%p, 설정 −5.50%p입니다. 옵션 수 0/1/2+별 차이는 −6.00/−6.71/−6.33%p입니다.</p><p>03 페이지에 조건별 분모와 구간을 연결했습니다. 가격 설정 여부를 예산 유연성으로, 옵션 개수를 옵션 수 유연성으로 바꾸어 해석하지 않습니다.</p></div>'
    h5='<div class="callout"><strong>생성 모형 지역 코드 · 일본 도시 아님</strong><p>일반 지역 코드의 시뮬레이션 차이는 일본 도시별 지역 확대 효과로 사용할 수 없습니다. 일본 5개 도시의 원본 관측 비교는 위 H5 그래프를 확인하세요.</p><p>사전 지역군의 합성 비교이며 지역 확대 제안을 선택한 효과는 아닙니다. 노출·선택 로그가 없어 지역 선택률과 제안 수락 퍼널은 산출할 수 없습니다.</p></div>'
    overview='<article class="panel" id="exploratory-overview"><span class="badge">10,000명 합성 탐색용 · C/T 합계</span><h2>1만 명 전체 현황 · 65,355검색</h2><div class="report-metrics">'+''.join('<article class="report-metric"><h3>'+title+'</h3><strong>'+value+'</strong><p>'+den+'</p></article>' for title,value,den in [('검색 0건률','46.84%','30,614 / 65,355검색'),('0건 후속검색률','95.33%','29,184 / 30,614건'),('즉시 회복률','19.23%','5,611 / 29,184전이'),('최종 회복률','77.54%','4,936 / 6,366세션')])+'</div><p>대조군·실험군을 합친 규모 요약입니다. 개입의 차이는 03 A/B의 집단별 분자·분모로 비교합니다.</p>'+badge+'</article>'
    overview += '<div class="analytics-grid">'+''.join(metric_chart(effects[i]) for i in [0,2,4,6])+'</div>'
    h1 += metric_chart(effects[2])
    flow = chart('0건 이후의 분기 비율', [('즉시 회복',2693/16761*100,2918/13853*100,'2,693 / 16,761','2,918 / 13,853'),('0건 반복',13242/16761*100,10331/13853*100,'13,242 / 16,761','10,331 / 13,853'),('후속검색 없음',826/16761*100,604/13853*100,'826 / 16,761','604 / 13,853')], '집단별 전체 0건 검색 · 즉시 회복 KPI의 후속검색 분모와 다름') + flow
    return {'EXPLORATORY_DETAILS':full,'EXPLORATORY_SEGMENTS':seg,'EXPLORATORY_FLOW':flow,'EXPLORATORY_H1':h1,'EXPLORATORY_H2':h2,'EXPLORATORY_H5':h5,'EXPLORATORY_OVERVIEW':overview}
