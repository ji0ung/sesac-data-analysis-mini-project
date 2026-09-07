# 01 Baseline and Contract Gate Report

## 최종 판정: PASS

PROMPT 0의 PASS 및 두 승인 해시를 확인했다. 이번 단계에서는 생성 코드나 신규 SQLite를 만들지 않았으며, 실제 A/B 결과를 주장하지 않았다.

## 핵심 재계산

| 지표 | SQLite 직접 계산 | grain | 판정 |
|---|---:|---|---|
| 0건률 | 147/296 = 49.7% | search_id | PASS |
| 0건 후 후속검색 | 140/147 = 95.2% | zero-result search_id | PASS |
| 즉시 회복 | 24/140 = 17.1% | zero→next transition | PASS |
| 세션 최종 회복 | 21/28 = 75.0% | zero 경험 session_id | PASS |
| 카드 G | 27/10/4/2, 합계 43 | session_id | PASS |
| 카드 H | hotel_detail_view 110/149 = 73.8% | rank-1 exposure row | PASS |
| 활성 필터 3개 이상 0건률 | 119/160 = 74.4% | search_id | PASS |

카드 G/H는 최우선 교수회신의 승인값과 일치한다. STOP 조건은 발생하지 않았다. G-1 3범주와 H-1 고유 클릭 정의는 사용하지 않았다.

## 프로파일 결과

### 실제 관측 v03

- 행 수: USER 89, HOTEL 1,000, ROOM 3,000, SEARCH 296, SEARCH_FILTER 296, SEARCH_RESULT 8,555, EVENT 10,432, BOOKING 36.
- 기간: USER 2026-08-28 18:06:29~2026-09-01 10:12:24 KST; SEARCH 2026-08-28 18:18:23~2026-08-31 19:43:27 KST; EVENT 2026-08-28 18:06:29~2026-09-01 10:12:24 KST.
- 모든 선언 PK의 NULL/공백/중복은 0건이다.
- 물리 FK 선언은 없지만 논리 FK orphan은 BOOKING–ROOM 호텔 일치 검사 2건 외 0건이다.
- 날짜 역전 9건, 검색결과 미연결 hotel_click 2건, hotel_detail_view 2건을 확인했다.
- 전체 null cell 수는 nullable/비적용 필드를 포함한다. 컬럼별 값은 XLSX `column_profile` 시트에 기록했다.

### 관측형 합성 1,000명

- 행 수: USER 1,000, HOTEL 1,000, ROOM 3,000, SEARCH 6,900, SEARCH_FILTER 6,900, SEARCH_RESULT 198,128, EVENT 238,851, BOOKING 0.
- 검색 세션과 이벤트 세션은 각각 고유 1,000개다.
- 기간: USER 2026-12-02~2027-08-09 KST; SEARCH 2027-01-01~2027-09-08 KST; EVENT 2027-01-01~2027-09-08 KST.
- 모든 선언 PK의 NULL/공백/중복 0건, 논리 FK orphan 0건, 결과 수 불일치 0건이다.
- 날짜 역전 및 검색결과 미연결 click/detail은 0건이다.
- v03 품질 플래그 컬럼 2개는 합성 DB 스키마에 없으므로 다음 생성 계약에서 보완 대상으로 명시했다.

## 조건부 확률과 희소성

- 모든 이항 확률은 관측 n·분자/분모·Beta(1,1) 사전·사후 alpha/beta를 기록했다.
- 행동 및 filter-state 구성비는 대칭 Dirichlet(1) 사전과 사후 alpha를 기록했다.
- 행동 분포는 동일 53, 완화 41, 검색어 10, 지역 24, 강화 10, 혼합 2로 합계 140이다.
- 희소 행동은 라벨을 유지하되 단독 점추정으로 고정하지 않고 상위 풀/전체 풀 민감도 규칙을 적용한다.
- 간격은 전체 140개 전이의 경험분포를 사용하며 행동별 희소 셀은 전체 분포로 후퇴한다.

## 원본 불변성

| 파일 | 실행 전/후 bytes | 실행 전/후 mtime_ns | 실행 전/후 SHA-256 | 결과 |
|---|---:|---:|---|---|
| 원본 v03 | 6,447,104 | 1788716585861624400 | `2f5bd2f73b02b103bb6107ee79aa109cf77afc6f5aecdf82b10c87c95a0bef80` | 동일 |
| 합성 1,000명 | 154,738,688 | 1788603037749345700 | `7d449fab6847730be38fe46ebb6bd6a5b31690cdf38cf4bdbadeaa75edd1ae04` | 동일 |

두 연결 모두 `mode=ro` 및 `query_only=1`로 검증했다. 원본·기존 산출물은 수정하지 않았다.

## 산출물 일관성

- `01_baseline_metrics.csv`: dataset class, grain, 분자, 분모, Q-ID, source SHA 포함.
- `01_metric_dictionary.xlsx`: metrics, table_profile, column_profile, logical_fk_checks, periods, db_files 6개 시트.
- `01_probability_parameters.csv`: Beta/Dirichlet 사전·사후와 sparse flag 포함.
- `01_segment_dictionary.json`: 실험 전/후 세그먼트 분리.
- `01_recompute.sql`: Q00~Q10 재계산 및 무결성 SQL.
- `01_contract.md`: 데이터·metric·불확실성·후퇴 규칙.

## 다음 단계 제한

PASS는 기준선 및 계약 확정에만 해당한다. BOOKING은 승인 전까지 최종 KPI와 생성 범위에서 제외한다. 10,000명 자료는 아직 시나리오 가정이며 실제 A/B 결과가 아니다.
