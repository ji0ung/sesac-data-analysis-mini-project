# Notion 기획서 기준 CSV 칼럼 명세

기준 문서: [기획서 종합본 (2차)](https://spiced-pentagon-516.notion.site/2-3ca95db60c68804f9413c8cc1d80acd6)

## HOTEL

한 행은 호텔의 객실 유형 1개다. 동일 `hotel_id`가 여러 행에 나타날 수 있으며 PK는 `room_id`다.

`room_id, hotel_id, hotel_name, city_name, grade, latitude, longitude, hotel_address, user_rating, property_type, review_count, guest_count, room_count, hotel_option, pay_later_flag, free_cancel_flag, RoomType, SalePrice`

현재 수집하지 않는 위도·경도·주소는 빈 값이다. `room_count`는 현재 남은 객실 수, `SalePrice`는 호텔 기준 가격과 객실 가격 조정값을 합한 대표 가격이다.

## SEARCH

`search_id, session_id, search_time, query_text, checkin_date, checkout_date, total_result_count, sort_option, guest_count, destination`

## SEARCH_FILTER

`search_filter_id, search_id, property_type, property_grade, user_rating_min, price, amenity_count, transportation, region`

## USER

`user_id, user_name, age, email, signup_at`

현재 사용자 화면에서 이메일을 수집하지 않으므로 `email`은 빈 값이다. 이름은 별명 사용이 가능하다.

## EVENT

`event_id, session_id, event_type, event_at, hotel_id, search_filter_id, search_id, behavior_unique_id, user_id, event_properties_json`

Notion의 핵심 칼럼과 함께 분석에 필요한 세부 JSON을 보존한다.

## REVIEW

`review_id, hotel_id, user_id, rating, review_created_at, review_text, review_photo_url`

## SEARCH_RESULT

한 행은 특정 검색에서 호텔 1개가 노출된 결과다. `hotel_impression` 이벤트를 정규화해 생성한다.

`search_result_id, search_id, hotel_id, result_rank, price_rank, free_cancel_flag, pay_later_flag, engine_score`

현재 검색 엔진은 별도의 추천점수를 계산하지 않으므로 `engine_score`는 빈 값이다. 존재하지 않는 점수를 임의 생성하지 않는다.

## BOOKING

`booking_id, user_id, hotel_id, booking_status, booking_amount, booking_at, checkin_date, checkout_date, guest_count, room_count`

## JOIN 주의사항

- HOTEL과 EVENT/REVIEW/BOOKING을 직접 `hotel_id`로 연결하면 객실 유형 수만큼 행이 늘어날 수 있다.
- 호텔 단위 분석에서는 HOTEL을 `hotel_id`로 중복 제거하거나 먼저 호텔 단위로 집계한다.
- SEARCH와 SEARCH_FILTER는 `search_id` 기준 1:0..1 관계다.
- SEARCH_RESULT는 SEARCH와 HOTEL 사이의 노출 사실과 순위를 보존한다.

## ID 길이 규칙

- 신규 사용자·세션·검색·이벤트·예약 ID는 종류 문자 1자와 영숫자 난수 9자의 총 10자 형식이다.
- 호텔 `H0001`, 객실 `R0001_1`, 리뷰 `V00011`처럼 기준 데이터 ID는 순번 기반의 짧은 형식을 쓴다.
- 검색필터는 검색 ID 앞에 `F`, 검색결과는 이벤트 ID 앞에 `X`를 붙여 원본 연결을 쉽게 확인한다.
- 기존 저장 데이터의 긴 ID는 관계 손상을 막기 위해 그대로 유지한다.
