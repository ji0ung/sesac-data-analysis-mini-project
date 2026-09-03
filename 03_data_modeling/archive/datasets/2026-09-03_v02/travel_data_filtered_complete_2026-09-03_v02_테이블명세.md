# 2026-09-03 v02 비식별 데이터 테이블 명세

- 기준 파일: `travel_data_filtered_complete_2026-09-03_v02_비식별.sqlite`
- 원천: 로컬 최신 `travel_data_filtered_complete_2026-09-01_v01_원본.sqlite`의 일관된 SQLite 백업
- 기준 시점: 2026-09-03 (KST)
- 데이터 범위: SQLite의 8개 업무 테이블 전체
- 행 단위: 각 테이블의 선언된 기본키 기준

## 1. 변환 규칙

- 필터·조인·중복 제거: 적용하지 않음. 최신 SQLite의 업무 테이블을 전량 추출함.
- `user.user_name`: `사용자_` + `SHA-256(user_id)` 앞 8자리로 치환함.
- `user.email`: 원래 값이 있으면 `masked_` + `SHA-256(user_id)` 앞 12자리 + `@example.invalid`로 치환하고, 원래 공란은 공란으로 유지함.
- 다른 컬럼: 값 변환 없이 유지함.
- CSV: UTF-8 BOM, 전체 필드 따옴표, LF 줄바꿈으로 저장함.

## 2. 원천 정합성 참고

- 로컬 기존 `user` CSV: 169행
- 최신 SQLite의 `user` 테이블: 89행
- 두 원천의 행 수가 달라 최신 SQLite를 단일 기준으로 채택하고 CSV를 다시 추출함.

## 3. 테이블 목록

| 테이블 | 기본 행 단위 | 행 수 | 컬럼 수 | CSV 파일 |
|---|---|---:|---:|---|
| `booking` | `booking_id` | 36 | 13 | `booking_2026-09-03_v02_비식별.csv` |
| `event` | `event_id` | 10,432 | 14 | `event_2026-09-03_v02_비식별.csv` |
| `hotel` | `hotel_id` | 1,000 | 24 | `hotel_2026-09-03_v02_비식별.csv` |
| `room` | `room_id` | 3,000 | 10 | `room_2026-09-03_v02_비식별.csv` |
| `search` | `search_id` | 296 | 11 | `search_2026-09-03_v02_비식별.csv` |
| `search_filter` | `search_filter_id` | 296 | 9 | `search_filter_2026-09-03_v02_비식별.csv` |
| `search_result` | `search_result_id` | 8,555 | 8 | `search_result_2026-09-03_v02_비식별.csv` |
| `user` | `user_id` | 89 | 6 | `user_2026-09-03_v02_비식별.csv` |

## 4. 컬럼 및 결측치

### booking

- 행 수: 36
- 기본 행 단위: `booking_id`
- 기본키 중복 그룹: 0

| 컬럼 | NULL 수 |
|---|---:|
| `booking_id` | 0 |
| `user_id` | 0 |
| `hotel_id` | 0 |
| `room_id` | 0 |
| `booking_status` | 0 |
| `booking_amount` | 0 |
| `booking_at` | 0 |
| `checkin_date` | 0 |
| `checkout_date` | 0 |
| `guest_count` | 0 |
| `room_count` | 0 |
| `cancellation_deadline` | 0 |
| `data_origin` | 0 |

### event

- 행 수: 10,432
- 기본 행 단위: `event_id`
- 기본키 중복 그룹: 0

| 컬럼 | NULL 수 |
|---|---:|
| `event_id` | 0 |
| `session_id` | 0 |
| `event_type` | 0 |
| `event_at` | 0 |
| `hotel_id` | 647 |
| `search_filter_id` | 158 |
| `search_id` | 158 |
| `user_id` | 0 |
| `rating` | 10,280 |
| `session_end_time` | 1,987 |
| `review_completed_at` | 10,432 |
| `review_text` | 10,432 |
| `device` | 9,688 |
| `data_origin` | 0 |

### hotel

- 행 수: 1,000
- 기본 행 단위: `hotel_id`
- 기본키 중복 그룹: 0

