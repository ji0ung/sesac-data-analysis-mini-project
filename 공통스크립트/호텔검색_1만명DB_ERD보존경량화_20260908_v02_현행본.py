"""호텔검색 1만 명 합성 DB의 ERD를 유지하며 분석용 정수키 사본을 생성한다.

원본 규칙형 문자열 ID를 숫자로 해석하거나 캐스팅하지 않는다. ID 영역별로
정렬한 원문 값에 연속 번호를 부여하고 관련 PK와 FK에 같은 임시 매핑을 적용한다.
영구 역매핑표는 출력 DB에 저장하지 않으며 source_session_id는 계보 키로 유지한다.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path


TABLES = [
    "SimulationRun",
    "UserSynthetic",
    "SessionSynthetic",
    "Hotel",
    "Room",
    "Search",
    "SearchFilter",
    "SearchResult",
    "ActionEvent",
    "SearchTransition",
    "Booking",
    "_generation_metadata",
]


SCHEMA = """
PRAGMA page_size=16384;
PRAGMA auto_vacuum=NONE;

CREATE TABLE SimulationRun(
  run_id INTEGER PRIMARY KEY,
  random_seed INTEGER NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN('unit_test','smoke_test','calibration','production')),
  scenario TEXT NOT NULL,
  created_at TEXT NOT NULL,
  disclaimer TEXT NOT NULL
);

CREATE TABLE UserSynthetic(
  user_id INTEGER PRIMARY KEY,
  pair_id INTEGER NOT NULL,
  sample_set_type TEXT NOT NULL CHECK(sample_set_type IN('control','treatment')),
  sample_stratum TEXT NOT NULL,
  simulation_run_id INTEGER NOT NULL REFERENCES SimulationRun(run_id),
  random_seed INTEGER NOT NULL,
  source_session_id TEXT NOT NULL,
  treatment_scenario TEXT NOT NULL,
  generation_model_version TEXT NOT NULL,
  age_group TEXT CHECK(age_group IS NULL),
  UNIQUE(pair_id,sample_set_type),
  CHECK((sample_set_type='control' AND treatment_scenario='none') OR
        (sample_set_type='treatment' AND treatment_scenario IN('conservative','expected','optimistic')))
);

CREATE TABLE SessionSynthetic(
  session_id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE REFERENCES UserSynthetic(user_id),
  pair_id INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NOT NULL,
  outcome_segment TEXT NOT NULL CHECK(outcome_segment IN('SG1','SG2','SG3','SG4')),
  treatment_exposed INTEGER NOT NULL CHECK(treatment_exposed IN(0,1))
);

CREATE TABLE Hotel(
  hotel_id INTEGER PRIMARY KEY,
  hotel_name TEXT NOT NULL
);

CREATE TABLE Room(
  room_id INTEGER PRIMARY KEY,
  hotel_id INTEGER NOT NULL REFERENCES Hotel(hotel_id)
);

CREATE TABLE Search(
  search_id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES SessionSynthetic(session_id),
  search_sequence INTEGER NOT NULL,
  search_time TEXT NOT NULL,
  total_result_count INTEGER NOT NULL CHECK(total_result_count>=0),
  query_text TEXT NOT NULL,
  destination TEXT NOT NULL,
  action_type TEXT NOT NULL,
  UNIQUE(session_id,search_sequence)
);

CREATE TABLE SearchFilter(
  search_filter_id INTEGER PRIMARY KEY,
  search_id INTEGER NOT NULL UNIQUE REFERENCES Search(search_id),
  price INTEGER,
  amenity_count INTEGER NOT NULL,
  region TEXT NOT NULL,
  property_type TEXT CHECK(property_type IS NULL),
  property_grade INTEGER CHECK(property_grade IS NULL)
);

