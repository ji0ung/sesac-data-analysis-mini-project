-- 01_recompute.sql
-- Contract: SQLite 3.x; source DB is opened externally with URI mode=ro.
-- Mandatory session setting:
PRAGMA query_only = ON;

-- Q00. File integrity (expected single row: ok)
PRAGMA integrity_check;

-- Q01. Physical tables and declared PK/FK metadata.
SELECT name AS table_name, sql
FROM sqlite_master
WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
ORDER BY name;
-- Run PRAGMA table_info(<table>) and PRAGMA foreign_key_list(<table>) for every Q01 table.

-- Q02. Core row counts and grains.
SELECT 'user' AS object_name, 'user_id' AS grain, COUNT(*) AS row_count,
       COUNT(DISTINCT user_id) AS distinct_grain_count FROM user
UNION ALL SELECT 'search','search_id',COUNT(*),COUNT(DISTINCT search_id) FROM search
UNION ALL SELECT 'search_session','session_id',COUNT(DISTINCT session_id),COUNT(DISTINCT session_id) FROM search
UNION ALL SELECT 'search_filter','search_filter_id',COUNT(*),COUNT(DISTINCT search_filter_id) FROM search_filter
UNION ALL SELECT 'search_result_exposure','search_result_id',COUNT(*),COUNT(DISTINCT search_result_id) FROM search_result
UNION ALL SELECT 'event','event_id',COUNT(*),COUNT(DISTINCT event_id) FROM event
UNION ALL SELECT 'booking','booking_id',COUNT(*),COUNT(DISTINCT booking_id) FROM booking;

-- Q03. Ordered search base. KST suffix is removed only for interval arithmetic;
-- lexical ordering is valid because every timestamp uses YYYY-MM-DD HH:MM:SS KST.
WITH ordered AS (
  SELECT s.*,
         ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY search_time, search_id) AS search_seq,
         LEAD(search_id) OVER (PARTITION BY session_id ORDER BY search_time, search_id) AS next_search_id,
         LEAD(search_time) OVER (PARTITION BY session_id ORDER BY search_time, search_id) AS next_search_time,
         LEAD(total_result_count) OVER (PARTITION BY session_id ORDER BY search_time, search_id) AS next_total_result_count
  FROM search s
)
SELECT * FROM ordered;

-- Q04. Approved baseline metrics. Each UNION branch has its own declared grain.
WITH ordered AS (
  SELECT s.*,
         ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY search_time, search_id) AS search_seq,
         LEAD(search_id) OVER (PARTITION BY session_id ORDER BY search_time, search_id) AS next_search_id,
         LEAD(total_result_count) OVER (PARTITION BY session_id ORDER BY search_time, search_id) AS next_total_result_count
  FROM search s
), session_rollup AS (
  SELECT session_id,
         MAX(CASE WHEN search_seq=1 THEN total_result_count END) AS first_result_count,
         MAX(CASE WHEN search_seq>1 AND total_result_count>0 THEN 1 ELSE 0 END) AS later_nonzero
  FROM ordered GROUP BY session_id
)
SELECT 'zero_result_rate' AS metric_id, 'search_id' AS grain,
       SUM(total_result_count=0) AS numerator, COUNT(*) AS denominator
FROM search
UNION ALL
SELECT 'zero_followup_rate','zero_result_search_id',
       SUM(next_search_id IS NOT NULL), COUNT(*)
FROM ordered WHERE total_result_count=0
UNION ALL
SELECT 'immediate_recovery_rate','zero_to_next_search_transition',
       SUM(next_total_result_count>0), COUNT(*)
FROM ordered WHERE total_result_count=0 AND next_search_id IS NOT NULL
UNION ALL
SELECT 'session_final_recovery_rate','session_id_experiencing_zero',
       SUM((SELECT o2.total_result_count FROM ordered o2 WHERE o2.session_id=sr.session_id ORDER BY o2.search_seq DESC LIMIT 1)>0), COUNT(*)
FROM session_rollup sr
WHERE EXISTS (SELECT 1 FROM ordered oz WHERE oz.session_id=sr.session_id AND oz.total_result_count=0);

