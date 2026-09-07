"""Render new diagnostic reports from measured JSON; never edits source artifacts."""
import collections, json, pathlib

OUT=pathlib.Path(__file__).resolve().parent
A=json.loads((OUT/'audit_raw.json').read_text(encoding='utf-8'))
B=json.loads((OUT/'benchmark_summary.json').read_text(encoding='utf-8'))
M=json.loads((OUT/'augmentation_risk_model.json').read_text(encoding='utf-8'))
P={(r['table'],r['column']):r for r in A['profiles'] if r['db']=='plain'}
E={(r['table'],r['column']):r for r in A['dictionary_effects']}
LABEL={'original':'최초 합성 DB','plain':'문자열 경량 DB','compact':'추가 경량 DB'}
NULL5={('event','review_completed_at'),('event','review_text'),('search_filter','property_type'),('search_filter','property_grade'),('user','age_group')}
def pct(v):return 'N/A' if v is None else f'{v*100:.4f}%'
def num(v):return 'N/A' if v is None else f'{v:,.2f}' if isinstance(v,float) else f'{v:,}'
def mib(n):return f'{n/1048576:,.3f}'
def cell(v):return str(v).replace('|','&#124;').replace('\n',' ')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|',*['| '+' | '.join(cell(v) for v in row)+' |' for row in rows]])+'\n'
def write(name,text):
    p=OUT/name
    if p.exists():raise FileExistsError(p)
    p.write_text(text,encoding='utf-8')

def storage(t,col):
    if (t,col) in E:return f'_data_{t}.{col}: INTEGER → {E[t,col]["dictionary"]}.id/value'
    if t=='event' and col in ['session_id','user_id','session_end_time']:
        return f'_data_event._session_ref → _sessions.{col} (TEXT); NULL 플래그 복원'
    if (t,col)==('event','search_filter_id'):return '_data_event.search_id에서 SYN_Q→SYN_F 형식으로 복원; 독립 저장 없음'
    if (t,col)==('search_result','hotel_id'):return '_data_search_result.room_id의 숫자 부분에서 복원; 독립 저장 없음'
    cp=next(r for r in A['profiles'] if r['db']=='compact' and r['table']=='_data_'+t and r['column']==col)
    if cp['declared_type']=='INTEGER' and P[t,col]['declared_type']=='TEXT':return f'_data_{t}.{col}: INTEGER; 고정 자릿수 문자열 ID 복원(사전 아님)'
    return f'_data_{t}.{col}: {cp["declared_type"]} 직접 저장'

def recommend(t,col):
    x=P[t,col];effect=E.get((t,col));typ=x['declared_type']
    savings=f'현재 순절감 근사 {effect["estimated_net_payload_saving"]/1024:,.1f} KiB' if effect else '현재 사전 미적용'
    if t=='booking':return '증강 대상에서 제외','현행 자료형·빈 스키마 유지','예약 생성 규칙이 없고 현재 S0 코드가 예약 이벤트를 제외함; 미래 예약 증강 여부는 추가 확인 필요','생성설정 booking_rows=0; 실제 0행',savings
    if (t,col) in NULL5:return '증강 대상에서 제외','현재 열·NULL 유지; 삭제 아님','원천 증거 없는 값 생성 금지; 해당 속성 생성은 추가 확인 필요','전체 행 NULL, 이번 요청에서 값 생성 규칙 확인 불가',savings
    if t in ['hotel','room']:
        fmt='사전 유지' if effect else ('현행 숫자 유지' if typ in ['INTEGER','REAL'] else '원문 문자열 권장' if col.endswith('_id') else '현행 원문 유지')
        return '증강 대상에서 제외',fmt,'사용자 증강 시 카탈로그 복사만 수행; 새 호텔·객실 생성은 추가 확인 필요','생성 코드가 hotel·room 전체를 그대로 복사; 임의 10배 증식 안 함',savings
    if typ in ['INTEGER','REAL']:return '기존 숫자 자료형 유지',typ,'분포·범위·결측의 증강 규칙은 원래 세션 복사 범위만 확인됨','원래 숫자값을 유지하는 것이 정보 손실이 없음',savings
    if col.endswith('_id'):
        issue='현재 문자열 복원 자릿수 제한/혼합 자릿수 재변환 오류; append 시 ID 중복 위험'
        if col in ['hotel_id','room_id']:issue='고정 카탈로그 참조는 유지 가능; ID 형식에서 관계를 추론하는 결합은 새 ID 형식에 취약'
        if (t,col)==('event','session_id') or (t,col)==('event','user_id'):issue='세션 공통값은 현재 일치; 향후 복수 사용자·세션 설계와 NULL 의미는 추가 확인 필요'
        return '원문 문자열로 저장','문자열 외부 ID를 명시적으로 유지; 별도 정수 대리키 도입은 승인 후 설계',issue,'현재 생성기가 문자열 ID를 만듦. 가변 자릿수 보존과 직접 분석 편의를 우선; 용량 비용은 증가',savings
    if (t,col)==('event','event_at'):
        return '원문 문자열로 저장','TEXT 시각; 정수 시각 도입은 별도 설계','새 시각마다 사전 등록 필요; 정렬·시간 연산 전 역매핑; 유일 시각 증가 시 순절감 역전','현재도 9.2648%로 절감은 큼. 그러나 생성 코드가 시각을 새로 만들고 시계열 처리가 주요 비용',savings
    if (t,col) in [('search','checkin_date'),('search','checkout_date')]:
        return '원문 문자열로 저장','TEXT 날짜','날짜 범위 확장 시 사전 갱신; 검색일보다 과거인 체크인 6,900행은 규칙 확인 필요','현 절감 약 44.7 KiB/열로 작고 생성기가 ISO 날짜를 직접 파싱',savings
    if (t,col)==('search','query_text'):
        return '추가 확인 필요','기존 23개 검색어 재사용이면 사전 유지; 자유 검색어 생성이면 원문','10,000명에서 새로운 검색어를 생성할지 명세가 없음','현재 코드는 검색어를 복사하므로 현 절감은 유효하지만 미래 어휘 성장률은 미확정',savings
    if effect:return '사전 매핑 유지','정수 코드 + 안정적인 사전 ID','새 범주 등록·value 중복 방지·참조 무결성 필요; 현재 코드는 증분 사전 갱신 미지원','현재 낮은 고유값 비율, 생성 코드는 범주 원문을 복사',savings
    if col in ['user_name','email']:return '원문 문자열로 저장','TEXT','사용자마다 새 값; 전체 고유값 비율 100%로 사전은 원문과 참조를 모두 저장','기존 생성 코드가 사용자 순번 기반 이름·이메일을 새로 생성',savings
    return '원문 문자열로 저장','TEXT','새 시각/문자열에 대한 의미·형식과 NULL 보존 필요','현재 직접 저장; 사전 추가보다 직접 파싱·조회 단순성을 우선',savings

