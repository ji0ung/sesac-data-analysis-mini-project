CREATE TABLE `admin_deleted_rows` (
	`table_name` text NOT NULL,
	`row_id` text NOT NULL,
	`snapshot` text NOT NULL,
	`deleted_at` text NOT NULL,
	`deleted_by` text NOT NULL,
	PRIMARY KEY(`table_name`, `row_id`)
);
