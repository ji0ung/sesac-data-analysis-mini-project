# 1,000명 기준 DB 분석 동등성 감사

## 판정

`STEP 2.7=HOLD — TEMPORAL_VALUE_CHANGED_AND_REFERENCE_INTERNAL_CLONE_VIOLATION`

후보 DB의 파일·무결성·행 수·주요 KPI·NULL 위치는 사전값 및 기존 승인 DB와 일치한다. 그러나 `search.search_time` 6,900행 전부의 숫자 시간값이 기존 승인 DB와 다르고, 후보 내부의 ID·절대시간 정규화 완전 경로 clone이 935건이다. 둘 다 PASS 조건을 위반한다.

## 물리 구조

| 항목 | 기존 | 후보 |
|---|---:|---:|
| bytes | 154,738,688 | 46,891,008 |
| SHA-256 | `7d449fab6847730be38fe46ebb6bd6a5b31690cdf38cf4bdbadeaa75edd1ae04` | `9120561ee85705141a92eae74c5015fb2c9a20f0c8d1f6df4d99893952fd1e9f` |
| page size | 4,096 | 16,384 |
| page count | 37,778 | 2,862 |
| freelist | 12,523 | 0 |
| integrity / quick | ok / ok | ok / ok |
| `_generation_metadata` | 있음 | 없음 |
| 사용자 정의 index | 4 | 0 |

후보의 metadata·index·PK 제약·`data_origin` 제거 및 16K page는 경량화 이력과 일치한다. 다만 정적 분석 전용이며 DB 자체의 PK 무결성 강제 수단은 제거됐다.

## 전수 데이터 비교

행 수와 business key 집합은 8개 업무 테이블에서 모두 같다: USER 1,000, HOTEL 1,000, ROOM 3,000, SEARCH 6,900, SEARCH_FILTER 6,900, SEARCH_RESULT 198,128, EVENT 238,851, BOOKING 0.

`signup_at`과 `event_at`/`session_end_time`은 후행 ` KST` 제거 후 동일하다. 반면 `search.search_time`은 정규화 후에도 6,900/6,900행이 다르다. 예: `SYN_Q0001_001`은 기존 `2027-01-01 00:05:23 KST`, 후보 `2027-01-01 00:01:00`이다. 이는 허용 가능한 텍스트 최적화가 아니라 숫자 시간값 변경이며 `UNEXPLAINED_DIFFERENCE`로 분류한다.

## NULL5

경량화 이력에서 NULL5는 행 5건이 아니라 전부 NULL인 5개 컬럼으로 확인됐다: `event.review_completed_at`, `event.review_text`, `search_filter.property_type`, `search_filter.property_grade`, `user.age_group`. 두 DB에서 NULL 수와 business-key 위치가 모두 일치하며 빈 문자열·0·문자열 `NULL`로 치환되지 않았다.

## 핵심 KPI

동일 SQL의 분자/분모는 모두 동일했다.

| 지표 | 기존 | 후보 |
|---|---:|---:|
| 검색 0건률 | 3,434/6,900 = 49.7681% | 동일 |
| 결과 존재 검색 | 3,466/6,900 | 동일 |
| 0건 후 후속검색 | 3,271/3,434 = 95.2533% | 동일 |
| 즉시 회복 | 558/3,271 = 17.0590% | 동일 |
| 최종 회복 | 488/651 = 74.9616% | 동일 |
| Card H-SEARCH | 680/3,466 = 19.6192% | 동일 |
| Card H-EVENT | 2,580행 | 동일 |
| BOOKING | 0 | 동일 |

집계 KPI 일치는 숫자 시간값 변경을 상쇄하지 않는다. 시간 간격·검색/이벤트 정렬을 사용하는 분석은 동등하다고 승인할 수 없다.

## clone 및 다양성

8개 테이블의 전체 물리행 중복 excess는 모두 0이다. 그러나 ID와 절대 시작시각을 제외하고 호텔·객실 ID를 세션 내부 등장순서로 정규화한 뒤, 상대 검색시각·검색조건·필터·결과 순위·호텔·객실·이벤트 유형·상대 이벤트시각을 포함한 완전 경로 fingerprint에서 42개 중복 그룹, 977개 관련 세션, 935개 clone excess가 검출됐다. 요구 기준 0건을 위반한다.

## 런타임 의존성

`02_base_config_prod_v02.yaml`이 기존 DB 경로와 SHA를 직접 보유하고 생성기가 config의 참조 DB를 검증하므로 경우 B(런타임 의존)다. 후보가 게이트를 통과하지 못했으므로 rebased code/config를 만들거나 테스트·교정을 재실행하지 않았다. 기존 승인 체인은 그대로 보존하며 신규 manifest는 실행 불허 HOLD 기록이다.

## 불변성과 출력 폴더

지정된 기존 승인 산출물 10개의 SHA는 모두 제공 승인값과 일치한다. `03_10k_ab_generation_v02_approved`는 파일 0개, 하위 폴더 0개이며 본 단계 산출물을 저장하지 않았다. 10,000명 DB와 production mode는 실행하지 않았다.