| 컬럼 | NULL 수 |
|---|---:|
| `hotel_id` | 0 |
| `hotel_name` | 0 |
| `city_name` | 0 |
| `grade` | 0 |
| `hotel_address` | 0 |
| `user_rating` | 0 |
| `review_count` | 0 |
| `property_type` | 0 |
| `actual_address` | 509 |
| `actual_city` | 509 |
| `actual_prefecture` | 678 |
| `actual_postal_code` | 678 |
| `actual_latitude` | 509 |
| `actual_longitude` | 509 |
| `actual_phone` | 520 |
| `actual_star_rating` | 688 |
| `supplier_hotel_code` | 552 |
| `rtx_code` | 678 |
| `agoda_code` | 695 |
| `expedia_code` | 831 |
| `top_selling_rank` | 881 |
| `source_last_mapped_at` | 552 |
| `actual_data_sources` | 509 |
| `data_origin` | 0 |

### room

- 행 수: 3,000
- 기본 행 단위: `room_id`
- 기본키 중복 그룹: 0

| 컬럼 | NULL 수 |
|---|---:|
| `room_id` | 0 |
| `hotel_id` | 0 |
| `guest_count` | 0 |
| `room_count` | 0 |
| `room_options` | 0 |
| `pay_later_flag` | 0 |
| `free_cancel_flag` | 0 |
| `room_price` | 0 |
| `room_type` | 0 |
| `data_origin` | 0 |

### search

- 행 수: 296
- 기본 행 단위: `search_id`
- 기본키 중복 그룹: 0

| 컬럼 | NULL 수 |
|---|---:|
| `search_id` | 0 |
| `session_id` | 0 |
| `search_time` | 0 |
| `query_text` | 108 |
| `checkin_date` | 0 |
| `checkout_date` | 0 |
| `total_result_count` | 0 |
| `sort_option` | 0 |
| `guest_count` | 0 |
| `destination` | 45 |
| `data_origin` | 0 |

### search_filter

- 행 수: 296
- 기본 행 단위: `search_filter_id`
- 기본키 중복 그룹: 0

| 컬럼 | NULL 수 |
|---|---:|
| `search_filter_id` | 0 |
| `search_id` | 0 |
| `property_type` | 296 |
| `property_grade` | 296 |
| `user_rating_min` | 144 |
| `price` | 150 |
| `amenity_count` | 0 |
| `region` | 45 |
| `data_origin` | 0 |

### search_result

- 행 수: 8,555
- 기본 행 단위: `search_result_id`
- 기본키 중복 그룹: 0

| 컬럼 | NULL 수 |
|---|---:|
| `search_result_id` | 0 |
| `search_id` | 0 |
| `hotel_id` | 0 |
| `room_id` | 0 |
| `result_score` | 0 |
| `result_rank` | 0 |
| `price_rank` | 0 |
| `data_origin` | 0 |

### user

- 행 수: 89
- 기본 행 단위: `user_id`
- 기본키 중복 그룹: 0

| 컬럼 | NULL 수 |
|---|---:|
| `user_id` | 0 |
| `user_name` | 0 |
| `age_group` | 48 |
| `email` | 0 |
| `signup_at` | 0 |
| `data_origin` | 0 |

## 5. 검증 결과

- SQLite 무결성 검사: `ok`
- 모든 업무 테이블의 선언 기본키 중복 그룹: 0
- 점검한 테이블 간 고아 참조: 0
- SQLite와 CSV의 테이블별 행 수 차이: 0
- 비식별 처리 전 비표준 사용자명: 89건
- 비식별 처리 전 일반 형식의 비공란 이메일: 41건
- 비식별 처리 후 사용자명 규칙 위반: 0건
- 비식별 처리 후 이메일 규칙 위반: 0건

## 6. 제한사항

- 이 버전은 최신 SQLite를 기준으로 재추출한 비식별 스냅샷이며, 기존 CSV와의 행 단위 병합은 수행하지 않음.
- `session_id` 전용 테이블이 없어 세션 참조 무결성은 이벤트 내부의 값 존재 여부까지만 확인 가능함.
- 비식별 토큰은 동일 `user_id`에 대해 재현 가능하지만 원래 사용자명·이메일 복원에는 사용하지 않음.
- 분석 지표는 이 스냅샷의 행 수와 기준으로 다시 계산해야 함.