-- Q05. Card G: approved mutually exclusive four-category session outcome.
WITH ordered AS (
  SELECT s.*,
         ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY search_time, search_id) AS search_seq
  FROM search s
), session_rollup AS (
  SELECT o.session_id,
         MAX(CASE WHEN search_seq=1 THEN total_result_count END) AS first_result_count,
         MAX(CASE WHEN search_seq>1 AND total_result_count>0 THEN 1 ELSE 0 END) AS later_nonzero,
         EXISTS(SELECT 1 FROM event e WHERE e.session_id=o.session_id AND e.event_type='hotel_click') AS has_hotel_click
  FROM ordered o GROUP BY o.session_id
), classified AS (
  SELECT session_id,
    CASE
      WHEN first_result_count>0 AND has_hotel_click=1 THEN 'direct_success'
      WHEN first_result_count>0 AND has_hotel_click=0 THEN 'exposed_unselected'
      WHEN first_result_count=0 AND later_nonzero=1 THEN 'requery_recovery'
      WHEN first_result_count=0 AND later_nonzero=0 THEN 'persistent_failure'
    END AS outcome_segment
  FROM session_rollup
)
SELECT outcome_segment, COUNT(*) AS numerator,
       (SELECT COUNT(*) FROM classified) AS denominator,
       ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM classified),1) AS rate_pct
FROM classified GROUP BY outcome_segment ORDER BY outcome_segment;

-- Q06. Card H: approved hotel_detail_view event count per rank-1 exposure row.
SELECT
  SUM(EXISTS(
    SELECT 1 FROM event e
    WHERE e.event_type='hotel_detail_view'
      AND e.search_id=sr.search_id AND e.hotel_id=sr.hotel_id
  )) AS unique_detail_pairs_candidate,
  (SELECT COUNT(*) FROM event e JOIN search_result r
     ON r.search_id=e.search_id AND r.hotel_id=e.hotel_id
   WHERE e.event_type='hotel_detail_view' AND r.result_rank=1) AS approved_detail_event_numerator,
  COUNT(*) AS rank1_exposure_denominator,
  ROUND(100.0*(SELECT COUNT(*) FROM event e JOIN search_result r
     ON r.search_id=e.search_id AND r.hotel_id=e.hotel_id
   WHERE e.event_type='hotel_detail_view' AND r.result_rank=1)/COUNT(*),1) AS approved_rate_pct
FROM search_result sr WHERE result_rank=1;

