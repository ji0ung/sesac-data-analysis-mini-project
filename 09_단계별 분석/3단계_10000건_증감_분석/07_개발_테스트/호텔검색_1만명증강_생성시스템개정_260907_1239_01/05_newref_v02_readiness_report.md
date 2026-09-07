# STEP 2.9-R readiness

## 판정

STEP 2.9-R=PASS

이 묶음은 합성 시나리오 생성 시스템의 개정·smoke 검수 결과이며 실제 A/B 관측 결과가 아니다. 30-seed calibration, production mode, production seed, 10,000명 생성은 실행하지 않았다.

## 원인과 수정

v01은 세션 길이를 terminal outcome보다 먼저 독립 제한하여 후속검색과 최종회복 상태가 잘렸고, 일부 config 값은 읽힌 뒤 검색별 결과 draw에 의해 사실상 덮였다. v02는 terminal outcome과 최소 검색 수를 먼저 정한 뒤 조건부 길이를 선택한다. 후속검색·즉시회복·최종회복 값은 각각 실제 Bernoulli 분기와 생성행에 직접 연결된다.

시간은 body lognormal과 rare tail lognormal의 mixture이다. 음수·역전·세션 종료 후 이벤트를 금지하고 최대값은 기준 자료의 51,304초로 제한한다. Card H는 결과 존재 고유 검색별 rank-1 hotel_detail_view Bernoulli와 반복 이벤트 수를 분리한다.

CLONE-A/B/C와 DIVERSITY-PATH를 분리했다. 종전 arm별 842는 필수 business fields를 생략한 추상 경로 signature의 반복이므로 새 정의상 DIVERSITY-PATH이며 CLONE-B로 승인할 수 없다.

## 검증 결과

- 입력 승인 SHA: 23/23 일치
- 자동 테스트: 42 PASS, 0 FAIL
- smoke: USER 200, control 100, treatment 100, pair 100
- pair 사전속성 불일치: 0; 최대 절대 SMD: 0
- integrity/FK/관계/시간 위반: 0; BOOKING: 0
- CLONE-A/B/C: 0/0/0
- 추상 경로 반복: control 39세션, treatment 66세션(허용, 다양성 지표)
- production seed 사용: 0
- calibration run: 0
- production run: 0
- 10,000명 DB: 0

다음 단계에서는 이 candidate 묶음 해시를 고정한 뒤 PROMPT 2.10-R2 calibration만 실행할 수 있다. Production 실행은 아직 승인되지 않았다.
