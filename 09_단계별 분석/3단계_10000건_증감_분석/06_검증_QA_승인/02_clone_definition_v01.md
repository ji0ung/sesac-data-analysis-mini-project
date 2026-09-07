# Clone 정의 v01

## 공통 정규화

- NULL: 문자열 `<NULL>`
- 문자열: 앞뒤 공백 제거, 내부 연속 공백 1개, 소문자화
- 실수: 소수점 6자리 반올림
- 정렬: 검색 `search_seq`, 결과 `result_rank`, 이벤트 `event_at,event_id`, 전이 `transition_id`
- 상대시간: ISO datetime을 파싱해 `event/search time - session_start_at`의 초로 변환하고 소수점 6자리 반올림

## CLONE-1

동일 테이블에서 모든 저장 컬럼이 같은 행의 첫 행 이후 초과 행 수다. `ExperimentAssignment`, `Search`, `SearchFilter`, `SearchResult`, `ActionEvent`, `SearchTransition`, `SessionSummary`에 대해 실제 전체 컬럼 GROUP fingerprint를 계산한다. 현 v02 스키마에 별도 USER/EVENT 테이블은 없으며 각각 ExperimentAssignment/ActionEvent가 대응한다.

## CLONE-2

PK, user/session/search/event/filter/result/pair/run 식별자, seed 및 절대시각을 제외한 payload의 반복이다. 테이블별 중복 payload 그룹, 그룹 소속 행 수, 전체 비율과 최빈 payload를 기록한다. 단일 상태·범주·호텔/객실/순위·이벤트 유형의 자연 충돌이므로 자동 FAIL에 사용하지 않는다.

## CLONE-3 canonical fingerprint

세션별 fingerprint에는 다음을 순서대로 포함한다.

- arm, stratum, intent, treatment policy
- 검색 순번과 세션 시작 대비 상대 초
- 결과 수와 이전 행동
- region, price, option count, query variant, 연속 선호도
- 결과 rank와 세션 내부 첫 등장 순서로 다시 매긴 hotel/room 구조
- 이벤트 유형·상대 초·세션 내부 hotel 대응·mirror flag
- 행동 전이, 회복 여부, inter-arrival
- 검색 수, 0건 경험, 최종 회복, Card H 검색/이벤트 수, outcome

모든 PK/FK 문자열, 원래 hotel/room 키, 사용자명·이메일, 절대 날짜·시각, run ID, seed, DB 생성시각, template cluster ID, 생성용 condition signature는 제외한다. canonical JSON은 키 정렬·공백 없는 UTF-8로 직렬화한 뒤 SHA-256 fingerprint를 만든다.

동일 fingerprint를 가진 서로 다른 세션을 CLONE-3 후보로 하며 후보 세션 수가 0이어야 PASS다. 교정 DB는 control-only이므로 `PAIR_FULL_PATH_IDENTICAL`은 적용 불가이며 향후 paired production QA에서 별도 계산한다.