CREATE TABLE SearchResult(
  search_result_id INTEGER PRIMARY KEY,
  search_id INTEGER NOT NULL REFERENCES Search(search_id),
  hotel_id INTEGER NOT NULL REFERENCES Hotel(hotel_id),
  room_id INTEGER NOT NULL REFERENCES Room(room_id),
  result_rank INTEGER NOT NULL CHECK(result_rank>0),
  UNIQUE(search_id,hotel_id),
  UNIQUE(search_id,result_rank)
);

CREATE TABLE ActionEvent(
  event_id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES UserSynthetic(user_id),
  session_id INTEGER NOT NULL REFERENCES SessionSynthetic(session_id),
  search_id INTEGER REFERENCES Search(search_id),
  hotel_id INTEGER REFERENCES Hotel(hotel_id),
  event_type TEXT NOT NULL,
  event_at TEXT NOT NULL,
  review_completed_at TEXT CHECK(review_completed_at IS NULL),
  review_text TEXT CHECK(review_text IS NULL)
);

CREATE TABLE SearchTransition(
  transition_id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES SessionSynthetic(session_id),
  from_search_id INTEGER NOT NULL REFERENCES Search(search_id),
  to_search_id INTEGER NOT NULL REFERENCES Search(search_id),
  action_type TEXT NOT NULL,
  recovered INTEGER NOT NULL CHECK(recovered IN(0,1))
);

CREATE TABLE Booking(
  booking_id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES UserSynthetic(user_id),
  hotel_id INTEGER REFERENCES Hotel(hotel_id),
  room_id INTEGER REFERENCES Room(room_id)
);