-- Q07. Zero-result transition classification. Priority is intentionally fixed:
-- same -> region -> query -> relaxation/strengthening/mixed -> other.
WITH joined AS (
  SELECT s.session_id, s.search_id, s.search_time, s.total_result_count,
         s.query_text, s.destination, sf.property_type, sf.property_grade, sf.user_rating_min,
         sf.price, sf.amenity_count, sf.region,
         LEAD(s.search_id) OVER w AS next_search_id,
         LEAD(s.search_time) OVER w AS next_search_time,
         LEAD(s.total_result_count) OVER w AS next_total_result_count,
         LEAD(s.query_text) OVER w AS next_query_text,
         LEAD(s.destination) OVER w AS next_destination,
         LEAD(sf.property_type) OVER w AS next_property_type,
         LEAD(sf.property_grade) OVER w AS next_property_grade,
         LEAD(sf.user_rating_min) OVER w AS next_user_rating_min,
         LEAD(sf.price) OVER w AS next_price,
         LEAD(sf.amenity_count) OVER w AS next_amenity_count,
         LEAD(sf.region) OVER w AS next_region
  FROM search s JOIN search_filter sf USING(search_id)
  WINDOW w AS (PARTITION BY s.session_id ORDER BY s.search_time, s.search_id)
), flags AS (
  SELECT *,
    CASE WHEN (user_rating_min IS NOT NULL AND next_user_rating_min IS NULL)
      OR (user_rating_min IS NOT NULL AND next_user_rating_min IS NOT NULL AND next_user_rating_min < user_rating_min)
      OR (amenity_count IS NOT NULL AND next_amenity_count IS NULL)
      OR (amenity_count IS NOT NULL AND next_amenity_count IS NOT NULL AND next_amenity_count < amenity_count)
      OR (price IS NOT NULL AND next_price IS NULL)
      OR (price IS NOT NULL AND next_price IS NOT NULL AND next_price > price) THEN 1 ELSE 0 END AS relaxed,
    CASE WHEN (user_rating_min IS NULL AND next_user_rating_min IS NOT NULL)
      OR (user_rating_min IS NOT NULL AND next_user_rating_min IS NOT NULL AND next_user_rating_min > user_rating_min)
      OR (amenity_count IS NULL AND next_amenity_count IS NOT NULL)
      OR (amenity_count IS NOT NULL AND next_amenity_count IS NOT NULL AND next_amenity_count > amenity_count)
      OR (price IS NULL AND next_price IS NOT NULL)
      OR (price IS NOT NULL AND next_price IS NOT NULL AND next_price < price) THEN 1 ELSE 0 END AS stricter
  FROM joined WHERE total_result_count=0 AND next_search_id IS NOT NULL
), typed AS (
  SELECT *, CASE
    WHEN query_text IS next_query_text AND destination IS next_destination AND property_type IS next_property_type
      AND property_grade IS next_property_grade AND user_rating_min IS next_user_rating_min
      AND price IS next_price AND amenity_count IS next_amenity_count AND region IS next_region THEN 'same'
    WHEN destination IS NOT next_destination OR region IS NOT next_region THEN 'region'
    WHEN query_text IS NOT next_query_text THEN 'query'
    WHEN relaxed=1 AND stricter=0 THEN 'relax'
    WHEN stricter=1 AND relaxed=0 THEN 'strengthen'
    WHEN relaxed=1 AND stricter=1 THEN 'mixed'
    ELSE 'other' END AS observed_behavior
  FROM flags
)
SELECT observed_behavior, COUNT(*) AS transition_n,
       SUM(next_total_result_count>0) AS recovered_n,
       SUM(EXISTS(SELECT 1 FROM event e WHERE e.event_type='hotel_detail_view' AND e.search_id=typed.next_search_id)) AS detail_n,
       ROUND(100.0*SUM(next_total_result_count>0)/COUNT(*),1) AS recovery_pct,
       ROUND(100.0*SUM(EXISTS(SELECT 1 FROM event e WHERE e.event_type='hotel_detail_view' AND e.search_id=typed.next_search_id))/COUNT(*),1) AS detail_pct
FROM typed GROUP BY observed_behavior ORDER BY observed_behavior;

-- Q08. Filter/intent dictionary inputs and 3+ active-filter combination.
-- Active filter dimensions: property_type, property_grade, user_rating_min, price,
-- amenity_count>0, and region. Search query/destination are not filter dimensions.
WITH f AS (
  SELECT s.search_id, s.total_result_count,
    (sf.property_type IS NOT NULL AND TRIM(sf.property_type)<>'')
    +(sf.property_grade IS NOT NULL AND TRIM(CAST(sf.property_grade AS TEXT))<>'')
    +(sf.user_rating_min IS NOT NULL)
    +(sf.price IS NOT NULL)
    +(COALESCE(sf.amenity_count,0)>0)
    +(sf.region IS NOT NULL AND TRIM(sf.region)<>'') AS active_filter_count,
    (sf.price IS NOT NULL)+(sf.user_rating_min IS NOT NULL)+(COALESCE(sf.amenity_count,0)>0) AS core_constraint_count
  FROM search s JOIN search_filter sf USING(search_id)
)
SELECT 'active_filter_count_ge_3' AS metric_id, 'search_id' AS grain,
       SUM(total_result_count=0) AS numerator, COUNT(*) AS denominator,
       ROUND(100.0*SUM(total_result_count=0)/COUNT(*),1) AS rate_pct
FROM f WHERE active_filter_count>=3;

