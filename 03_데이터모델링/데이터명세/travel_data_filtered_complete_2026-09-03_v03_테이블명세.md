# 2026-09-03 v03 비식별 데이터 테이블 명세

- 기준 DB: `travel_data_filtered_complete_2026-09-03_v03_비식별.sqlite`
- 기준 시점: 2026-09-03 (KST)
- 구성: SQLite 업무 테이블 8개 및 동기화 CSV 8개
- 원천 보존본: `03_데이터모델링/이전버전/데이터셋/2026-09-03_v02/`
- 변경 목적: 확인된 품질 문제를 원천값 수정 없이 테이블 내 분석용 플래그로 표시

## 1. v03 변경 사항

| 테이블 | 추가 컬럼 | 정의 | 값 분포 |
|---|---|---|---|
| `search` | `invalid_stay_date_flag` | `checkout_date < checkin_date`이면 1, 아니면 0 | 1: 9건, 0: 287건 |
| `event` | `click_in_result_flag` | `hotel_click`의 `(search_id, hotel_id)`가 `search_result`에 있으면 1, 없으면 0 | 클릭 1: 229건, 클릭 0: 2건, 비클릭 NULL: 10,201건 |

원천 날짜, 이벤트 키 및 행은 수정하거나 삭제하지 않았다. `booking`, `hotel`, `room`,
`search_filter`, `search_result`, `user` CSV의 내용은 v02와 동일하다.

## 2. 테이블 목록

| 테이블 | 기본키 | 행 수 | 컬럼 수 | CSV |
|---|---|---:|---:|---|
| `booking` | `booking_id` | 36 | 13 | `booking_2026-09-03_v03_비식별.csv` |
| `event` | `event_id` | 10,432 | 15 | `event_2026-09-03_v03_비식별.csv` |
| `hotel` | `hotel_id` | 1,000 | 24 | `hotel_2026-09-03_v03_비식별.csv` |
| `room` | `room_id` | 3,000 | 10 | `room_2026-09-03_v03_비식별.csv` |
| `search` | `search_id` | 296 | 12 | `search_2026-09-03_v03_비식별.csv` |
| `search_filter` | `search_filter_id` | 296 | 9 | `search_filter_2026-09-03_v03_비식별.csv` |
| `search_result` | `search_result_id` | 8,555 | 8 | `search_result_2026-09-03_v03_비식별.csv` |
| `user` | `user_id` | 89 | 6 | `user_2026-09-03_v03_비식별.csv` |

## 3. 컬럼

- `booking`: `booking_id`, `user_id`, `hotel_id`, `room_id`, `booking_status`,
  `booking_amount`, `booking_at`, `checkin_date`, `checkout_date`, `guest_count`,
  `room_count`, `cancellation_deadline`, `data_origin`
- `event`: `event_id`, `session_id`, `event_type`, `event_at`, `hotel_id`,
  `search_filter_id`, `search_id`, `user_id`, `rating`, `session_end_time`,
  `review_completed_at`, `review_text`, `device`, `data_origin`, `click_in_result_flag`
- `hotel`: `hotel_id`, `hotel_name`, `city_name`, `grade`, `hotel_address`, `user_rating`,
  `review_count`, `property_type`, `actual_address`, `actual_city`, `actual_prefecture`,
  `actual_postal_code`, `actual_latitude`, `actual_longitude`, `actual_phone`,
  `actual_star_rating`, `supplier_hotel_code`, `rtx_code`, `agoda_code`, `expedia_code`,
  `top_selling_rank`, `source_last_mapped_at`, `actual_data_sources`, `data_origin`
- `room`: `room_id`, `hotel_id`, `guest_count`, `room_count`, `room_options`,
  `pay_later_flag`, `free_cancel_flag`, `room_price`, `room_type`, `data_origin`
- `search`: `search_id`, `session_id`, `search_time`, `query_text`, `checkin_date`,
  `checkout_date`, `total_result_count`, `sort_option`, `guest_count`, `destination`,
  `data_origin`, `invalid_stay_date_flag`
- `search_filter`: `search_filter_id`, `search_id`, `property_type`, `property_grade`,
  `user_rating_min`, `price`, `amenity_count`, `region`, `data_origin`
- `search_result`: `search_result_id`, `search_id`, `hotel_id`, `room_id`,
  `result_score`, `result_rank`, `price_rank`, `data_origin`
- `user`: `user_id`, `user_name`, `age_group`, `email`, `signup_at`, `data_origin`

## 4. 분석 적용 규칙

1. 숙박일수·체크아웃·숙박기간·숙박 날짜 코호트는
   `invalid_stay_date_flag = 0`만 사용한다.
2. 결과 없음·재검색·클릭 존재 등 검색 행동 분석에서는 해당 검색을 삭제하지 않는다.
3. 노출 기반 CTR·노출-클릭 퍼널·검색결과 호텔 귀속은 `hotel_click` 중
   `click_in_result_flag = 1`만 사용한다.
4. 전체 검색의 클릭·상세진입 존재와 이벤트 흐름에는 플래그 0 클릭도 유지하고
   노출 연결이 확인되지 않았음을 한계로 적는다.
5. 원천 확인 전 날짜 순서 변경, 절댓값 변환, 이벤트 키 보정 또는 결과행 추정 삽입을 금지한다.

## 5. 검증 결과

- SQLite `PRAGMA integrity_check`: `ok`
- CSV와 SQLite 테이블별 행 수: 일치
- 모든 테이블 기본키 NULL·공백·중복: 0건
- `search.invalid_stay_date_flag`: NULL 0건, 값 범위 `{0,1}`, 플래그 1은 9건
- `event.click_in_result_flag`: `hotel_click` 231건은 모두 `{0,1}`, 그 외 10,201건은 NULL
- 검색결과 미연결 클릭: 2건 (`EUDMKVOFRk`, `EglOupSyiI`)
- v02 원천 보존본은 내용 변경 없이 `03_데이터모델링/이전버전/데이터셋/2026-09-03_v02/`로 이동

상세 정책은 `data_quality/data_quality_manifest.json`, AI 적용 규칙은 `AGENTS.md`와
`호텔검색_AI데이터분석지침_20260903_v01_현행본.md`를 따른다.