CREATE TABLE _generation_metadata(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def scalar(con: sqlite3.Connection, sql: str):
    return con.execute(sql).fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--verification")
    args = parser.parse_args()

    source = Path(args.input).resolve()
    output = Path(args.output).resolve()
    verification = Path(args.verification).resolve() if args.verification else output.with_suffix(".verification.json")

    if not source.is_file():
        raise SystemExit(f"입력 파일 없음: {source}")
    if source == output:
        raise SystemExit("입력과 출력 경로가 같습니다.")
    if output.exists() or verification.exists():
        raise SystemExit("출력 또는 검증 파일이 이미 존재합니다. 덮어쓰지 않습니다.")

    output.parent.mkdir(parents=True, exist_ok=True)
    source_hash_before = sha256(source)
    started = time.perf_counter()
    report = {"status": "FAIL", "input": str(source), "output": str(output)}

    try:
        con = sqlite3.connect(output)
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        con.execute("PRAGMA temp_store=FILE")
        con.executescript(SCHEMA)
        con.execute("ATTACH DATABASE ? AS src", (str(source),))

        source_tables = {r[0] for r in con.execute("SELECT name FROM src.sqlite_master WHERE type='table'")}
        missing = [t for t in TABLES if t not in source_tables]
        if missing:
            raise RuntimeError(f"필수 테이블 누락: {missing}")

        con.executescript("""
        CREATE TEMP TABLE map_run(old TEXT PRIMARY KEY, new INTEGER UNIQUE);
        INSERT INTO map_run SELECT run_id, row_number() OVER(ORDER BY run_id) FROM src.SimulationRun;
        CREATE TEMP TABLE map_user(old TEXT PRIMARY KEY, new INTEGER UNIQUE);
        INSERT INTO map_user SELECT user_id, row_number() OVER(ORDER BY user_id) FROM src.UserSynthetic;
        CREATE TEMP TABLE map_pair(old TEXT PRIMARY KEY, new INTEGER UNIQUE);
        INSERT INTO map_pair SELECT pair_id, row_number() OVER(ORDER BY pair_id) FROM (SELECT DISTINCT pair_id FROM src.UserSynthetic);
        CREATE TEMP TABLE map_session(old TEXT PRIMARY KEY, new INTEGER UNIQUE);
        INSERT INTO map_session SELECT session_id, row_number() OVER(ORDER BY session_id) FROM src.SessionSynthetic;
        CREATE TEMP TABLE map_hotel(old TEXT PRIMARY KEY, new INTEGER UNIQUE);
        INSERT INTO map_hotel SELECT hotel_id, row_number() OVER(ORDER BY hotel_id) FROM src.Hotel;
        CREATE TEMP TABLE map_room(old TEXT PRIMARY KEY, new INTEGER UNIQUE);
        INSERT INTO map_room SELECT room_id, row_number() OVER(ORDER BY room_id) FROM src.Room;
        CREATE TEMP TABLE map_search(old TEXT PRIMARY KEY, new INTEGER UNIQUE);
        INSERT INTO map_search SELECT search_id, row_number() OVER(ORDER BY search_id) FROM src.Search;

        INSERT INTO SimulationRun
        SELECT mr.new,s.random_seed,s.mode,s.scenario,s.created_at,s.disclaimer
        FROM src.SimulationRun s JOIN map_run mr ON mr.old=s.run_id;

        INSERT INTO UserSynthetic
        SELECT mu.new,mp.new,s.sample_set_type,s.sample_stratum,mr.new,s.random_seed,
               s.source_session_id,s.treatment_scenario,s.generation_model_version,s.age_group
        FROM src.UserSynthetic s
        JOIN map_user mu ON mu.old=s.user_id
        JOIN map_pair mp ON mp.old=s.pair_id
        JOIN map_run mr ON mr.old=s.simulation_run_id;

        INSERT INTO SessionSynthetic
        SELECT ms.new,mu.new,mp.new,s.started_at,s.ended_at,s.outcome_segment,s.treatment_exposed
        FROM src.SessionSynthetic s
        JOIN map_session ms ON ms.old=s.session_id
        JOIN map_user mu ON mu.old=s.user_id
        JOIN map_pair mp ON mp.old=s.pair_id;

        INSERT INTO Hotel
        SELECT mh.new,s.hotel_name FROM src.Hotel s JOIN map_hotel mh ON mh.old=s.hotel_id;

        INSERT INTO Room
        SELECT mr.new,mh.new FROM src.Room s
        JOIN map_room mr ON mr.old=s.room_id JOIN map_hotel mh ON mh.old=s.hotel_id;

        INSERT INTO Search
        SELECT mq.new,ms.new,s.search_sequence,s.search_time,s.total_result_count,
               s.query_text,s.destination,s.action_type
        FROM src.Search s
        JOIN map_search mq ON mq.old=s.search_id
        JOIN map_session ms ON ms.old=s.session_id;

        INSERT INTO SearchFilter
        SELECT row_number() OVER(ORDER BY s.search_filter_id),mq.new,s.price,s.amenity_count,
               s.region,s.property_type,s.property_grade
        FROM src.SearchFilter s JOIN map_search mq ON mq.old=s.search_id;

        INSERT INTO SearchResult
        SELECT row_number() OVER(ORDER BY s.search_result_id),mq.new,mh.new,mr.new,s.result_rank
        FROM src.SearchResult s
        JOIN map_search mq ON mq.old=s.search_id
        JOIN map_hotel mh ON mh.old=s.hotel_id
        JOIN map_room mr ON mr.old=s.room_id;

        INSERT INTO ActionEvent
        SELECT row_number() OVER(ORDER BY s.event_id),mu.new,ms.new,mq.new,mh.new,
               s.event_type,s.event_at,s.review_completed_at,s.review_text
        FROM src.ActionEvent s
        JOIN map_user mu ON mu.old=s.user_id
        JOIN map_session ms ON ms.old=s.session_id
        LEFT JOIN map_search mq ON mq.old=s.search_id
        LEFT JOIN map_hotel mh ON mh.old=s.hotel_id;

        INSERT INTO SearchTransition
        SELECT row_number() OVER(ORDER BY s.transition_id),ms.new,mf.new,mt.new,s.action_type,s.recovered
        FROM src.SearchTransition s
        JOIN map_session ms ON ms.old=s.session_id
        JOIN map_search mf ON mf.old=s.from_search_id
        JOIN map_search mt ON mt.old=s.to_search_id;

        INSERT INTO Booking
        SELECT row_number() OVER(ORDER BY s.booking_id),mu.new,mh.new,mr.new
        FROM src.Booking s
        LEFT JOIN map_user mu ON mu.old=s.user_id
        LEFT JOIN map_hotel mh ON mh.old=s.hotel_id
        LEFT JOIN map_room mr ON mr.old=s.room_id;

        INSERT INTO _generation_metadata SELECT key,value FROM src._generation_metadata;
        """)

        con.executescript("""
        CREATE INDEX idx_event_search_type ON ActionEvent(search_id,event_type);
        CREATE INDEX idx_event_session_time ON ActionEvent(session_id,event_at);
        CREATE INDEX idx_search_session_time ON Search(session_id,search_time);
        """)
        con.commit()
        con.execute("DETACH DATABASE src")
        con.execute("PRAGMA foreign_keys=ON")

        counts = {}
        for table in TABLES:
            with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src_con:
                src_count = scalar(src_con, f'SELECT COUNT(*) FROM "{table}"')
            out_count = scalar(con, f'SELECT COUNT(*) FROM "{table}"')
            counts[table] = {"source": src_count, "output": out_count, "match": src_count == out_count}

        fk_issues = con.execute("PRAGMA foreign_key_check").fetchall()
        integrity = scalar(con, "PRAGMA integrity_check")
        pair_issues = scalar(con, """
          SELECT COUNT(*) FROM (
            SELECT pair_id,
                   SUM(sample_set_type='control') c,
                   SUM(sample_set_type='treatment') t
            FROM UserSynthetic GROUP BY pair_id HAVING c<>1 OR t<>1
          )
        """)
        kpi = dict(con.execute("""
        WITH base AS (
          SELECT u.sample_set_type arm, s.search_id, s.session_id, s.search_sequence,
                 s.total_result_count,
                 LEAD(s.total_result_count) OVER(PARTITION BY s.session_id ORDER BY s.search_sequence) next_count
          FROM Search s JOIN SessionSynthetic ss ON ss.session_id=s.session_id
          JOIN UserSynthetic u ON u.user_id=ss.user_id
        )
        SELECT arm,
               printf('%d/%d',SUM(total_result_count=0),COUNT(*)) || '|' ||
               printf('%.10f',1.0*SUM(total_result_count=0)/COUNT(*)) || '|' ||
               printf('%d/%d',SUM(total_result_count=0 AND next_count>0),SUM(total_result_count=0 AND next_count IS NOT NULL)) || '|' ||
               printf('%.10f',1.0*SUM(total_result_count=0 AND next_count>0)/SUM(total_result_count=0 AND next_count IS NOT NULL))
        FROM base GROUP BY arm
        """))

        con.execute("VACUUM")
        con.close()

        source_hash_after = sha256(source)
        report.update({
            "status": "PASS" if all(v["match"] for v in counts.values()) and not fk_issues and integrity == "ok" and pair_issues == 0 and source_hash_before == source_hash_after else "FAIL",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "source_bytes": source.stat().st_size,
            "output_bytes": output.stat().st_size,
            "reduction_percent": round((1-output.stat().st_size/source.stat().st_size)*100, 6),
            "source_sha256_before": source_hash_before,
            "source_sha256_after": source_hash_after,
            "output_sha256": sha256(output),
            "page_size": sqlite3.connect(output).execute("PRAGMA page_size").fetchone()[0],
            "counts": counts,
            "foreign_key_issues": fk_issues,
            "integrity_check": integrity,
            "pair_balance_issues": pair_issues,
            "kpi_zero_and_immediate_recovery": kpi,
            "notes": [
                "12 tables and all original column names retained.",
                "Internal PK/FK IDs and pair_id converted from TEXT to INTEGER.",
                "source_session_id and business/category/timestamp text retained.",
                "Redundant idx_result_search_rank omitted because UNIQUE(search_id,result_rank) provides the same key order."
            ]
        })
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        try:
            con.close()
        except Exception:
            pass
    finally:
        verification.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