def recommendations():
    rows=[];structured=[]
    for (t,col),x in P.items():
        category,fmt,problem,basis,effect=recommend(t,col)
        row=[t,col,storage(t,col),pct(x['unique_ratio']),effect,problem,category+' — '+fmt,basis]
        rows.append(row);structured.append(dict(table=t,column=col,current_storage=storage(t,col),unique_ratio=x['unique_ratio'],category=category,recommended_format=fmt,augmentation_problem=problem,basis=basis,dictionary_effect=effect))
    s='# 컬럼별 저장 방식 진단\n\n현재 DB의 기존 이름 8개는 뷰다. 아래는 뷰의 87개 업무 열과 실제 저장 위치를 연결한 전수 판단표다. 모든 권고는 미적용 상태이며 사용자 확인 전 구조·코드를 변경하지 않는다.\n\n'
    s+='고유값 비율은 비NULL 고유값 수 / 전체 행 수다. 빈 booking은 N/A다. “증강 대상에서 제외”는 열·원천값 삭제가 아니라 현행 사용자/세션 증강에서 새 값을 만들지 않는다는 뜻이다. 원문 ID 권고는 저장 공간보다 현재 생성기 호환성과 안전한 형식 보존을 우선한 선택이며, 일반적인 정수 대리키의 효용을 부정하지 않는다.\n\n'
    s+=table(['실제 뷰명','컬럼명','현재 저장 방식 / 실제 테이블·컬럼','고유값 비율','사전 매핑 효과','증강 시 예상 문제','권장 저장 방식(5개 분류)','판단 근거'],rows)
    s+='\n## 물리 테이블 113개 열의 판단\n\n사전 value의 고유값 비율이 100%인 것은 정상이다. 사전의 효과는 해당 value의 고유값 비율이 아니라 업무 테이블의 참조 빈도로 판단한다. `_dict_*`의 열은 독립적인 합성 대상이 아니라 업무 데이터와 일관되게 관리해야 하는 내부 저장 열이다.\n\n'
    rows=[]
    for x in A['profiles']:
        if x['db']!='compact' or x['object_type']!='table':continue
        t,col=x['table'],x['column']
        if t.startswith('_data_') and (t[6:],col) in P:
            cat,fmt,problem,basis,effect=recommend(t[6:],col)
        elif t.startswith('_dict_'):
            e=next(e for e in E.values() if e['dictionary']==t);cat,fmt,problem,basis,effect=recommend(e['table'],e['column'])
            fmt=('안정적인 INTEGER 사전 키' if col=='id' else '원문 TEXT 사전 값')+'; 업무 열 권고: '+fmt
        elif t=='_sessions':
            cat='기존 숫자 자료형 유지' if col=='id' else '원문 문자열로 저장';fmt=x['declared_type'];problem='복수 사용자/복수 종료시각 발생 시 세션 종속성 재검토';basis='기존 세션 공통 정보 저장; id는 내부 대리키';effect='세션당 한 번 저장, 독립 문자열 사전과 구분'
        else:
            cat='기존 숫자 자료형 유지';fmt='INTEGER';problem='세션 참조·NULL 플래그의 일관성 필요';basis='내부 참조 또는 원래 NULL 여부를 보존하는 플래그';effect='사전 매핑과 별개의 세션 정규화'
        rows.append([t,col,x['declared_type'],pct(x['unique_ratio']),effect,problem,cat+' — '+fmt,basis])
    s+=table(['실제 테이블명','컬럼명','현재 저장 자료형','고유값 비율','매핑 효과','증강 시 예상 문제','권장 저장 방식','판단 근거'],rows)
    write('컬럼별권고.md',s)
    write('column_recommendations.json',json.dumps(structured,ensure_ascii=False,indent=2))

