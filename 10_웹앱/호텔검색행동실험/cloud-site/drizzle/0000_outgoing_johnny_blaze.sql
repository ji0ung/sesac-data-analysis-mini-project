CREATE TABLE `events` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`session_id` text NOT NULL,
	`search_id` text,
	`hotel_id` text,
	`name` text NOT NULL,
	`page` text NOT NULL,
	`properties` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `hotels` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`city` text NOT NULL,
	`type` text NOT NULL,
	`grade` integer NOT NULL,
	`rating` real NOT NULL,
	`price` integer NOT NULL,
	`reviews` integer NOT NULL,
	`station_distance` integer NOT NULL,
	`amenities` text NOT NULL,
	`free_cancellation` integer NOT NULL,
	`pay_at_hotel` integer NOT NULL,
	`breakfast` integer NOT NULL,
	`family_room` integer NOT NULL,
	`pet_friendly` integer NOT NULL,
	`pool` integer NOT NULL,
	`spa` integer NOT NULL,
	`chain` text
);
--> statement-breakpoint
CREATE TABLE `reservations` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`session_id` text NOT NULL,
	`search_id` text NOT NULL,
	`hotel_id` text NOT NULL,
	`total_price` integer NOT NULL,
	`status` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `searches` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`session_id` text NOT NULL,
	`parent_id` text,
	`created_at` text NOT NULL,
	`conditions` text NOT NULL,
	`result_count` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`started_at` text NOT NULL,
	`ended_at` text
);
--> statement-breakpoint
CREATE TABLE `users` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`created_at` text NOT NULL
);
