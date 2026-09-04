# 분석용 데이터 품질 플래그 처리 규칙

이 디렉터리는 `03_데이터모델링/현행데이터/`의 `2026-09-03_v03` 데이터에 직접 포함된 품질 플래그의
정의, 검증 및 재생성 방법을 관리한다. 원천 v02는 수정하지 않고 보관했으며, v03의
`search`와 `event`를 읽으면 별도 조인 없이 플래그를 확인할 수 있다.

## 제공 파일

- `data_quality_manifest.json`: 플래그 정의, 적용 범위, 제외·유지 정책
- `analysis_guardrails.sql`: v03 SQLite의 직접 포함 플래그를 이용한 세션 범위 TEMP VIEW
- `build_quality_snapshot_v03.py`: v02 보존본에서 v03 CSV·SQLite를 재생성하고 검증

## 품질 계약

### 숙박일 역전

```text
grain: search_id당 1행
invalid_stay_date_flag = 1 if checkout_date < checkin_date else 0
stay_nights = checkout_date - checkin_date
```

- 현재 결과: 296개 검색 중 9개(3.04%)가 비정상이며 모두 `stay_nights = -16`이다.
- 숙박일수·체크아웃·숙박기간·숙박 날짜 코호트 지표: 플래그 1 제외
- 검색 결과 없음·재검색·클릭 존재 같은 행동 지표: 행 유지 가능
- 체크인만 쓰는 리드타임: 체크아웃이 불필요하다는 지표 계약이 있을 때만 유지하고 명시
- 원천 확인 전 날짜 대체, 순서 교환, 절댓값 변환 금지

### 검색결과에 없는 호텔 클릭

```text
grain: hotel_click event_id당 1행
calculation: EXISTS search_result on (search_id, hotel_id)
click_in_result_flag = 1 if pair exists else 0
click_in_result_flag = NULL for non-hotel_click events
```

- 현재 결과: 231개 클릭 중 2개(0.87%)가 검색결과와 연결되지 않는다.
- 노출 기반 CTR·노출-클릭 퍼널·검색결과 호텔 귀속: 플래그 0 제외
- 클릭/상세진입의 존재를 보는 행동 분석: 이벤트 유지, 노출 연결 한계 명시
- 원천 확인 전 `search_id` 또는 `hotel_id` 보정 금지

## 재생성

저장소 루트를 현재 디렉터리로 두고 실행한다.

```text
python 03_데이터모델링/데이터품질/build_quality_snapshot_v03.py
```

스크립트는 보관된 v02를 읽어 루트에 v03 CSV·SQLite를 만든다. 알려진 이슈 건수나 ID가
달라지면 오류로 종료하므로 데이터 버전이 바뀐 경우 규칙과 기대값을 먼저 검토해야 한다.
