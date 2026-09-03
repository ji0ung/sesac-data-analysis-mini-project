#!/usr/bin/env python3
"""Build reproducible analysis marts for the original 296 hotel searches.

Scope: descriptive mart construction only. No hypothesis tests, synthetic records,
1,000/10,000-person datasets, or source-database writes are performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd


SEARCH_EXPECTED = 296
ZERO_TRANSITIONS_EXPECTED = 140
SESSIONS_EXPECTED = 43

# Search is the analysis unit for search_base/event_search_flags/ordered_searches.
# A transition is one zero-result search and the immediately following search in
# the same session. A session is the denominator for session_summary/segments.
SEARCH_FIELDS = [
    "query_text", "destination", "checkin_date", "checkout_date", "sort_option",
    "guest_count", "property_type", "property_grade", "user_rating_min", "price",
    "amenity_count", "region",
]
# H3 compares location, query, and filter state. Travel dates/sort/party size are
# retained in the mart for audit but are outside the approved H3 change taxonomy.
H3_FIELDS = ["query_text", "destination", "property_type", "property_grade",
             "user_rating_min", "price", "amenity_count", "region"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build original-296 read-only analysis marts")
    p.add_argument("--db", required=True, type=Path, help="source SQLite file")
    p.add_argument("--output-dir", required=True, type=Path, help="directory for CSV/JSON outputs")
    return p.parse_args()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_fingerprint(path: Path) -> dict[str, int | str]:
    """Values that must remain identical before and after the read-only run."""
    stat = path.stat()
    return {"size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": sha256(path)}


def open_read_only(db: Path) -> sqlite3.Connection:
    """Open SQLite through a read-only URI and prohibit writes again at PRAGMA level."""
    db = db.expanduser().resolve(strict=True)
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise AssertionError("SQLite query_only guard was not enabled")
    return conn


def normalize_text(value) -> str | None:
    """Comparison normalization required by H3: NFKC -> trim -> casefold."""
    if pd.isna(value):
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    return text or None


def load_sources(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # No user table is loaded; therefore user_name/email cannot leak to outputs.
    search = pd.read_sql_query("SELECT * FROM search", conn)
    filt = pd.read_sql_query("SELECT * FROM search_filter", conn)
    event = pd.read_sql_query(
        "SELECT event_id, session_id, event_type, event_at, hotel_id, "
        "search_filter_id, search_id FROM event", conn,
    )
    return search, filt, event


def coerce_types(search: pd.DataFrame, filt: pd.DataFrame, event: pd.DataFrame):
    """Apply explicit types; source values remain unchanged in SQLite.

    Missing strings remain NA and normalize to None only for comparisons. Missing
    price/rating means 'not set'; that state is meaningful in H3 direction rules.
    Counts are numeric and missing result counts are invalid (not imputed).
    """
    search = search.copy()
    filt = filt.copy()
    event = event.copy()
    for col in ["total_result_count", "guest_count"]:
        search[col] = pd.to_numeric(search[col], errors="raise").astype("Int64")
    for col in ["user_rating_min", "price", "amenity_count"]:
        filt[col] = pd.to_numeric(filt[col], errors="coerce")
    for col in ["search_time", "checkin_date", "checkout_date"]:
        cleaned = search[col].astype("string").str.replace(r"\s+KST$", "", regex=True)
        search[col] = pd.to_datetime(cleaned, errors="raise")
    # SQLite timestamps contain a literal KST suffix. Strip only that suffix and
    # parse as local-naive values so chronological ordering is deterministic.
    event["event_at"] = pd.to_datetime(
        event["event_at"].astype("string").str.replace(r"\s+KST$", "", regex=True),
        errors="raise",
    )
    return search, filt, event


def build_search_base(search: pd.DataFrame, filt: pd.DataFrame) -> pd.DataFrame:
    assert search["search_id"].is_unique
    assert filt["search_id"].is_unique
    assert set(search["search_id"]) == set(filt["search_id"])
    filt = filt.rename(columns={
        "data_origin": "filter_data_origin",
    })
    search = search.rename(columns={"data_origin": "search_data_origin"})
    out = search.merge(filt, on="search_id", how="inner", validate="one_to_one")
    assert len(out) == len(search) == len(filt)
    return out


def build_event_search_flags(search_base: pd.DataFrame, event: pd.DataFrame) -> pd.DataFrame:
    relevant = event[event["search_id"].notna()].copy()
    relevant["is_impression"] = relevant["event_type"].eq("hotel_impression")
    relevant["is_click"] = relevant["event_type"].eq("hotel_click")
    relevant["is_detail"] = relevant["event_type"].eq("hotel_detail_view")
    agg = relevant.groupby("search_id", as_index=False).agg(
        impression_count=("is_impression", "sum"),
        click_count=("is_click", "sum"),
        detail_count=("is_detail", "sum"),
        first_event_at=("event_at", "min"),
        last_event_at=("event_at", "max"),
    )
    for src, dst in [("impression_count", "has_impression"), ("click_count", "has_click"),
                     ("detail_count", "has_detail")]:
        agg[dst] = agg[src].gt(0)
    out = search_base[["search_id", "session_id"]].merge(agg, on="search_id", how="left", validate="one_to_one")
    count_cols = ["impression_count", "click_count", "detail_count"]
    flag_cols = ["has_impression", "has_click", "has_detail"]
    out[count_cols] = out[count_cols].fillna(0).astype("int64")
    out[flag_cols] = out[flag_cols].fillna(False).astype(bool)
    return out


def build_ordered_searches(search_base: pd.DataFrame) -> pd.DataFrame:
    # Stable total order: session_id, parsed search_time, then search_id tie-breaker.
    out = search_base.sort_values(["session_id", "search_time", "search_id"], kind="mergesort").copy()
    g = out.groupby("session_id", sort=False)
    out["search_order"] = g.cumcount() + 1
    out["prev_search_id"] = g["search_id"].shift(1)
    out["next_search_id"] = g["search_id"].shift(-1)
    out["prev_total_result_count"] = g["total_result_count"].shift(1).astype("Int64")
    out["next_total_result_count"] = g["total_result_count"].shift(-1).astype("Int64")
    out["prev_search_time"] = g["search_time"].shift(1)
    out["next_search_time"] = g["search_time"].shift(-1)
    assert out[["session_id", "search_order"]].duplicated().sum() == 0
    assert out.groupby("session_id")["search_order"].min().eq(1).all()
    # Every non-final row must point to the immediately following stable-order row.
    expected_next = out.groupby("session_id", sort=False)["search_id"].shift(-1)
    assert out["next_search_id"].equals(expected_next)
    return out


def direction(old, new, lower_is_relaxation: bool) -> str | None:
    """Return relax/strengthen for a numeric filter, including set/unset semantics."""
    old_missing, new_missing = pd.isna(old), pd.isna(new)
    if old_missing and new_missing:
        return None
    if not old_missing and new_missing:
        return "relax"
    if old_missing and not new_missing:
        return "strengthen"
    if float(old) == float(new):
        return None
    decreased = float(new) < float(old)
    relax = decreased if lower_is_relaxation else not decreased
    return "relax" if relax else "strengthen"


def classify_transition(row: pd.Series) -> tuple[str, list[str]]:
    # Precedence is authoritative: exact repeat > location > query > other filters.
    def equal(field):
        a, b = row[field], row[f"next_{field}"]
        if field in {"user_rating_min", "price", "amenity_count"}:
            if pd.isna(a) and pd.isna(b):
                return True
            if pd.isna(a) or pd.isna(b):
                return False
            return float(a) == float(b)
        return normalize_text(a) == normalize_text(b)
    changed = [f for f in H3_FIELDS if not equal(f)]
    if not changed:
        return "동일조건 반복", changed
    if any(f in changed for f in ("destination", "region")):
        return "지역 변경", changed
    if "query_text" in changed:
        return "검색어 수정", changed

    directions = []
    # Price upper bound: increase/unset relaxes; decrease/new setting strengthens.
    directions.append(direction(row["price"], row["next_price"], lower_is_relaxation=False))
    # Minimum rating and amenity count: decrease/unset relaxes; increase/new strengthens.
    directions.append(direction(row["user_rating_min"], row["next_user_rating_min"], lower_is_relaxation=True))
    directions.append(direction(row["amenity_count"], row["next_amenity_count"], lower_is_relaxation=True))
    dirs = {d for d in directions if d}
    if dirs == {"relax", "strengthen"}:
        return "혼합 변경", changed
    if dirs == {"relax"}:
        return "조건 완화", changed
    if dirs == {"strengthen"}:
        return "조건 강화", changed
    # Non-directional remaining filters (dates, guests, sort, property fields) changed.
    # They cannot be called relaxed/strengthened without an approved ordering.
    return "기타 필터 변경", changed


def build_zero_transitions(ordered: pd.DataFrame) -> pd.DataFrame:
    next_cols = ["search_id", "search_time", "total_result_count", *SEARCH_FIELDS]
    out = ordered[(ordered["total_result_count"] == 0) & ordered["next_search_id"].notna()].copy()
    # lead values are recomputed on the already stable order for all H3 comparison fields.
    grouped = ordered.groupby("session_id", sort=False)
    for col in next_cols:
        lead = grouped[col].shift(-1)
        out[f"next_{col}"] = lead.loc[out.index]
    labels = out.apply(classify_transition, axis=1)
    out["transition_type"] = [x[0] for x in labels]
    out["changed_fields"] = ["|".join(x[1]) for x in labels]
    out["next_recovered"] = out["next_total_result_count"].gt(0)
    assert out["total_result_count"].eq(0).all()
    assert out["next_search_id"].notna().all()
    assert out["transition_type"].isin({
        "동일조건 반복", "지역 변경", "검색어 수정", "조건 완화", "조건 강화", "혼합 변경",
    }).all(), "Unapproved H3 transition label produced"
    keep = [
        "session_id", "search_id", "search_time", "total_result_count", "next_search_id",
        "next_search_time", "next_total_result_count", "next_recovered", "transition_type",
        "changed_fields", *SEARCH_FIELDS, *[f"next_{x}" for x in SEARCH_FIELDS],
    ]
    return out[keep]


def build_session_summary(ordered: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    click_by_session = flags.groupby("session_id")["has_click"].any()
    rows = []
    for session_id, g in ordered.groupby("session_id", sort=True):
        first = g.iloc[0]
        first_zero = int(first["total_result_count"]) == 0
        later_nonzero = bool((g.iloc[1:]["total_result_count"] > 0).any())
        rows.append({
            "session_id": session_id,
            "first_search_id": first["search_id"],
            "first_search_time": first["search_time"],
            "first_result_count": int(first["total_result_count"]),
            "search_count": len(g),
            "experienced_zero": bool((g["total_result_count"] == 0).any()),
            "first_search_zero": first_zero,
            "subsequent_recovery": first_zero and later_nonzero,
            "has_hotel_click": bool(click_by_session.get(session_id, False)),
        })
    return pd.DataFrame(rows)


def build_session_segments(summary: pd.DataFrame) -> pd.DataFrame:
    def label(r):
        if not r.first_search_zero:
            return "직접 성공" if r.has_hotel_click else "결과 노출·미선택"
        return "재검색 회복" if r.subsequent_recovery else "지속 실패"
    out = summary[["session_id"]].copy()
    out["result_segment"] = summary.apply(label, axis=1)
    assert out["session_id"].is_unique
    assert out["result_segment"].notna().all()
    assert out["result_segment"].isin({"직접 성공", "결과 노출·미선택", "재검색 회복", "지속 실패"}).all()
    return out


def build_validation(conn, search_base, flags, ordered, transitions, summary, segments) -> pd.DataFrame:
    checks = []
    def add(name, actual, expected, severity="ERROR"):
        checks.append({"check_name": name, "actual": actual, "expected": expected,
                       "passed": actual == expected, "severity": severity})
    add("search_base_rows", len(search_base), SEARCH_EXPECTED)
    add("search_filter_1_to_1", search_base["search_id"].nunique(), len(search_base))
    add("event_search_flags_rows", len(flags), SEARCH_EXPECTED)
    add("ordered_searches_rows", len(ordered), SEARCH_EXPECTED)
    add("zero_transitions_rows", len(transitions), ZERO_TRANSITIONS_EXPECTED)
    add("session_summary_rows", len(summary), SESSIONS_EXPECTED)
    add("session_segments_rows", len(segments), SESSIONS_EXPECTED)
    add("segments_sum", int(segments["result_segment"].value_counts().sum()), SESSIONS_EXPECTED)
    add("segment_labels_count", segments["result_segment"].nunique(), 4)
    for label, expected in {"동일조건 반복": 53, "조건 완화": 41, "검색어 수정": 10,
                            "지역 변경": 24, "조건 강화": 10, "혼합 변경": 2}.items():
        add(f"transition_type::{label}", int((transitions["transition_type"] == label).sum()), expected)
    add("hotel_impression_count", int(flags["impression_count"].sum()),
        conn.execute("SELECT COUNT(*) FROM search_result").fetchone()[0])
    click_keys = conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT session_id,search_id,hotel_id FROM event WHERE event_type='hotel_click')").fetchone()[0]
    detail_keys = conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT session_id,search_id,hotel_id FROM event WHERE event_type='hotel_detail_view')").fetchone()[0]
    add("hotel_click_detail_distinct_key_count", click_keys, detail_keys)
    key_diff = conn.execute("""
        SELECT COUNT(*) FROM (
          SELECT session_id,search_id,hotel_id FROM event WHERE event_type='hotel_click'
          EXCEPT SELECT session_id,search_id,hotel_id FROM event WHERE event_type='hotel_detail_view'
        )
    """).fetchone()[0] + conn.execute("""
        SELECT COUNT(*) FROM (
          SELECT session_id,search_id,hotel_id FROM event WHERE event_type='hotel_detail_view'
          EXCEPT SELECT session_id,search_id,hotel_id FROM event WHERE event_type='hotel_click'
        )
    """).fetchone()[0]
    add("hotel_click_detail_key_symmetric_difference", key_diff, 0)
    # Known source-quality checks are surfaced, not repaired or used to redefine marts.
    sql_checks = {
        "search_date_reversals": "SELECT COUNT(*) FROM search WHERE date(checkout_date)<=date(checkin_date)",
        "click_hotel_outside_results": "SELECT COUNT(*) FROM event e WHERE e.event_type='hotel_click' AND e.hotel_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM search_result r WHERE r.search_id=e.search_id AND r.hotel_id=e.hotel_id)",
        "booking_room_hotel_mismatch": "SELECT COUNT(*) FROM booking b JOIN room r ON r.room_id=b.room_id WHERE b.hotel_id<>r.hotel_id",
    }
    for name, sql in sql_checks.items():
        actual = conn.execute(sql).fetchone()[0]
        checks.append({"check_name": name, "actual": actual, "expected": 0,
                       "passed": actual == 0, "severity": "WARNING"})
    return pd.DataFrame(checks)


def write_outputs(output_dir: Path, marts: dict[str, pd.DataFrame], metadata: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    forbidden = {"user_name", "email"}
    for name, df in marts.items():
        leaked = forbidden.intersection(df.columns)
        assert not leaked, f"PII columns blocked from {name}: {sorted(leaked)}"
        # UTF-8 BOM supports Korean labels in common spreadsheet tools.
        df.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig", date_format="%Y-%m-%d %H:%M:%S")
    (output_dir / "run_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    db = args.db.expanduser().resolve(strict=True)
    before = source_fingerprint(db)
    conn = open_read_only(db)
    try:
        search, filt, event = load_sources(conn)
        search, filt, event = coerce_types(search, filt, event)
        search_base = build_search_base(search, filt)
        flags = build_event_search_flags(search_base, event)
        ordered = build_ordered_searches(search_base)
        transitions = build_zero_transitions(ordered)
        summary = build_session_summary(ordered, flags)
        segments = build_session_segments(summary)
        validation = build_validation(conn, search_base, flags, ordered, transitions, summary, segments)
        segment_counts = segments["result_segment"].value_counts().sort_index().to_dict()
        transition_counts = transitions["transition_type"].value_counts().sort_index().to_dict()
        metadata = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "source_db": str(db), "source_sha256": before["sha256"],
            "source_size_bytes": before["size_bytes"],
            "sqlite_mode": "file URI mode=ro; PRAGMA query_only=ON",
            "analysis_scope": "original 296 descriptive marts only",
            "denominators": {"search": len(search_base), "zero_transition": len(transitions), "session": len(summary)},
            "segment_counts": segment_counts, "transition_counts": transition_counts,
            "sorting": ["session_id", "search_time", "search_id"],
            "text_normalization": "NFKC -> trim -> casefold",
            "pii_exported": False, "statistical_tests_executed": False,
            "synthetic_data_generated": False,
        }
        marts = {
            "search_base": search_base, "event_search_flags": flags,
            "ordered_searches": ordered, "zero_transitions": transitions,
            "session_summary": summary, "session_segments": segments,
            "validation_results": validation,
        }
        write_outputs(args.output_dir.resolve(), marts, metadata)
        failed_errors = validation[(~validation["passed"]) & validation["severity"].eq("ERROR")]
        after = source_fingerprint(db)
        assert before == after, "Source DB fingerprint changed during a read-only analysis run"
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        print(validation.to_string(index=False))
        assert failed_errors.empty, "Smoke-test invariant failure; definitions were not altered. See validation_results.csv."
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
