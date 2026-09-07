PRAGMA foreign_keys=ON;

CREATE TABLE SimulationRun(
 simulation_run_id TEXT PRIMARY KEY,
 execution_mode TEXT NOT NULL CHECK(execution_mode IN('dry_run','production')),
 scenario_type TEXT NOT NULL CHECK(scenario_type='base'),
 random_seed INTEGER NOT NULL,
 n_users_total INTEGER NOT NULL,
 n_users_control INTEGER NOT NULL,
 n_users_treatment INTEGER NOT NULL,
 source_db_sha256 TEXT NOT NULL,
 reference_1000_db_sha256 TEXT NOT NULL,
 code_sha256 TEXT NOT NULL,
 config_sha256 TEXT NOT NULL,
 schema_sha256 TEXT NOT NULL,
 package_versions_json TEXT NOT NULL,
 posterior_draws_json TEXT NOT NULL,
 started_at_utc TEXT NOT NULL,
 completed_at_utc TEXT
);

CREATE TABLE HotelDimension(
 hotel_key INTEGER PRIMARY KEY,
 hotel_cluster_id TEXT NOT NULL UNIQUE,
 city_group TEXT NOT NULL,
 grade_band TEXT NOT NULL
);

CREATE TABLE RoomDimension(
 room_key INTEGER PRIMARY KEY,
 hotel_key INTEGER NOT NULL REFERENCES HotelDimension(hotel_key),
 room_type_group TEXT NOT NULL,
 capacity INTEGER NOT NULL CHECK(capacity>0),
 UNIQUE(hotel_key,room_type_group,capacity)
);

CREATE TABLE ExperimentAssignment(
 user_id TEXT PRIMARY KEY,
 pair_id TEXT NOT NULL,
 sample_set_type TEXT NOT NULL CHECK(sample_set_type IN('control','treatment')),
 sample_stratum TEXT NOT NULL,
 intent_segment TEXT NOT NULL CHECK(intent_segment IN('condition_keeper','location_flexible','budget_flexible','option_count_flexible','query_reframer','rapid_resolver')),
 intent_assignment_prob REAL NOT NULL CHECK(intent_assignment_prob>0 AND intent_assignment_prob<=1),
 intent_version TEXT NOT NULL,
 simulation_run_id TEXT NOT NULL REFERENCES SimulationRun(simulation_run_id),
 random_seed INTEGER NOT NULL,
 scenario_type TEXT NOT NULL CHECK(scenario_type='base'),
 treatment_policy TEXT NOT NULL,
 template_cluster_id TEXT NOT NULL,
 region_group TEXT NOT NULL,
 initial_filter_state TEXT NOT NULL,
 price_limited_flag INTEGER NOT NULL CHECK(price_limited_flag IN(0,1)),
 option_limited_flag INTEGER NOT NULL CHECK(option_limited_flag IN(0,1)),
 base_search_propensity INTEGER NOT NULL CHECK(base_search_propensity>=1),
 baseline_recovery_probability REAL NOT NULL CHECK(baseline_recovery_probability BETWEEN 0 AND 1),
 common_random_zero REAL NOT NULL CHECK(common_random_zero>=0 AND common_random_zero<1),
 common_random_behavior REAL NOT NULL CHECK(common_random_behavior>=0 AND common_random_behavior<1),
 common_random_recovery REAL NOT NULL CHECK(common_random_recovery>=0 AND common_random_recovery<1),
 common_random_detail REAL NOT NULL CHECK(common_random_detail>=0 AND common_random_detail<1),
 distribution_lineage_policy TEXT NOT NULL CHECK(distribution_lineage_policy='row-level source lineage removed'),
 UNIQUE(pair_id,sample_set_type)
);

CREATE TABLE Search(
 search_id TEXT PRIMARY KEY,
 simulation_run_id TEXT NOT NULL REFERENCES SimulationRun(simulation_run_id),
 user_id TEXT NOT NULL REFERENCES ExperimentAssignment(user_id),
 pair_id TEXT NOT NULL,
 session_id TEXT NOT NULL,
 search_seq INTEGER NOT NULL,
 search_at TEXT NOT NULL,
 region_group TEXT NOT NULL,
 query_variant TEXT NOT NULL,
 price_limit INTEGER,
 option_limit_count INTEGER,
 total_result_count INTEGER NOT NULL CHECK(total_result_count>=0),
 condition_signature TEXT NOT NULL,
 UNIQUE(user_id,search_seq)
);

