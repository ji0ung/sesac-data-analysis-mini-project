CREATE TABLE `room_inventory` (
	`id` text PRIMARY KEY NOT NULL,
	`hotel_id` text NOT NULL,
	`name` text NOT NULL,
	`bed_type` text NOT NULL,
	`view_type` text NOT NULL,
	`size_sqm` integer NOT NULL,
	`capacity` integer NOT NULL,
	`breakfast` integer NOT NULL,
	`free_cancellation` integer NOT NULL,
	`pay_at_hotel` integer NOT NULL,
	`spa_access` integer NOT NULL,
	`bathtub` integer NOT NULL,
	`smoking` integer NOT NULL,
	`units_left` integer NOT NULL,
	`price_modifier` integer NOT NULL
);
