CREATE TABLE `participant_identities` (
	`normalized_name` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL UNIQUE,
	`display_name` text NOT NULL,
	`created_at` text NOT NULL
);