def profiles():
    s='# 전체 컬럼 통계 — 384개 객체·컬럼 조합\n\n'
    s+='3개 파일의 모든 사용자 테이블과 추가 경량 DB의 뷰를 전수 측정했다. 시스템 sqlite_schema 자체는 업무 프로파일에서 제외한다. 현재 경량 DB는 물리 113열 + 뷰 87열 = 200열이다.\n\n'
    s+='N=전체 행 수, NN=비NULL 행 수, D=COUNT(DISTINCT 컬럼), 고유값 비율=D/N, 비NULL 기준 고유값 비율=D/NN, NULL 비율=(N−NN)/N. 평균·최대 길이는 typeof(value)=text인 값만 대상으로 한 SQLite length(문자 수)다. 숫자를 문자열로 CAST해 길이를 부풀리지 않았다. UTF-8 바이트는 별도 지표다. 빈 테이블의 비율, 문자열이 없는 열의 길이는 N/A다. 표본 추출·행 제외·NULL 대체·중복 제거 없이 전체 행을 측정했다.\n\n'
    for label in ['compact','plain','original']:
        s+='## '+LABEL[label]+'\n\n'
        for kind in ['table','view']:
            xx=[r for r in A['profiles'] if r['db']==label and r['object_type']==kind]
            if not xx:continue
            s+='### '+kind+'\n\n'
            s+=table(['실제 객체.컬럼','선언형','관측 typeof:행수','N','NN','D','D/N','D/NN','NULL 비율','평균 문자','최대 문자','문자열 UTF-8 총 bytes'],[
                [x['table']+'.'+x['column'],x['declared_type'] or '미선언(뷰 표현식)',json.dumps(x['runtime_types'],ensure_ascii=False),num(x['rows']),num(x['non_null']),num(x['distinct']),pct(x['unique_ratio']),pct(x['unique_nonnull_ratio']),pct(x['null_ratio']),num(x['avg_text_chars']),num(x['max_text_chars']),num(x['text_utf8_bytes'])] for x in xx])+'\n'
    write('전체컬럼통계.md',s)

def schema():
    s='# 실제 스키마와 관계\n\n선언된 PK·FK와 코드/값으로 확인한 논리 관계를 구분한다. 뷰에는 별도의 저장 데이터와 PK·FK 제약이 없다. 모든 DB에서 선언 FK는 0개다.\n\n'
    for label in ['compact','plain','original']:
        s+='## '+LABEL[label]+'\n\n'
        for obj in A['schema'][label]:
            if obj['type'] not in ['table','view']:continue
            s+='### '+obj['type']+' `'+obj['name']+'`\n\n'
            s+=table(['컬럼','선언 자료형','PK 순번','NOT NULL 선언','기본값'],[[c[1],c[2] or '미선언(뷰 표현식)',c[5],bool(c[3]),c[4] if c[4] is not None else '없음'] for c in obj['columns']])
            s+='\nFK: '+json.dumps(obj['foreign_keys'])+'; 인덱스(PRAGMA index_list): '+json.dumps(obj['indexes'])+'\n\n'
        s+='### 전체 DDL(진단 기록; 실행하지 않음)\n\n```sql\n'+';\n'.join(o['sql'] for o in A['schema'][label] if o['sql'])+';\n```\n\n'
    s+='## 검증한 논리 관계\n\n아래는 선언 FK가 아니다. 코드/뷰가 사용하는 관계에 대해 비NULL 자식값의 부모 존재 여부를 전수 확인했다. booking의 0행은 통과 증거가 아니라 현재 검증할 표본이 없음을 뜻한다.\n\n'
    s+=table(['자식 테이블.컬럼','부모 테이블.컬럼','확인 근거','비NULL 자식 행','부모 미존재 행','선언 FK'],[[r['source_table']+'.'+r['source_column'],r['target_table']+'.'+r['target_column'],r['evidence'],num(r['non_null']),num(r['orphans']),'없음'] for r in A['relations']])
    s+='\n`search.session_id`는 6,900행에서 1,000개로 중복되므로 PK가 아니다. 위 세션 존재 검사는 유일 부모 FK 검사가 아니라 세션 집합 포함 검사다. `_sessions.id` 및 12개 `_dict_*.id`만 INTEGER PRIMARY KEY이고 `_data_*`에는 선언 PK가 없다. `_room_key`는 `_data_room(room_id)`의 UNIQUE 인덱스다. FK가 선언되지 않았으므로 PRAGMA foreign_keys=ON만으로 이 관계가 보호되지는 않는다.\n'
    write('스키마와관계.md',s)

