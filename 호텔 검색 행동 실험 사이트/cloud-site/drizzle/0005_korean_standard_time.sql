-- Convert existing UTC timestamps once to explicit Korea Standard Time.
UPDATE `users` SET `created_at` = strftime('%Y-%m-%dT%H:%M:%S', `created_at`, '+9 hours') || '+09:00' WHERE `created_at` LIKE '%Z';
UPDATE `sessions` SET `started_at` = strftime('%Y-%m-%dT%H:%M:%S', `started_at`, '+9 hours') || '+09:00' WHERE `started_at` LIKE '%Z';
UPDATE `sessions` SET `ended_at` = strftime('%Y-%m-%dT%H:%M:%S', `ended_at`, '+9 hours') || '+09:00' WHERE `ended_at` LIKE '%Z';
UPDATE `searches` SET `created_at` = strftime('%Y-%m-%dT%H:%M:%S', `created_at`, '+9 hours') || '+09:00' WHERE `created_at` LIKE '%Z';
UPDATE `events` SET `created_at` = strftime('%Y-%m-%dT%H:%M:%S', `created_at`, '+9 hours') || '+09:00' WHERE `created_at` LIKE '%Z';
UPDATE `reservations` SET `created_at` = strftime('%Y-%m-%dT%H:%M:%S', `created_at`, '+9 hours') || '+09:00' WHERE `created_at` LIKE '%Z';
UPDATE `admin_deleted_rows` SET `deleted_at` = strftime('%Y-%m-%dT%H:%M:%S', `deleted_at`, '+9 hours') || '+09:00' WHERE `deleted_at` LIKE '%Z';
UPDATE `participant_identities` SET `created_at` = strftime('%Y-%m-%dT%H:%M:%S', `created_at`, '+9 hours') || '+09:00' WHERE `created_at` LIKE '%Z';
