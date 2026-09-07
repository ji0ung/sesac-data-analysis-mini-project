#!/usr/bin/env python3
"""Read-only structural and corrected-metric QA for the S0 augmentation bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path


TABLES = ["user", "hotel", "room", "search", "search_filter", "search_result", "event", "booking"]
CORE_METRICS = {
    "zero_result_rate",
    "followup_rate_after_zero",
    "immediate_recovery_rate",
    "session_final_recovery_rate",
    "hotel_click_rate",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
    return connection


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace(" KST", "+09:00"))


def metrics(path: Path) -> tuple[dict, dict, str, dict]:
    connection = read_only(path)
    searches = connection.execute(
        "SELECT search_id, session_id, search_time, total_result_count FROM search"
    ).fetchall()
    clicked = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT search_id FROM event WHERE event_type='hotel_click' AND search_id IS NOT NULL"
        )
    }
    counts = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in TABLES
    }
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    coverage_row = connection.execute(
        "SELECT MIN(search_time), MAX(search_time), COUNT(DISTINCT session_id) FROM search"
    ).fetchone()
    coverage = {
        "search_time_min": coverage_row[0],
        "search_time_max": coverage_row[1],
        "distinct_sessions": coverage_row[2],
    }
    connection.close()

    ordered = sorted(searches, key=lambda row: (row[1], parse_time(row[2]), row[0]))
    sessions: dict[str, list[tuple]] = {}
    for row in ordered:
        sessions.setdefault(row[1], []).append(row)

    zero_count = sum(row[3] == 0 for row in ordered)
    transitions = 0
    immediate_recoveries = 0
    any_zero_sessions = 0
    finally_recovered_sessions = 0
    first_zero_sessions = 0
    first_zero_recovered_sessions = 0
    for group in sessions.values():
        results = [row[3] for row in group]
        for index, value in enumerate(results):
            if value == 0 and index + 1 < len(results):
                transitions += 1
                immediate_recoveries += results[index + 1] > 0
        zero_positions = [index for index, value in enumerate(results) if value == 0]
        if zero_positions:
            any_zero_sessions += 1
            finally_recovered_sessions += any(
                any(value > 0 for value in results[index + 1 :]) for index in zero_positions
            )
        if results[0] == 0:
            first_zero_sessions += 1
            first_zero_recovered_sessions += any(value > 0 for value in results[1:])

    definitions = {
        "zero_result_rate": (zero_count, len(ordered), "search"),
        "followup_rate_after_zero": (transitions, zero_count, "zero-result search"),
        "immediate_recovery_rate": (immediate_recoveries, transitions, "zero-to-next transition"),
        "session_final_recovery_rate": (
            finally_recovered_sessions,
            any_zero_sessions,
            "session experiencing any zero result",
        ),
        "hotel_click_rate": (
            sum(row[0] in clicked for row in ordered),
            len(ordered),
            "search",
        ),
        "first_search_zero_session_research_recovery_rate": (
            first_zero_recovered_sessions,
            first_zero_sessions,
            "session whose first search is zero",
        ),
    }
    calculated = {
        name: {
            "numerator": numerator,
            "denominator": denominator,
            "rate": numerator / denominator if denominator else None,
            "analysis_unit": unit,
        }
        for name, (numerator, denominator, unit) in definitions.items()
    }
    return calculated, counts, integrity, coverage


def structural_checks(path: Path, counts: dict, integrity: str) -> dict[str, bool]:
    connection = read_only(path)
    scalar = lambda sql: connection.execute(sql).fetchone()[0]
    checks = {
        "user_1000": counts["user"] == 1000,
        "sessions_1000": scalar("SELECT COUNT(DISTINCT session_id) FROM search") == 1000,
        "hotel_1000": counts["hotel"] == 1000,
        "room_3000": counts["room"] == 3000,
        "booking_0": counts["booking"] == 0,
        "search_filter_1to1": counts["search"] == counts["search_filter"] == scalar(
            "SELECT COUNT(DISTINCT search_id) FROM search_filter"
        ),
        "result_sum_matches": scalar("SELECT SUM(total_result_count) FROM search") == counts["search_result"],
        "duplicate_search_hotel_0": scalar(
            "SELECT COUNT(*) FROM (SELECT search_id, hotel_id FROM search_result GROUP BY 1,2 HAVING COUNT(*)>1)"
        ) == 0,
        "room_hotel_mismatch_0": scalar(
            "SELECT COUNT(*) FROM search_result r JOIN room x ON r.room_id=x.room_id WHERE r.hotel_id<>x.hotel_id"
        ) == 0,
        "unexposed_click_0": scalar(
            "SELECT COUNT(*) FROM event e WHERE e.event_type='hotel_click' "
            "AND NOT EXISTS (SELECT 1 FROM search_result r WHERE r.search_id=e.search_id AND r.hotel_id=e.hotel_id)"
        ) == 0,
        "invalid_stay_0": scalar("SELECT COUNT(*) FROM search WHERE date(checkout_date)<=date(checkin_date)") == 0,
        "zero_result_behavior_0": scalar(
            "SELECT COUNT(*) FROM event e JOIN search s ON e.search_id=s.search_id "
            "WHERE s.total_result_count=0 AND e.event_type IN ('hotel_impression','hotel_click','hotel_detail_view')"
        ) == 0,
        "synthetic_origin_only": scalar(
            "SELECT COUNT(*) FROM search WHERE data_origin<>'synthetic_augmentation' OR data_origin IS NULL"
        ) == 0,
        "integrity_ok": integrity == "ok",
    }
    metadata = dict(connection.execute("SELECT key, value FROM _generation_metadata"))
    checks["scenario_s0"] = json.loads(metadata["scenario_id"]) == "S0"
    checks["observed_like"] = json.loads(metadata["sample_set_type"]) == "observed_like"
    connection.close()
    return checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--synthetic", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    source_hash_before = sha256(args.source)
    original, original_counts, original_integrity, original_coverage = metrics(args.source)
    synthetic, synthetic_counts, synthetic_integrity, synthetic_coverage = metrics(args.synthetic)
    checks = structural_checks(args.synthetic, synthetic_counts, synthetic_integrity)
    comparisons = []
    for name in original:
        difference_pp = (synthetic[name]["rate"] - original[name]["rate"]) * 100
        comparisons.append(
            {
                "metric": name,
                "original": original[name],
                "synthetic": synthetic[name],
                "difference_pp": difference_pp,
                "abs_difference_pp": abs(difference_pp),
                "tolerance_pp": 3.0 if name in CORE_METRICS else None,
                "pass": abs(difference_pp) <= 3.0 if name in CORE_METRICS else None,
            }
        )
    core = [item for item in comparisons if item["metric"] in CORE_METRICS]
    source_hash_after = sha256(args.source)
    gates = {
        "G1_structure": "PASS" if all(checks.values()) else "FAIL",
        "G2_semantic_integrity": "PASS" if all(
            checks[name]
            for name in ["room_hotel_mismatch_0", "unexposed_click_0", "invalid_stay_0", "zero_result_behavior_0", "integrity_ok"]
        ) else "FAIL",
        "G3_core_metric_similarity": "PASS" if all(item["pass"] for item in core) else "FAIL",
        "G4_source_preservation": "PASS" if source_hash_before == source_hash_after == config["source_db_sha256"] else "FAIL",
        "G5_scope_and_provenance": "PASS" if all(
            checks[name] for name in ["booking_0", "synthetic_origin_only", "scenario_s0", "observed_like"]
        ) else "FAIL",
    }
    final_status = "PASS" if all(value == "PASS" for value in gates.values()) else "FAIL"
    result = {
        "run_id": config["stage2_bundle_run_id"],
        "ordering": "session_id, parsed search_time, search_id; stable chronological order",
        "source_db": {
            "path": str(args.source.resolve()),
            "sha256_before": source_hash_before,
            "sha256_after": source_hash_after,
            "preserved": source_hash_before == source_hash_after,
            "row_counts": original_counts,
            "coverage": original_coverage,
            "integrity": original_integrity,
        },
        "synthetic_db": {
            "path": str(args.synthetic.resolve()),
            "sha256": sha256(args.synthetic),
            "row_counts": synthetic_counts,
            "coverage": synthetic_coverage,
            "integrity": synthetic_integrity,
        },
        "structural_checks": checks,
        "corrected_metric_comparison": comparisons,
        "core_max_abs_difference_pp": max(item["abs_difference_pp"] for item in core),
        "gates": gates,
        "final_qa_status": final_status,
        "expansion_allowed": final_status == "PASS",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if final_status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
