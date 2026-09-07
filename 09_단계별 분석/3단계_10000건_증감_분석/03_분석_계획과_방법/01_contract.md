# 01 Metric and Data Contract

## 1. 범위와 데이터 등급

| 등급 | 파일 | 허용 용도 | 금지 |
|---|---|---|---|
| 실제 관측 | `travel_data_filtered_complete_2026-09-03_v03_비식별.sqlite` | 기준선·조건부 확률의 원천 | 합성 1,000명 수치와 합산 |
| 관측형 합성 QA | `호텔검색_관측형합성1000명_분석용lineage제거정제DB_260905_1650_01.sqlite` | 구조·분포·무결성 비교 | 실제 사용자/A/B 결과로 표현 |
| 시나리오 가정 | 향후 10,000명 A/B 시뮬레이션 | 가정 민감도·설계 검증 | 실제 실험 효과·실제 전환 상승으로 표현 |

원본 해시는 `2f5bd2f73b02b103bb6107ee79aa109cf77afc6f5aecdf82b10c87c95a0bef80`, 합성 1,000명 기준 DB 해시는 `7d449fab6847730be38fe46ebb6bd6a5b31690cdf38cf4bdbadeaa75edd1ae04`로 잠근다.

## 2. grain 계약

| 객체 | grain | 원본 n | 사용 예 |
|---|---|---:|---|
| user | `user_id` | 전체 USER 89; 검색 연결 USER 41 | 사용자 구성 |
| search | `search_id` | 296 | 0건률 |
| session | `session_id` | 43 | 카드 G, 세션 최종 회복 |
| zero search | `total_result_count=0`인 `search_id` | 147 | 후속검색률 |
| zero transition | 0건 검색과 같은 세션의 시간순 바로 다음 검색 쌍 | 140 | 즉시 회복·행동 유형 |
| exposure | `search_result_id` | 전체 8,555; rank 1은 149 | 카드 H 분모 |
| event | `event_id` | 10,432 | `hotel_detail_view` 등 이벤트 수 |
| booking | `booking_id` | 36 | 무결성 점검만; KPI/생성 제외 |

서로 다른 grain의 비율을 더하거나 증감률로 연결하지 않는다. 특히 24/140과 21/28은 각각 전이와 세션 비율이다.

## 3. 승인 지표 계약

| 지표 | 분자 | 분모 | SQL |
|---|---|---|---|
| 0건률 | 결과 수 0인 검색 147 | 검색 296 | Q04 |
| 0건 후 후속검색률 | 바로 다음 검색이 있는 0건 검색 140 | 0건 검색 147 | Q04 |
| 즉시 회복률 | 다음 검색 결과가 양수인 전이 24 | 0건→다음 검색 전이 140 | Q04 |
| 세션 최종 회복률 | 시간순 마지막 검색 결과가 양수인 세션 21 | 0건 경험 세션 28 | Q04 |
| 카드 G | 직접성공 27 / 노출·미선택 10 / 재검색회복 4 / 지속실패 2 | 검색 세션 43 | Q05 |
| 카드 H | rank 1과 연결된 `hotel_detail_view` EVENT 110 | rank-1 `search_result` 행 149 | Q06 |

카드 G의 3범주 재편은 G-1, 카드 H의 고유 클릭 29/149는 H-1 후보이며 승인 지표를 대체하지 않는다. 카드 H의 분자는 `hotel_click`이 아니라 `hotel_detail_view` 이벤트 행이다.

## 4. 세그먼트 계약

- 실험 전: `filter_state_segment`, `intent_segment`. 처치 배정 전의 검색 필터 상태/프록시 의도만 사용한다.
- 실험 후: `observed_behavior`, `outcome_segment`. 처치 이후 관측된 검색 변경과 세션 결과만 사용한다.
- `intent_segment`는 실제 진술 의도가 아니라 가격·최소평점·편의시설 상태에서 만든 프록시다.
- 사후 `outcome_segment`를 처치 배정에 사용하지 않는다.
- 전체 코드와 판정식은 `01_segment_dictionary.json`을 따른다.

## 5. 행동 유형과 시간 계약

0건→바로 다음 검색 전이는 `search_time, search_id`의 안정 정렬을 사용한다. 상호배타 우선순위는 동일 조건 → 목적지/지역 변경 → 검색어 변경 → 조건 완화 → 조건 강화 → 완화·강화 혼합이다.