-- Q09. Zero -> next-search interval distribution in seconds (nearest-rank percentiles).
WITH ordered AS (
  SELECT s.*,
    LEAD(search_id) OVER w AS next_search_id,
    LEAD(search_time) OVER w AS next_search_time
  FROM search s WINDOW w AS (PARTITION BY session_id ORDER BY search_time, search_id)
), gaps AS (
  SELECT CAST(ROUND((julianday(SUBSTR(next_search_time,1,19))-julianday(SUBSTR(search_time,1,19)))*86400) AS INTEGER) AS gap_seconds
  FROM ordered WHERE total_result_count=0 AND next_search_id IS NOT NULL
), ranked AS (
  SELECT gap_seconds, ROW_NUMBER() OVER(ORDER BY gap_seconds) rn, COUNT(*) OVER() n FROM gaps
)
SELECT COUNT(*) AS n, MIN(gap_seconds) AS min_seconds,
       ROUND(AVG(gap_seconds),3) AS mean_seconds,
       MAX(CASE WHEN rn=(n+1)/2 THEN gap_seconds END) AS median_seconds,
       MAX(CASE WHEN rn=(n*25+99)/100 THEN gap_seconds END) AS p25_seconds,
       MAX(CASE WHEN rn=(n*75+99)/100 THEN gap_seconds END) AS p75_seconds,
       MAX(CASE WHEN rn=(n*90+99)/100 THEN gap_seconds END) AS p90_seconds,
       MAX(CASE WHEN rn=(n*95+99)/100 THEN gap_seconds END) AS p95_seconds,
       MAX(gap_seconds) AS max_seconds
FROM ranked;

-- Q10. Logical FK/orphan checks. SQLite declares no physical FKs; these are contract checks.
SELECT 'room.hotel_id->hotel.hotel_id' relation, COUNT(*) orphan_n FROM room c LEFT JOIN hotel p ON p.hotel_id=c.hotel_id WHERE p.hotel_id IS NULL
UNION ALL SELECT 'search_filter.search_id->search.search_id',COUNT(*) FROM search_filter c LEFT JOIN search p ON p.search_id=c.search_id WHERE p.search_id IS NULL
UNION ALL SELECT 'search_result.search_id->search.search_id',COUNT(*) FROM search_result c LEFT JOIN search p ON p.search_id=c.search_id WHERE p.search_id IS NULL
UNION ALL SELECT 'search_result.hotel_id->hotel.hotel_id',COUNT(*) FROM search_result c LEFT JOIN hotel p ON p.hotel_id=c.hotel_id WHERE p.hotel_id IS NULL
UNION ALL SELECT 'search_result.room_id->room.room_id',COUNT(*) FROM search_result c LEFT JOIN room p ON p.room_id=c.room_id WHERE p.room_id IS NULL
UNION ALL SELECT 'event.search_id->search.search_id(nonnull)',COUNT(*) FROM event c LEFT JOIN search p ON p.search_id=c.search_id WHERE c.search_id IS NOT NULL AND p.search_id IS NULL
UNION ALL SELECT 'event.hotel_id->hotel.hotel_id(nonnull)',COUNT(*) FROM event c LEFT JOIN hotel p ON p.hotel_id=c.hotel_id WHERE c.hotel_id IS NOT NULL AND p.hotel_id IS NULL
UNION ALL SELECT 'booking.user_id->user.user_id',COUNT(*) FROM booking c LEFT JOIN user p ON p.user_id=c.user_id WHERE p.user_id IS NULL
UNION ALL SELECT 'booking.hotel_id->hotel.hotel_id',COUNT(*) FROM booking c LEFT JOIN hotel p ON p.hotel_id=c.hotel_id WHERE p.hotel_id IS NULL
UNION ALL SELECT 'booking.room_id->room.room_id',COUNT(*) FROM booking c LEFT JOIN room p ON p.room_id=c.room_id WHERE p.room_id IS NULL
UNION ALL SELECT 'booking.hotel_id=room.hotel_id',COUNT(*) FROM booking b JOIN room r ON r.room_id=b.room_id WHERE b.hotel_id<>r.hotel_id;
