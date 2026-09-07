#!/usr/bin/env python3
"""Read-only analysis of the 1,000-session observed-like synthetic SQLite."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sqlite3
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.api as sm
import statsmodels.formula.api as smf


TABLES = ["user", "hotel", "room", "search", "search_filter", "search_result", "event", "booking"]
TRANSITION_FIELDS = [
    "query_text", "destination", "property_type", "property_grade",
    "user_rating_min", "price", "amenity_count", "region",
]
SIGNATURE_FIELDS = [
    "query_text", "total_result_count", "sort_option", "guest_count",
    "destination", "property_type", "property_grade", "user_rating_min",
    "price", "amenity_count", "region",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def open_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
    return connection


def rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def metric(numerator: int, denominator: int, unit: str) -> dict:
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "rate": rate(int(numerator), int(denominator)),
        "analysis_unit": unit,
    }


def normalize(value) -> str | None:
    if pd.isna(value):
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    return text or None


def direction(old, new, lower_is_relaxation: bool) -> str | None:
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
    relaxed = decreased if lower_is_relaxation else not decreased
    return "relax" if relaxed else "strengthen"


def classify_transition(row: pd.Series) -> str:
    def equal(field: str) -> bool:
        old, new = row[field], row[f"next_{field}"]
        if field in {"user_rating_min", "price", "amenity_count"}:
            if pd.isna(old) and pd.isna(new):
                return True
            if pd.isna(old) or pd.isna(new):
                return False
            return float(old) == float(new)
        return normalize(old) == normalize(new)

    changed = [field for field in TRANSITION_FIELDS if not equal(field)]
    if not changed:
        return "동일조건 반복"
    if "destination" in changed or "region" in changed:
        return "지역 변경"
    if "query_text" in changed:
        return "검색어 변경"
    directions = {
        item for item in [
            direction(row["price"], row["next_price"], False),
            direction(row["user_rating_min"], row["next_user_rating_min"], True),
            direction(row["amenity_count"], row["next_amenity_count"], True),
        ] if item
    }
    if directions == {"relax", "strengthen"}:
        return "완화·강화 혼합"
    if directions == {"relax"}:
        return "조건 완화"
    if directions == {"strengthen"}:
        return "조건 강화"
    raise ValueError(f"승인되지 않은 전이 유형: {changed}")


def session_signature(group: pd.DataFrame) -> str:
    # Stay dates are omitted because invalid source dates were repaired with sampled
    # valid durations; all other search/filter states recover the 43 source paths.
    payload = group[SIGNATURE_FIELDS].fillna("<NA>").astype(str).values.tolist()
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


def main() -> None:
    args = parse_args()
    db = args.db.resolve(strict=True)
    before_hash = sha256(db)
    connection = open_read_only(db)
    counts = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in TABLES
    }
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    search = pd.read_sql_query("SELECT * FROM search", connection)
    search_filter = pd.read_sql_query("SELECT * FROM search_filter", connection)
    search_result = pd.read_sql_query("SELECT search_id,hotel_id,result_rank FROM search_result", connection)
    event = pd.read_sql_query(
        "SELECT event_id,session_id,event_type,event_at,hotel_id,search_id FROM event",
        connection,
    )

    assert search.search_id.is_unique
    assert search_filter.search_id.is_unique
    assert set(search.search_id) == set(search_filter.search_id)
    base = search.merge(search_filter, on="search_id", how="inner", validate="one_to_one", suffixes=("", "_filter"))
    base["search_at"] = pd.to_datetime(base.search_time.str.replace(" KST", "", regex=False), errors="raise")
    base = base.sort_values(["session_id", "search_at", "search_id"], kind="stable").reset_index(drop=True)
    base["search_order"] = base.groupby("session_id").cumcount() + 1
    base["zero"] = base.total_result_count.eq(0)
    lead_fields = ["search_id", "total_result_count", *TRANSITION_FIELDS]
    for field in lead_fields:
        base[f"next_{field}"] = base.groupby("session_id", sort=False)[field].shift(-1)
    base["has_next"] = base.next_search_id.notna()

    click_events = event[event.event_type.eq("hotel_click") & event.search_id.notna() & event.hotel_id.notna()]
    click_search_ids = set(click_events.search_id)
    click_pairs = set(click_events[["search_id", "hotel_id"]].itertuples(index=False, name=None))

    card_a = {}
    conditions = {
        "amenity_count_ge_3": base.amenity_count.ge(3),
        "minimum_rating_set": base.user_rating_min.notna(),
        "price_filter_set": base.price.notna(),
    }
    for name, mask in conditions.items():
        card_a[name] = metric(int((mask & base.zero).sum()), int(mask.sum()), "search")

    zero_with_next = base[base.zero & base.has_next].copy()
    zero_with_next["transition_type"] = zero_with_next.apply(classify_transition, axis=1)
    zero_with_next["recovered"] = zero_with_next.next_total_result_count.gt(0)
    zero_with_next["detail_entered"] = zero_with_next.next_search_id.isin(click_search_ids)

    card_b = {
        "followup_after_zero": metric(len(zero_with_next), int(base.zero.sum()), "zero-result search"),
        "search_sessions": int(base.session_id.nunique()),
        "session_start_events": int(event.event_type.eq("session_start").sum()),
        "session_end_events": int(event.event_type.eq("session_end").sum()),
        "immediate_exit_rate_calculable": False,
    }

    final_numerator = 0
    final_denominator = 0
    for _, group in base.groupby("session_id", sort=False):
        values = group.total_result_count.astype(int).tolist()
        zero_positions = [index for index, value in enumerate(values) if value == 0]
        if zero_positions:
            final_denominator += 1
            final_numerator += any(
                any(value > 0 for value in values[index + 1 :])
                for index in zero_positions
            )
    card_c = {
        "immediate_recovery": metric(int(zero_with_next.recovered.sum()), len(zero_with_next), "zero-to-next transition"),
        "session_final_recovery": metric(final_numerator, final_denominator, "session experiencing any zero result"),
    }

    method_results = {}
    method_order = ["동일조건 반복", "조건 완화", "검색어 변경", "지역 변경", "조건 강화", "완화·강화 혼합"]
    for name in method_order:
        group = zero_with_next[zero_with_next.transition_type.eq(name)]
        method_results[name] = {
            "transitions": len(group),
            "recovery": metric(int(group.recovered.sum()), len(group), "zero-to-next transition"),
            "detail_entry": metric(int(group.detail_entered.sum()), len(group), "zero-to-next transition"),
        }

    search_order = base[["session_id", "search_id", "search_order"]]
    clicked_order = search_order[search_order.search_id.isin(click_search_ids)]
    first_clicked_order = clicked_order.groupby("session_id").search_order.min().to_dict()
    segments = {"직접 상호작용 성공": 0, "재검색 후 상호작용 성공": 0, "상호작용 없음": 0}
    for session_id in base.session_id.unique():
        first_order = first_clicked_order.get(session_id)
        if first_order == 1:
            segments["직접 상호작용 성공"] += 1
        elif first_order is not None:
            segments["재검색 후 상호작용 성공"] += 1
        else:
            segments["상호작용 없음"] += 1
    card_g = {
        name: metric(value, int(base.session_id.nunique()), "session")
        for name, value in segments.items()
    }

    card_h = {}
    for rank in range(1, 6):
        ranked = search_result[search_result.result_rank.eq(rank)]
        numerator = sum(
            pair in click_pairs
            for pair in ranked[["search_id", "hotel_id"]].itertuples(index=False, name=None)
        )
        card_h[str(rank)] = metric(numerator, len(ranked), "exposed search-result pair")

    signatures = {}
    for session_id, group in base.groupby("session_id", sort=True):
        signatures[session_id] = session_signature(group)
    signature_counts = pd.Series(signatures).value_counts()
    seen = set()
    representative_sessions = []
    for session_id in sorted(signatures):
        signature = signatures[session_id]
        if signature not in seen:
            seen.add(signature)
            representative_sessions.append(session_id)
    model_data = base[base.session_id.isin(representative_sessions)].copy()
    model_data["zero_result"] = model_data.zero.astype(int)
    model_data["price_set"] = model_data.price.notna().astype(int)
    model_data["rating_set"] = model_data.user_rating_min.notna().astype(int)
    model_data["amenity_ge3"] = model_data.amenity_count.ge(3).astype(int)
    destination = model_data.destination.fillna("UNKNOWN").astype(str)
    model_data["city"] = destination.str.extract(
        r"^(Tokyo|Osaka|Kyoto|Sapporo|Fukuoka)", expand=False
    ).fillna("UNKNOWN")
    model_data["checkin_month"] = pd.to_datetime(model_data.checkin_date).dt.strftime("%Y-%m")
    model_data["stay_nights"] = (
        pd.to_datetime(model_data.checkout_date) - pd.to_datetime(model_data.checkin_date)
    ).dt.days.clip(lower=1)
    formula = (
        "zero_result ~ price_set + rating_set + amenity_ge3 + "
        "C(city) + C(checkin_month) + guest_count + stay_nights"
    )
    fitted = smf.glm(formula, data=model_data, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": model_data.session_id}
    )
    constraint_terms = {}
    confidence = fitted.conf_int()
    for term in ["price_set", "rating_set", "amenity_ge3"]:
        condition_off = model_data.copy()
        condition_on = model_data.copy()
        condition_off[term] = 0
        condition_on[term] = 1
        probability_off = float(fitted.predict(condition_off).mean())
        probability_on = float(fitted.predict(condition_on).mean())
        constraint_terms[term] = {
            "odds_ratio": float(np.exp(fitted.params[term])),
            "odds_ratio_ci95_low": float(np.exp(confidence.loc[term, 0])),
            "odds_ratio_ci95_high": float(np.exp(confidence.loc[term, 1])),
            "p_value": float(fitted.pvalues[term]),
            "standardized_probability_if_off": probability_off,
            "standardized_probability_if_on": probability_on,
            "standardized_difference_pp": (probability_on - probability_off) * 100,
        }

    checks = {
        "sqlite_integrity_ok": integrity == "ok",
        "search_rows_6900": counts["search"] == 6900,
        "session_rows_1000": base.session_id.nunique() == 1000,
        "search_filter_one_to_one": len(base) == counts["search"] == counts["search_filter"],
        "search_result_reconciliation": int(base.total_result_count.sum()) == counts["search_result"],
        "all_zero_transitions_classified": sum(item["transitions"] for item in method_results.values()) == len(zero_with_next),
        "session_segments_sum_1000": sum(item["numerator"] for item in card_g.values()) == 1000,
        "source_trajectory_signatures_43": len(seen) == 43,
        "representative_searches_296": len(model_data) == 296,
        "representative_zero_searches_147": int(model_data.zero.sum()) == 147,
        "model_converged": bool(fitted.converged),
    }
    source_hash_after = sha256(db)
    checks["source_hash_unchanged"] = before_hash == source_hash_after

    result = {
        "analysis": {
            "database": str(db),
            "database_sha256_before": before_hash,
            "database_sha256_after": source_hash_after,
            "access": "SQLite mode=ro and PRAGMA query_only=ON",
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "statsmodels": statsmodels.__version__,
        },
        "coverage": {
            "row_counts": counts,
            "search_time_min": base.search_time.min(),
            "search_time_max": base.search_time.max(),
            "searches": len(base),
            "sessions": int(base.session_id.nunique()),
            "reconstructed_source_trajectories": len(seen),
            "trajectory_replication_counts": {
                str(int(copies)): int(number)
                for copies, number in signature_counts.value_counts().sort_index().items()
            },
        },
        "quality_checks": checks,
        "card_A": card_a,
        "card_B": card_b,
        "card_C": card_c,
        "card_D_F": method_results,
        "card_G": card_g,
        "card_H": card_h,
        "A2_adjusted_model": {
            "formula": formula,
            "population": "296 searches from one representative of each of 43 reconstructed source trajectories",
            "covariance": "cluster-robust by representative session (43 clusters)",
            "n_searches": int(fitted.nobs),
            "n_session_clusters": int(model_data.session_id.nunique()),
            "aic": float(fitted.aic),
            "converged": bool(fitted.converged),
            "constraint_terms": constraint_terms,
        },
        "limitations": [
            "The 1,000 sessions are balanced copies of 43 source trajectories, not 1,000 independent observations.",
            "Stay dates are excluded from trajectory fingerprinting because invalid source stays were repaired with sampled valid durations.",
            "The adjusted model is observational and does not identify a causal effect of relaxing a condition.",
            "Immediate exit cannot be measured because only 23 session_end events exist for 1,000 sessions.",
            "Booking conversion and revenue cannot be measured because booking and booking events contain zero rows.",
            "Intervention exposure events for condition-relaxation choices and repeat-search warnings do not yet exist.",
        ],
    }
    if not all(checks.values()):
        raise RuntimeError({name: passed for name, passed in checks.items() if not passed})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
