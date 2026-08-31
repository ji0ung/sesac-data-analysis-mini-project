-- Exact historical browser-close times do not exist. Use each session's final
-- recorded event as an explicitly documented estimate for open legacy rows.
UPDATE `sessions`
SET `ended_at` = (
  SELECT MAX(`events`.`created_at`)
  FROM `events`
  WHERE `events`.`session_id` = `sessions`.`id`
)
WHERE `ended_at` IS NULL
  AND EXISTS (
    SELECT 1 FROM `events` WHERE `events`.`session_id` = `sessions`.`id`
  );
