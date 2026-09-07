#!/usr/bin/env python3
"""Quantifies known STEP 2.11 residual limitations from the frozen evaluation SQLite."""
import csv
import json
import sqlite3
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "호텔검색_1만명증강_통합평가결과_260907_1418_03.sqlite"
OUT_CSV = ROOT / "호텔검색_1만명증강_잔여한계정량영향_260907_1539_01.csv"
OUT_JSON = ROOT / "호텔검색_1만명증강_잔여한계정량영향_260907_1539_01.json"
REFERENCE = {
    "search_zero_rate": 3434 / 6900,
    "zero_followup_rate": 3271 / 3434,
    "immediate_recovery_transition_rate": 558 / 3271,
    "first_zero_immediate_recovery_rate": 69 / 628,
    "final_recovery_rate": 488 / 651,
    "card_h_search_rate": 680 / 3466,
}


def quantile(values, p):
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * p)]


def main():
    for path in (OUT_CSV, OUT_JSON):
        if path.exists():
            raise FileExistsError(path)
    connection = sqlite3.connect("file:" + INPUT.resolve().as_posix() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = []
    for metric, reference in REFERENCE.items():
        seeds = list(connection.execute(
            "SELECT seed,numerator,denominator,value,interval_pass FROM seed_metrics "
            "WHERE scenario='expected' AND arm='control' AND metric=? ORDER BY seed", (metric,)
        ))
        pooled_n = sum(row["numerator"] for row in seeds)
        pooled_d = sum(row["denominator"] for row in seeds)
        pooled = pooled_n / pooled_d
        projected_d = pooled_d / 20 * 5
        impacts = [(row["value"] - reference) * row["denominator"] * 5 for row in seeds]
        rows.append({
            "metric": metric,
            "reference_rate": reference,
            "expected20_pooled_rate": pooled,
            "difference_percentage_points": (pooled - reference) * 100,
            "seed_standard_deviation_pp": statistics.stdev(row["value"] for row in seeds) * 100,
            "production_control_expected_denominator": projected_d,
            "production_control_central_excess_numerator": (pooled - reference) * projected_d,
            "production_control_seed_min_excess_numerator": min(impacts),
            "production_control_seed_max_excess_numerator": max(impacts),
            "seed_p05_rate": quantile([row["value"] for row in seeds], .05),
            "seed_p95_rate": quantile([row["value"] for row in seeds], .95),
            "interval_fail_seed_count": sum(row["interval_pass"] == 0 for row in seeds) if metric != "first_zero_immediate_recovery_rate" else None,
            "severity": "HIGH" if metric == "search_zero_rate" else ("MEDIUM" if metric in ("immediate_recovery_transition_rate", "final_recovery_rate") else "LOW"),
        })
    transitions = list(connection.execute(
        "SELECT ever_Z,searches FROM transitions WHERE source='evaluation' AND scenario='expected' AND arm='control' ORDER BY seed"
    ))
    ever_z_rate = sum(row["ever_Z"] for row in transitions) / 20000
    avg_searches = sum(row["searches"] for row in transitions) / 20000
    structural = [
        {"metric":"ever_zero_session_rate","reference":0.651,"generated":ever_z_rate,"difference_percentage_points":(ever_z_rate-.651)*100,"projected_control_5000_difference":(ever_z_rate-.651)*5000},
        {"metric":"searches_per_session","reference":6.9,"generated":avg_searches,"difference_percentage_points":None,"projected_control_5000_difference":(avg_searches-6.9)*5000},
    ]
    connection.close()
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "input_sqlite": str(INPUT.resolve()),
        "scope": "projection for one future 5,000-user control arm; synthetic-model risk, not observed business impact",
        "metric_impacts": rows,
        "structural_impacts": structural,
        "single_seed_search_zero_interval_failure_frequency": "4/20 = 20% in frozen independent evaluation",
        "prohibited_interpretation": "Do not treat projected count differences as observed losses or causal effects.",
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
