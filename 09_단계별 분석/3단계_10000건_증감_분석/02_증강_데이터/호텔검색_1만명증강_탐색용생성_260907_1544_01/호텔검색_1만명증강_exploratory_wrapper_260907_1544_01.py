#!/usr/bin/env python3
"""One-run exploratory authorization wrapper. It does not grant strict production approval."""
import argparse
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

GENERATOR_V02_SHA = "150b7bae317809c0007335311b41bdff663e7f81d4b9fbab1083bdfc01fcbd56"
SEQUENTIAL_V06_SHA = "83c11424c1a5dfa0fc3276424de394e840ccd208f12d1faa7fff8d68044e6195"
EXPECTED_CONFIG_SHA = "32341f518e2edf251af08769aca11955e28d2e135bd6b0d24f4a995401b07a6b"
REFERENCE_SHA = "9120561ee85705141a92eae74c5015fb2c9a20f0c8d1f6df4d99893952fd1e9f"
PRODUCTION_SEED = 2434815518


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path, name, expected_sha):
    if sha256(path) != expected_sha:
        raise RuntimeError(name + " SHA mismatch")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_authorization(auth_path, manifest_path, config, output, mode, users, seed, scenario):
    if not auth_path:
        raise PermissionError("limited-use authorization required")
    authorization = json.loads(Path(auth_path).read_text(encoding="utf-8"))
    common_required = {
        "limited_use_status": "ACCEPTED_FOR_EXPLORATORY_SIMULATION_WITH_LIMITATIONS",
        "strict_calibration_status": "HOLD",
        "strict_calibration_passed": False,
        "execution_authorized": True,
        "general_production_approved": False,
        "scenario": "expected",
        "overwrite": False,
        "full_run_limit": 1,
    }
    for key, value in common_required.items():
        if authorization.get(key) != value:
            raise PermissionError("authorization mismatch: " + key)
    kind = authorization.get("authorization_kind")
    if kind == "limited_full_run":
        scope = {"purpose":"exploratory_ab_simulation","users":10000,"control_users":5000,"treatment_users":5000,"pairs":5000,"seed":PRODUCTION_SEED}
    elif kind == "interface_regression":
        scope = {"purpose":"interface_regression","users":200,"control_users":100,"treatment_users":100,"pairs":100,"seed":2026090712}
    else:
        raise PermissionError("authorization kind invalid")
    for key, value in scope.items():
        if authorization.get(key) != value:
            raise PermissionError("authorization scope mismatch: " + key)
    if (mode, users, seed, scenario) != ("production", scope["users"], scope["seed"], "expected"):
        raise PermissionError("execution scope mismatch")
    if sha256(config) != EXPECTED_CONFIG_SHA or authorization["config_sha256"] != EXPECTED_CONFIG_SHA:
        raise PermissionError("config SHA mismatch")
    if authorization["reference_sha256"] != REFERENCE_SHA:
        raise PermissionError("reference SHA mismatch")
    target = Path(output).resolve()
    if target != Path(authorization["allowed_output_file"]).resolve():
        raise PermissionError("output file not authorized")
    if target.exists():
        raise FileExistsError(target)
    if any(target.parent.iterdir()):
        raise PermissionError("authorized output directory is not empty")
    manifest = Path(manifest_path).resolve()
    if manifest != Path(authorization["execution_manifest_path"]).resolve():
        raise PermissionError("manifest path mismatch")
    if sha256(manifest) != authorization["execution_manifest_sha256"]:
        raise PermissionError("manifest SHA mismatch")
    frozen = json.loads(manifest.read_text(encoding="utf-8"))
    for role, item in frozen["files"].items():
        if sha256(item["path"]) != item["sha256"]:
            raise PermissionError("frozen dependency changed: " + role)
    return authorization


def stored_signature(plan):
    clean = []
    for item in plan:
        clean.append(item[:-1] if isinstance(item, tuple) and len(item) == 9 else item)
    return json.dumps(clean, sort_keys=True, default=str)


def generate(args):
    authorization = validate_authorization(
        args.authorization, args.manifest, args.config, args.output,
        args.mode, args.users, args.seed, args.scenario,
    )
    base = load(args.v02_generator, "approved_v02", GENERATOR_V02_SHA)
    sequential = load(args.sequential_generator, "approved_sequential_v06", SEQUENTIAL_V06_SHA)
    base.SCHEMA = Path(args.schema)
    base.state_plan = sequential.sequential_plan
    base.business_signature = stored_signature

    def limited_guard(config, mode, users, seed, output):
        validate_authorization(
            args.authorization, args.manifest, args.config, output,
            mode, users, seed, args.scenario,
        )

    base.guard = limited_guard
    result = base.generate(args.config, args.output, args.mode, args.users, args.seed)
    connection = sqlite3.connect(result)
    metadata = {
        "limited_use_status": "ACCEPTED_FOR_EXPLORATORY_SIMULATION_WITH_LIMITATIONS",
        "strict_calibration_status": "HOLD",
        "strict_calibration_passed": "false",
        "exception_code": "ZERO_RATE_SEED_COVERAGE_16_OF_20",
        "purpose": "exploratory_ab_simulation",
        "interpretation": "synthetic scenario contrast; not observed A/B causal effect",
        "full_run_limit": "1",
        "authorization_sha256": sha256(args.authorization),
        "execution_manifest_sha256": sha256(args.manifest),
    }
    connection.executemany(
        "INSERT INTO _generation_metadata(key,value) VALUES(?,?)", metadata.items()
    )
    connection.commit()
    connection.close()
    return result


def parser():
    p = argparse.ArgumentParser()
    for name in ("v02-generator", "sequential-generator", "schema", "config", "output", "authorization", "manifest", "mode", "scenario"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--users", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    return p


if __name__ == "__main__":
    generate(parser().parse_args())
