#!/usr/bin/env python3
"""History-aware Z/P/END model with a separately calibrated first-Z transition."""
import hashlib
import importlib.util
from pathlib import Path

V05_SHA = "0a25be0996ce4ccd56d47a2e4dd478decb074844f88e2dd37e17097fb8ec5bd3"


def load(path):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != V05_SHA:
        raise RuntimeError("v05 SHA mismatch")
    spec = importlib.util.spec_from_file_location("v05", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sequential_plan(rng, config, profile, force=None, arm="control", scenario="expected"):
    transition = config["sequential_transition"]
    force = force or {}
    first_zero = force.get(
        "first_zero", rng.random() < transition["first_zero_probability"]
    )
    states = ["FIRST_SEARCH_ZERO" if first_zero else "FIRST_SEARCH_POSITIVE"]
    current = "Z" if first_zero else "P"
    ever_zero = first_zero
    current_is_first_zero = first_zero

    while len(states) < config["state_machine"]["max_searches"]:
        u = rng.random()
        if current == "Z":
            if current_is_first_zero:
                end_probability = transition["first_z_to_end"]
                recovery_probability = transition["first_z_to_p"]
            else:
                end_probability = transition["later_z_to_end"]
                recovery_probability = transition["later_z_to_p"]
            if arm == "treatment":
                recovery_probability += transition["treatment_recovery_uplift"][scenario]
            zero_probability = 1.0 - end_probability - recovery_probability
            if u < end_probability:
                break
            next_state = "Z" if u < end_probability + zero_probability else "P"
        else:
            end_probability = transition["p_to_end"]
            zero_probability = (
                transition["p_to_z_after_zero"]
                if ever_zero
                else transition["p_to_z_before_zero"]
            )
            if u < end_probability:
                break
            next_state = "Z" if u < end_probability + zero_probability else "P"

        states.append(
            "IMMEDIATE_RECOVERY"
            if current == "Z" and next_state == "P"
            else ("FOLLOWUP_ZERO" if next_state == "Z" else "CONTINUED_SEARCH")
        )
        current = next_state
        current_is_first_zero = next_state == "Z" and not ever_zero
        ever_zero = ever_zero or next_state == "Z"

    outcome = "SG1" if not ever_zero else ("SG3" if current == "P" else "SG4")
    return states, outcome


def generate(v05_generator, *args):
    module = load(v05_generator)
    module.sequential_plan = sequential_plan
    return module.generate(*args)
