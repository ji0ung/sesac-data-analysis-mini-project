"""Apply the Sep 7 screenshot feedback to the six Sep 5 submissions.

Patch only document.xml text and the opening policy paragraphs; preserve all
other DOCX package parts. Sources remain untouched.
"""
from pathlib import Path
from copy import deepcopy
import io
import json
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '04_분석설계/팀프로젝트/2026/09'
SOURCE = BASE / 'BI시각화_32-34일차_TO-BE_클린제출본_20260905'
OUT = ROOT / '04_분석설계' / '이전버전' / '화면피드백반영' / 'BI시각화_32-34일차_TO-BE_화면피드백반영_20260907'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
def q(t): return '{'+W+'}'+t
def text(p): return ''.join(t.text or '' for t in p.findall('.//w:t', NS))

RULES = [
    '화면 반영 기준 · 2026-09-07 (2팀 피드백)',
    '카드 H에는 33일차 승인값인 1위 상세진입 110/149 = 73.8%만 표시한다. 고유 클릭 재정의값(29/149), 예약 지표, ×·△ 구간에서 만든 값, 조건 구분 없는 전체 평균은 화면에서 제외한다.',
    '검색 296건·결과 있는 검색 149건·세션 43개·사용자 41명·전이 140건은 분석 단위와 분모별로 화면을 분리한다. 서로 다른 분모의 비율을 같은 축에 놓지 않는다. 조건별 비교는 같은 지표 정의·분모 기준을 적용하고 각 집단의 분자/분모와 n을 표시한다.',
]
EXACT = {
 '고유 결과 단위 CTR': '순위 통제 분석 보류; 화면은 H 승인값만 표시',
 '가격·옵션 수·호텔 특성 통제 후 순위별 클릭 재분석': '가격·옵션 수·호텔 특성 통제 분석은 내부 검토로 분리',
 '1위 73.8%, 2위 22.6%, 3위 21.4%, 4위 7.2%, 5위 17.4%': '1위 상세진입 110/149=73.8% (33일차 승인값만 표시)',
 '전체 상세진입 45/296과 카드 H 1위 상세진입 110/149의 분자 단위를 정리하시오. 확정 전까지 73.8%를 단독으로 쓰지 않는다.': '카드 H는 33일차 승인값 110/149=73.8%만 표시한다. 전체 검색 296건 기준 지표는 결과 있는 검색 149건 기준 카드 H와 다른 화면에서 다룬다.',
 '원천에는 ×·△ 라벨 컬럼이 없다. 가격·평점·편의시설 원시값으로 조건을 판정하고, ×·△를 사용하려면 기준표와 파생 컬럼 정의를 먼저 확정한다.': '원천에는 ×·△ 라벨 컬럼이 없다. ×·△ 구간에서 만든 값은 화면에서 제외한다. 조건별 비교는 원천 조건과 집단별 분모가 확인된 지표만 사용한다.',
 '예약 완료율': '예약 지표 — 화면·성과 KPI 제외',
 'booking_complete 검색 / 상세진입 검색': '산식 적용 보류; 출처·연결 검증은 내부 QA에서 수행',
 '예약 성과 KPI 준비': '예약 데이터 내부 QA — 화면 표시 제외',
 '상세진입률(2차)·예약완료율(검증 완료 전 참고)': '상세진입률(2차); 예약 지표 제외',
 'Overview': 'Overview — 승인 카드 H',
 '관측 0건·회복·상세진입': '1위 상세진입 110/149=73.8%만 표시',
 'A/B 차이, 95% 구간, treatment 우세 확률': 'A/B는 별도 화면에서 조건·분모별 비교',
 '01 Overview': '01 Overview — 승인 카드 H',
 '전체 A/B 결과와 사업적 판단은?': '현재 화면에 고정할 승인값은?',
 '회복률·상세진입률 차이, 95% 구간, 승산확률': '1위 상세진입 110/149=73.8%; A/B는 별도 화면',
 '전체·세그먼트별 uplift, 퍼널, 효과 순위': '조건·분모별 별도 화면의 A/B 차이·불확실성',
 '04 행동 퍼널': '04 행동 단계 — 분모별 별도 화면',
 '노출→선택→변경→회복→상세짅입': '각 단계는 동일 단위로 검증 후 비교; 분모가 다르면 화면 분리',
 'Power BI에 전체 오버뷰, 세그먼트 A/B, 0건 회복 퍼널, 제안별 성과, 불확실성 페이지를 구성합니다.': 'Power BI의 카드 H에는 110/149=73.8%만 표시합니다. A/B·회복·제안별 성과는 조건과 분모별 별도 화면으로 구성하고, 조건 구분 없는 전체 평균과 예약 지표는 제외합니다.',
}

