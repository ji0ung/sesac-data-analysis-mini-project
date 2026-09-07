# STEP 2.10-R 다중 seed 교정 보고서

## 판정

`STEP 2.10-R=HOLD — CONTROL_FIDELITY_AND_ARM_INTERNAL_CLONE_FAILURE`

30개 고정 seed, 총 60,000명의 합성 A/B calibration을 완료했다. 이는 실제 서비스 A/B나 관측 인과효과가 아니다. production seed와 production mode는 사용하지 않았다.

## 대조군 재현성

| 지표 | 기준 | 20 seed 평균 | 범위 | 통과 seed |
|---|---:|---:|---:|---:|
| 검색 0건률 | 49.7681% | 62.5308% | 59.5353~65.6591% | 0/20 |
| 0건 후 후속검색 | 95.2533% | 80.8922% | 79.0898~82.3204% | 0/20 |
| 즉시 회복 | 17.0590% | 17.2865% | 16.1339~18.9313% | 18/20 |
| 최종 회복 | 74.9616% | 41.0888% | 37.7289~44.8669% | 0/20 |
| Card H-SEARCH | 19.6192% | 19.0726% | 17.3733~20.7627% | 16/20 |

검색 0건·후속검색·최종회복은 허용구간 확대 대상으로 볼 수 없는 큰 구조적 이탈이다. generator의 세션 길이 생성에서 길이 1 확률이 고정되어 `zero_followup_probability` 설정이 실제 후속검색을 제어하지 못하고, `final_recovery_probability`도 세션 종료 결과에 직접 사용되지 않는다. 허용 가능한 config 항목만으로는 기준 95.25%와 74.96%를 재현할 수 없어 교정 cycle은 0회로 종료했다.

## Pair와 treatment

30개 seed 모두 pair 1,000개, 사전 속성 불일치 0, 최대 절대 SMD 0, treatment leakage 0이다. expected treatment의 평균 최종회복률은 58.9280%로 control보다 높고 SG3 증가·SG4 감소 방향은 성립했다. scenario별 treatment 최종회복은 conservative 50.1871% ≤ expected 58.9280% ≤ optimistic 65.3635%로 단조적이다. Card H는 각각 18.4928%, 19.6393%, 19.4028%로 실현값 단조성을 강제하지 않았으며 심각한 악화는 관측되지 않았다.

## 시간과 clone

모든 DB의 PK/FK·관계·시간 역전 위반은 0이다. expected control 검색 간격 평균의 seed 평균은 34.247초, 중앙값 평균은 17.85초, p90 78.51초, p95 117.61초다. 기준의 긴 꼬리 평균 263.122초는 재현되지 않았으나 중앙·상위 분위수는 근접했다. 긴 꼬리 mixture가 generator에 구현되지 않은 별도 개정사항이다.

기준 DB exact session 및 exact delay-vector clone은 0이다. 그러나 동일 arm 내부 완전 경로 clone excess가 expected 20개 seed 합계에서 control 842, treatment 842건 발생했다. 1,000명/arm 규모에서 완전 경로 충돌 재생성 로직이 없으므로 mandatory-zero 기준을 위반했다.

## 고차·희소 분석

가격 유무, 옵션 0/1/2+, 지역, 검색 순번, 이전 0건 수, 세션 길이 결합 셀을 전수 집계하고 n<30을 희소 셀로 표시했다. 강제 셀 일치는 적용하지 않았으며 Beta(1,1) partial pooling 후보로 기록했다. 지속 실패·검색어/지역 변경·조건 완화·동일 조건·가격·옵션 세그먼트의 pooled n과 production arm 예상 n은 별도 workbook에 저장했다.

## 해석 안전성

본 데이터는 합성 A/B 시뮬레이션이다. treatment 효과는 실제 서비스 실험에서 관측된 인과효과가 아니다. treatment 확률은 소표본 관측값과 Beta smoothing을 이용한 시나리오다. 10,000명 확대는 실제 정보량이 10배 증가했다는 뜻이 아니며 기준 DB 편향이 남을 수 있다. 희소 구간은 모형 가정 아래의 정밀도이며 실제 의사결정에는 실서비스 A/B가 필요하다.

production config·다양성 최종 threshold·빈 production 폴더는 승인하지 않았다. generator를 별도 신규 버전으로 개정한 뒤 STEP 2.9 상당의 테스트와 STEP 2.10 calibration을 다시 수행해야 한다.
