# 02 Generator Dry-run Gate Report

## 최종 판정: PASS

PROMPT 1 PASS를 선행조건으로 확인했다. 전체 10,000명은 생성하지 않았으며, 실행기는 200명을 초과하는 요청을 거부한다. 이번 산출물은 100개 pair profile에서 만든 control 100명 + treatment 100명의 **합성 dry-run 시나리오**다. 실제 A/B 실험 결과가 아니다.

## 실행 잠금

| 항목 | 값 |
|---|---|
| run_id | `dryrun_200_seed_20260904` |
| seed | 20260904 |
| effect level | base — 시나리오 가정 |
| 원본 v03 SHA-256 | `2f5bd2f73b02b103bb6107ee79aa109cf77afc6f5aecdf82b10c87c95a0bef80` |
| 참조 1,000명 SHA-256 | `7d449fab6847730be38fe46ebb6bd6a5b31690cdf38cf4bdbadeaa75edd1ae04` |
| generator SHA-256 | `fe2844c270f334478b1e289d9f168e89907075d03aa9478b977e2194146a107f` |
| config SHA-256 | `7c365dc958ac9fa630b1e6b5b9d7cb439526067ab149d609e8b511f643a51bd9` |
| config schema SHA-256 | `1343333f53c6112a5597688c79a4df9e1f93b9fb5ad727c8e215599ea0400755` |
| DB schema SHA-256 | `a0c500fc05a2c8010dc25676d37bfd86c94dda2e2ea62cd7e435602d8fa25aea` |
| probability parameter SHA-256 | `ced8714f2ec3f650506eee574214f00d14ad103493caa9c1c8bb7b69427e4fef` |
| dry-run DB SHA-256 | `7f46d72acd844067fb9267ba266e32f21567ebf36dea1bcfd383e2b38fb214de` |
| dry-run DB 크기 | 1,056,768 bytes / 1.056768 MB / 1.0078125 MiB |
| package versions | Python 3.13.1; SQLite 3.45.3; PyYAML 6.0.3; jsonschema 4.26.0; openpyxl 3.1.5 |

코드/config/schema/source/package 버전과 run별로 추출한 Beta/Dirichlet 확률은 `SimulationRun` 및 `_generation_metadata`에 기록했다.

## dry-run 행 수

| 테이블 | 행 수 | grain |
|---|---:|---|
| SimulationRun | 1 | run_id |
| UserProfile | 200 | user_id |
| ExperimentAssignment | 200 | assignment_id; user 1:1 |
| Search | 296 | search_id |
| SearchResult | 2,118 | search_result_id |
| ActionEvent | 3,062 | action_event_id |
| SearchTransition | 96 | transition_id |
| SessionSummary | 200 | session_id; user 1:1 |
| _generation_metadata | 16 | key |

BOOKING 테이블과 booking 이벤트는 생성하지 않았다.

## pair 및 사전 균형

- pair profile: 100개. 각 pair에 control/treatment가 정확히 1명씩 있다.
- 군별 사용자: control 100, treatment 100.
- 같은 pair의 age_group, destination, filter_state_segment, intent_segment, source template은 동일하다.
- intent별 control/treatment 수가 모두 동일하다: budget 20/20, condition keeper 10/10, location 22/22, option 22/22, query 16/16, quick solver 10/10.
- SG1~SG4는 `SessionSummary`에만 있는 사후 결과 라벨이며 ExperimentAssignment에는 없다.

## 시나리오 결과 표기

아래 수치는 실제 관측이나 실제 A/B 성과가 아니라 seed와 base 효과 가정에서 나온 dry-run 논리검사용 결과다.

| arm | SG1 | SG2 | SG3 | SG4 |
|---|---:|---:|---:|---:|
| control | 37 | 13 | 6 | 44 |
| treatment | 37 | 13 | 7 | 43 |

