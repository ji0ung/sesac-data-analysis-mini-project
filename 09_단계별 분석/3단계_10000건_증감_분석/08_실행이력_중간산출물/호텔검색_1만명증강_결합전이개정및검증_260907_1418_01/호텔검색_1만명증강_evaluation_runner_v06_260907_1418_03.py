#!/usr/bin/env python3
"""Frozen STEP 2.11 evaluator. Production mode and production seed are prohibited."""
import argparse
import hashlib
import importlib.util
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PRODUCTION_SEED = 2434815518
INTERVALS = {
    "search_zero_rate": (0.485888, 0.509477),
    "zero_followup_rate": (0.944902, 0.959154),
    "immediate_recovery_transition_rate": (0.158088, 0.183871),
    "final_recovery_rate": (0.714909, 0.781366),
    "card_h_search_rate": (0.183310, 0.209750),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ro(path):
    connection = sqlite3.connect("file:" + Path(path).resolve().as_posix() + "?mode=ro", uri=True)
    connection.execute("pragma query_only=on")
    return connection


def scoped_metrics(db_path, arm):
    connection = ro(db_path)
    params = (arm,)
    rows = connection.execute(
        """
        WITH ordered AS (
          SELECT s.*, LEAD(s.total_result_count) OVER (
            PARTITION BY s.session_id
            ORDER BY s.search_sequence,s.search_time,s.search_id
          ) AS next_count
          FROM Search s
          JOIN SessionSynthetic ss USING(session_id)
          JOIN UserSynthetic u USING(user_id)
          WHERE u.sample_set_type=?
        ), first_zero AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY session_id ORDER BY search_sequence,search_id
          ) AS zero_rank
          FROM ordered WHERE total_result_count=0
        ), last_state AS (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY session_id ORDER BY search_sequence DESC,search_time DESC,search_id DESC
          ) AS reverse_rank,
          MAX(total_result_count=0) OVER(PARTITION BY session_id) AS ever_zero
          FROM ordered
        ), positive AS (
          SELECT DISTINCT search_id FROM ordered WHERE total_result_count>0
        ), rank1_detail AS (
          SELECT DISTINCT e.search_id
          FROM SearchResult r
          JOIN ActionEvent e ON e.search_id=r.search_id AND e.hotel_id=r.hotel_id
          JOIN ordered o ON o.search_id=r.search_id
          WHERE r.result_rank=1 AND e.event_type='hotel_detail_view'
        )
        SELECT
          SUM(total_result_count=0), COUNT(*),
          SUM(total_result_count=0 AND next_count IS NOT NULL),
          SUM(total_result_count=0 AND next_count>0),
          (SELECT SUM(zero_rank=1 AND next_count>0) FROM first_zero),
          (SELECT SUM(zero_rank=1 AND next_count IS NOT NULL) FROM first_zero),
          (SELECT SUM(reverse_rank=1 AND ever_zero=1 AND total_result_count>0) FROM last_state),
          (SELECT SUM(reverse_rank=1 AND ever_zero=1) FROM last_state),
          (SELECT COUNT(*) FROM rank1_detail),
          (SELECT COUNT(*) FROM positive)
        FROM ordered
        """,
        params,
    ).fetchone()
    event_rows = connection.execute(
        """
        SELECT COUNT(*)
        FROM Search s
        JOIN SessionSynthetic ss USING(session_id)
        JOIN UserSynthetic u USING(user_id)
        JOIN SearchResult r ON r.search_id=s.search_id AND r.result_rank=1
        JOIN ActionEvent e ON e.search_id=s.search_id AND e.hotel_id=r.hotel_id
        WHERE u.sample_set_type=? AND s.total_result_count>0
          AND e.event_type='hotel_detail_view'
        """,
        params,
    ).fetchone()[0]
    connection.close()
    zero_n, search_n, follow_n, immediate_n, first_n, first_d, final_n, final_d, h_n, h_d = rows
    pairs = {
        "search_zero_rate": (zero_n, search_n),
        "zero_followup_rate": (follow_n, zero_n),
        "immediate_recovery_transition_rate": (immediate_n, follow_n),
        "first_zero_immediate_recovery_rate": (first_n, first_d),
        "final_recovery_rate": (final_n, final_d),
        "card_h_search_rate": (h_n, h_d),
        "card_h_event_rows": (event_rows, None),
    }
    return {
        key: {
            "numerator": numerator,
            "denominator": denominator,
            "value": None if denominator in (None, 0) else numerator / denominator,
            "interval_pass": (
                None
                if key not in INTERVALS
                else INTERVALS[key][0] <= numerator / denominator <= INTERVALS[key][1]
            ),
        }
        for key, (numerator, denominator) in pairs.items()
    }


def transitions(db_path, arm):
    connection = ro(db_path)
    states = connection.execute(
        """
        WITH o AS (
          SELECT s.session_id,s.search_sequence,s.total_result_count,
                 LEAD(s.total_result_count) OVER(
                   PARTITION BY s.session_id ORDER BY s.search_sequence,s.search_time,s.search_id
                 ) AS nxt
          FROM Search s JOIN SessionSynthetic ss USING(session_id)
          JOIN UserSynthetic u USING(user_id)
          WHERE u.sample_set_type=?
        )
        SELECT
          SUM(total_result_count=0 AND nxt=0),
          SUM(total_result_count=0 AND nxt>0),
          SUM(total_result_count=0 AND nxt IS NULL),
          SUM(total_result_count>0 AND nxt=0),
          SUM(total_result_count>0 AND nxt>0),
          SUM(total_result_count>0 AND nxt IS NULL),
          COUNT(*)
        FROM o
        """,
        (arm,),
    ).fetchone()
    sessions = connection.execute(
        """
        WITH o AS (
          SELECT s.*, ROW_NUMBER() OVER(PARTITION BY s.session_id ORDER BY s.search_sequence) AS rn,
                 ROW_NUMBER() OVER(PARTITION BY s.session_id ORDER BY s.search_sequence DESC) AS rr,
                 MAX(s.total_result_count=0) OVER(PARTITION BY s.session_id) AS ever_zero
          FROM Search s JOIN SessionSynthetic ss USING(session_id)
          JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type=?
        )
        SELECT SUM(rn=1 AND total_result_count=0),SUM(rn=1 AND total_result_count>0),
               COUNT(DISTINCT CASE WHEN ever_zero=1 THEN session_id END),
               COUNT(DISTINCT CASE WHEN ever_zero=0 THEN session_id END),
               SUM(rr=1 AND ever_zero=1 AND total_result_count>0),
               SUM(rr=1 AND ever_zero=1 AND total_result_count=0),COUNT(*)*1.0/COUNT(DISTINCT session_id)
        FROM o
        """,
        (arm,),
    ).fetchone()
    first_zero = connection.execute(
        """
        WITH o AS (
          SELECT s.*, LEAD(total_result_count) OVER(PARTITION BY s.session_id ORDER BY s.search_sequence) nxt
          FROM Search s JOIN SessionSynthetic ss USING(session_id)
          JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type=?
        ), z AS (
          SELECT *,ROW_NUMBER() OVER(PARTITION BY session_id ORDER BY search_sequence) zr
          FROM o WHERE total_result_count=0
        )
        SELECT SUM(zr=1 AND nxt=0),SUM(zr=1 AND nxt>0),SUM(zr=1 AND nxt IS NULL) FROM z
        """,
        (arm,),
    ).fetchone()
    lengths = connection.execute(
        """
        SELECT n,COUNT(*) FROM (
          SELECT s.session_id,COUNT(*) n FROM Search s JOIN SessionSynthetic ss USING(session_id)
          JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type=? GROUP BY s.session_id
        ) GROUP BY n ORDER BY n
        """,
        (arm,),
    ).fetchall()
    connection.close()
    return {
        "Z_to_Z": states[0], "Z_to_P": states[1], "Z_to_END": states[2],
        "P_to_Z": states[3], "P_to_P": states[4], "P_to_END": states[5],
        "searches": states[6], "first_Z": sessions[0], "first_P": sessions[1],
        "ever_Z": sessions[2], "never_Z": sessions[3], "final_recovered": sessions[4],
        "final_Z": sessions[5], "average_searches": sessions[6],
        "first_Z_to_Z": first_zero[0], "first_Z_to_P": first_zero[1],
        "first_Z_to_END": first_zero[2], "length_distribution": dict(lengths),
    }


def structural_qa(db_path):
    connection = ro(db_path)
    one = lambda sql: connection.execute(sql).fetchone()[0]
    result = {
        "users": one("SELECT COUNT(*) FROM UserSynthetic"),
        "control_users": one("SELECT COUNT(*) FROM UserSynthetic WHERE sample_set_type='control'"),
        "treatment_users": one("SELECT COUNT(*) FROM UserSynthetic WHERE sample_set_type='treatment'"),
        "complete_pairs": one("SELECT COUNT(*) FROM (SELECT pair_id FROM UserSynthetic GROUP BY pair_id HAVING COUNT(*)=2 AND COUNT(DISTINCT sample_set_type)=2)"),
        "pair_pre_attribute_mismatch": one("SELECT COUNT(*) FROM (SELECT pair_id FROM UserSynthetic GROUP BY pair_id HAVING COUNT(DISTINCT sample_stratum)>1 OR COUNT(DISTINCT source_session_id)>1)"),
        "booking_rows": one("SELECT COUNT(*) FROM Booking"),
        "control_treatment_leakage": one("SELECT COUNT(*) FROM SessionSynthetic ss JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type='control' AND ss.treatment_exposed<>0"),
        "sample_set_null_or_other": one("SELECT COUNT(*) FROM UserSynthetic WHERE sample_set_type IS NULL OR sample_set_type NOT IN('control','treatment')"),
    }
    connection.close()
    return result


def run(args):
    if args.mode != "calibration" or args.seed == PRODUCTION_SEED:
        raise PermissionError("production execution is prohibited")
    generator = load(args.generator, "frozen_generator")
    generator.generate(
        args.v05_generator, args.v04_generator, args.v02_generator, args.auth_wrapper,
        args.schema, args.config, args.output, args.authorization,
        args.mode, 2000, args.seed, args.scenario,
    )
    gate_module = load(args.gate, "integrated_gate")
    gate = gate_module.gate(
        args.output, args.reference, args.contract, args.metric_module,
        args.clone_adapter, args.clone_audit,
    )
    sidecar = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "classification": "synthetic scenario simulation; not an observed A/B result",
        "scenario": args.scenario,
        "seed": args.seed,
        "production_seed_used": False,
        "db_path": str(Path(args.output).resolve()),
        "db_sha256": sha256(args.output),
        "db_bytes": Path(args.output).stat().st_size,
        "control_metrics": scoped_metrics(args.output, "control"),
        "treatment_metrics": scoped_metrics(args.output, "treatment"),
        "control_transitions": transitions(args.output, "control"),
        "treatment_transitions": transitions(args.output, "treatment"),
        "structural_qa": structural_qa(args.output),
        "integrated_gate": gate,
    }
    sidecar_path = Path(args.output).with_suffix(".sidecar.json")
    if sidecar_path.exists():
        raise FileExistsError(sidecar_path)
    sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"scenario": args.scenario, "seed": args.seed, "status": gate["status"], "sidecar": str(sidecar_path)}, ensure_ascii=False))


def parser():
    p = argparse.ArgumentParser()
    for name in (
        "generator", "v05-generator", "v04-generator", "v02-generator", "auth-wrapper",
        "schema", "config", "output", "authorization", "mode", "scenario", "gate",
        "reference", "contract", "metric-module", "clone-adapter", "clone-audit",
    ):
        p.add_argument("--" + name, required=True)
    p.add_argument("--seed", required=True, type=int)
    return p


if __name__ == "__main__":
    run(parser().parse_args())
