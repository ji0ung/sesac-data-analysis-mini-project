-- SQLite analysis helpers for the current 2026-09-03_v03 dataset.
-- The flags are already stored in search and event; no external join is required.
-- TEMP VIEWs live only in the current connection.

DROP VIEW IF EXISTS temp.dq_search;
CREATE TEMP VIEW dq_search AS
SELECT
    s.*,
    CASE
        WHEN s.invalid_stay_date_flag = 1 THEN NULL
        ELSE CAST(julianday(s.checkout_date) - julianday(s.checkin_date) AS INTEGER)
    END AS valid_stay_nights
FROM search AS s;

DROP VIEW IF EXISTS temp.dq_hotel_click;
CREATE TEMP VIEW dq_hotel_click AS
SELECT e.*
FROM event AS e
WHERE e.event_type = 'hotel_click';

DROP VIEW IF EXISTS temp.dq_valid_stay_search;
CREATE TEMP VIEW dq_valid_stay_search AS
SELECT *
FROM dq_search
WHERE invalid_stay_date_flag = 0;

DROP VIEW IF EXISTS temp.dq_exposure_linked_hotel_click;
CREATE TEMP VIEW dq_exposure_linked_hotel_click AS
SELECT *
FROM dq_hotel_click
WHERE click_in_result_flag = 1;

-- Required checks for this version:
-- SELECT COUNT(*), SUM(invalid_stay_date_flag) FROM search; -- 296, 9
-- SELECT COUNT(*), SUM(click_in_result_flag = 0)
-- FROM event WHERE event_type = 'hotel_click';             -- 231, 2
-- SELECT COUNT(*) FROM event
-- WHERE event_type <> 'hotel_click' AND click_in_result_flag IS NOT NULL; -- 0
