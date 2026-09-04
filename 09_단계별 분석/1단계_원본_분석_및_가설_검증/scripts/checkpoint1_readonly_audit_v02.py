#!/usr/bin/env python3
"""Read-only checkpoint-1 audit. No hypothesis tests or synthetic generation."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parent
DB = PROJECT_ROOT / "03_데이터모델링" / "이전버전" / "데이터셋" / "2026-09-03_v02" / "travel_data_filtered_complete_2026-09-03_v02_비식별.sqlite"
OUT = PACKAGE_ROOT / "artifacts" / "checkpoint1_readonly_audit_v02.json"
EXPECTED = {"user": 89, "hotel": 1000, "room": 3000, "search": 296,
            "search_filter": 296, "search_result": 8555, "event": 10432, "booking": 36}


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def one(conn: sqlite3.Connection, sql: str, args=()):
    return conn.execute(sql, args).fetchone()[0]


def rows(conn: sqlite3.Connection, sql: str, args=()):
    cur = conn.execute(sql, args)
    names = [x[0] for x in cur.description]
    return [dict(zip(names, x)) for x in cur.fetchall()]


def parse_dt(value):
    if value is None or str(value).strip() == "":
        return None
    s = str(value).strip()
    if s.endswith(" KST"):
        s = s[:-4] + "+09:00"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    before = {"size_bytes": DB.stat().st_size, "sha256": digest(DB), "mtime_ns": DB.stat().st_mtime_ns}
    conn = sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    mode = one(conn, "PRAGMA query_only")
    integrity = one(conn, "PRAGMA integrity_check")
    table_names = [x[0] for x in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    audit = {"guardrails": {"uri_mode": "ro", "pragma_query_only": mode,
                            "statistical_analysis": False, "synthetic_generation": False},
             "file": {"display_name": DB.name, "actual_path": str(DB.resolve()), **before},
             "integrity_check": integrity, "tables": {}, "checks": {}}

    date_cols = {"signup_at", "search_time", "checkin_date", "checkout_date", "event_at",
                 "session_end_time", "review_completed_at", "booking_at", "cancellation_deadline",
                 "source_last_mapped_at"}
    numeric_ranges = {}
    for table in table_names:
        info = [dict(x) for x in conn.execute(f"PRAGMA table_info({q(table)})")]
        cols = [x["name"] for x in info]
        pk = [x["name"] for x in sorted(info, key=lambda z: z["pk"]) if x["pk"]]
        indexes = []
        for ix in conn.execute(f"PRAGMA index_list({q(table)})"):
            item = dict(ix)
            item["columns"] = [x["name"] for x in conn.execute(f"PRAGMA index_info({q(item['name'])})")]
            indexes.append(item)
        n = one(conn, f"SELECT COUNT(*) FROM {q(table)}")
        nulls = {c: one(conn, f"SELECT COUNT(*) FROM {q(table)} WHERE {q(c)} IS NULL") for c in cols}
        blanks = {c: one(conn, f"SELECT COUNT(*) FROM {q(table)} WHERE typeof({q(c)})='text' AND trim({q(c)})=''") for c in cols}
        group_all = ",".join(q(c) for c in cols)
        full_dupe_groups = one(conn, f"SELECT COUNT(*) FROM (SELECT 1 FROM {q(table)} GROUP BY {group_all} HAVING COUNT(*)>1)")
        parse = {}
        for c in cols:
            if c in date_cols:
                vals = [x[0] for x in conn.execute(f"SELECT {q(c)} FROM {q(table)} WHERE {q(c)} IS NOT NULL AND trim(CAST({q(c)} AS TEXT))<>''")]
                bad = []
                for v in vals:
                    try:
                        parse_dt(v)
                    except (ValueError, TypeError):
                        bad.append(v)
                parse[c] = {"nonblank": len(vals), "failures": len(bad), "examples": bad[:5]}
        ranges = {}
        for col in info:
            typ = (col["type"] or "").upper()
            if any(t in typ for t in ("INT", "REAL", "NUM", "DEC", "FLOAT", "DOUBLE")):
                mn, mx = conn.execute(f"SELECT MIN({q(col['name'])}),MAX({q(col['name'])}) FROM {q(table)}").fetchone()
                ranges[col["name"]] = {"min": mn, "max": mx}
        audit["tables"][table] = {"row_count": n, "expected": EXPECTED.get(table),
            "row_count_match": EXPECTED.get(table) in (None, n), "columns": info, "pk": pk,
            "pk_duplicate_groups": 0 if not pk else one(conn, f"SELECT COUNT(*) FROM (SELECT 1 FROM {q(table)} GROUP BY {','.join(q(c) for c in pk)} HAVING COUNT(*)>1)"),
            "indexes": indexes, "foreign_keys": [dict(x) for x in conn.execute(f"PRAGMA foreign_key_list({q(table)})")],
            "nulls": nulls, "blank_strings": blanks, "full_row_duplicate_groups": full_dupe_groups,
            "date_parsing": parse, "numeric_ranges": ranges}

    checks = audit["checks"]
    def count(name, sql, example_sql=None):
        checks[name] = {"count": one(conn, sql)}
        if example_sql:
            checks[name]["examples"] = rows(conn, example_sql)[:20]

    count("search_without_filter", "SELECT COUNT(*) FROM search s LEFT JOIN search_filter f USING(search_id) WHERE f.search_id IS NULL")
    count("filter_without_search", "SELECT COUNT(*) FROM search_filter f LEFT JOIN search s USING(search_id) WHERE s.search_id IS NULL")
    count("duplicate_filter_per_search", "SELECT COUNT(*) FROM (SELECT search_id FROM search_filter GROUP BY search_id HAVING COUNT(*)<>1)")
    count("result_count_delta", "SELECT (SELECT COUNT(*) FROM search_result)-(SELECT SUM(total_result_count) FROM search)")
    count("duplicate_search_hotel", "SELECT COUNT(*) FROM (SELECT search_id,hotel_id FROM search_result GROUP BY 1,2 HAVING COUNT(*)>1)")
    count("duplicate_search_rank", "SELECT COUNT(*) FROM (SELECT search_id,result_rank FROM search_result GROUP BY 1,2 HAVING COUNT(*)>1)")
    count("result_room_hotel_mismatch", "SELECT COUNT(*) FROM search_result sr JOIN room r USING(room_id) WHERE sr.hotel_id<>r.hotel_id")
    count("search_date_reversal", "SELECT COUNT(*) FROM search WHERE date(checkout_date)<=date(checkin_date)",
          "SELECT search_id,checkin_date,checkout_date FROM search WHERE date(checkout_date)<=date(checkin_date) ORDER BY search_id")
    count("booking_date_reversal", "SELECT COUNT(*) FROM booking WHERE date(checkout_date)<=date(checkin_date)")
    count("booking_room_hotel_mismatch", "SELECT COUNT(*) FROM booking b JOIN room r USING(room_id) WHERE b.hotel_id<>r.hotel_id",
          "SELECT b.booking_id,b.hotel_id booking_hotel_id,b.room_id,r.hotel_id room_hotel_id FROM booking b JOIN room r USING(room_id) WHERE b.hotel_id<>r.hotel_id ORDER BY b.booking_id")
    count("clicked_hotel_not_in_result", "SELECT COUNT(*) FROM event e WHERE e.event_type='hotel_click' AND NOT EXISTS (SELECT 1 FROM search_result sr WHERE sr.search_id=e.search_id AND sr.hotel_id=e.hotel_id)",
          "SELECT event_id,search_id,hotel_id,event_at FROM event e WHERE e.event_type='hotel_click' AND NOT EXISTS (SELECT 1 FROM search_result sr WHERE sr.search_id=e.search_id AND sr.hotel_id=e.hotel_id) ORDER BY event_at,event_id")
    count("confirmed_room_overlap_review", "SELECT COUNT(*) FROM booking a JOIN booking b ON a.booking_id<b.booking_id AND a.room_id=b.room_id AND a.booking_status='confirmed' AND b.booking_status='confirmed' AND date(a.checkin_date)<date(b.checkout_date) AND date(b.checkin_date)<date(a.checkout_date)")

    parents = {"user_id": ("user", "user_id"), "hotel_id": ("hotel", "hotel_id"),
               "room_id": ("room", "room_id"), "search_id": ("search", "search_id"),
               "search_filter_id": ("search_filter", "search_filter_id")}
    orphans = []
    for table, data in audit["tables"].items():
        for col in [x["name"] for x in data["columns"]]:
            if col in parents and table != parents[col][0]:
                pt, pc = parents[col]
                n = one(conn, f"SELECT COUNT(*) FROM {q(table)} c LEFT JOIN {q(pt)} p ON c.{q(col)}=p.{q(pc)} WHERE c.{q(col)} IS NOT NULL AND p.{q(pc)} IS NULL")
                orphans.append({"child": table, "column": col, "parent": pt, "count": n})
    checks["orphan_keys"] = orphans

    # Python parsing is necessary because source timestamps carry a literal KST suffix.
    search_times = {x["search_id"]: parse_dt(x["search_time"]) for x in conn.execute("SELECT search_id,search_time FROM search")}
    before_search = []
    after_session_end = []
    for x in conn.execute("SELECT event_id,search_id,event_at,session_end_time FROM event"):
        event_at = parse_dt(x["event_at"])
        if x["search_id"] and event_at and event_at < search_times[x["search_id"]]:
            before_search.append(dict(x))
        end = parse_dt(x["session_end_time"])
        if end and event_at and event_at > end:
            after_session_end.append(dict(x))
    checks["event_before_linked_search"] = {"count": len(before_search), "examples": before_search[:20]}
    checks["event_after_own_session_end"] = {"count": len(after_session_end), "examples": after_session_end[:20]}

    cardinality_sql = {
        "hotel_to_room": "SELECT MIN(n),MAX(n),AVG(n) FROM (SELECT h.hotel_id,COUNT(r.room_id)n FROM hotel h LEFT JOIN room r USING(hotel_id) GROUP BY h.hotel_id)",
        "search_to_result": "SELECT MIN(n),MAX(n),AVG(n) FROM (SELECT s.search_id,COUNT(r.search_result_id)n FROM search s LEFT JOIN search_result r USING(search_id) GROUP BY s.search_id)",
        "search_to_event": "SELECT MIN(n),MAX(n),AVG(n) FROM (SELECT s.search_id,COUNT(e.event_id)n FROM search s LEFT JOIN event e USING(search_id) GROUP BY s.search_id)",
        "user_to_event": "SELECT MIN(n),MAX(n),AVG(n) FROM (SELECT u.user_id,COUNT(e.event_id)n FROM user u LEFT JOIN event e USING(user_id) GROUP BY u.user_id)",
        "user_to_booking": "SELECT MIN(n),MAX(n),AVG(n) FROM (SELECT u.user_id,COUNT(b.booking_id)n FROM user u LEFT JOIN booking b USING(user_id) GROUP BY u.user_id)"}
    checks["cardinalities"] = {name: dict(zip(("min", "max", "avg"), conn.execute(sql).fetchone())) for name, sql in cardinality_sql.items()}
    checks["declared_fk_violations"] = rows(conn, "PRAGMA foreign_key_check")
    conn.close()
    after = {"size_bytes": DB.stat().st_size, "sha256": digest(DB), "mtime_ns": DB.stat().st_mtime_ns}
    audit["source_unchanged"] = before == after
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(str(OUT))


if __name__ == "__main__":
    main()