def revise(s):
    if s.startswith('BOOKING은 2026-09-07까지 출처·중복·호텔 연결을 검증하고'):
        return 'BOOKING의 출처·중복·호텔 연결은 내부 QA에서 검증합니다. 예약 지표는 화면과 성과 KPI에서 제외합니다.'
    if s == '결과 회복은 hotel_detail_view 기반 상세진입 증가로 이어진다. 예약완료는 2026-09-07 검증 통과 후 보조 KPI로 검토한다.':
        return '결과 회복은 hotel_detail_view 기반 상세진입 증가로 이어진다. 예약완료는 화면·성과 KPI에서 제외하고 내부 QA에서만 검토한다.'
    s = EXACT.get(s, s)
    if s.startswith('순위별 상세진입률: 1위 110/149=73.8%'):
        s = '카드 H 표시값: 1위 상세진입 110/149=73.8% (33일차 승인값). 결과 있는 검색 149건 기준이며, 다른 순위 수치와 고유 클릭 재정의값은 화면에서 제외한다.'
    if s.startswith('1위 결과의 상세진입률은 73.8%로 가장 높'):
        s = '카드 H는 1위 상세진입 110/149=73.8%만 표시한다. 관찰 자료이므로 순위 자체의 인과효과로 단정하지 않는다.'
    # Remove stale permission to expose reservations after a date or QA gate.
    if any(k in s for k in ['예약', 'BOOKING', '보조 KPI', '참고 지표', '고유 클릭']):
        s = s.replace('정의 확인 전 배포·Power BI에서 제외', '배포·Power BI 화면에서 제외')
        s = s.replace('정의 확인 전 배포·Power BI 확정값에서 제외', '배포·Power BI 화면에서 제외')
        s = s.replace('정의 확인 전 Power BI 및 성과 판정에서 제외', 'Power BI 화면 및 성과 판정에서 제외')
        s = re.sub(r'2026-09-07[^.。]*?보조 KPI로 (?:승격합니다|승격|검토한다|검토합니다)', '출처·연결 검증은 내부 QA에서 수행하며 예약 지표는 화면·성과 KPI에서 제외한다', s)
        s = re.sub(r'예약완료는 2026-09-07[^.。]*?참고 지표로만 표시(?:합니다|한다)', '예약완료는 화면·성과 KPI에서 제외하고 내부 QA에서만 검토한다', s)
        s = s.replace('참고 지표로만 표시하고', '내부 QA 기록으로만 보관하고').replace('참고 지표로만 사용합니다', '내부 QA 기록으로만 보관합니다')
        s = s.replace('예약시작·예약완료는 2026-09-07 검증 완료 전 참고 지표', '예약시작·예약완료는 화면·성과 KPI 제외')
        s = s.replace('통과 전에는 참고 지표이며', '예약 지표는 화면에 표시하지 않으며')
        s = s.replace('그전에는 참고 지표이며', '예약 지표는 화면에 표시하지 않으며')
        s = s.replace('완료 전 참고 지표로만 표시', '검증 결과는 내부 QA 기록으로만 보관')
        s = s.replace('2026-09-07 무결성 검증 완료 전 참고 지표; 최종 성과 판정 제외', '예약 지표는 화면·성과 KPI 제외; 검증은 내부 QA')
    if '상세진입입니다.' in s:
        s=s.replace('내부 QA에서만 검토한다.', '내부 QA에서만 검토합니다.')
    return s

def replace(p, value):
    runs=p.findall('w:r', NS)
    prop=deepcopy(runs[0].find('w:rPr',NS)) if runs and runs[0].find('w:rPr',NS) is not None else ET.Element(q('rPr'))
    color=prop.find('w:color',NS)
    if color is None: color=ET.SubElement(prop,q('color'))
    color.set(q('val'),'9C0006')
    for child in list(p):
        if child.tag != q('pPr'): p.remove(child)
    r=ET.SubElement(p,q('r'));r.append(prop)
    ET.SubElement(r,q('t')).text=value

def main():
    OUT.mkdir(exist_ok=True)
    audit=[]
    for src in sorted(SOURCE.glob('*.docx')):
        with zipfile.ZipFile(src) as z:
            raw=z.read('word/document.xml')
            namespaces=list(ET.iterparse(io.BytesIO(raw),events=['start-ns']))
            for _, (prefix,uri) in namespaces:
                ET.register_namespace(prefix,uri)
            root=ET.fromstring(raw)
            changes=[]
            for p in root.findall('.//w:p',NS):
                old=text(p);new=revise(old)
                if new != old: replace(p,new);changes.append({'before':old,'after':new})
            body=root.find('w:body',NS)
            for i,rule in enumerate(RULES):
                p=ET.Element(q('p'));pr=ET.SubElement(p,q('pPr'))
                ET.SubElement(pr,q('spacing'),{q('after'):'100'})
                r=ET.SubElement(p,q('r'));rp=ET.SubElement(r,q('rPr'))
                ET.SubElement(rp,q('rFonts'),{q('ascii'):'Calibri',q('hAnsi'):'Calibri',q('eastAsia'):'맑은 고딕'})
                ET.SubElement(rp,q('sz'),{q('val'):'19'})
                ET.SubElement(rp,q('color'),{q('val'):'9C0006'})
                if i==0: ET.SubElement(rp,q('b'))
                ET.SubElement(r,q('t')).text=rule
                body.insert(1+i,p)
            name=src.name.replace('20260905_v02_클린제출본','20260907_v03_제출본').replace('20260905_v04_클린제출본','20260907_v05_제출본')
            dst=OUT/name
            xml=ET.tostring(root,encoding='UTF-8',xml_declaration=True)
            # Keep declarations referenced only by mc:Ignorable/QName values.
            start=xml.index(b'<w:document');end=xml.index(b'>',start)
            head=xml[start:end]
            missing=b''
            for _,(prefix,uri) in namespaces:
                attr=('xmlns:'+prefix if prefix else 'xmlns').encode()
                if attr+b'=' not in head and attr+b'=' not in missing:
                    missing+=b' '+attr+b'="'+uri.encode()+b'"'
            xml=xml[:end]+missing+xml[end:]
            with zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED) as out:
                for item in z.infolist():
                    out.writestr(item,xml if item.filename=='word/document.xml' else z.read(item.filename))
            audit.append({'source':str(src),'output':str(dst),'changes':changes})
            print(name,len(changes))
    qa=ROOT/'.codex_tmp/screen_feedback_20260907';qa.mkdir(parents=True,exist_ok=True)
    (qa/'changes.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