CREATE TABLE ExposureBridge(
 exposure_id TEXT PRIMARY KEY,
 search_id TEXT NOT NULL REFERENCES Search(search_id),
 hotel_key INTEGER NOT NULL REFERENCES HotelDimension(hotel_key),
 room_key INTEGER NOT NULL REFERENCES RoomDimension(room_key),
 result_rank INTEGER NOT NULL CHECK(result_rank>=1),
 exposed_at TEXT NOT NULL,
 UNIQUE(search_id,hotel_key),
 UNIQUE(search_id,result_rank)
);

CREATE TABLE ActionEvent(
 action_event_id TEXT PRIMARY KEY,
 simulation_run_id TEXT NOT NULL REFERENCES SimulationRun(simulation_run_id),
 user_id TEXT NOT NULL REFERENCES ExperimentAssignment(user_id),
 session_id TEXT NOT NULL,
 search_id TEXT REFERENCES Search(search_id),
 event_type TEXT NOT NULL CHECK(event_type IN('session_start','search_submit','treatment_exposure','proposal_selected','condition_changed','hotel_click','hotel_detail_view','session_end')),
 event_at TEXT NOT NULL,
 hotel_key INTEGER REFERENCES HotelDimension(hotel_key),
 treatment_policy TEXT
);

CREATE TABLE SearchTransition(
 transition_id TEXT PRIMARY KEY,
 simulation_run_id TEXT NOT NULL REFERENCES SimulationRun(simulation_run_id),
 user_id TEXT NOT NULL REFERENCES ExperimentAssignment(user_id),
 pair_id TEXT NOT NULL,
 from_search_id TEXT NOT NULL UNIQUE REFERENCES Search(search_id),
 to_search_id TEXT NOT NULL REFERENCES Search(search_id),
 observed_behavior TEXT NOT NULL CHECK(observed_behavior IN('same','region','query','relax','strengthen','mixed')),
 interarrival_seconds INTEGER NOT NULL CHECK(interarrival_seconds>0),
 proposal_exposed_flag INTEGER NOT NULL CHECK(proposal_exposed_flag IN(0,1)),
 proposal_selected_flag INTEGER NOT NULL CHECK(proposal_selected_flag IN(0,1)),
 condition_changed_flag INTEGER NOT NULL CHECK(condition_changed_flag IN(0,1)),
 recovered_flag INTEGER NOT NULL CHECK(recovered_flag IN(0,1)),
 detail_after_recovery_flag INTEGER NOT NULL CHECK(detail_after_recovery_flag IN(0,1)),
 CHECK(proposal_selected_flag<=proposal_exposed_flag),
 CHECK(condition_changed_flag<=proposal_selected_flag),
 CHECK(detail_after_recovery_flag<=recovered_flag)
);

CREATE TABLE SessionSummary(
 session_id TEXT PRIMARY KEY,
 simulation_run_id TEXT NOT NULL REFERENCES SimulationRun(simulation_run_id),
 user_id TEXT NOT NULL UNIQUE REFERENCES ExperimentAssignment(user_id),
 pair_id TEXT NOT NULL,
 sample_set_type TEXT NOT NULL CHECK(sample_set_type IN('control','treatment')),
 sample_stratum TEXT NOT NULL,
 intent_segment TEXT NOT NULL,
 treatment_policy TEXT NOT NULL,
 scenario_type TEXT NOT NULL CHECK(scenario_type='base'),
 random_seed INTEGER NOT NULL,
 session_start_at TEXT NOT NULL,
 session_end_at TEXT NOT NULL,
 search_count INTEGER NOT NULL CHECK(search_count>=1),
 experienced_zero_flag INTEGER NOT NULL CHECK(experienced_zero_flag IN(0,1)),
 recovered_flag INTEGER NOT NULL CHECK(recovered_flag IN(0,1)),
 detail_view_flag INTEGER NOT NULL CHECK(detail_view_flag IN(0,1)),
 outcome_segment TEXT NOT NULL CHECK(outcome_segment IN('SG1','SG2','SG3','SG4')),
 CHECK(session_end_at>session_start_at)
);

CREATE TABLE _generation_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);

CREATE INDEX ix_assignment_pair ON ExperimentAssignment(pair_id);
CREATE INDEX ix_assignment_stratum_arm ON ExperimentAssignment(sample_stratum,sample_set_type);
CREATE INDEX ix_search_user_seq ON Search(user_id,search_seq);
CREATE INDEX ix_exposure_search ON ExposureBridge(search_id);
CREATE INDEX ix_event_session_time ON ActionEvent(session_id,event_at);
CREATE INDEX ix_transition_user ON SearchTransition(user_id);
CREATE INDEX ix_summary_arm_intent ON SessionSummary(sample_set_type,intent_segment);
