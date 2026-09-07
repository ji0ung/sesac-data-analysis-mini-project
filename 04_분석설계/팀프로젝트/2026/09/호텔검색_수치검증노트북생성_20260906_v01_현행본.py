"""Convert the existing report analysis into visible, executable notebook cells."""
from pathlib import Path
import textwrap
import nbformat as nbf
from nbclient import NotebookClient

folder = Path(__file__).resolve().parent
source = (folder / '호텔검색_증강데이터인사이트분석_20260904_v01_현행본.py').read_text(encoding='utf-8')
target = folder / '호텔검색_보고서수치검증_20260906_v01_현행본.ipynb'
cells = []
def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))
def code(text):
    cells.append(nbf.v4.new_code_cell(textwrap.dedent(text).strip()))
def section(start, end):
    return textwrap.dedent(source[source.index(start):source.index(end)]).strip()

md('''# 호텔검색 보고서 수치 검증 노트북

2026-09-04 분석 보고서의 값을 SQLite에서 직접 재계산합니다. 코드 셀 아래에 결과가 저장되어 있어 실행 전에도 읽을 수 있습니다.

**사용법:** VS Code에서 오른쪽 위 커널을 `Python 3.14 (team_i)` 또는 라이브러리가 설치된 Python 3.14로 선택 → **모두 실행(Run All)**. 셀 하나씩은 `Shift+Enter`입니다. 중간 셀부터 실행하면 앞에서 정의한 변수가 없어 오류가 날 수 있습니다.

순서: 환경 → 데이터/결합 → A → B → C → D·F → G → H → A-2 통제모형 → 보고서 대조.

비율은 모두 분자/분모×100입니다. 기술통계는 6,900검색·1,000세션, 통제모형은 기존 보고서와 동일한 43개 대표 경로·296검색을 사용합니다. 예약·이탈·개입 효과는 필요한 데이터가 없으므로 이번 수치 검증 범위에 포함되지 않습니다.
''')
md('''## 1. 환경 확인

라이브러리가 없을 때만 다음 셀의 주석을 풀어 실행하고 커널을 재시작하세요. `%pip`는 현재 노트북 커널에 설치합니다.''')
code('# %pip install pandas numpy scipy statsmodels==0.15.0 ipykernel')
code(section('from __future__ import annotations', 'def parse_args()') + '\nfrom IPython.display import display\nimport sys\npd.set_option("display.max_columns", 20)\nprint("Python:", sys.executable)\nprint("pandas:", pd.__version__, "statsmodels:", statsmodels.__version__)')
md('''## 2. 공통 함수

기존 분석 코드의 읽기 전용 연결, 비율 계산, 전이 분류 함수를 그대로 사용합니다. 전이는 동일조건 → 지역 변경 → 검색어 변경 → 완화/강화 순서로 판정합니다. 가격·평점 결측은 미설정이며 문자열 비교는 NFKC 정규화·공백 제거·소문자화합니다. 날짜·정렬·인원 변경은 기존 전이 분류 대상에서 제외되어 있습니다.''')
code(section('def sha256(', 'def main()'))
code('''
def show_metrics(items):
    rows = []
    for label, item in items.items():
        rows.append({"지표": label, "분자": item["numerator"], "분모": item["denominator"],
                     "비율(%)": 100 * item["rate"] if item["rate"] is not None else None,
                     "단위": item["analysis_unit"]})
    display(pd.DataFrame(rows).style.format({"비율(%)": "{:.2f}"}))

ROOT = next((p for p in [Path.cwd(), *Path.cwd().parents]
             if (p / '00_프로젝트관리').is_dir() and (p / '09_단계별 분석').is_dir()), None)
if ROOT is None:
    raise FileNotFoundError('team_i 폴더 또는 그 하위 폴더에서 실행하세요.')
analysis_folder = ROOT / '04_분석설계/팀프로젝트/2026/09'
db = ROOT / '09_단계별 분석/2단계_1000건_증감_분석/02_관측형합성1000명_실행묶음_260904_1259_01/호텔검색_관측형합성1000명_데이터_260904_1259_01.sqlite'
reference_path = analysis_folder / '호텔검색_증강데이터인사이트분석결과_20260904_v01_현행본.json'
reference = json.loads(reference_path.read_text(encoding='utf-8'))
assert db.is_file(), db
print('입력 SQLite:', db)
print('대조 JSON:', reference_path)
''')
md('''## 3. SQLite 로딩과 전처리

SEARCH–SEARCH_FILTER를 `search_id`로 1:1 결합하고, 세션·검색 시각·검색 ID로 정렬합니다. 순위 클릭은 고유 `(search_id, hotel_id)`로 집계합니다. DB 내용은 변경하지 않습니다.''')
code(section('    before_hash = sha256(db)', '    card_a = {}') + '''
display(pd.DataFrame(list(counts.items()), columns=['테이블', '행 수']))
print('무결성:', integrity)
print('검색 기간(KST):', base.search_at.min(), '~', base.search_at.max())
print('분석 전 SHA-256:', before_hash)
assert before_hash == reference['analysis']['database_sha256_before'], '보고서와 다른 DB입니다.'
display(base[['search_id','session_id','search_order','total_result_count','price','user_rating_min','amenity_count']].head(10))
''')
md('''## 4. 카드 A — 제한조건별 0건률

분자: 해당 조건이 설정된 검색 중 결과 0건. 분모: 해당 조건이 설정된 전체 검색. 조건들은 중첩될 수 있습니다.''')
code(section('    card_a = {}', '    zero_with_next =') + '\nshow_metrics(card_a)')
md('''수치 해석: 보고서의 편의시설 2,808/3,181, 평점 2,695/3,558, 가격 2,473/3,408을 대조합니다. 조건별 집단이 겹치므로 이 차이만으로 조건 해제의 효과를 확정할 수 없습니다.''')
md('''## 5. 카드 B — 후속검색과 종료 로그

0건 검색에서 같은 세션의 다음 검색으로 이어지는 전이를 만듭니다. 종료 이벤트 수는 실제 이탈자 수와 다릅니다.''')
code(section('    zero_with_next =', '    final_numerator =') + '''
show_metrics({'0건 후 후속검색': card_b['followup_after_zero']})
display(pd.DataFrame([{'검색 세션': card_b['search_sessions'], '시작 이벤트': card_b['session_start_events'], '종료 이벤트': card_b['session_end_events']}]))
display(zero_with_next[['search_id','next_search_id','transition_type','recovered','detail_entered']].head(10))
''')
md('''## 6. 카드 C — 즉시 회복과 세션 회복

즉시 회복: 다음 검색이 양수인 전이/0건 후 전이. 기존 JSON의 세션 회복: 0건 뒤 어느 시점이든 양수 검색이 존재한 세션/0건 경험 세션입니다.

**정의 확인:** 첨부 카드의 “마지막 검색이 양수”와 기존 코드의 “0건 뒤 한 번이라도 양수”는 일반적으로 다른 정의입니다. 아래에서 두 값을 함께 확인합니다. 서로 다른 분모의 즉시·세션 회복률을 상승률로 비교하지 않습니다.''')
code(section('    final_numerator =', '    method_results =') + '''
show_metrics(card_c)
zero_sessions = base.groupby('session_id')['zero'].any()
last_results = base.groupby('session_id').tail(1).set_index('session_id')['total_result_count']
last_positive_n = int(last_results.loc[zero_sessions[zero_sessions].index].gt(0).sum())
show_metrics({'마지막 검색 양수(별도 정의)': metric(last_positive_n, final_denominator, 'session')})
print('두 정의의 분자 차이:', final_numerator - last_positive_n)
''')
md('''## 7. 카드 D·F — 재검색 방법별 회복과 상세진입

회복 분자: 다음 검색 결과가 양수인 전이. 상세진입 분자: 다음 검색에 `hotel_click`이 있는 전이. 분모는 각 방법의 전이 수입니다. 반복 클릭은 검색 단위에서 한 번으로 처리합니다.''')
code(section('    method_results =', '    search_order =') + '''
method_table = []
for name, item in method_results.items():
    method_table.append({'방법': name, '전이 수': item['transitions'],
                         '회복 분자': item['recovery']['numerator'], '회복률(%)': item['recovery']['rate']*100,
                         '상세진입 분자': item['detail_entry']['numerator'], '상세진입률(%)': item['detail_entry']['rate']*100})
display(pd.DataFrame(method_table).style.format({'회복률(%)':'{:.2f}', '상세진입률(%)':'{:.2f}'}))
''')
md('''수치 해석: 지역 변경 회복 233/563과 검색어 변경 상세진입 69/234를 구분해서 읽습니다. 복제된 전이가 늘어났어도 원래 검색어 변경 표본 10건의 정보량이 늘어난 것은 아닙니다.''')
md('''## 8. 카드 G — 클릭 기준 세션 분류

기존 보고서의 축약 정의를 재현합니다. 첫 검색에 클릭이 귀속되면 직접 성공, 이후 검색에 최초 클릭이 귀속되면 재검색 후 성공, 클릭이 없으면 상호작용 없음입니다.

이 분류는 찜·객실 선택을 포함하지 않으며 클릭 시각이 다음 검색보다 앞서는지, 조건을 실제 바꿨는지는 추가 검증하지 않습니다. 따라서 첨부 카드 G의 전체 정의와 동등하다고 보지 않습니다.''')
code(section('    search_order =', '    card_h =') + '\nshow_metrics(card_g)')
md('''## 9. 카드 H — 순위별 고유 클릭

분자: 한 번 이상 클릭된 고유 `(search_id, hotel_id)`. 분모: 해당 순위의 결과 행. 반복 클릭은 제거합니다. 여기서는 기존 보고서의 기술통계만 재현하며 가격·평점·편의시설 통제 순위모형은 실행하지 않습니다.''')
code(section('    card_h =', '    signatures =') + '\nshow_metrics(card_h)')
md('''## 10. A-2 — 대표 경로와 통제모형

동일 조건 시퀀스의 세션은 하나의 대표 세션으로 줄입니다. 날짜는 생성 중 교정되어 지문에서 제외합니다. 이는 원본 계보 ID를 검증한 복원이 아닌 시퀀스 기반 추정입니다. 43개 경로·296검색이 재현되는지 확인합니다.

모형: 0건 여부 ~ 가격 설정 + 평점 설정 + 편의시설 3개 이상 + 도시 + 체크인월 + 인원 + 숙박일수. 세션 군집 표준오차를 사용해 보고서의 추정값을 재현합니다. 동일 원본 사용자가 여러 세션을 가졌을 가능성 및 원본 생성 규칙 영향은 남아 있으므로 p값은 확정적 근거로 사용하지 않습니다.''')
code(section('    signatures =', '    formula =') + '''
display(signature_counts.value_counts().sort_index().rename_axis('경로별 복제 수').to_frame('경로 수'))
print('대표 세션:', model_data.session_id.nunique(), '대표 검색:', len(model_data))
display(model_data[['zero_result','price_set','rating_set','amenity_ge3','city','checkin_month','guest_count','stay_nights']].head())
''')
code(section('    formula =', '    checks =') + '''
print('모형식:', formula)
print('수렴:', fitted.converged, '검색 수:', fitted.nobs)
display(pd.DataFrame(constraint_terms).T)
display(fitted.summary())
''')
md('''수치 해석: 표준화 확률은 각 대표 검색의 조건 플래그만 0 또는 1로 바꾼 모형 예측값을 평균한 것입니다. 오즈비 29.69는 확률이 29.69배라는 뜻이 아니며, +61.1%p도 실제 개입 효과가 아닙니다. 가격·평점의 신뢰구간은 넓습니다.''')
md('''## 11. 보고서 JSON 자동 대조와 품질 검증

아래에서 모든 카드의 분자·분모·비율 및 A-2 계수·확률을 기존 JSON과 비교합니다. 정수는 정확히, 실수는 작은 오차 허용 범위로 대조합니다. 이 PASS는 기존 계산 재현을 뜻하며 지표 정의나 인과적 타당성을 승인하는 의미는 아닙니다.''')
code(section('    checks =', '    result =') + '''
actual_sections = {'card_A': card_a, 'card_B': card_b, 'card_C': card_c,
                   'card_D_F': method_results, 'card_G': card_g, 'card_H': card_h,
                   'A2_terms': constraint_terms}
comparison = []
def compare_tree(actual, expected, path):
    if isinstance(expected, dict):
        for key, value in expected.items():
            compare_tree(actual[key], value, path + '.' + key)
    else:
        if isinstance(expected, float):
            passed = bool(np.isclose(actual, expected, rtol=1e-6, atol=1e-9))
        else:
            passed = actual == expected
        comparison.append({'항목': path, '재계산': actual, '보고서 JSON': expected, '일치': passed})
for name, actual in actual_sections.items():
    expected = reference['A2_adjusted_model']['constraint_terms'] if name == 'A2_terms' else reference[name]
    compare_tree(actual, expected, name)
comparison_df = pd.DataFrame(comparison)
display(comparison_df)
display(pd.DataFrame(list(checks.items()), columns=['QA 항목', '통과']))
connection.close()
assert all(checks.values()), '품질 검증 실패'
assert comparison_df['일치'].all(), '보고서 수치와 다른 항목이 있습니다.'
print(f"보고서 대조 {len(comparison_df)}개 PASS / QA {len(checks)}개 PASS")
print('분석 전후 DB SHA-256:', source_hash_after)
''')
md('''## 12. 직접 확인하는 예시

`base`는 검색별 데이터, `zero_with_next`는 0건 후 전이, `model_data`는 대표 검색, `comparison_df`는 대조표입니다. 아래 필터를 바꾸어 개별 행을 확인할 수 있습니다.''')
code('''
display(zero_with_next.loc[zero_with_next['transition_type'].eq('지역 변경'),
    ['session_id','search_id','next_search_id','destination','next_destination','recovered','detail_entered']].head(20))
''')

nb = nbf.v4.new_notebook(cells=cells, metadata={
    'kernelspec': {'name': 'team_i_py314', 'display_name': 'Python 3.14 (team_i)', 'language': 'python'},
    'language_info': {'name': 'python', 'version': '3.14.6'},
})
nbf.validate(nb)
nbf.write(nb, target)
NotebookClient(nb, timeout=180, kernel_name='team_i_py314', resources={'metadata': {'path': str(folder)}}).execute()
nbf.write(nb, target)
errors = [out for cell in nb.cells if cell.cell_type == 'code' for out in cell.outputs if out.output_type == 'error']
assert not errors
print(f'Notebook: {target}\nCells: {len(nb.cells)}; code cells: {sum(c.cell_type == "code" for c in nb.cells)}; errors: {len(errors)}')