def main_report():
    ss={ (r['query'],r['db']):r for r in B['summary'] }
    s='# SQLite 및 생성 코드 읽기 전용 진단 — 2026-09-07\n\n'
    s+='**현재 14.297 MiB DB는 1,000명 데이터의 조회용 압축본으로는 값이 보존되지만, 기존 생성 코드에 그대로 넣어 10,000명으로 확장하는 입력 DB로는 호환되지 않는다.** 저장 구조를 변경하거나 증강을 실행하지 않았다. 모든 수치는 이번 진단에서 측정했으며, 10,000명 수치는 조건부 모형이다.\n\n'
    s+='## 1. 입력, 범위, 확인이 필요한 증강 정의\n\n'
    s+=table(['구분','실제 파일','크기 MiB','SHA-256'],[[LABEL[k],v['path'],mib(v['bytes']),v['sha256']] for k,v in A['sources'].items()])
    s+='\n- 주 비교: 바로 이전 문자열 경량본 44.719 MiB와 추가 경량본 14.297 MiB. 두 파일의 8개 업무 데이터셋 455,779행·87개 열 값/NULL이 일치한다.\n- 보조 비교: 최초 합성 DB 93.363 MiB. 동일한 열만 조회하고 시간 문자열의 ` KST`를 제거해 결과 의미를 맞췄다. `data_origin`과 `_generation_metadata`는 비교 결과에서 제외했지만 파일 크기에는 포함된다. 최초 파일은 13개 인덱스를 보유하므로 그 성능 차이를 사전 효과로만 해석하면 안 된다.\n- 확인한 생성기: 같은 실행 묶음의 `호텔검색_관측형합성1000명_생성코드_260903_1606_01.py`, 생성설정 JSON, `sqlite_compact_lossless.py`. 별도 260904_1259 생성기도 읽었으며 세션 종료 시각 NULL 처리 차이는 있으나 테이블 전제·data_origin·1,000명 QA 제한은 동일하다. 다른 실행 묶음을 임의로 입력으로 교체하지 않았다.\n- 현재 1,000건은 `user` 1,000명, `search.session_id` 1,000개로 확인된다. 이 데이터 자체도 코드와 설정상 합성 파일럿이며 1,000명의 새 관측 원천이라고 확인된 것은 아니다.\n- **추가 확인 필요:** “총 10,000건”의 단위, 기존 1,000명 보존 후 9,000명 추가인지 새 10,000명 생성인지, 검색어·시간·호텔·예약·리뷰의 새 값 생성 범위. 응답이 없으므로 아래는 사용자/세션 10배라는 명시적 조건부 시나리오이며 확정 규칙이 아니다.\n\n'
    s+='## 2. 현재 저장 구조와 무결성\n\n'
    s+=table(['구성','실제 객체','역할/확인 결과'],[
        ['업무 저장 테이블 8개',', '.join('`'+x['name']+'`' for x in A['schema']['compact'] if x['type']=='table' and x['name'].startswith('_data_')),'정수화한 ID·숫자·일부 원문 저장; 모두 선언 PK 없음'],
        ['사전 테이블 12개','`_dict_*` — 전체 이름은 아래 표/스키마 문서','id INTEGER PRIMARY KEY, value TEXT; value UNIQUE 없음'],
        ['세션 테이블 1개','`_sessions`','id INTEGER PRIMARY KEY; session_id/user_id/session_end_time은 원문 TEXT'],
        ['조회 뷰 8개',', '.join('`'+x['name']+'`' for x in A['schema']['compact'] if x['type']=='view'),'원래 87개 업무 열 복원; 저장 결과를 중복 보관하지 않음'],
        ['명시적 인덱스 1개','`_room_key`','_data_room(room_id) UNIQUE; 최종 검색 결과 뷰는 호텔 ID를 숫자 형식에서 직접 복원'],
        ['선언 FK / 쓰기 트리거','0개 / 0개','참조 누락/잘못된 코드는 DB 제약으로 차단되지 않음'],
    ])
    s+='\n현재 사전 참조 12개 관계와 세션 참조에서 고아 참조 0행, 사전 value 중복 0개다. 업무 ID의 비NULL·고유성을 전수 확인했으며 빈 booking을 제외한 각 업무 ID는 현재 유일하다. 이는 미래 삽입이 안전하다는 제약 보장은 아니다. 3개 DB의 integrity_check는 모두 ok다.\n\n'
    s+='원문 문자열은 `_dict_*.value`, `_sessions.session_id/user_id/session_end_time`, `_data_user.user_name/email/signup_at`, `_data_search.search_time`, 호텔 이름·주소 등 `_data_hotel`의 TEXT 열에 저장된다. 산술 정수 ID는 사전 매핑과 다르며, 접두사·자릿수 규칙으로 문자열을 복원한다. 전수 위치·자료형·PK·FK는 [스키마와관계.md](스키마와관계.md), 모든 열 통계는 [전체컬럼통계.md](전체컬럼통계.md)에 있다.\n\n'
    s+='## 3. 사전 매핑의 실제 효과\n\n'
    s+='12개 사전은 총 **22,324개 원문 값**, **802,816 bytes (0.766 MiB)**를 차지한다. 그중 시각 사전이 22,129개·0.594 MiB다.\n\n'
    s+=table(['업무 열','실제 사전','D / 전체 N','고유값 비율','원문 총 KiB','정수 payload KiB','사전 페이지 KiB','순절감 근사 KiB'],[[e['table']+'.'+e['column'],e['dictionary'],str(e['distinct'])+' / '+str(P[e['table'],e['column']]['rows']),pct(P[e['table'],e['column']]['unique_ratio']),f'{e["raw_text_bytes"]/1024:,.2f}',f'{e["code_payload_bytes"]/1024:,.2f}',f'{e["dictionary_page_bytes"]/1024:,.2f}',f'{e["estimated_net_payload_saving"]/1024:,.2f}'] for e in E.values()])
    s+='\n계산: 원문 UTF-8 bytes 합 − 정수값의 SQLite payload bytes 합 − 사전 테이블의 실제 할당 페이지 bytes. 정수는 값 범위에 따라 0/1/2/3/4/6/8 bytes를 적용했다. 원래/변환 행 헤더 및 B-tree 충전율 차이는 제외하므로 열별 실제 파일 절감량은 아니다. 페이지 수를 직접 추적했고 전체 객체 크기 합이 파일 크기와 일치함을 검증했다.\n\n'
    s+='### 고유값 증가와 관리 비용\n\n'
    s+='`event.event_at`의 현재 고유값 비율 9.2648%는 “고유값이 많으니 압축 효과가 없다”는 수준이 아니다. 현재는 약 3.28 MiB 순절감 근사가 나온다. 다만 생성기는 시각을 새로 이동시키므로 사전 갱신·역매핑·시각 파싱 비용을 함께 판단해야 한다. `search.search_time`은 97.5072%, `user.user_name/email/signup_at`과 주요 업무 ID는 100%여서 원문이 바뀔 때마다 사전을 추가하는 방식은 적합하지 않다. 해당 열들은 현재도 문자열 또는 산술 ID로 저장되어 별도 문자열 사전이 아니다.\n\n'
    s+='사전 모형: 원문 약 `N×L`, 사전 약 `D×(L+10)+16,384+N×k` bytes. N은 비NULL 행 수, D는 사전 수, L은 평균 UTF-8 길이, k는 코드 payload 상한이다. D가 N에 가까우면 원문을 한 번씩 전부 저장한 뒤 코드와 사전 행 관리 공간까지 추가된다. 10 bytes/사전 행은 명시적 근사이며 실제 스키마·인덱스·페이지 상태에 따라 달라진다.\n\n'
    ts=next(x for x in M['dictionary_scenarios'] if x['column']=='event_at')
    s+=table(['event_at 조건부 시나리오 (이벤트 2,388,510행)','D','사전 추정 MiB','코드 상한 MiB','원문 대비 순절감 추정 MiB'],[[{'same_vocabulary':'현재 시각 값만 재사용','same_unique_ratio':'현재 고유값 비율 유지','all_new_values':'모든 이벤트 시각이 서로 다름'}[name],num(v['distinct']),mib(v['dictionary_bytes_estimate']),mib(v['code_bytes_upper']),mib(v['net_bytes_estimate'])] for name,v in ts['cases'].items()])
    s+='\n이 시나리오는 새 데이터를 생성해 확인한 예측이 아니다. 12개 사전별 어휘 고정·고유비율 유지·모든 값 신규의 수치는 `augmentation_risk_model.json`에 보관했다. 정적 event_type/device 범주의 고유값을 10배 늘려야 한다는 의미는 아니다.\n\n'
    s+='## 4. 같은 조건의 조회·역매핑·메모리 비교\n\n'
    s+='Windows, Python '+B['environment']['python'].split()[0]+', SQLite '+B['environment']['sqlite']+'. 각 쿼리·파일 조합을 새 Python 프로세스와 새 연결에서 5회 실행하고 실행 순서를 고정 seed로 섞었다. SQLite 캐시는 8 MiB, mmap=0, temp_store=MEMORY, threads=1, automatic_index=ON, 읽기 전용이다. 모든 파일을 먼저 읽어 OS 캐시를 예열했으며 cold-disk 시험은 아니다. 프로세스 기동·연결·정합성 해시는 시간에서 제외했고 SQL 실행과 fetch를 포함했다. 파일별 반환 결과는 행 해시 멀티셋으로 동등함을 검증했다.\n\n'
    names={'event_type_group':'이벤트 유형 집계','event_id_lookup':'이벤트 ID 1건 조회','session_search':'세션별 검색 조회','search_result_join':'검색 결과-호텔 JOIN','all_text_stream':'전체 문자열 조회/역매핑 (5,000행 배치)','all_columns_stream':'전체 열 조회 (5,000행 배치)','all_columns_materialize':'전체 열 메모리 적재(fetchall)'}
    s+=table(['동일 작업','최초 합성 DB 초','문자열 경량 DB 초','추가 경량 DB 초','추가/문자열 배율'],[[name,*[f'{ss[key,label]["seconds_median"]:.6f}' for label in ['original','plain','compact']],f'{ss[key,"compact"]["seconds_median"]/ss[key,"plain"]["seconds_median"]:.2f}×'] for key,name in names.items()])
    s+='\n전체 문자열 조회는 8개 업무 데이터셋의 원래 TEXT 열을 모두 조회해 455,779행을 끝까지 fetch한 시간이다. 일반 숫자 열까지 함께 가져오는 “전체 열”과 구분한다. SELECT COUNT(*)로 복원 작업을 생략하지 않았다. 최초 DB는 KST 제거 연산과 기존 인덱스/페이지 차이가 있으므로 주 비교는 문자열 경량 DB 대 추가 경량 DB다.\n\n'
    s+=table(['작업','파일','프로세스 최고 RSS 중앙값 MiB','기준선 대비 증가 MiB','실행시간 최소~최대 초'],[[names[key],LABEL[label],mib(ss[key,label]['rss_peak_median']),mib(ss[key,label]['rss_increment_median']),f'{ss[key,label]["seconds_min"]:.4f}~{ss[key,label]["seconds_max"]:.4f}'] for key in ['all_text_stream','all_columns_materialize'] for label in ['original','plain','compact']])
    s+='\nRSS는 2ms 주기 및 fetch 종료 시점의 프로세스 메모리 측정이다. 절대 최고값에는 Python 인터프리터가 포함된다. 샘플 간 순간 피크는 놓칠 수 있고 OS 전체 파일 캐시·정확한 SQLite 할당량은 아니다. 파일 크기 68.03% 감소를 결과 객체 메모리 68.03% 감소로 해석할 수 없다. 작은 쿼리의 1ms 미만 값은 측정 잡음의 영향이 크다.\n\n'
    s+='원래 인덱스가 있는 최초 DB는 이벤트 ID와 검색 결과 조인에서 빠르다. 추가 DB의 조건식은 문자열 ID를 계산한 후 비교하며, 쿼리 계획에는 `_data_event`/`_data_search_result` 스캔과 상관 스칼라 사전 조회가 나타난다. 코드용 새 인덱스를 정의해도 복원 문자열 조건이 자동으로 해당 인덱스를 사용하는 것은 아니다. 전체 SQL, 쿼리 계획, 결과 동등성, 105회 원시 측정은 JSON에 보관했다.\n\n'
    s+='## 5. 생성 코드 진단: 현재 상태로 실행하면 안 되는 이유\n\n'
    s+=table(['우선순위','실제 코드/객체','확인한 문제','증강 영향'],[
        ['차단','생성기 create_schema: sqlite_master type=table 조회','compact의 user/event 등은 view. 동일 조회식의 읽기 전용 재현 결과 '+M['generator_schema_error'],'입력 경량 DB에서 스키마 복제 단계 실패'],
        ['차단','생성기 users/rec/fr/x의 data_origin 대입 및 qa G5_origin','plain과 compact 업무 스키마 모두 data_origin 없음','테이블/뷰 문제만 바꿔도 INSERT 또는 QA에서 열 없음 오류'],
        ['차단','user/search/event 뷰의 printf+substr','정수 사용자 10000 → SYN_U1000; 현재 고정 자리 복원식이 잘림','새 ID가 기존 사용자처럼 보이거나 참조가 깨짐'],
        ['차단','경량화기 고정폭 정규식 + 마지막 search_result 뷰','4자리/5자리 혼합 ID면 산술 변환을 포기하고 TEXT 유지. 그러나 search_result 뷰는 정수 나눗셈을 강제','읽기 전용 식 검증: SYN_Q10000_001 텍스트 → SYN_Q0000_000. 재실행은 자동 해결책 아님'],
        ['차단','생성기 qa 및 cfg n_sessions','QA는 user/session==1000 하드코딩; n_users는 build 반복 수에 사용되지 않음','n_users만 10000으로 바꾸면 10000명이 되지 않음; n_sessions 변경 시 QA 실패'],
        ['높음','사전 enumerate(sorted(unique),1), mapping[x]','일괄 구축만 지원; 새 값 추가 시 증분 get-or-create/고정 ID 정책 없음','기존 mapping에 새 원문을 넣으면 KeyError. 부분 사전 재구축은 ID 재배치로 기존 참조 오해 가능'],
        ['높음','_dict_*.value, _data_*','value UNIQUE와 선언 FK가 없음; 업무 ID PK 대부분 없음','미등록 코드가 뷰에서 NULL로 보일 수 있고 중복·잘못된 참조가 차단되지 않음'],
        ['높음','생성기 enumerate(chosen,1)','항상 SYN_U0001/SYN_S0001부터 시작. 기존 사용자를 복사 보존하는 append 로직 없음','현재 1000명 유지 후 9000명 추가라면 ID 공간 분리 및 계보 정책 필요'],
        ['높음','생성기 base 시각 + checkin_date/checkout_date 복사','현재 검색 6900행 모두 체크인 날짜가 검색 날짜보다 과거','증강 시각 이동과 숙박일 규칙을 함께 재검토; 데이터 의미상 허용 여부 추가 확인 필요'],
        ['높음','생성기 pandas 전체 로딩 및 out_s/out_f/out_r/out_e','출력 전체를 dict 리스트에 누적하고 마지막에 삽입; 루프마다 전체 DataFrame 마스크','10배 규모에서 필터링 CPU와 메모리 비용 증가; 배치/사전그룹화 검토 필요'],
        ['보통','경량화기 ROOT.rglob + next','정확한 입력 경로 인자 없이 첫 패턴 매칭 파일 선택','유사 파일이 늘면 다른 입력을 선택할 위험'],
        ['보통','경량화기 commit/VACUUM 후 assert 비교','검증 실패 시 이미 생성·커밋한 출력의 원자적 폐기/승격 없음; assert는 -O에서 생략','실패한 파일이 완성본처럼 남을 수 있음. 이번 입력 검증은 통과했음'],
        ['보통','경량화기 임시 변수 sql/view_columns/hotel_expr','최종 뷰 구성에 사용되지 않는 코드와 남은 객실 인덱스','즉시 값 오류는 아니지만 유지보수 판단을 혼동시킴'],
    ])
    s+='\n고정폭 경계 시험은 기존 뷰의 계산식에 스칼라 값을 넣은 SELECT만 실행했다. 기존 테이블에 시험 행을 삽입하지 않았다. room_id의 2자리 객실 순번 시험도 실패했지만 현재 카탈로그는 1자리이므로 해당 카탈로그가 확장될 때의 조건부 위험이다. **기존 1,000명 데이터가 이미 깨졌다는 뜻은 아니다.**\n\n'
    s+='## 6. 10,000명 조건부 규모·시간 모델\n\n'
    s+='사용자/세션을 10배로 하고 세션당 행동량을 유지하며 hotel/room 카탈로그는 고정하는 경우다. 실제 10,000명 설정·추가 생성 규칙은 확인되지 않았다. 현재 설정의 10000_users 금지는 과거 파일럿 범위 기록이며, 이번 요청을 차단하는 명령으로 적용하지 않았다. 현재 사용자가 진단만 요청했으므로 생성은 실행하지 않았다.\n\n'
    s+=table(['실제 업무 이름','현재 행','조건부 10,000명 행'],[[t,num(v['now']),num(v['x10_users'])] for t,v in M['row_scenario'].items()])
    s+= '\n'+table(['저장 방식','현재 MiB','10배 행동량 페이지 선형 모델 MiB'],[[LABEL[k],mib(A['sources'][k]['bytes']),mib(v['page_linear_estimate_bytes'])] for k,v in M['db_scale'].items()])
    s+='\n파일 모형은 현재 객체별 페이지 크기에 행동 테이블·관련 인덱스·세션은 10배, 정적 카탈로그/고정 사전은 1배를 적용했다. compact의 event_at 사전만 현재 고유비율 유지로 10배 처리했다. 페이지 충전율, 정수 2→3 bytes 증가, ID 문자열 길이, 새 제약/인덱스, 향후 코드 수정은 미반영이므로 확정 크기가 아니다. 특히 현재 compact는 10,000명 입력을 그대로 처리할 수 없어 이 숫자는 수정 후 실제 산출 크기를 보장하지 않는다.\n\n'
    s+=f'모든 이벤트 시각이 고유해지면 시각 사전 증가만 반영한 compact 민감도 추정은 약 **{mib(M["compact_all_unique_timestamp_estimate_bytes"])} MiB**다. 현재 고유비율 유지의 {mib(M["db_scale"]["compact"]["page_linear_estimate_bytes"])} MiB보다 커진다. 새 자유 텍스트까지 추가되면 이 값은 상한이 아니다.\n\n'
    s+='사전 수는 기존 event_type 24개/device 2개 등 범주 재사용 여부에 따라 유지될 수 있다. event_at은 고유비율 유지 시 221,290개, 모든 시각 고유 시 2,388,510개다. “행을 10배 늘리면 모든 사전도 10배”로 가정하지 않는다.\n\n'
    s+=table(['코드에 실제 있는 필터 연산','호출당 측정 중앙값 ms','조건부 호출 수','단순 환산 초'],[[x['operation'],f'{x["median_seconds_per_call"]*1000:.3f}',num(x['calls_scenario']),f'{x["estimated_seconds"]:.1f}'] for x in M['generator_filter_cost_model']])
    s+=f'\n위 연산만 단순 환산하면 약 **{sum(x["estimated_seconds"] for x in M["generator_filter_cost_model"]):.1f}초**다. 실제 입력 DataFrame에서 30개 키를 5회 측정한 마스크/부분선택 비용이며, 정렬·itertuples·날짜 처리·새 행 생성·SQLite 쓰기·인덱스 생성·QA·경량화는 제외한다. 생성기 전체를 실행한 시간도, 총 실행시간 예측도 아니다. 전체 생성 시간은 추가 확인 필요다.\n\n'
    s+=f'생성 코드가 사용하는 4개 입력 DataFrame의 deep 메모리 합은 {mib(sum(M["pandas_input_memory_bytes"].values()))} MiB다(프로세스 RSS와 다른 지표). 현재 출력 dict 구조를 10배 행에 적용하면 **dict 컨테이너 껍데기만 약 {M["output_dict_shell_lower_bound_bytes"]/1073741824:.2f} GiB**다. 원문 문자열·숫자 객체·리스트·입력 프레임·변환 복사본은 빠져 있어 실제 피크는 더 커진다. 전체 fetchall 메모리 역시 현재 약 258 MiB 증가분을 단순 10배하면 약 2.5 GiB 수준이며, 실측 10,000명 메모리는 아니다.\n\n'
    s+=f'단순 행수 비례로 전체 문자열 조회를 환산하면 plain 약 {ss["all_text_stream","plain"]["seconds_median"]*10:.1f}초, compact 약 {ss["all_text_stream","compact"]["seconds_median"]*10:.1f}초지만, 사전 B-tree 성장·캐시·새 인덱스·동시 부하에 따라 달라진다. 새 코드의 실제 처리시간은 수정 승인 후 별도 벤치마크가 필요하다.\n\n'
    s+='## 7. 컬럼별 권고와 다음 결정\n\n'
    s+='**모든 업무 87열 및 물리 저장 113열의 실제 이름·저장 방식·고유값 비율·효과·예상 문제·5분류 권고·근거는 [컬럼별권고.md](컬럼별권고.md)에 전수 정리했다.** 원문/숫자 보존과 증강 대상 여부를 함께 표기했으며 “제외”는 삭제 지시가 아니다.\n\n'
    s+='진단 기준 권고는 안정적인 범주(event_type/device/sort_option/destination/region)는 사전을 유지하고, 새로 만드는 업무 ID·시간·이름·이메일은 원문 보존을 우선하는 것이다. 검색어는 기존 23개 재사용인지 자유 텍스트 생성인지 추가 확인이 필요하다. 호텔·객실은 현재 생성 코드상 고정 카탈로그이며, 빈 booking과 NULL 5개 열은 임의로 채우지 않는다.\n\n'
    s+='구조·코드 수정 전 확인할 항목은 (1) 10,000건의 단위와 기존 행 보존 여부, (2) 새 검색어·시각·예약·리뷰·카탈로그 생성 범위, (3) 읽기 편의/생성 호환성과 파일 크기의 우선순위다. 현재 상태의 경량 DB를 증강 입력으로 바로 사용하지 않는 것을 권고한다. 이 진단에서는 기존 DB·생성 코드·이력 문서를 수정하지 않았고 GitHub에도 추가 push하지 않았다.\n\n'
    s+='## 8. 재현성과 원본 보존\n\n'
    s+='진단 전후 DB 3개와 기존 경량화 코드·해당 생성 코드·설정·매니페스트의 SHA-256이 일치했다. 새 파일은 이 diagnostics/sqlite_20260907 폴더에만 생성했다. 진단 스크립트의 모든 DB 연결은 mode=ro이고 query_only=on을 적용한다. 백업 파일 변경·VACUUM·DDL·DML·증강 생성은 수행하지 않았다.\n\n'
    s+='- `read_only_audit.py` / `audit_raw.json`: 전체 스키마·384열 프로파일·페이지별 크기·관계·값 검증\n- `benchmark_read_only.py` / `benchmark_queries.json` / `benchmark_trials.json` / `benchmark_summary.json` / `benchmark_plans_and_equality.json`: 동일 조건 SQL·105회 측정·실행계획·반환값 정합성\n- `augmentation_risk_model.py` / `augmentation_risk_model.json`: 조건부 크기·필터링 비용·메모리·스칼라 ID 경계 시험\n- `column_recommendations.json`: 업무 열별 5분류 판단 원자료\n\n'
    s+='비율·길이의 분모와 제외 규칙은 전체컬럼통계 문서에 명시했다. 사전/세션 참조 검사는 LEFT JOIN 또는 부모 비NULL 값 집합 포함 검사로 수행했고 원래 행을 삭제하거나 수정하지 않았다. 논리 동일성 비교는 plain 전체 행과 compact 뷰 전체 행을 배치 비교하고, 성능 쿼리의 결과는 순서와 무관한 행 해시 멀티셋으로 비교했다.\n\n'
    s+='SQLite의 정수 가변 저장 크기는 [공식 자료형 문서](https://www.sqlite.org/datatype3.html), 뷰의 읽기 전용 동작은 [CREATE VIEW](https://sqlite.org/lang_createview.html), FK 선언/활성화의 구분은 [Foreign Key Support](https://www.sqlite.org/foreignkeys.html)를 참고했다. 성능 수치는 외부 일반론이 아닌 이 장비에서의 측정값이다.\n'
    write('진단결과.md',s)

recommendations();profiles();schema();main_report()
print('REPORTS WRITTEN')
