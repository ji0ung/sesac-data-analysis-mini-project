# newref_v01 생성 시스템 준비성 보고서

## 판정

`STEP 2.9=PASS`

본 단계는 개발·정적검사·200명 smoke test만 수행했다. 생성 결과는 관측 A/B가 아니라 합성 시나리오이며 10,000명 production은 실행하지 않았다.

## 권위와 입력

신규 기준 DB SHA-256 `9120561ee85705141a92eae74c5015fb2c9a20f0c8d1f6df4d99893952fd1e9f`와 STEP 2.8 승인 입력 4개의 SHA가 모두 일치했다. treatment는 교수 판단회신을 우선 적용해 가격 범위 확대·옵션 수 감소, 지역 변경, 단계형 회복, 보조 검색어 변경만 구현했다. 평점 하향과 구체 편의시설 treatment 세분화는 제외했다.

## 생성 모형

5,000개 pair profile을 위한 공통 사전 random stream과 arm별 결과·시간 stream을 분리했다. control은 신규 기준의 0건·후속검색·즉시회복·Card H 확률 및 세션 길이/시간 분포를 확률적으로 사용한다. treatment는 안내 이후 행동 전략 확률에만 개입하며 결과를 quota로 덮어쓰지 않는다. `source_session_id`는 유효 계보값만 저장하고 기준 행·경로는 읽거나 복제하지 않는다.

전략별 Beta(1,1) smoothing은 지역 변경 Beta(11,15), 검색어 변경 Beta(4,8), 조건 완화 Beta(12,31), 동일 조건 Beta(1,54), 조건 강화 Beta(1,11)이다. expected는 후험평균, conservative/optimistic은 후험평균 ±1 후험 표준편차를 [0.001,0.999]로 제한해 산출한다. 원시 n과 후험 파라미터·사용 확률은 `_generation_metadata`에 기록한다.

## 시간 모형

양수 검색 간격은 기준 lognormal μ=2.899725, σ=1.144826에서 새로 draw하고 0.7797%의 동시 검색을 별도 mixture로 둔다. 상세진입 시간과 반복 이벤트 간격도 별도 stream에서 새로 생성한다. 마지막 이벤트 이후 세션 종료시각을 계산하므로 음수 간격·검색 역전·종료 후 이벤트를 허용하지 않는다. 기준 delay vector는 재사용하지 않는다. STEP 2.10에서는 긴 꼬리 혼합과 winsorization 경계를 다중 seed로 교정한다.

## Smoke test

seed `2026090711`, USER 200명, control 100명, treatment 100명, pair 100개를 `tests` 아래에 생성했다. 검색은 547건이며 0건 330/547, 후속검색 286/330, 즉시회복 56/286, 최종회복 55/99, Card H-SEARCH 47/217, Card H-EVENT 195행이다. 소표본 KPI는 합격 quota로 사용하지 않았다.

논리 PK/FK, SEARCH–FILTER 1:1, 결과 수, 호텔 중복, 이벤트 연결, 시간순서 및 BOOKING 검사는 위반 0건이다. arm 내부 완전 경로 clone excess는 control 0, treatment 0이며 기준 세션·delay vector exact 복제도 0이다. 전체 arm 간 완전 경로 충돌 7건은 공통 사전경로 또는 비노출 pair 가능성을 포함하므로 arm 내부 clone 실패로 처리하지 않았다.

자동 테스트 21개가 모두 통과했다. 동일 seed 결정성, 다른 seed 변화, config schema, pair 사전속성, leakage, source lineage, metrics, clone detector, 201명 거부, calibration/production 거부, 출력경로 및 덮어쓰기 방지를 확인했다.

## 안전 상태

`unit_test`는 40명, `smoke_test`는 200명으로 제한된다. `calibration`은 STEP 2.10 승인 전 차단되고 `production`은 승인 manifest의 `execution_authorized=true` 없이는 차단된다. candidate manifest는 STEP 2.10 진입 후보이며 production 실행 승인서가 아니다.

production 출력 폴더는 파일 0개, 하위 폴더 0개다. 기존 파일은 수정하지 않았고 10,000명 DB를 생성하지 않았다.
