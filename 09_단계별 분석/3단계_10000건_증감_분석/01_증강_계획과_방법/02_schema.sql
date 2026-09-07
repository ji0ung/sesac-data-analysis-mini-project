PRAGMA foreign_keys = ON;

CREATE TABLE SimulationRun (
  run_id TEXT PRIMARY KEY,
  scenario_type TEXT NOT NULL,
  effect_level TEXT NOT NULL,
  seed INTEGER NOT NULL,
  total_users INTEGER NOT NULL CHECK(total_users > 0 AND total_users <= 200 AND total_users % 2 = 0),
  pair_count INTEGER NOT NULL CHECK(pair_count * 2 = total_users),
  source_db_sha256 TEXT NOT NULL CHECK(length(source_db_sha256)=64),
  reference_1000_db_sha256 TEXT NOT NULL CHECK(length(reference_1000_db_sha256)=64),
  code_sha256 TEXT NOT NULL CHECK(length(code_sha256)=64),
  config_sha256 TEXT NOT NULL CHECK(length(config_sha256)=64),
  schema_sha256 TEXT NOT NULL CHECK(length(schema_sha256)=64),
  package_versions_json TEXT NOT NULL,
  started_at_utc TEXT NOT NULL,
  completed_at_utc TEXT
);

CREATE TABLE UserProfile (
  user_id TEXT PRIMARY KEY,
  pair_id TEXT NOT NULL,
  arm TEXT NOT NULL CHECK(arm IN ('control','treatment')),
  age_group TEXT,
  destination TEXT,
  filter_state_segment TEXT NOT NULL,
  intent_segment TEXT NOT NULL,
  template_search_id TEXT NOT NULL,
  template_signature TEXT NOT NULL,
  data_class TEXT NOT NULL CHECK(data_class='synthetic_dryrun')
);
CREATE UNIQUE INDEX ux_user_pair_arm ON UserProfile(pair_id, arm);

CREATE TABLE ExperimentAssignment (
  assignment_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES SimulationRun(run_id),
  user_id TEXT NOT NULL UNIQUE REFERENCES UserProfile(user_id),
  pair_id TEXT NOT NULL,
  arm TEXT NOT NULL CHECK(arm IN ('control','treatment')),
  treatment_policy TEXT NOT NULL,
  assigned_at TEXT NOT NULL
);

CREATE TABLE Search (
  search_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES SimulationRun(run_id),
  user_id TEXT NOT NULL REFERENCES UserProfile(user_id),
  pair_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  search_seq INTEGER NOT NULL CHECK(search_seq >= 1),
  search_at TEXT NOT NULL,
  query_text TEXT,
  destination TEXT,
  price INTEGER,
  user_rating_min REAL,
  amenity_count INTEGER,
  total_result_count INTEGER NOT NULL CHECK(total_result_count >= 0),
  filter_state_segment TEXT NOT NULL,
  intent_segment TEXT NOT NULL,
  data_class TEXT NOT NULL CHECK(data_class='synthetic_dryrun'),
  UNIQUE(session_id, search_seq)
);

CREATE TABLE SearchResult (
  search_result_id TEXT PRIMARY KEY,
  search_id TEXT NOT NULL REFERENCES Search(search_id),
  result_rank INTEGER NOT NULL CHECK(result_rank >= 1),
  hotel_id TEXT NOT NULL,
  room_id TEXT NOT NULL,
  result_score REAL NOT NULL CHECK(result_score BETWEEN 0 AND 1),
  exposed_at TEXT NOT NULL,
  UNIQUE(search_id, result_rank),
  UNIQUE(search_id, hotel_id)
);

CREATE TABLE ActionEvent (
  action_event_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES SimulationRun(run_id),
  user_id TEXT NOT NULL REFERENCES UserProfile(user_id),
  session_id TEXT NOT NULL,
  search_id TEXT REFERENCES Search(search_id),
  event_type TEXT NOT NULL CHECK(event_type IN ('session_start','search_submit','hotel_impression','hotel_click','hotel_detail_view','treatment_exposure','session_end')),
  event_at TEXT NOT NULL,
  hotel_id TEXT,
  treatment_policy TEXT,
  data_class TEXT NOT NULL CHECK(data_class='synthetic_dryrun')
);

CREATE TABLE SearchTransition (
  transition_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES SimulationRun(run_id),
  user_id TEXT NOT NULL REFERENCES UserProfile(user_id),
  session_id TEXT NOT NULL,
  from_search_id TEXT NOT NULL UNIQUE REFERENCES Search(search_id),
  to_search_id TEXT NOT NULL REFERENCES Search(search_id),
  transition_seq INTEGER NOT NULL,
  observed_behavior TEXT NOT NULL CHECK(observed_behavior IN ('same','region','query','relax','strengthen','mixed')),
  interarrival_seconds INTEGER NOT NULL CHECK(interarrival_seconds > 0),
  recovered_flag INTEGER NOT NULL CHECK(recovered_flag IN (0,1)),
  detail_after_recovery_flag INTEGER NOT NULL CHECK(detail_after_recovery_flag IN (0,1)),
  CHECK(detail_after_recovery_flag <= recovered_flag)
);

CREATE TABLE SessionSummary (
  session_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES SimulationRun(run_id),
  user_id TEXT NOT NULL UNIQUE REFERENCES UserProfile(user_id),
  pair_id TEXT NOT NULL,
  arm TEXT NOT NULL CHECK(arm IN ('control','treatment')),
  session_start_at TEXT NOT NULL,
  session_end_at TEXT NOT NULL,
  search_count INTEGER NOT NULL CHECK(search_count >= 1),
  first_result_count INTEGER NOT NULL CHECK(first_result_count >= 0),
  experienced_zero_flag INTEGER NOT NULL CHECK(experienced_zero_flag IN (0,1)),
  final_recovered_flag INTEGER NOT NULL CHECK(final_recovered_flag IN (0,1)),
  detail_view_flag INTEGER NOT NULL CHECK(detail_view_flag IN (0,1)),
  outcome_segment TEXT NOT NULL CHECK(outcome_segment IN ('SG1','SG2','SG3','SG4')),
  data_class TEXT NOT NULL CHECK(data_class='synthetic_dryrun'),
  CHECK(session_end_at > session_start_at)
);

CREATE TABLE _generation_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