| 행동 | n | 회복 | 상세진입 |
|---|---:|---:|---:|
| 동일 조건 | 53 | 0/53 | 0/53 |
| 조건 완화 | 41 | 11/41 | 8/41 |
| 검색어 수정 | 10 | 3/10 | 3/10 |
| 지역 변경 | 24 | 10/24 | 3/24 |
| 조건 강화 | 10 | 0/10 | 0/10 |
| 혼합 변경 | 2 | 0/2 | 0/2 |

간격은 `substr(timestamp,1,19)`를 SQLite `julianday`로 변환한 초 단위다. n=140, 최소 0초, 평균 17.721초, p25 7초, 중앙값 12초, p75 18초, p90 31초, p95 39초, 최대 249초다. 백분위는 nearest-rank를 사용한다.

## 6. 필터 결합과 확률 사후분포

활성 필터는 `property_type`, `property_grade`, `user_rating_min`, `price`, `amenity_count>0`, `region`의 6차원으로 정의한다. 검색어와 목적지는 필터 개수에 넣지 않는다. 활성 필터 3개 이상 검색의 0건률은 119/160=74.4%다.

- 이항률: 사전분포 `Beta(1,1)`, 사후분포 `Beta(1+분자, 1+분모-분자)`.
- 다범주 구성비: 대칭 `Dirichlet(alpha_i=1)`, 사후 `alpha_i=1+n_i`.
- 희소 플래그: 이항은 분모 <30 또는 성공/실패 셀 중 하나가 <5, 다범주는 범주 n<30.
- 원자료 분자·분모와 사후 평균을 함께 저장하며 사후 평균으로 관측률을 덮어쓰지 않는다.

희소 범주는 보고 시 합치지 않는다. 생성 파라미터가 필요할 때만 다음 후퇴 규칙을 적용한다.

1. 행동별 n≥30이면 행동별 Beta 사후를 사용한다.
2. n<30이면 해당 행동 라벨은 유지하고, 회복/상세진입 확률은 `adaptive_change = region + query + relax` 상위 풀과 전체 전이 풀을 함께 제시해 민감도 분석한다.
3. n=2인 mixed는 단독 점추정값으로 성공확률을 0에 고정하지 않는다.
4. 간격의 행동별 표본이 부족하면 전체 140개 전이의 경험분포로 병합한다.
5. 3개 이상 필터 결합은 n=160으로 전체율 추정에는 충분하지만 세부 조합별 셀이 n<30이면 `active_filter_count>=3` 상위 그룹으로 후퇴한다.

## 7. 데이터 품질·키 계약

- 두 DB 모두 물리적 FOREIGN KEY 선언은 0개다. `01_metric_dictionary.xlsx`의 `logical_fk_checks` 시트에 논리 FK 검사를 기록한다.
- 모든 테이블의 선언 PK는 NULL/공백/중복 0건이다.
- `search_filter.search_id` 중복과 `search_result(search_id,hotel_id)` 중복은 두 DB 모두 0건이다.
- `search.total_result_count`와 실제 `search_result` 행 수 불일치는 두 DB 모두 0건이다.
- 원본은 날짜 역전 9건, 검색결과 미연결 `hotel_click` 2건 및 `hotel_detail_view` 2건이 있다. v03 품질 플래그 규칙에 따라 관련 지표에서만 조건 처리한다.
- 원본 BOOKING 36건은 모두 가상 출처이고 BOOKING–ROOM 호텔 불일치 2건이 있다. 최종 KPI와 생성 범위에서 제외한다.
- 합성 1,000명 DB에는 `invalid_stay_date_flag`와 `click_in_result_flag` 컬럼이 없다. 실제 관측 기준선 계산에는 사용하지 않으며, 다음 생성 스키마에서는 명시적 QA 플래그 또는 동등한 검증 결과를 계약 필드로 추가해야 한다.

## 8. 재현 규칙

1. DB는 SQLite URI `mode=ro`로 열고 즉시 `PRAGMA query_only=ON`을 확인한다.
2. 지표 산식은 `01_recompute.sql`의 Q-ID로 추적한다.
3. 모든 결과에는 dataset class, grain, 분자, 분모, source SHA를 남긴다.
4. 실행 전후 두 DB의 SHA-256·bytes·mtime_ns가 모두 동일해야 한다.
5. 이 계약은 생성 승인이 아니다. 10,000명 시뮬레이션은 별도 실행 게이트 이후에만 가능하다.