base 효과값은 recovery +6%p, detail +5%p, repeat -6%p의 **설정 가정**이다. 효과값을 관측 추정치로 사용하지 않았다. 원본 후험분포에서 이번 run의 확률을 다시 추출했으며, 지속 실패 4.7%(원본 2/43)와 검색어 수정 상세진입 3/10은 합성 n으로 신뢰구간을 축소하지 않는다.

## 논리·복제 QA

| 검사 | 결과 |
|---|---:|
| integrity_check | ok |
| foreign_key_check 위반 | 0 |
| PK NULL/중복 | 0 |
| User–Assignment–Summary 1:1 위반 | 0 |
| 결과 수 ≠ SearchResult 행 수 | 0 |
| 한 검색 내 호텔 중복 노출 | 0 |
| 노출 전 click/detail | 0 |
| click 전 detail | 0 |
| 미회복 상태의 상세진입 | 0 |
| 검색/전이/세션 시각 역순 | 0 |
| BOOKING/booking event | 0 |
| 원본과 exact timestamp row clone | 0 |
| 원본과 exact session path clone | 0 |
| template별 최대 pair 사용 | 1/100=1.0% |
| config template 상한 | 5.0% |

원본 세션을 그대로 복제하지 않도록 원본 검색 3회 이상 세션만 템플릿 후보로 허용하고, 새 시간·후험확률·전이 결과를 생성했다. 연속형 `result_score`만 경계 보존 jitter를 적용했다. PK, 범주, 결과 수에는 jitter를 적용하지 않았다.

## 시간 생성

- 0건→다음 검색 간격은 원본 140개 양수화 간격에 적합한 lognormal에서 추출한다.
- 1~249초 경계를 적용하며 모든 `SearchTransition.interarrival_seconds`는 양수다.
- session_start ≤ search_submit ≤ impression < click < detail < session_end를 강제한다.
- 결과가 회복되지 않은 전이에는 detail을 만들지 않는다.

## 테스트

Python `unittest` 18개를 실행해 전부 PASS했다.

- PK/FK, 1:1, 시간순서, 노출 전 선택 금지, 회복 전 상세진입 금지
- pair 사전 속성 및 군 균형
- 결과 수–노출행 일치
- BOOKING 금지 및 SG 사후 라벨 분리
- exact row/session clone 및 template concentration
- config schema, 10,000명 실행 차단, 덮어쓰기 방지
- 동일 seed의 SQLite SHA-256 재현성

최초 dry-run에서 exact session path 4건이 검출되어 해당 실패 DB를 승인 산출물로 남기지 않고 제거했다. 템플릿 후보 규칙을 수정한 뒤 새 파일명 경로에 재생성·재검수했으며 최종 위반은 0건이다.

## 원본 불변성

| 입력 | 실행 전후 bytes | 실행 전후 mtime_ns | 실행 전후 SHA-256 | 결과 |
|---|---:|---:|---|---|
| 실제 관측 v03 | 6,447,104 | 1788716585861624400 | `2f5bd2f73b02b103bb6107ee79aa109cf77afc6f5aecdf82b10c87c95a0bef80` | 동일 |
| 승인 1,000명 참조 DB | 154,738,688 | 1788603037749345700 | `7d449fab6847730be38fe46ebb6bd6a5b31690cdf38cf4bdbadeaa75edd1ae04` | 동일 |

두 입력은 SQLite URI `mode=ro` 및 `PRAGMA query_only=ON`으로 열었다. 출력 경로가 존재하면 `FileExistsError`가 발생하며, 부분 실패 파일은 최종 파일명으로 승격하지 않는다.

## 다음 단계 제한

- 이 PASS는 200명 dry-run 생성기와 계약의 논리 검증에만 해당한다.
- 전체 10,000명 생성은 여전히 금지 상태다.
- conservative/base/optimistic는 관측값이 아닌 시나리오 가정이다.
- BOOKING은 승인 후 별도 모듈에서만 추가할 수 있다.
