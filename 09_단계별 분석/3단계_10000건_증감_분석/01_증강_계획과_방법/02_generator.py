#!/usr/bin/env python3
"""Config-driven paired dry-run generator.

This stage intentionally refuses populations above 200. It produces synthetic
scenario data, never observed A/B results, and never creates BOOKING rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import random
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema
import yaml


HERE = Path(__file__).resolve().parent
GENERATOR_PATH = Path(__file__).resolve()
SCHEMA_PATH = HERE / "02_schema.sql"
CONFIG_SCHEMA_PATH = HERE / "02_config_schema.json"
DATA_CLASS = "synthetic_dryrun"
DETERMINISTIC_RUN_TIME = "2026-09-07T00:00:00+00:00"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256(path),
    }


def resolve_from_config(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    with CONFIG_SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    jsonschema.Draft202012Validator(schema).validate(config)
    return config


def open_source(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    if conn.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise RuntimeError("query_only guard was not enabled")
    return conn


def package_versions() -> dict[str, str]:
    names = ["PyYAML", "jsonschema", "openpyxl"]
    versions = {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version}
    for name in names:
        versions[name] = importlib.metadata.version(name)
    return versions


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def filter_state(row: sqlite3.Row) -> str:
    price = row["price"] is not None
    rating = row["user_rating_min"] is not None
    amenity = (row["amenity_count"] or 0) > 0
    states = {
        (False, False, False): "none",
        (True, False, False): "price_only",
        (False, True, False): "rating_only",
        (False, False, True): "amenity_only",
        (True, False, True): "price_amenity",
        (True, True, False): "price_rating",
        (False, True, True): "rating_amenity",
        (True, True, True): "price_rating_amenity",
    }
    return states[(price, rating, amenity)]


def choose_intent(row: sqlite3.Row, rng: random.Random) -> str:
    # This is a scenario assignment proxy, not an observed user statement.
    weights = {
        "condition_keeper": 1.0,
        "location_flexible": 1.0 + (1.0 if row["region"] else 0.0),
        "budget_flexible": 1.0 + (2.0 if row["price"] is not None else 0.0),
        "option_flexible": 1.0 + (2.0 if (row["amenity_count"] or 0) > 0 else 0.0),
        "query_reframer": 1.0 + (1.0 if row["query_text"] else 0.0),
        "quick_solver": 1.0,
    }
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


POLICY_BY_INTENT = {
    "condition_keeper": "repeat_prevention",
    "location_flexible": "nearby_region",
    "budget_flexible": "price_expansion",
    "option_flexible": "required_option_reduction",
    "query_reframer": "related_query",
    "quick_solver": "stepwise_relaxation",
}

BEHAVIOR_BY_POLICY = {
    "repeat_prevention": "relax",
    "nearby_region": "region",
    "price_expansion": "relax",
    "required_option_reduction": "relax",
    "related_query": "query",
    "stepwise_relaxation": "relax",
}


def load_probability_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def beta_draw(rows: list[dict[str, str]], parameter_id: str, rng: random.Random) -> float:
    row = next(r for r in rows if r["parameter_id"] == parameter_id)
    return rng.betavariate(float(row["posterior_alpha"]), float(row["posterior_beta"]))


def dirichlet_draw(
    rows: list[dict[str, str]], prefix: str, rng: random.Random
) -> dict[str, float]:
    selected = [r for r in rows if r["parameter_id"].startswith(prefix)]
    values = {r["outcome"]: rng.gammavariate(float(r["posterior_alpha"]), 1.0) for r in selected}
    total = sum(values.values())
    return {key: value / total for key, value in values.items()}


def sample_key(weights: dict[str, float], rng: random.Random) -> str:
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


def fit_positive_lognormal(conn: sqlite3.Connection) -> tuple[float, float]:
    rows = conn.execute(
        """
        WITH o AS (
          SELECT search_time, total_result_count,
                 LEAD(search_id) OVER w AS next_id,
                 LEAD(search_time) OVER w AS next_time
          FROM search
          WINDOW w AS (PARTITION BY session_id ORDER BY search_time, search_id)
        )
        SELECT MAX(1, CAST(ROUND(
          (julianday(substr(next_time,1,19))-julianday(substr(search_time,1,19)))*86400
        ) AS INTEGER))
        FROM o WHERE total_result_count=0 AND next_id IS NOT NULL
        """
    ).fetchall()
    logs = [math.log(row[0]) for row in rows]
    mean = sum(logs) / len(logs)
    variance = sum((value - mean) ** 2 for value in logs) / max(1, len(logs) - 1)
    return mean, math.sqrt(variance)


def template_signature(row: sqlite3.Row) -> str:
    values = [
        row["destination"], row["query_text"], row["property_type"], row["property_grade"],
        row["user_rating_min"], row["price"], row["amenity_count"], row["region"],
    ]
    return hashlib.sha256(
        json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]


def allocate_templates(
    templates: list[sqlite3.Row], pair_count: int, cap_share: float, rng: random.Random
) -> list[sqlite3.Row]:
    cap = max(1, math.ceil(pair_count * cap_share))
    shuffled = templates[:]
    rng.shuffle(shuffled)
    used: Counter[str] = Counter()
    selected: list[sqlite3.Row] = []
    cursor = 0
    while len(selected) < pair_count:
        if cursor >= len(shuffled):
            rng.shuffle(shuffled)
            cursor = 0
        candidate = shuffled[cursor]
        cursor += 1
        key = candidate["search_id"]
        if used[key] >= cap:
            if all(used[row["search_id"]] >= cap for row in shuffled):
                raise RuntimeError("template concentration cap makes allocation impossible")
            continue
        used[key] += 1
        selected.append(candidate)
    return selected


def add_seconds(value: datetime, seconds: int) -> datetime:
    return value + timedelta(seconds=seconds)


def iso_kst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S KST")


def insert_event(
    out: sqlite3.Connection, ids: dict[str, int], run_id: str, user_id: str,
    session_id: str, search_id: str | None, event_type: str, event_at: datetime,
    hotel_id: str | None = None, policy: str | None = None,
) -> None:
    ids["event"] += 1
    out.execute(
        "INSERT INTO ActionEvent VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            f"AE{ids['event']:08d}", run_id, user_id, session_id, search_id,
            event_type, iso_kst(event_at), hotel_id, policy, DATA_CLASS,
        ),
    )


def generate(config_path: Path, output_path: Path, total_users: int) -> dict[str, Any]:
    config_path = config_path.resolve()
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(output_path)
    config = load_config(config_path)
    maximum = config["dry_run"]["max_total_users"]
    if total_users <= 0 or total_users > maximum or total_users % 2:
        raise ValueError(f"dry-run users must be even and between 2 and {maximum}")

    source_path = resolve_from_config(config_path, config["source"]["observed_db"])
    reference_path = resolve_from_config(config_path, config["source"]["reference_1000_db"])
    probability_path = resolve_from_config(config_path, config["source"]["probability_parameters"])
    for path, expected in [
        (source_path, config["source"]["observed_db_sha256"]),
        (reference_path, config["source"]["reference_1000_db_sha256"]),
    ]:
        if sha256(path) != expected:
            raise RuntimeError(f"source hash mismatch: {path.name}")

    source_before = fingerprint(source_path)
    reference_before = fingerprint(reference_path)
    code_hash = sha256(GENERATOR_PATH)
    config_hash = sha256(config_path)
    schema_hash = sha256(SCHEMA_PATH)
    probability_hash = sha256(probability_path)
    rng = random.Random(config["seed"])
    probability_rows = load_probability_rows(probability_path)

    source = open_source(source_path)
    source.row_factory = sqlite3.Row
    reference = open_source(reference_path)
    if reference.execute("SELECT COUNT(*) FROM booking").fetchone()[0] != 0:
        raise RuntimeError("reference 1000 DB BOOKING must be empty")

    templates = source.execute(
        """
        SELECT s.search_id, s.query_text, s.destination, s.total_result_count,
               sf.property_type, sf.property_grade, sf.user_rating_min, sf.price,
               sf.amenity_count, sf.region
        FROM search s JOIN search_filter sf USING(search_id)
        WHERE (SELECT COUNT(*) FROM search sx WHERE sx.session_id=s.session_id) >= 3
        ORDER BY s.search_id
        """
    ).fetchall()
    age_groups = [r[0] for r in source.execute("SELECT age_group FROM user WHERE age_group IS NOT NULL")]
    positive_counts = [
        min(config["generation"]["max_results_per_search"], r[0])
        for r in source.execute("SELECT total_result_count FROM search WHERE total_result_count>0")
    ]
    result_pool = source.execute(
        """
        SELECT sr.hotel_id, sr.room_id, sr.result_score
        FROM search_result sr JOIN room r ON r.room_id=sr.room_id
        WHERE r.hotel_id=sr.hotel_id
        GROUP BY sr.hotel_id
        ORDER BY sr.hotel_id
        """
    ).fetchall()
    mu, sigma = fit_positive_lognormal(source)

    p_zero = beta_draw(probability_rows, "p_zero_result_rate", rng)
    p_followup = beta_draw(probability_rows, "p_zero_followup_rate", rng)
    p_rank1_detail = beta_draw(probability_rows, "p_card_h_rank1_detail_event", rng)
    behavior_weights = dirichlet_draw(probability_rows, "dirichlet_behavior_", rng)
    recovery_by_behavior = {
        behavior: beta_draw(probability_rows, f"p_behavior_{behavior}_recovery", rng)
        for behavior in behavior_weights
    }
    detail_by_behavior = {
        behavior: beta_draw(probability_rows, f"p_behavior_{behavior}_detail", rng)
        for behavior in behavior_weights
    }

    pair_count = total_users // 2
    chosen_templates = allocate_templates(
        templates, pair_count, config["generation"]["max_template_share"], rng
    )
    partial = output_path.with_name(output_path.name + f".partial.{os.getpid()}")
    if partial.exists():
        partial.unlink()
    out: sqlite3.Connection | None = None
    try:
        out = sqlite3.connect(partial)
        out.execute("PRAGMA foreign_keys=ON")
        out.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        run_id = config["scenario"]["run_id"]
        out.execute(
            "INSERT INTO SimulationRun VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id, config["scenario"]["name"], config["scenario"]["effect_level"],
                config["seed"], total_users, pair_count,
                config["source"]["observed_db_sha256"],
                config["source"]["reference_1000_db_sha256"],
                code_hash, config_hash, schema_hash,
                json.dumps(package_versions(), sort_keys=True),
                DETERMINISTIC_RUN_TIME, None,
            ),
        )
        ids = {"event": 0, "result": 0, "transition": 0}
        effects = config["effects"][config["scenario"]["effect_level"]]
        base_epoch = datetime(2028, 1, 1, 9, 0, 0)

        for pair_index, template in enumerate(chosen_templates, start=1):
            pair_id = f"P{pair_index:05d}"
            intent = choose_intent(template, rng)
            state = filter_state(template)
            policy = POLICY_BY_INTENT[intent]
            signature = template_signature(template)
            common_zero_u = rng.random()
            common_follow_u = rng.random()
            common_behavior_u = rng.random()
            common_recovery_u = rng.random()
            common_detail_u = rng.random()
            pair_offset = rng.randint(0, 365 * 24 * 3600)
            age_group = rng.choice(age_groups) if age_groups else None

            for arm_index, arm in enumerate(("control", "treatment")):
                user_id = f"U{pair_index:05d}{'C' if arm=='control' else 'T'}"
                session_id = f"S{pair_index:05d}{'C' if arm=='control' else 'T'}"
                assignment_id = f"A{pair_index:05d}{'C' if arm=='control' else 'T'}"
                assigned_at = base_epoch + timedelta(seconds=pair_offset, microseconds=arm_index)
                out.execute(
                    "INSERT INTO UserProfile VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        user_id, pair_id, arm, age_group,
                        template["destination"], state, intent, template["search_id"],
                        signature, DATA_CLASS,
                    ),
                )
                out.execute(
                    "INSERT INTO ExperimentAssignment VALUES (?,?,?,?,?,?,?)",
                    (
                        assignment_id, run_id, user_id, pair_id, arm,
                        policy if arm == "treatment" else "none", iso_kst(assigned_at),
                    ),
                )
                start_at = assigned_at + timedelta(seconds=1)
                insert_event(out, ids, run_id, user_id, session_id, None, "session_start", start_at)
                if arm == "treatment":
                    insert_event(
                        out, ids, run_id, user_id, session_id, None,
                        "treatment_exposure", start_at + timedelta(milliseconds=500),
                        policy=policy,
                    )

                first_zero = common_zero_u < p_zero
                has_followup = first_zero and common_follow_u < p_followup
                behavior = sample_key(behavior_weights, random.Random(int(common_behavior_u * 2**31)))
                if arm == "treatment":
                    target = BEHAVIOR_BY_POLICY[policy]
                    if behavior == "same" and common_behavior_u < effects["repeat_reduction_pp"]:
                        behavior = target
                    elif common_behavior_u < effects["recovery_lift_pp"]:
                        behavior = target
                base_recovery = recovery_by_behavior[behavior]
                recovery_probability = clamp(
                    base_recovery + (effects["recovery_lift_pp"] if arm == "treatment" else 0.0),
                    0.0, 1.0,
                )
                recovered = has_followup and common_recovery_u < recovery_probability
                detail_probability = clamp(
                    detail_by_behavior[behavior]
                    + (effects["detail_lift_pp"] if arm == "treatment" and recovered else 0.0),
                    0.0, 1.0,
                )
                detail_after_recovery = recovered and common_detail_u < detail_probability

                search_specs = [(first_zero, False)]
                if has_followup:
                    search_specs.append((not recovered, detail_after_recovery))
                current_at = start_at + timedelta(seconds=1)
                first_result_count = 0
                any_detail = False
                previous_search_id: str | None = None
                last_event_at = current_at
                for seq, (is_zero, detail_flag) in enumerate(search_specs, start=1):
                    search_id = f"Q{pair_index:05d}{'C' if arm=='control' else 'T'}{seq:02d}"
                    result_count = 0 if is_zero else rng.choice(positive_counts)
                    if seq == 1:
                        first_result_count = result_count
                    price = template["price"]
                    rating = template["user_rating_min"]
                    amenity = template["amenity_count"]
                    destination = template["destination"]
                    query_text = template["query_text"]
                    if seq > 1:
                        if behavior == "region":
                            destination = f"{destination or 'UNKNOWN'}_NEARBY"
                        elif behavior == "query":
                            query_text = ((query_text or destination or "hotel") + " 추천").strip()
                        elif behavior == "relax":
                            if price is not None:
                                price = int(price * 1.2)
                            elif amenity:
                                amenity = max(0, amenity - 1)
                            else:
                                rating = max(0.0, (rating or 8.0) - 1.0)
                        elif behavior == "strengthen":
                            if price is not None:
                                price = max(1, int(price * 0.8))
                            else:
                                amenity = (amenity or 0) + 1
                        elif behavior == "mixed":
                            price = int((price or 200000) * 1.2)
                            amenity = (amenity or 0) + 1
                    out.execute(
                        "INSERT INTO Search VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            search_id, run_id, user_id, pair_id, session_id, seq,
                            iso_kst(current_at), query_text, destination, price, rating,
                            amenity, result_count, state, intent, DATA_CLASS,
                        ),
                    )
                    insert_event(
                        out, ids, run_id, user_id, session_id, search_id,
                        "search_submit", current_at,
                    )
                    selected_hotel: str | None = None
                    max_exposure_at = current_at
                    if result_count:
                        sampled_results = rng.sample(result_pool, result_count)
                        for rank, candidate in enumerate(sampled_results, start=1):
                            ids["result"] += 1
                            exposed_at = current_at + timedelta(seconds=rank)
                            score = clamp(
                                float(candidate["result_score"]) + rng.gauss(
                                    0, config["generation"]["continuous_jitter"]["result_score_sd"]
                                ),
                                config["generation"]["continuous_jitter"]["clip_min"],
                                config["generation"]["continuous_jitter"]["clip_max"],
                            )
                            out.execute(
                                "INSERT INTO SearchResult VALUES (?,?,?,?,?,?,?)",
                                (
                                    f"SR{ids['result']:09d}", search_id, rank,
                                    candidate["hotel_id"], candidate["room_id"], score,
                                    iso_kst(exposed_at),
                                ),
                            )
                            insert_event(
                                out, ids, run_id, user_id, session_id, search_id,
                                "hotel_impression", exposed_at, candidate["hotel_id"],
                            )
                            max_exposure_at = exposed_at
                            if rank == 1:
                                selected_hotel = candidate["hotel_id"]
                    do_detail = detail_flag or (
                        seq == 1 and not first_zero and common_detail_u < p_rank1_detail
                    )
                    if do_detail and selected_hotel:
                        click_at = max_exposure_at + timedelta(seconds=1)
                        detail_at = click_at + timedelta(seconds=1)
                        insert_event(
                            out, ids, run_id, user_id, session_id, search_id,
                            "hotel_click", click_at, selected_hotel,
                        )
                        insert_event(
                            out, ids, run_id, user_id, session_id, search_id,
                            "hotel_detail_view", detail_at, selected_hotel,
                        )
                        any_detail = True
                        last_event_at = detail_at
                    else:
                        last_event_at = max_exposure_at
                    if previous_search_id is not None:
                        ids["transition"] += 1
                        gap = int((current_at - previous_at).total_seconds())
                        out.execute(
                            "INSERT INTO SearchTransition VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                f"T{ids['transition']:08d}", run_id, user_id, session_id,
                                previous_search_id, search_id, seq - 1, behavior, gap,
                                int(recovered), int(detail_after_recovery),
                            ),
                        )
                    previous_search_id = search_id
                    previous_at = current_at
                    if seq < len(search_specs):
                        raw_gap = int(round(rng.lognormvariate(mu, sigma)))
                        gap = int(clamp(
                            raw_gap,
                            config["generation"]["interarrival"]["min_seconds"],
                            config["generation"]["interarrival"]["max_seconds"],
                        ))
                        current_at = add_seconds(current_at, gap)

                end_at = last_event_at + timedelta(seconds=1)
                insert_event(out, ids, run_id, user_id, session_id, None, "session_end", end_at)
                if not first_zero:
                    outcome = "SG1" if any_detail else "SG2"
                else:
                    outcome = "SG3" if recovered else "SG4"
                out.execute(
                    "INSERT INTO SessionSummary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        session_id, run_id, user_id, pair_id, arm, iso_kst(start_at),
                        iso_kst(end_at), len(search_specs), first_result_count,
                        int(first_zero), int(recovered), int(any_detail), outcome, DATA_CLASS,
                    ),
                )

        out.execute(
            "UPDATE SimulationRun SET completed_at_utc=? WHERE run_id=?",
            (DETERMINISTIC_RUN_TIME, run_id),
        )
        metadata = {
            "artifact_class": DATA_CLASS,
            "booking_policy": "PROHIBITED",
            "code_sha256": code_hash,
            "config_sha256": config_hash,
            "schema_sha256": schema_hash,
            "probability_parameters_sha256": probability_hash,
            "source_db_sha256": source_before["sha256"],
            "reference_1000_db_sha256": reference_before["sha256"],
            "seed": str(config["seed"]),
            "run_id": run_id,
            "total_users": str(total_users),
            "pair_count": str(pair_count),
            "scenario_assumption": json.dumps(config["effects"][config["scenario"]["effect_level"]], sort_keys=True),
            "drawn_probabilities": json.dumps(
                {
                    "p_zero": p_zero, "p_followup": p_followup,
                    "p_rank1_detail": p_rank1_detail,
                    "behavior_weights": behavior_weights,
                    "recovery_by_behavior": recovery_by_behavior,
                    "detail_by_behavior": detail_by_behavior,
                }, sort_keys=True,
            ),
            "package_versions": json.dumps(package_versions(), sort_keys=True),
            "created_at_utc": DETERMINISTIC_RUN_TIME,
        }
        out.executemany(
            "INSERT INTO _generation_metadata(key,value) VALUES (?,?)",
            sorted(metadata.items()),
        )
        fk_errors = out.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise RuntimeError(f"foreign key errors: {fk_errors[:3]}")
        out.commit()
        out.execute("PRAGMA optimize")
        out.close()
        out = None
        source.close()
        reference.close()

        if fingerprint(source_path) != source_before or fingerprint(reference_path) != reference_before:
            raise RuntimeError("source immutability check failed")
        os.replace(partial, output_path)
        return {
            "output": str(output_path),
            "users": total_users,
            "pairs": pair_count,
            "code_sha256": code_hash,
            "config_sha256": config_hash,
            "schema_sha256": schema_hash,
            "source_unchanged": True,
            "reference_unchanged": True,
        }
    except Exception:
        if out is not None:
            out.close()
        source.close()
        reference.close()
        if partial.exists():
            partial.unlink()
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=HERE / "02_base_config.yaml")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run-users", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config.resolve())
    users = args.dry_run_users or config["dry_run"]["default_total_users"]
    print(json.dumps(generate(args.config, args.output, users), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
