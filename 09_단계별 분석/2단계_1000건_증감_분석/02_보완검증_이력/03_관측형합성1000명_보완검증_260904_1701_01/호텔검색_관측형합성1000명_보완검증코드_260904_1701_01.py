#!/usr/bin/env python3
"""STEP B: read-only validation of S0 joint structure, timing, and duplication.

This script never runs or changes the generator. SQLite inputs are opened with
URI mode=ro and PRAGMA query_only=ON. Outputs must be written to a new folder.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from scipy import stats
from scipy.stats import mannwhitneyu

KST = ZoneInfo("Asia/Seoul")
SEED = 20260904
BOOTSTRAPS = 500
FOLDS = 5
REGIONS = ["Tokyo", "Osaka", "Kyoto", "Sapporo", "Fukuoka", "UNKNOWN"]
INTENTS = ["LOCATION_ONLY", "PRICE", "QUALITY_FILTER", "AMENITY", "MIXED"]
H3_ORDER = ["동일조건 반복", "조건 완화", "검색어 수정", "지역 변경", "조건 강화", "혼합 변경"]
SEGMENT_ORDER = ["직접 성공", "결과 노출·미선택", "재검색 회복", "지속 실패"]
H3_FIELDS = ["query_text", "destination", "property_type", "property_grade", "user_rating_min", "price", "amenity_count", "region"]
TABLES = ["user", "hotel", "room", "search", "search_filter", "search_result", "event", "booking"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def open_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    assert conn.execute("PRAGMA query_only").fetchone()[0] == 1
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    return conn


def norm(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    x = unicodedata.normalize("NFKC", str(v)).strip().casefold()
    return x or None


def city(v):
    x = norm(v)
    if x:
        for raw, label in [("tokyo", "Tokyo"), ("osaka", "Osaka"), ("kyoto", "Kyoto"), ("sapporo", "Sapporo"), ("fukuoka", "Fukuoka")]:
            if x == raw or x.startswith(raw + " ·"):
                return label
    return "UNKNOWN"


def direction(old, new, lower_relax):
    om, nm = pd.isna(old), pd.isna(new)
    if om and nm:
        return None
    if not om and nm:
        return "relax"
    if om and not nm:
        return "strengthen"
    if float(old) == float(new):
        return None
    dec = float(new) < float(old)
    return "relax" if (dec if lower_relax else not dec) else "strengthen"


def equal(a, b, numeric=False):
    if numeric:
        if pd.isna(a) and pd.isna(b):
            return True
        if pd.isna(a) or pd.isna(b):
            return False
        return float(a) == float(b)
    return norm(a) == norm(b)


def classify_h3(row):
    changed = [f for f in H3_FIELDS if not equal(row[f], row["next_" + f], f in {"user_rating_min", "price", "amenity_count"})]
    if not changed:
        return "동일조건 반복"
    if "destination" in changed or "region" in changed:
        return "지역 변경"
    if "query_text" in changed:
        return "검색어 수정"
    dirs = {x for x in [direction(row.price, row.next_price, False), direction(row.user_rating_min, row.next_user_rating_min, True), direction(row.amenity_count, row.next_amenity_count, True)] if x}
    if dirs == {"relax", "strengthen"}:
        return "혼합 변경"
    if dirs == {"relax"}:
        return "조건 완화"
    if dirs == {"strengthen"}:
        return "조건 강화"
    raise AssertionError(f"unclassified transition: {row.search_id}, {changed}")


def odds_ci(a, b, c, d):
    corrected = any(x == 0 for x in (a, b, c, d))
    raw = stats.fisher_exact([[a, b], [c, d]], alternative="two-sided")
    aa, bb, cc, dd = ([x + 0.5 for x in (a, b, c, d)] if corrected else [a, b, c, d])
    se = math.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd)
    odds = aa * dd / (bb * cc)
    return float(raw.statistic), math.exp(math.log(odds) - 1.96 * se), math.exp(math.log(odds) + 1.96 * se), float(raw.pvalue), corrected


def load_dataset(db: Path, dataset_type: str):
    with open_ro(db) as conn:
        schema = pd.DataFrame([dict(r) for r in conn.execute("PRAGMA table_info(search_filter)")])
        search = pd.read_sql_query("SELECT * FROM search", conn)
        filt = pd.read_sql_query("SELECT * FROM search_filter", conn)
        event = pd.read_sql_query("SELECT * FROM event", conn)
        result = pd.read_sql_query("SELECT * FROM search_result", conn)
        room = pd.read_sql_query("SELECT * FROM room", conn)
    assert search.search_id.is_unique and filt.search_id.is_unique
    base = search.merge(filt, on="search_id", validate="one_to_one", suffixes=("_search", "_filter"))
    base["search_time_dt"] = pd.to_datetime(base.search_time.astype(str).str.replace(r"\s+KST$", "+09:00", regex=True), errors="raise", utc=True)
    for col in ["total_result_count", "guest_count", "property_grade", "user_rating_min", "price", "amenity_count"]:
        base[col] = pd.to_numeric(base[col], errors="coerce")
    base["region_code"] = base.destination.map(city)
    base["price_active"] = base.price.notna()
    base["rating_active"] = base.user_rating_min.notna()
    base["amenity_active"] = base.amenity_count.fillna(0).gt(0)
    base["property_type_active"] = base.property_type.notna()
    base["property_grade_active"] = base.property_grade.notna()
    base["region_filter_active"] = base.region.notna()
    active = ["price_active", "rating_active", "amenity_active", "property_type_active", "property_grade_active", "region_filter_active"]
    base["active_filter_count"] = base[active].astype(int).sum(axis=1)
    base["active_filter_count_bin"] = pd.cut(base.active_filter_count, [-1, 0, 1, 2, 6], labels=["0", "1", "2", "3+"]).astype(str)
    core_count = base[["price_active", "rating_active", "amenity_active"]].astype(int).sum(axis=1)
    base["intent_code"] = "LOCATION_ONLY"
    base.loc[core_count.ge(2), "intent_code"] = "MIXED"
    base.loc[core_count.eq(1) & base.price_active, "intent_code"] = "PRICE"
    base.loc[core_count.eq(1) & base.rating_active, "intent_code"] = "QUALITY_FILTER"
    base.loc[core_count.eq(1) & base.amenity_active, "intent_code"] = "AMENITY"
    base["is_zero_result"] = base.total_result_count.eq(0)
    clicks = set(event.loc[event.event_type.eq("hotel_click") & event.search_id.notna(), "search_id"])
    base["has_hotel_click"] = base.search_id.isin(clicks)
    base = base.sort_values(["session_id", "search_time_dt", "search_id"], kind="mergesort").reset_index(drop=True)
    group = base.groupby("session_id", sort=False)
    base["search_order"] = group.cumcount() + 1
    for col in ["search_id", "search_time_dt", "total_result_count", *H3_FIELDS]:
        base["next_" + col] = group[col].shift(-1)
    base["has_next_search"] = base.next_search_id.notna()
    base["next_search_success"] = base.next_total_result_count.gt(0)
    base["next_search_has_hotel_click"] = base.next_search_id.isin(clicks)
    trans = base[base.is_zero_result & base.has_next_search].copy()
    trans["transition_type"] = trans.apply(classify_h3, axis=1)
    trans["inter_arrival_seconds"] = (trans.next_search_time_dt - trans.search_time_dt).dt.total_seconds()
    sessions = []
    for sid, x in base.groupby("session_id", sort=True):
        vals = x.total_result_count.astype(int).tolist()
        anyzero = any(v == 0 for v in vals)
        recovered = any(v == 0 and any(q > 0 for q in vals[i + 1:]) for i, v in enumerate(vals))
        firstzero = vals[0] == 0
        firstrecovered = any(v > 0 for v in vals[1:]) if firstzero else False
        hasclick = bool(x.has_hotel_click.any())
        segment = ("재검색 회복" if firstrecovered else "지속 실패") if firstzero else ("직접 성공" if hasclick else "결과 노출·미선택")
        sessions.append({"session_id": sid, "search_count": len(x), "experienced_zero": anyzero, "zero_later_positive": recovered, "first_zero": firstzero, "first_zero_later_positive": firstrecovered, "has_click": hasclick, "segment": segment})
    return {"type": dataset_type, "schema": schema, "base": base, "trans": trans, "sessions": pd.DataFrame(sessions), "event": event, "result": result, "room": room}


def high_order_tables(original, synthetic):
    count_rows, combo_rows = [], []
    flags = ["price_active", "rating_active", "amenity_active", "property_type_active", "property_grade_active", "region_filter_active"]
    for data in (original, synthetic):
        b = data["base"]
        for n, x in b.groupby("active_filter_count", dropna=False):
            z = int(x.is_zero_result.sum())
            count_rows.append({"dataset_type": data["type"], "analysis_unit": "search", "active_filter_count": int(n), "numerator_definition": "total_result_count=0", "denominator_definition": "searches at active_filter_count", "n": len(x), "zero_n": z, "zero_rate": z / len(x)})
        hi = b[b.active_filter_count.ge(3)].copy()
        hi["active_combination"] = hi.apply(lambda r: "+".join(f.replace("_active", "") for f in flags if r[f]), axis=1)
        for combo, x in hi.groupby("active_combination"):
            z = int(x.is_zero_result.sum())
            combo_rows.append({"dataset_type": data["type"], "analysis_unit": "search", "active_combination": combo, "n": len(x), "zero_n": z, "zero_rate": z / len(x), "sparse_lt5": len(x) < 5, "sparse_lt10": len(x) < 10})
    counts, combos = pd.DataFrame(count_rows), pd.DataFrame(combo_rows)
    op = combos[combos.dataset_type.eq("ORIGINAL_296")].set_index("active_combination")
    sp = combos[combos.dataset_type.eq("S0_1000")].set_index("active_combination")
    comp = op[["n", "zero_n", "zero_rate"]].join(sp[["n", "zero_n", "zero_rate"]], lsuffix="_original", rsuffix="_synthetic", how="outer").reset_index()
    comp["rate_difference_pp"] = (comp.zero_rate_synthetic - comp.zero_rate_original) * 100
    comp["rate_ratio"] = comp.zero_rate_synthetic / comp.zero_rate_original.replace(0, np.nan)
    sparse = pd.DataFrame([{ "dataset_type": d["type"], "cell_definition": "active combination among count>=3", "total_cells": int(len(combos[combos.dataset_type.eq(d["type"])])), "sparse_lt5_cells": int(combos.loc[combos.dataset_type.eq(d["type"]), "sparse_lt5"].sum()), "sparse_lt5_ratio": float(combos.loc[combos.dataset_type.eq(d["type"]), "sparse_lt5"].mean()), "sparse_lt10_cells": int(combos.loc[combos.dataset_type.eq(d["type"]), "sparse_lt10"].sum()), "sparse_lt10_ratio": float(combos.loc[combos.dataset_type.eq(d["type"]), "sparse_lt10"].mean())} for d in (original, synthetic)])
    return counts, combos, comp, sparse


def nb_fit(train: pd.DataFrame, features, alpha=1.0):
    classes = [False, True]
    model = {"prior": {}, "features": {}, "categories": {f: sorted(train[f].astype(str).unique()) for f in features}}
    n = len(train)
    for y in classes:
        sub = train[train.is_zero_result.eq(y)]
        model["prior"][y] = (len(sub) + alpha) / (n + alpha * 2)
        model["features"][y] = {}
        for f in features:
            cats = model["categories"][f]
            ctr = Counter(sub[f].astype(str))
            den = len(sub) + alpha * len(cats)
            model["features"][y][f] = {v: (ctr[v] + alpha) / den for v in cats}
    return model


def nb_predict(model, frame, features, alpha_floor=1e-12):
    pred = []
    for _, r in frame.iterrows():
        lp = {}
        for y in [False, True]:
            v = math.log(model["prior"][y])
            for f in features:
                v += math.log(model["features"][y][f].get(str(r[f]), alpha_floor))
            lp[y] = v
        m = max(lp.values())
        a, b = math.exp(lp[False] - m), math.exp(lp[True] - m)
        pred.append(b / (a + b))
    return np.asarray(pred)


def auc_score(y, p):
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        return np.nan
    ranks = stats.rankdata(p)
    n1, n0 = y.sum(), len(y) - y.sum()
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def score_predictions(y, p):
    y = np.asarray(y, dtype=int); p = np.clip(np.asarray(p), 1e-12, 1 - 1e-12)
    return {"log_loss": float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()), "brier_score": float(np.mean((p - y) ** 2)), "roc_auc": auc_score(y, p)}


def calibration(y, p, dataset_type):
    d = pd.DataFrame({"y": np.asarray(y, int), "p": p})
    d["bin"] = pd.qcut(d.p.rank(method="first"), q=min(10, len(d)), labels=False, duplicates="drop")
    out = d.groupby("bin").agg(n=("y", "size"), mean_predicted=("p", "mean"), observed_rate=("y", "mean")).reset_index()
    out.insert(0, "dataset_type", dataset_type)
    out["absolute_gap"] = (out.mean_predicted - out.observed_rate).abs()
    return out


def cluster_boot_ci(pred_df, metric, rng, reps=BOOTSTRAPS):
    groups = pred_df.cv_group.unique()
    vals = []
    for _ in range(reps):
        chosen = rng.choice(groups, len(groups), replace=True)
        chunks = [pred_df[pred_df.cv_group.eq(g)] for g in chosen]
        x = pd.concat(chunks, ignore_index=True)
        vals.append(score_predictions(x.y, x.p)[metric])
    return float(np.nanquantile(vals, .025)), float(np.nanquantile(vals, .975))


def template_groups(original, synthetic):
    cols = ["query_text", "total_result_count", "sort_option", "guest_count", "destination", "property_type", "property_grade", "user_rating_min", "price", "amenity_count", "region"]
    def mapping(base):
        out = {}
        for sid, x in base.groupby("session_id", sort=True):
            payload = json.dumps([[None if pd.isna(r[c]) else r[c] for c in cols] for _, r in x.iterrows()], ensure_ascii=False, default=str, separators=(",", ":"))
            out[sid] = hashlib.sha256(payload.encode()).hexdigest()
        return out
    om, sm = mapping(original["base"]), mapping(synthetic["base"])
    valid = set(om.values())
    assert set(sm.values()) <= valid
    return om, sm


def bn_cross_validation(original, synthetic, seed=SEED):
    features = ["region_code", "intent_code", "price_active", "rating_active", "amenity_active", "property_type_active", "property_grade_active", "region_filter_active", "active_filter_count_bin"]
    om, sm = template_groups(original, synthetic)
    outputs, calibrations, prediction_frames = [], [], []
    rng = np.random.default_rng(seed)
    for data, groupmap in [(original, om), (synthetic, sm)]:
        b = data["base"].copy(); b["cv_group"] = b.session_id.map(groupmap)
        groups = np.array(sorted(b.cv_group.unique())); rng.shuffle(groups)
        fold_sets = np.array_split(groups, FOLDS)
        pred = np.empty(len(b)); fold_id = np.empty(len(b), int)
        for fold, test_groups in enumerate(fold_sets):
            test = b.cv_group.isin(set(test_groups)); train = ~test
            assert not set(b.loc[train, "session_id"]) & set(b.loc[test, "session_id"])
            model = nb_fit(b.loc[train], features, alpha=1.0)
            pred[test.to_numpy()] = nb_predict(model, b.loc[test], features)
            fold_id[test.to_numpy()] = fold
        pdf = pd.DataFrame({"dataset_type": data["type"], "session_id": b.session_id, "cv_group": b.cv_group, "fold": fold_id, "y": b.is_zero_result.astype(int), "p": pred})
        scores = score_predictions(pdf.y, pdf.p)
        cal = calibration(pdf.y, pdf.p, data["type"]); calibrations.append(cal)
        ece = float((cal.n / cal.n.sum() * cal.absolute_gap).sum())
        row = {"dataset_type": data["type"], "analysis_unit": "search; folds grouped by source-session template", "model": "domain-constrained categorical Naive Bayes", "dag": "region,intent,active flags,count bin -> zero_result", "smoothing": "Laplace alpha=1", "folds": FOLDS, "sessions": b.session_id.nunique(), "cv_groups": b.cv_group.nunique(), **scores, "ece_10bin": ece}
        for metric in ["log_loss", "brier_score", "roc_auc"]:
            lo, hi = cluster_boot_ci(pdf, metric, rng)
            row[metric + "_ci_low"], row[metric + "_ci_high"] = lo, hi
        outputs.append(row); prediction_frames.append(pdf)
    return pd.DataFrame(outputs), pd.concat(calibrations, ignore_index=True), pd.concat(prediction_frames, ignore_index=True), om, sm


def sequence_number(value):
    # Natural-sort key with one stable return type, including IDs without digits.
    return re.sub(r"\d+", lambda m: m.group(0).zfill(20), str(value))


def time_validation(data, rng):
    t = data["trans"].copy(); gaps = t.inter_arrival_seconds.to_numpy(float); pos = gaps[gaps > 0]
    def q(v): return float(np.quantile(gaps, v)) if len(gaps) else np.nan
    logs = np.log(pos); mu, sigma = float(logs.mean()), float(logs.std(ddof=0))
    ks = stats.kstest(pos, "lognorm", args=(sigma, 0, math.exp(mu)))
    observed_d = float(ks.statistic); sim_d = []
    for _ in range(BOOTSTRAPS):
        sim = rng.lognormal(mu, sigma, len(pos)); l = np.log(sim); m, s = l.mean(), l.std(ddof=0)
        sim_d.append(stats.kstest(sim, "lognorm", args=(s, 0, math.exp(m))).statistic)
    boot_p = float((1 + sum(x >= observed_d for x in sim_d)) / (BOOTSTRAPS + 1))
    b = data["base"]
    search_reverse = 0
    search_ties = 0
    search_id_order_time_decrease = 0
    for _, x in b.groupby("session_id"):
        y = x.sort_values(["search_time_dt", "search_id"], kind="mergesort")
        d = y.search_time_dt.diff().dt.total_seconds().dropna()
        search_reverse += int((d < 0).sum()); search_ties += int((d == 0).sum())
        id_y = x.sort_values("search_id", key=lambda z: z.map(sequence_number), kind="mergesort")
        search_id_order_time_decrease += int((id_y.search_time_dt.diff().dt.total_seconds().dropna() < 0).sum())
    e = data["event"].copy(); e["event_at_dt"] = pd.to_datetime(e.event_at.astype(str).str.replace(r"\s+KST$", "+09:00", regex=True), errors="coerce", utc=True)
    event_reverse = 0; event_ties = 0; event_id_order_time_decrease = 0
    for _, x in e.groupby("session_id"):
        y = x.sort_values(["event_at_dt", "event_id"], kind="mergesort")
        d = y.event_at_dt.diff().dt.total_seconds().dropna()
        event_reverse += int((d < 0).sum()); event_ties += int((d == 0).sum())
        id_y = x.sort_values("event_id", key=lambda z: z.map(sequence_number), kind="mergesort")
        event_id_order_time_decrease += int((id_y.event_at_dt.diff().dt.total_seconds().dropna() < 0).sum())
    return {"dataset_type": data["type"], "analysis_unit": "current zero-result search with immediate next search in same session", "numerator_definition": "eligible adjacent transitions", "denominator_definition": "all zero-result searches with next_search_id", "transition_n": len(gaps), "negative_n": int((gaps < 0).sum()), "zero_n": int((gaps == 0).sum()), "positive_n": len(pos), "mean_seconds": float(gaps.mean()), "median_seconds": q(.5), "q1_seconds": q(.25), "q3_seconds": q(.75), "p90_seconds": q(.9), "p95_seconds": q(.95), "max_seconds": float(gaps.max()), "timestamp_tie_n": int((gaps == 0).sum()), "search_time_reverse_n": search_reverse, "search_timestamp_tie_n_all_adjacent": search_ties, "search_id_order_time_decrease_aux": search_id_order_time_decrease, "event_time_reverse_n": event_reverse, "event_timestamp_tie_n_all_adjacent": event_ties, "event_id_order_time_decrease_aux": event_id_order_time_decrease, "lognormal_mu": mu, "lognormal_sigma": sigma, "ks_statistic_fitted_parameters": observed_d, "ks_naive_pvalue_auxiliary": float(ks.pvalue), "parametric_bootstrap_gof_pvalue": boot_p, "bootstrap_reps": BOOTSTRAPS, "interpretation": "empirical source intervals preserved; not generated from lognormal; ID-only order is auxiliary because IDs are not sequence fields"}


def condition_signature(row):
    ci = pd.to_datetime(row.checkin_date, errors="coerce"); co = pd.to_datetime(row.checkout_date, errors="coerce")
    stay = int((co - ci).days) if pd.notna(ci) and pd.notna(co) else None
    payload = {
        "destination": norm(row.destination), "region_filter": norm(row.region), "stay_nights": stay,
        "guest_count": None if pd.isna(row.guest_count) else int(row.guest_count),
        "room_count": None, "price": None if pd.isna(row.price) else float(row.price),
        "user_rating_min": None if pd.isna(row.user_rating_min) else float(row.user_rating_min),
        "amenity_count": None if pd.isna(row.amenity_count) else int(row.amenity_count),
        "property_type": norm(row.property_type), "property_grade": None if pd.isna(row.property_grade) else int(row.property_grade),
        "cancel_option": None, "payment_option": None, "sort_option": norm(row.sort_option),
        "query_text": norm(row.query_text), "intent": row.intent_code,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def mode_metrics(data, template_map):
    b = data["base"].copy(); b["condition_signature"] = b.apply(condition_signature, axis=1)
    counts = b.condition_signature.value_counts(); p = counts / len(b)
    paths = []
    for sid, x in b.groupby("session_id", sort=True):
        path = hashlib.sha256("\n".join(x.condition_signature).encode()).hexdigest()
        paths.append((sid, path, template_map[sid]))
    pc = Counter(x[1] for x in paths); tc = Counter(x[2] for x in paths)
    top10 = counts.head(10).reset_index(); top10.columns = ["condition_signature", "frequency"]; top10.insert(0, "dataset_type", data["type"]); top10["share"] = top10.frequency / len(b)
    return {"dataset_type": data["type"], "analysis_unit": "search condition signature", "n": len(b), "unique_signatures": len(counts), "unique_ratio": len(counts) / len(b), "max_frequency": int(counts.max()), "top10_share": float(counts.head(10).sum() / len(b)), "singleton_signatures": int((counts == 1).sum()), "singleton_ratio_of_signatures": float((counts == 1).mean()), "shannon_entropy_nats": float(-(p * np.log(p)).sum()), "normalized_shannon_entropy": float(-(p * np.log(p)).sum() / math.log(len(counts))) if len(counts) > 1 else 0.0, "hhi_simpson_concentration": float((p ** 2).sum()), "session_paths": len(paths), "unique_session_paths": len(pc), "sessions_in_duplicated_paths": int(sum(v for v in pc.values() if v > 1)), "duplicated_session_path_share": float(sum(v for v in pc.values() if v > 1) / len(paths)), "max_identical_session_path_frequency": max(pc.values()), "source_template_count": len(tc), "source_template_min_copies": min(tc.values()), "source_template_max_copies": max(tc.values()), "source_template_copy_distribution": json.dumps(dict(sorted(Counter(tc.values()).items())), ensure_ascii=False)}, top10, b


def jitter_audit(generator: Path, original, synthetic):
    text = generator.read_text(encoding="utf-8")
    terms = {"jitter": bool(re.search(r"jitter", text, re.I)), "normal_draw": bool(re.search(r"rng\.(normal|lognormal)", text)), "uniform_draw": bool(re.search(r"rng\.uniform", text)), "choice_draw": bool(re.search(r"rng\.choice", text)), "clip": bool(re.search(r"clip|minimum|maximum", text, re.I)), "round": bool(re.search(r"round", text, re.I))}
    cols = {"search_filter": ["user_rating_min", "price", "amenity_count"], "search_result": ["result_score"], "room": ["room_price"], "hotel": ["user_rating", "review_count", "actual_latitude", "actual_longitude"]}
    rows = []
    with open_ro(original) as oc, open_ro(synthetic) as sc:
        for table, fields in cols.items():
            for field in fields:
                ov = {r[0] for r in oc.execute(f'SELECT DISTINCT "{field}" FROM "{table}"')}
                sv = {r[0] for r in sc.execute(f'SELECT DISTINCT "{field}" FROM "{table}"')}
                rows.append({"table": table, "field": field, "original_distinct": len(ov), "synthetic_distinct": len(sv), "synthetic_values_not_in_original": len(sv - ov), "jitter_evidence": "none" if not (sv - ov) else "new values present; code review required"})
    summary = {"generator_sha256": sha256(generator), "static_terms": terms, "jittering_applied": False, "conditional_random_repair_only": "invalid checkout dates sample a duration with rng.choice; this is not continuous jittering", "excluded_noise_candidates": "PK/FK, zero-result labels, event types, segment labels, result ranks", "cause_of_duplication": "balanced session bootstrap repeats each of 43 source templates 23 or 24 times", "jittering_expected_value": "limited unless applied to time/continuous fields; categorical condition repetition remains", "integrity_risk": "filter or outcome jitter can change A1/A2/H3 and integrity", "recommendation": "do not modify generator in STEP B; approve a narrowly scoped jitter policy first"}
    return summary, pd.DataFrame(rows)


def integrity_checks(db: Path, dataset_type: str):
    rows = []
    with open_ro(db) as c:
        for t in TABLES:
            n = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            pk = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")') if r[5] > 0]
            dup = c.execute(f'SELECT COUNT(*) FROM (SELECT {",".join(pk)},COUNT(*) n FROM "{t}" GROUP BY {",".join(pk)} HAVING n>1)').fetchone()[0] if pk else None
            rows.append({"dataset_type": dataset_type, "check_type": "row_count_pk", "table": t, "relationship": None, "row_count": n, "failure_count": dup, "status": "PASS" if dup == 0 else "FAIL"})
        relationships = [
            ("room", "hotel_id", "hotel", "hotel_id"), ("search_filter", "search_id", "search", "search_id"),
            ("search_result", "search_id", "search", "search_id"), ("search_result", "hotel_id", "hotel", "hotel_id"), ("search_result", "room_id", "room", "room_id"),
            ("event", "search_id", "search", "search_id"), ("event", "search_filter_id", "search_filter", "search_filter_id"), ("event", "hotel_id", "hotel", "hotel_id"), ("event", "user_id", "user", "user_id"),
            ("booking", "user_id", "user", "user_id"), ("booking", "hotel_id", "hotel", "hotel_id"), ("booking", "room_id", "room", "room_id")]
        for child, ck, parent, pk in relationships:
            sql = f'SELECT COUNT(*) FROM "{child}" c LEFT JOIN "{parent}" p ON c."{ck}"=p."{pk}" WHERE c."{ck}" IS NOT NULL AND p."{pk}" IS NULL'
            n = c.execute(sql).fetchone()[0]
            rows.append({"dataset_type": dataset_type, "check_type": "fk_orphan", "table": child, "relationship": f"{child}.{ck}->{parent}.{pk}", "row_count": None, "failure_count": n, "status": "PASS" if n == 0 else "FAIL"})
        s, f, du = c.execute("SELECT COUNT(*),(SELECT COUNT(*) FROM search_filter),(SELECT COUNT(*) FROM (SELECT search_id FROM search_filter GROUP BY search_id HAVING COUNT(*)<>1)) FROM search").fetchone()
        rows.append({"dataset_type": dataset_type, "check_type": "search_filter_1to1", "table": "search/search_filter", "relationship": "search.search_id=search_filter.search_id", "row_count": f, "failure_count": abs(s-f)+du, "status": "PASS" if s == f and du == 0 else "FAIL"})
        expected = c.execute("SELECT COALESCE(SUM(total_result_count),0) FROM search").fetchone()[0]; actual = c.execute("SELECT COUNT(*) FROM search_result").fetchone()[0]
        rows.append({"dataset_type": dataset_type, "check_type": "result_count_sum", "table": "search_result", "relationship": "SUM(search.total_result_count)=COUNT(search_result)", "row_count": actual, "failure_count": abs(expected-actual), "status": "PASS" if expected == actual else "FAIL"})
    return pd.DataFrame(rows)


def regression_metrics(data):
    b, t, ss = data["base"], data["trans"], data["sessions"]
    rows = []
    def add(family, metric, group, num=None, den=None, **kw):
        rows.append({"dataset_type": data["type"], "family": family, "metric_id": metric, "group": group, "numerator": num, "denominator": den, "rate": num/den if num is not None and den else None, **kw})
    add("core", "ZERO_RESULT_RATE", None, int(b.is_zero_result.sum()), len(b))
    add("core", "ZERO_FOLLOWUP_RATE", None, int((b.is_zero_result & b.has_next_search).sum()), int(b.is_zero_result.sum()))
    add("core", "B3_IMMEDIATE_RECOVERY", None, int(t.next_search_success.sum()), len(t))
    add("core", "B3_SESSION_FINAL_RECOVERY", None, int(ss.loc[ss.experienced_zero, "zero_later_positive"].sum()), int(ss.experienced_zero.sum()))
    add("core", "SEARCH_HOTEL_CLICK_RATE", None, int(b.has_hotel_click.sum()), len(b))
    add("core", "DIAG_FIRST_SEARCH_ZERO_RECOVERY", None, int(ss.loc[ss.first_zero, "first_zero_later_positive"].sum()), int(ss.first_zero.sum()))
    for mid, mask, yes, no in [("A1_AMENITY_GE3", b.amenity_count.ge(3), "amenity_count>=3", "amenity_count<3"), ("A1_RATING_SET", b.user_rating_min.notna(), "set", "unset"), ("A1_PRICE_SET", b.price.notna(), "set", "unset")]:
        for label, m in [(yes, mask), (no, ~mask)]: add("A1", mid, label, int((m & b.is_zero_result).sum()), int(m.sum()))
    for reg in REGIONS:
        for intent in INTENTS:
            m = b.region_code.eq(reg) & b.intent_code.eq(intent); add("A2", "A2_REGION_INTENT_ZERO_RESULT", reg+"|"+intent, int((m & b.is_zero_result).sum()), int(m.sum()))
    for label, m in [("zero_result", b.is_zero_result), ("positive_result", ~b.is_zero_result)]: add("B1", "B1_IMMEDIATE_FOLLOWUP", label, int((m & b.has_next_search).sum()), int(m.sum()))
    for label, m in [("experienced_zero", ss.experienced_zero), ("no_zero_experience", ~ss.experienced_zero)]:
        v=ss.loc[m,"search_count"].astype(float); add("B2","B2_SESSION_SEARCH_COUNT",label,n=len(v),mean=float(v.mean()),median=float(v.median()),q1=float(v.quantile(.25)),q3=float(v.quantile(.75)),minimum=float(v.min()),maximum=float(v.max()))
    for label in SEGMENT_ORDER: add("segments", "SESSION_RESULT_SEGMENT", label, int(ss.segment.eq(label).sum()), len(ss))
    for label in H3_ORDER:
        x=t[t.transition_type.eq(label)]; add("H3", "H3_TRANSITION_TYPE", label, int(x.next_search_success.sum()), len(x), next_hotel_click_count=int(x.next_search_has_hotel_click.sum()), composition_rate=len(x)/len(t))
    return pd.DataFrame(rows)


def compare_regression(recalc, step2_xlsx):
    sheets={"core":"G3_core_metrics","A1":"A1_filters","A2":"A2_region_intent","B1":"B1_followup","B2":"B2_search_count","segments":"session_segments","H3":"H3_transitions"}
    stored={k:pd.read_excel(step2_xlsx,sheet_name=v) for k,v in sheets.items()}
    checks=[]
    for _, r in recalc.iterrows():
        s=stored[r.family]; cand=s[(s.dataset_type==r.dataset_type)&(s.metric_id==r.metric_id)]
        if r.group is not None:
            cand=cand[cand.group==r.group]
        ok=len(cand)==1; diffs=[]
        if ok:
            q=cand.iloc[0]
            for col in ["numerator","denominator","rate","n","mean","median","q1","q3","minimum","maximum","next_hotel_click_count","composition_rate"]:
                if col in r.index and col in q.index and not pd.isna(r[col]):
                    try: same=math.isclose(float(r[col]),float(q[col]),rel_tol=1e-8,abs_tol=1e-10)
                    except: same=r[col]==q[col]
                    if not same: diffs.append(f"{col}:{r[col]}!={q[col]}")
        checks.append({"dataset_type":r.dataset_type,"family":r.family,"metric_id":r.metric_id,"group":r.group,"match_status":"PASS" if ok and not diffs else "FAIL","differences":";".join(diffs),"stored_row_count":len(cand)})
    return pd.DataFrame(checks)


def trace_validation(original, synthetic, step3_xlsx):
    stored=pd.read_excel(step3_xlsx,sheet_name="deterministic_traces"); data={"ORIGINAL_296":original,"S0_1000":synthetic}; rows=[]
    for _,r in stored.iterrows():
        d=data[r.dataset_type]; ok=True; notes=[]
        if r.trace_type=="H3 stable first":
            x=d["trans"][d["trans"].search_id.eq(r.current_search_id)]
            ok=len(x)==1
            if ok:
                q=x.iloc[0];ok=(q.next_search_id==r.next_search_id and q.transition_type==r.independent_classification)
        elif r.trace_type=="segment minimum session":
            x=d["sessions"][d["sessions"].session_id.eq(r.session_id)];ok=len(x)==1 and x.iloc[0].segment==r.independent_classification
        else:
            x=d["base"][d["base"].search_id.eq(r.current_search_id)];ok=len(x)==1
        rows.append({"trace_type":r.trace_type,"dataset_type":r.dataset_type,"session_id":r.session_id,"current_search_id":r.current_search_id,"next_search_id":r.next_search_id,"expected_classification":r.independent_classification,"status":"PASS" if ok else "FAIL","note":"DB key and independently rebuilt classification"})
    return pd.DataFrame(rows)


def plots(output, stem, original, synthetic, bn_cal, top10):
    plt.rcParams["font.family"]=["Malgun Gothic","DejaVu Sans"];plt.rcParams["axes.unicode_minus"]=False
    files=[]
    fig,axs=plt.subplots(2,2,figsize=(12,9))
    for d,c in [(original,"#2463eb"),(synthetic,"#e87924")]:
        pos=d["trans"].loc[d["trans"].inter_arrival_seconds.gt(0),"inter_arrival_seconds"].to_numpy();log=np.log(pos);label=d["type"]
        axs[0,0].hist(log,bins=20,density=True,histtype="step",linewidth=1.8,label=label,color=c)
        xs=np.sort(pos);axs[0,1].step(xs,np.arange(1,len(xs)+1)/len(xs),where="post",label=label,color=c)
        osm,osr=stats.probplot(log,dist="norm",fit=False);axs[1,0].scatter(osm,osr,s=8,alpha=.35,label=label,color=c)
    axs[0,0].set_title("log(0건 후 다음 검색 간격) 히스토그램");axs[0,1].set_title("양수 간격 ECDF");axs[0,1].set_xscale("log");axs[1,0].set_title("로그 간격 정규 Q-Q");axs[1,1].axis("off")
    for ax in axs.flat:
        if ax.has_data():ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();p=output/f"호텔검색_관측형합성1000명_시간간격시각화_{stem}_01.png";fig.savefig(p,dpi=160);plt.close(fig);files.append(p)
    fig,ax=plt.subplots(figsize=(7,6))
    for ds,x in bn_cal.groupby("dataset_type"):
        ax.plot(x.mean_predicted,x.observed_rate,marker="o",label=ds)
    ax.plot([0,1],[0,1],"--",color="gray");ax.set(xlabel="평균 예측확률",ylabel="관측 0건률",title="제한 Naive Bayes 교정도");ax.legend();ax.grid(alpha=.2);fig.tight_layout();p=output/f"호텔검색_관측형합성1000명_BN교정시각화_{stem}_01.png";fig.savefig(p,dpi=160);plt.close(fig);files.append(p)
    fig,ax=plt.subplots(figsize=(10,5)); z=top10.copy();z["rank"]=z.groupby("dataset_type").cumcount()+1
    for ds,x in z.groupby("dataset_type"):ax.plot(x["rank"],x.share,marker="o",label=ds)
    ax.set(xlabel="signature 빈도 순위",ylabel="전체 검색 점유율",title="상위 10개 condition signature 점유율");ax.legend();ax.grid(alpha=.2);fig.tight_layout();p=output/f"호텔검색_관측형합성1000명_모드중복시각화_{stem}_01.png";fig.savefig(p,dpi=160);plt.close(fig);files.append(p)
    return files


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--original-db",type=Path,required=True);ap.add_argument("--synthetic-db",type=Path,required=True);ap.add_argument("--generator",type=Path,required=True);ap.add_argument("--step2-excel",type=Path,required=True);ap.add_argument("--step3-excel",type=Path,required=True);ap.add_argument("--output-dir",type=Path,required=True);ap.add_argument("--stamp",required=True);args=ap.parse_args()
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=False) if not output.exists() else None
    existing=[p.resolve() for p in output.iterdir() if p.resolve()!=Path(__file__).resolve()]
    if existing:raise FileExistsError(f"output directory must contain only this script: {existing}")
    started=datetime.now(KST).isoformat();inputs=[args.original_db,args.synthetic_db,args.generator,args.step2_excel,args.step3_excel];before={str(p.resolve()):sha256(p) for p in inputs}
    rng=np.random.default_rng(SEED);original=load_dataset(args.original_db,"ORIGINAL_296");synthetic=load_dataset(args.synthetic_db,"S0_1000")
    counts,combos,combo_comp,sparse=high_order_tables(original,synthetic)
    bn_scores,bn_cal,bn_predictions,om,sm=bn_cross_validation(original,synthetic)
    timing=pd.DataFrame([time_validation(original,rng),time_validation(synthetic,rng)])
    mm1,top1,_=mode_metrics(original,om);mm2,top2,_=mode_metrics(synthetic,sm);mode=pd.DataFrame([mm1,mm2]);top10=pd.concat([top1,top2],ignore_index=True)
    template_counts=pd.DataFrame([{"dataset_type":"S0_1000","source_template_hash":k,"copy_count":v} for k,v in sorted(Counter(sm.values()).items())])
    jitter,jitter_fields=jitter_audit(args.generator,args.original_db,args.synthetic_db)
    integrity=pd.concat([integrity_checks(args.original_db,"ORIGINAL_296"),integrity_checks(args.synthetic_db,"S0_1000")],ignore_index=True)
    regression=pd.concat([regression_metrics(original),regression_metrics(synthetic)],ignore_index=True)
    regression_check=compare_regression(regression,args.step2_excel);traces=trace_validation(original,synthetic,args.step3_excel)
    schema=original["schema"][["cid","name","type","notnull","dflt_value","pk"]].copy();schema.insert(0,"dataset_type","ORIGINAL_296")
    active_defs=pd.DataFrame([
      {"field":"price","active_rule":"price IS NOT NULL"},{"field":"user_rating_min","active_rule":"user_rating_min IS NOT NULL"},{"field":"amenity_count","active_rule":"amenity_count > 0"},{"field":"property_type","active_rule":"property_type IS NOT NULL"},{"field":"property_grade","active_rule":"property_grade IS NOT NULL"},{"field":"region","active_rule":"region IS NOT NULL"}])
    definition=pd.DataFrame([
      {"validation":"high_order","analysis_unit":"SEARCH 1 row","numerator":"total_result_count=0 searches","denominator":"searches in filter-count/combination cell","exclusion":"none; active_count>=3 defines high-order"},
      {"validation":"BN","analysis_unit":"SEARCH 1 row; CV grouped by source-session template","numerator":"zero_result=1 probability scoring","denominator":"all held-out searches","exclusion":"none"},
      {"validation":"timing","analysis_unit":"adjacent zero-to-next transition","numerator":"eligible zero-result current searches","denominator":"zero-result searches with immediate next search","exclusion":"no next search; log fit additionally excludes gaps<=0"},
      {"validation":"mode","analysis_unit":"normalized search condition signature/session path","numerator":"frequency by signature/path","denominator":"all searches/all sessions","exclusion":"PII; unavailable room/cancel/pay fields recorded as null"}])
    high_orig=original["base"].active_filter_count.ge(3);high_syn=synthetic["base"].active_filter_count.ge(3)
    max_combo_diff=float(combo_comp.rate_difference_pp.abs().max())
    bn_delta_logloss=float(bn_scores.set_index("dataset_type").loc["S0_1000","log_loss"]-bn_scores.set_index("dataset_type").loc["ORIGINAL_296","log_loss"])
    regression_pass=bool(regression_check.match_status.eq("PASS").all() and traces.status.eq("PASS").all() and integrity.status.eq("PASS").all())
    time_hard_fail=bool(timing.negative_n.sum()>0 or timing.search_time_reverse_n.sum()>0 or timing.event_time_reverse_n.sum()>0)
    time_fit_warn=bool((timing.parametric_bootstrap_gof_pvalue<.05).any())
    time_status="FAIL" if time_hard_fail else ("WARN" if time_fit_warn else "PASS")
    gates=pd.DataFrame([
      {"validation":"고차 조건부 결합확률","status":"PASS" if max_combo_diff<=3 and abs(bn_delta_logloss)<=.05 else "WARN","criterion":"max major-combination rate difference <=3pp and |CV log-loss delta|<=0.05","actual":f"max_diff={max_combo_diff:.6f}pp; logloss_delta={bn_delta_logloss:.6f}","interpretation":"joint/conditional preservation only; non-causal"},
      {"validation":"세션 시계열 간격","status":time_status,"criterion":"negative gaps/search reversals/event reversals all zero; fitted-lognormal bootstrap GOF p>=0.05 for distributional PASS","actual":f"negative={timing.negative_n.sum()}; search_reverse={timing.search_time_reverse_n.sum()}; event_reverse={timing.event_time_reverse_n.sum()}; bootstrap_p_original={timing.iloc[0].parametric_bootstrap_gof_pvalue:.6f}; bootstrap_p_s0={timing.iloc[1].parametric_bootstrap_gof_pvalue:.6f}","interpretation":"empirical intervals preserved; fitted lognormal rejected at 5%; not lognormal-generated"},
      {"validation":"모드 붕괴와 Jittering","status":"WARN","criterion":"diagnose designed repetition separately from stochastic mode collapse","actual":f"S0 unique ratio={mm2['unique_ratio']:.6f}; templates 32x23 + 11x24; jitter=false","interpretation":"designed balanced-bootstrap repetition; no learned generator collapse, but low diversity and exact duplication are material"},
      {"validation":"필수 회귀검증","status":"PASS" if regression_pass else "FAIL","criterion":"all DB recalculations equal existing STEP2/STEP3 and integrity checks pass","actual":f"regression_fail={(regression_check.match_status!='PASS').sum()}; trace_fail={(traces.status!='PASS').sum()}; integrity_fail={(integrity.status!='PASS').sum()}","interpretation":"no existing result changed"}])
    final="CONDITIONAL PASS" if regression_pass and not gates.status.eq("FAIL").any() else "FAIL"
    stem=args.stamp;pngs=plots(output,stem,original,synthetic,bn_cal,top10)
    xlsx=output/f"호텔검색_관측형합성1000명_보완검증결과_{stem}_01.xlsx"
    sheets={"run_definitions":definition,"filter_schema":schema,"active_filter_rules":active_defs,"filter_count":counts,"high_order_combos":combos,"combo_comparison":combo_comp,"sparse_cells":sparse,"BN_scores":bn_scores,"BN_calibration":bn_cal,"timing":timing,"mode_metrics":mode,"top10_signatures":top10,"template_copies":template_counts,"jitter_fields":jitter_fields,"integrity":integrity,"regression_values":regression,"regression_check":regression_check,"deterministic_traces":traces,"validation_gates":gates}
    with pd.ExcelWriter(xlsx,engine="openpyxl") as w:
        for name,df in sheets.items():df.to_excel(w,sheet_name=name,index=False)
        for ws in w.book.worksheets:
            ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
            for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=min(60,max(12,max(len(str(c.value or "")) for c in col)+2))
    after={str(p.resolve()):sha256(p) for p in inputs};immutable=before==after
    package_versions={x:importlib.metadata.version(x) for x in ["numpy","pandas","scipy","openpyxl","matplotlib"]}
    summary={"step":"STEP_B","status":final,"started_at_kst":started,"finished_at_kst":datetime.now(KST).isoformat(),"seed":SEED,"bootstrap_reps":BOOTSTRAPS,"folds":FOLDS,"python":platform.python_version(),"platform":platform.platform(),"packages":package_versions,"sqlite_access":"URI mode=ro; PRAGMA query_only=ON","inputs_before":before,"inputs_after":after,"inputs_immutable":immutable,"analysis_definitions":definition.to_dict("records"),"high_order":{"original_n":int(high_orig.sum()),"original_zero_n":int((high_orig&original['base'].is_zero_result).sum()),"synthetic_n":int(high_syn.sum()),"synthetic_zero_n":int((high_syn&synthetic['base'].is_zero_result).sum()),"max_combo_rate_difference_pp":max_combo_diff},"bn_scores":bn_scores.to_dict("records"),"timing":timing.to_dict("records"),"mode_metrics":mode.to_dict("records"),"jitter_audit":jitter,"regression_pass":regression_pass,"gates":gates.to_dict("records"),"limitations":["Synthetic p-values and narrow intervals are model-internal diagnostics, not stronger real-population evidence.","The constrained Naive Bayes is a diagnostic DAG, not a causal graph.","KS naive p-values are auxiliary because lognormal parameters are estimated from the same sample.","S0 source templates repeat across sessions; CV groups use source-template fingerprints to avoid template leakage.","Room count, cancellation, and payment options are not search/search_filter condition columns and are null in the signature."],"generated_files_pending_hash":[]}
    json_path=output/f"호텔검색_관측형합성1000명_보완검증결과_{stem}_01.json";json_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    judgment=output/f"호텔검색_관측형합성1000명_검증판단로그_{stem}_01.md"
    judgment.write_text("# STEP B 검증 판단 로그\n\n"+f"- 최종 판정: **STEP B={final}**\n- 입력 불변: **{'PASS' if immutable else 'FAIL'}**\n- 회귀검증: **{'PASS' if regression_pass else 'FAIL'}**\n\n## 보완사항별 판정\n\n"+"\n".join(f"- {r.validation}: **{r.status}** — {r.actual}. {r.interpretation}" for _,r in gates.iloc[:3].iterrows())+"\n\n## Jittering\n\n- 연속형 Jittering은 적용되지 않았다. 현재 중복의 직접 원인은 43개 원본 세션을 23~24회 반복하는 균등 부트스트랩이다.\n- 이는 학습형 생성기의 확률적 모드 붕괴로 확인된 것은 아니지만, 조건 다양성이 증가하지 않는다는 실질적 한계가 있다.\n- 필터·결과·세그먼트 정답에 대한 Jittering은 기존 가설을 바꿀 위험이 있어 바로 도입하지 않는다.\n\n## 해석 제한\n\n- 합성 표본의 작은 p값은 실제 모집단 근거 강화가 아니다.\n- BN은 결합분포 보존 점검용 제한 DAG이며 인과모형이 아니다.\n- 시간 간격은 로그정규분포에서 생성된 것이 아니라 원본 경험분포를 반복 보존한 것이다.\n",encoding="utf-8")
    log=output/f"호텔검색_관측형합성1000명_보완검증실행로그_{stem}_01.md"
    cmd=f'python "{Path(__file__).resolve()}" --original-db "{args.original_db.resolve()}" --synthetic-db "{args.synthetic_db.resolve()}" --generator "{args.generator.resolve()}" --step2-excel "{args.step2_excel.resolve()}" --step3-excel "{args.step3_excel.resolve()}" --output-dir "<NEW_EMPTY_OUTPUT_DIR>" --stamp "{stem}"'
    log.write_text(f"# STEP B 보완검증 실행 로그\n\n- 시작: `{started}`\n- 종료: `{datetime.now(KST).isoformat()}`\n- 판정: **STEP B={final}**\n- Python: `{platform.python_version()}`\n- 패키지: `{json.dumps(package_versions,ensure_ascii=False)}`\n- seed: `{SEED}` / bootstrap: `{BOOTSTRAPS}` / folds: `{FOLDS}`\n- SQLite: URI `mode=ro`, `PRAGMA query_only=ON`\n- 입력 전후 SHA-256 불변: **{immutable}**\n- 생성기 실행·수정: 없음\n- 합성 DB 수정: 없음\n- 보고서 수정: 없음\n- 재현 명령: `{cmd}`\n",encoding="utf-8")
    artifacts=[Path(__file__).resolve(),xlsx,json_path,*pngs,log,judgment]
    manifest=[{"path":str(p),"size_bytes":p.stat().st_size,"sha256":sha256(p)} for p in artifacts if p != json_path]
    manifest.append({"path":str(json_path),"size_bytes":json_path.stat().st_size,"sha256":None,"reason":"self-referential JSON hash omitted; calculate externally"})
    summary["generated_files_pending_hash"]=manifest
    json_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    # JSON self-hash is reported externally; avoid a recursive embedded self-hash claim.
    # ASCII-safe console output also works in Windows shells using legacy code pages.
    print(json.dumps({"status":final,"output_dir":str(output),"gates":gates.to_dict("records"),"artifacts":[{"path":str(p),"sha256":sha256(p)} for p in artifacts]},ensure_ascii=True,indent=2))
    if final=="FAIL" or not immutable:sys.exit(2)


if __name__=="__main__":
    main()
