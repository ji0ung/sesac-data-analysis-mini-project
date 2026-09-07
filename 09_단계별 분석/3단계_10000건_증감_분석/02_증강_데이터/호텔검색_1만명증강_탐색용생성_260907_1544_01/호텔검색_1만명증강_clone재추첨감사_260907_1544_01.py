#!/usr/bin/env python3
"""Read-only deterministic replay of the approved pre-commit clone redraw loop."""
import hashlib
import importlib.util
import json
import random
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "호텔검색_1만명증강_실행파일manifest_260907_1544_01.json"
DATABASE = ROOT / "output" / "호텔검색_1만명증강_탐색용AB10000_260907_1544_01.sqlite"
OUTPUT = ROOT / "호텔검색_1만명증강_clone재추첨감사_260907_1544_01.json"
SEED = 2434815518


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    frozen = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    for role in ("v02", "seq", "config", "ref"):
        assert sha256(frozen[role]["path"]) == frozen[role]["sha256"], role
    base = load(frozen["v02"]["path"], "clone_replay_v02")
    seq = load(frozen["seq"]["path"], "clone_replay_seq")
    base.SCHEMA = Path(frozen["schema"]["path"])
    config, reference = base.load_config(frozen["config"]["path"])
    profile = base.reference_profile(reference)
    seen = {"control": set(), "treatment": set()}
    redraws = Counter()
    attempts = Counter()
    searches = Counter()
    zeros = Counter()
    failures = []
    for pair_index in range(5000):
        common = random.Random(base.seedof(SEED, pair_index, "common"))
        region = common.choice(["metro", "coastal", "inland", "island"])
        price = common.choice([None, 80000, 120000, 180000])
        amenity = common.choice([0, 1, 2, 3])
        common.choice(["low", "medium", "high"])
        common.choice(profile["sources"])
        first_query = common.choice(["hotel", "stay", "weekend", "family", "business"])
        first_date = common.randrange(1, 29)
        common_ever = common.random() < config["state_machine"]["ever_zero_probability"]
        common_first = common.random() < config["state_machine"]["first_zero_given_ever_zero"] if common_ever else False
        common_first_count = 0 if common_first else common.choice(profile["positive_counts"])
        common_first_hotels = tuple(common.sample(range(1, 1001), common_first_count))
        for arm in ("control", "treatment"):
            accepted = None
            for attempt in range(config["clone"]["max_redraw_attempts"]):
                rng = random.Random(base.seedof(SEED, pair_index, arm, attempt, "state"))
                plan, outcome = seq.sequential_plan(
                    rng, config, profile,
                    {"ever_zero": common_ever, "first_zero": common_first},
                    arm, config["scenario"],
                )
                values = []
                for index, state in enumerate(plan):
                    action = "initial" if index == 0 else (
                        "region_change" if arm == "treatment" and "ZERO" in plan[index - 1]
                        else rng.choice(["same_condition", "constraint_relax", "query_change", "region_change"])
                    )
                    count = common_first_count if index == 0 else (
                        0 if state in ("FIRST_SEARCH_ZERO", "FOLLOWUP_ZERO", "PERSISTENT_FAILURE")
                        else rng.choice(profile["positive_counts"])
                    )
                    hotels = common_first_hotels if index == 0 else tuple(rng.sample(range(1, 1001), count))
                    values.append((state, action, count, hotels, region, price, amenity, first_query, first_date))
                signature = json.dumps(
                    [item[:-1] if isinstance(item, tuple) and len(item) == 9 else item for item in values + [outcome]],
                    sort_keys=True, default=str,
                )
                if signature not in seen[arm]:
                    seen[arm].add(signature)
                    accepted = (attempt, values)
                    break
            if accepted is None:
                failures.append({"pair_index": pair_index, "arm": arm})
                continue
            attempt, values = accepted
            redraws[arm] += attempt
            attempts[(arm, attempt + 1)] += 1
            searches[arm] += len(values)
            zeros[arm] += sum(value[2] == 0 for value in values)
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    observed = {}
    for arm in ("control", "treatment"):
        observed[arm] = {
            "searches": connection.execute(
                "SELECT COUNT(*) FROM Search s JOIN SessionSynthetic x USING(session_id) JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type=?", (arm,)
            ).fetchone()[0],
            "zero_searches": connection.execute(
                "SELECT COUNT(*) FROM Search s JOIN SessionSynthetic x USING(session_id) JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type=? AND s.total_result_count=0", (arm,)
            ).fetchone()[0],
        }
    connection.close()
    replay = {arm: {"searches": searches[arm], "zero_searches": zeros[arm]} for arm in ("control", "treatment")}
    result = {
        "purpose": "deterministic read-only replay of approved internal clone collision redraw",
        "production_database_sha256_before": sha256(DATABASE),
        "seed": SEED,
        "pairs": 5000,
        "sessions": 10000,
        "max_redraw_attempts": config["clone"]["max_redraw_attempts"],
        "collision_redraw_count": dict(redraws),
        "collision_redraw_total": sum(redraws.values()),
        "accepted_attempt_distribution": {
            arm: {str(attempt): attempts[(arm, attempt)] for attempt in range(1, config["clone"]["max_redraw_attempts"] + 1) if attempts[(arm, attempt)]}
            for arm in ("control", "treatment")
        },
        "redraw_failure_count": len(failures),
        "redraw_failures": failures,
        "replayed_counts": replay,
        "database_counts": observed,
        "exact_replay_match": replay == observed,
        "production_database_sha256_after": sha256(DATABASE),
    }
    result["database_unchanged"] = result["production_database_sha256_before"] == result["production_database_sha256_after"]
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
