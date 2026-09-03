# 데이터 모델링 및 분석 데이터

> **분석 전 필수:** 이 폴더의 원본 CSV와 SQLite에는 확인된 품질 이슈가 있다.
> 원본을 바로 집계하지 말고 [`data_quality/README.md`](data_quality/README.md)와
> [`data_quality/data_quality_manifest.json`](data_quality/data_quality_manifest.json)의
> 품질 플래그 처리 규칙을 먼저 적용한다.

현재 분석 기준은 `2026-09-03_v03`이다. `search`와 `event` CSV 및 SQLite 테이블에
분석용 품질 플래그가 직접 포함되어 있다. 이전 v02는
`archive/datasets/2026-09-03_v02/`에 원천값 그대로 보존한다.

## 반드시 적용할 플래그

| 대상 | 플래그 파일 | 조인 키 | 기본 처리 |
|---|---|---|---|
| 검색 296건 | `search_2026-09-03_v03_비식별.csv` | `invalid_stay_date_flag` | 날짜 유효성이 필요한 지표에서 값이 1인 행 제외 |
| 행동 이벤트 10,432건 | `event_2026-09-03_v03_비식별.csv` | `click_in_result_flag` | 노출 기반 클릭 지표에서 값이 0인 클릭 제외 |

SQLite 분석은 [`data_quality/analysis_guardrails.sql`](data_quality/analysis_guardrails.sql)을
실행해 원본 DB를 변경하지 않는 TEMP VIEW를 사용할 수 있다.

변경 내용과 사용 방법은
[`호텔검색_데이터품질갱신안내_20260903_v01_현행본.md`](호텔검색_데이터품질갱신안내_20260903_v01_현행본.md)를
먼저 확인한다. AI 분석은
[`호텔검색_AI데이터분석지침_20260903_v01_현행본.md`](호텔검색_AI데이터분석지침_20260903_v01_현행본.md)도
함께 적용한다.

알려진 품질 이슈는 숙박일 역전 검색 9건과 검색결과에 없는 호텔 클릭 2건이다.
두 유형 모두 원본 행과 행동 이벤트는 유지하며, 영향을 받는 지표에서만 조건부로 제외한다.
행동 존재를 보는 분석에서는 이벤트를 삭제하지 말고, 노출 또는 날짜 연결 한계를 함께
기술한다.
