#!/usr/bin/env python3
"""Compute the approved original-296 analysis directly from read-only SQLite.

No synthetic, stress, 1,000-person, or 10,000-person records are created.
BOOKING is not used as a conversion KPI. It is checked only for integrity.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu

from build_original_296_marts import (
    build_event_search_flags,
    build_ordered_searches,
    build_search_base,
    build_session_segments,
    build_session_summary,
    build_zero_transitions,
    coerce_types,
    load_sources,
    normalize_text,
    open_read_only,
    source_fingerprint,
)

EXPECTED = {
    "searches": 296,
    "zero_transitions": 140,
    "sessions": 43,
    "segments": {"직접 성공": 27, "결과 노출·미선택": 10, "재검색 회복": 4, "지속 실패": 2},
    "transitions": {"동일조건 반복": 53, "조건 완화": 41, "검색어 수정": 10,
                    "지역 변경": 24, "조건 강화": 10, "혼합 변경": 2},
}
A1_LIMITATION = "입력 상태를 구분할 컬럼이 없어 조건 제한 효과와 입력 품질 효과를 분리하지 못했다."


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyze the original 296 searches")
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    return p.parse_args()


def pct(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else math.nan


def normalized_row(**kwargs) -> dict:
    """Common Excel schema; unused statistical cells remain null, never invented."""
    row = {k: None for k in [
        "metric", "group", "analysis_unit", "numerator", "denominator", "rate",
        "n", "test", "statistic", "odds_ratio", "ci_95_low", "ci_95_high",
        "p_value", "interpretation", "limitation",
    ]}
    row.update(kwargs)
    return row


def fisher_with_ci(a: int, b: int, c: int, d: int) -> dict:
    """Two-sided Fisher test and large-sample log-OR CI when all cells are positive."""
    result = fisher_exact([[a, b], [c, d]], alternative="two-sided")
    odds = float(result.statistic)
    lo = hi = math.nan
    if min(a, b, c, d) > 0 and math.isfinite(odds) and odds > 0:
        se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        lo, hi = math.exp(math.log(odds) - 1.96 * se), math.exp(math.log(odds) + 1.96 * se)
    return {"test": "Fisher exact (two-sided)", "statistic": odds,
            "odds_ratio": odds, "ci_95_low": lo, "ci_95_high": hi,
            "p_value": float(result.pvalue)}


def add_group_comparison(df: pd.DataFrame, mask: pd.Series, metric: str,
                         exposed: str, reference: str) -> list[dict]:
    zero = df["total_result_count"].eq(0)
    a, b = int((mask & zero).sum()), int((mask & ~zero).sum())
    c, d = int((~mask & zero).sum()), int((~mask & ~zero).sum())
    stats = fisher_with_ci(a, b, c, d)
    r1, r0 = pct(a, a + b), pct(c, c + d)
    common = dict(metric=metric, analysis_unit="search", test=stats["test"],
                  statistic=stats["statistic"], odds_ratio=stats["odds_ratio"],
                  ci_95_low=stats["ci_95_low"], ci_95_high=stats["ci_95_high"],
                  p_value=stats["p_value"], interpretation="A1 부분 채택",
                  limitation=A1_LIMITATION)
    return [
        normalized_row(group=exposed, numerator=a, denominator=a + b, rate=r1,
                       n=a + b, percentage_point_difference=(r1 - r0) * 100, **common),
        normalized_row(group=reference, numerator=c, denominator=c + d, rate=r0,
                       n=c + d, percentage_point_difference=(r0 - r1) * 100, **common),
    ]


def build_overview(base, flags, ordered, transitions, summary, conn) -> pd.DataFrame:
    total = len(base)
    zero_n = int(base["total_result_count"].eq(0).sum())
    positive = total - zero_n
    result_counts = base["total_result_count"]
    rows = [
        normalized_row(metric="search_count", analysis_unit="search", n=total,
                       interpretation="원본 검색 행 수"),
        normalized_row(metric="session_count", analysis_unit="session", n=len(summary),
                       interpretation="세션 분모"),
        normalized_row(metric="result_count_min", analysis_unit="search", statistic=float(result_counts.min())),
        normalized_row(metric="result_count_q1", analysis_unit="search", statistic=float(result_counts.quantile(.25))),
        normalized_row(metric="result_count_median", analysis_unit="search", statistic=float(result_counts.median())),
        normalized_row(metric="result_count_mean", analysis_unit="search", statistic=float(result_counts.mean())),
        normalized_row(metric="result_count_q3", analysis_unit="search", statistic=float(result_counts.quantile(.75))),
        normalized_row(metric="result_count_max", analysis_unit="search", statistic=float(result_counts.max())),
        normalized_row(metric="zero_result_rate", analysis_unit="search", numerator=zero_n,
                       denominator=total, rate=pct(zero_n, total), n=total),
    ]
    # B1-style immediate follow-up rates, shown here as basic funnel metrics.
    has_next = ordered["next_search_id"].notna()
    for is_zero, label in [(True, "followup_rate_after_zero"), (False, "followup_rate_after_nonzero")]:
        cohort = ordered["total_result_count"].eq(0) if is_zero else ordered["total_result_count"].gt(0)
        num, den = int((cohort & has_next).sum()), int(cohort.sum())
        rows.append(normalized_row(metric=label, analysis_unit="search", numerator=num,
                                   denominator=den, rate=pct(num, den), n=den))
    immediate_n = int(transitions["next_recovered"].sum())
    rows.append(normalized_row(metric="immediate_recovery_rate", analysis_unit="zero search with next search",
                               numerator=immediate_n, denominator=len(transitions),
                               rate=pct(immediate_n, len(transitions)), n=len(transitions)))
    # Final recovery uses sessions that experienced any zero result. A session is
    # recovered when its chronologically final search has a nonzero result.
    final_cohort = summary["experienced_zero"]
    final_n, final_d = int(summary.loc[final_cohort, "session_final_recovered"].sum()), int(final_cohort.sum())
    rows.append(normalized_row(metric="session_final_recovery_rate", analysis_unit="session experiencing any zero result",
                               numerator=final_n, denominator=final_d, rate=pct(final_n, final_d), n=final_d))
    click_searches = int(flags["has_click"].sum())
    rows.extend([
        normalized_row(metric="hotel_click_detail_entry_rate_all_searches", analysis_unit="search",
                       numerator=click_searches, denominator=total, rate=pct(click_searches, total), n=total,
                       limitation="hotel_click만 KPI로 사용; hotel_detail_view는 중복 KPI로 사용하지 않음"),
        normalized_row(metric="hotel_click_detail_entry_rate_positive_result_searches", analysis_unit="positive-result search",
                       numerator=int((flags.set_index("search_id").loc[base.loc[base.total_result_count.gt(0), "search_id"], "has_click"]).sum()),
                       denominator=positive, rate=pct(int((flags.set_index("search_id").loc[base.loc[base.total_result_count.gt(0), "search_id"], "has_click"]).sum()), positive), n=positive,
                       limitation="노출 결과가 있는 검색만 분모; 미노출 클릭 이슈는 품질경고로 분리"),
    ])
    # BOOKING is integrity-only and never converted into a booking rate.
    mismatch = conn.execute("SELECT COUNT(*) FROM booking b JOIN room r USING(room_id) WHERE b.hotel_id<>r.hotel_id").fetchone()[0]
    rows.append(normalized_row(metric="booking_room_hotel_mismatch", analysis_unit="booking",
                               numerator=mismatch, denominator=conn.execute("SELECT COUNT(*) FROM booking").fetchone()[0],
                               n=conn.execute("SELECT COUNT(*) FROM booking").fetchone()[0],
                               interpretation="참고·무결성 점검만 수행",
                               limitation="BOOKING을 핵심 예약 전환율로 사용하지 않음"))
    return pd.DataFrame(rows)


def build_a1(base: pd.DataFrame) -> pd.DataFrame:
    records = []
    records += add_group_comparison(base, base["amenity_count"].ge(3), "amenity_count>=3 vs <3", "amenity_count>=3", "amenity_count<3")
    records += add_group_comparison(base, base["user_rating_min"].notna(), "user_rating_min set vs unset", "set", "unset")
    records += add_group_comparison(base, base["price"].notna(), "price set vs unset", "set", "unset")
    return pd.DataFrame(records)


def build_a2_region(base: pd.DataFrame) -> pd.DataFrame:
    # Approved region is the city prefix of destination (e.g. Tokyo · Shinjuku).
    # Missing/unrecognized values are UNKNOWN and are never imputed to a city.
    def city(value):
        text = normalize_text(value)
        if text is None:
            return "UNKNOWN"
        for raw, label in [("tokyo", "Tokyo"), ("osaka", "Osaka"), ("kyoto", "Kyoto"),
                           ("sapporo", "Sapporo"), ("fukuoka", "Fukuoka")]:
            if text == raw or text.startswith(raw + " ·"):
                return label
        return "UNKNOWN"
    region = base["destination"].map(city)
    records = []
    for label in ["Tokyo", "Osaka", "Kyoto", "Sapporo", "Fukuoka", "UNKNOWN"]:
        m = region.eq(label); n = int(m.sum()); z = int((m & base.total_result_count.eq(0)).sum())
        records.append(normalized_row(metric="zero_result_rate_by_region", group=label,
            analysis_unit="search", numerator=z, denominator=n, rate=pct(z, n), n=n,
            interpretation="기술통계", limitation="지역×의도 희소 셀은 우열·인과 해석 금지"))
    return pd.DataFrame(records)


def build_a2_intent(base: pd.DataFrame) -> pd.DataFrame:
    # Intent is one-search-level coding. Amenity is set only when amenity_count > 0.
    price = base["price"].notna()
    rating = base["user_rating_min"].notna()
    amenity = base["amenity_count"].fillna(0).gt(0)
    count = price.astype(int) + rating.astype(int) + amenity.astype(int)
    intent = pd.Series("LOCATION_ONLY", index=base.index)
    intent[count.ge(2)] = "MIXED"
    intent[(count.eq(1)) & price] = "PRICE"
    intent[(count.eq(1)) & rating] = "QUALITY_FILTER"
    intent[(count.eq(1)) & amenity] = "AMENITY"
    records = []
    for label in ["LOCATION_ONLY", "PRICE", "QUALITY_FILTER", "AMENITY", "MIXED"]:
        m = intent.eq(label); n = int(m.sum()); z = int((m & base.total_result_count.eq(0)).sum())
        records.append(normalized_row(metric="zero_result_rate_by_intent", group=label,
            analysis_unit="search", numerator=z, denominator=n, rate=pct(z, n), n=n,
            interpretation="기술통계", limitation="희소 의도 셀은 우열·인과 해석 금지; QUALITY_FILTER는 C3 사용자 세그먼트가 아님"))
    return pd.DataFrame(records)


def build_b1(ordered: pd.DataFrame) -> pd.DataFrame:
    zero, nxt = ordered.total_result_count.eq(0), ordered.next_search_id.notna()
    a, b = int((zero & nxt).sum()), int((zero & ~nxt).sum())
    c, d = int((~zero & nxt).sum()), int((~zero & ~nxt).sum())
    stats = fisher_with_ci(a, b, c, d)
    common = dict(metric="immediate_followup_search_rate", analysis_unit="search", **stats,
                  interpretation="B1 채택: 0건 여부와 바로 다음 검색 존재의 관련",
                  limitation="관찰 관련이며 인과효과로 단정하지 않음")
    return pd.DataFrame([
        normalized_row(group="zero_result", numerator=a, denominator=a+b, rate=pct(a,a+b), n=a+b, **common),
        normalized_row(group="positive_result", numerator=c, denominator=c+d, rate=pct(c,c+d), n=c+d, **common),
    ])


def build_b2(summary: pd.DataFrame) -> pd.DataFrame:
    yes = summary.loc[summary.experienced_zero, "search_count"].astype(float)
    no = summary.loc[~summary.experienced_zero, "search_count"].astype(float)
    result = mannwhitneyu(yes, no, alternative="two-sided", method="auto")
    records = []
    for label, values in [("experienced_zero", yes), ("no_zero_experience", no)]:
        records.append(normalized_row(metric="session_search_count", group=label,
            analysis_unit="session", n=len(values), mean=float(values.mean()), median=float(values.median()),
            q1=float(values.quantile(.25)), q3=float(values.quantile(.75)),
            iqr=float(values.quantile(.75)-values.quantile(.25)), test="Mann–Whitney U (two-sided)",
            statistic=float(result.statistic), p_value=float(result.pvalue),
            interpretation="B2 채택·주의: 세션 특성 간 연관만 보고",
            limitation="탐색지속성이 높은 사용자가 0건과 많은 검색을 모두 경험했을 교란 가능성; 인과 해석 금지"))
    return pd.DataFrame(records)


def build_b3(transitions: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    immediate_n, immediate_d = int(transitions.next_recovered.sum()), len(transitions)
    final_cohort = summary.experienced_zero
    final_n, final_d = int(summary.loc[final_cohort, "session_final_recovered"].sum()), int(final_cohort.sum())
    return pd.DataFrame([
        normalized_row(metric="immediate_recovery", analysis_unit="zero search with immediate next search",
                       numerator=immediate_n, denominator=immediate_d, rate=pct(immediate_n,immediate_d), n=immediate_d,
                       interpretation="B3 즉시 회복", limitation="분모는 0건→바로 다음 검색 전이"),
        normalized_row(metric="session_final_recovery", analysis_unit="session experiencing any zero result",
                       numerator=final_n, denominator=final_d, rate=pct(final_n,final_d), n=final_d,
                       interpretation="B3 세션 최종 회복", limitation="분모는 0건을 1회 이상 경험한 세션; 즉시 회복과 다른 분모"),
    ])


def build_segments(segments: pd.DataFrame) -> pd.DataFrame:
    counts = segments.result_segment.value_counts()
    order = ["직접 성공", "결과 노출·미선택", "재검색 회복", "지속 실패"]
    return pd.DataFrame([normalized_row(metric="session_result_segment", group=x,
        analysis_unit="session", numerator=int(counts.get(x,0)), denominator=len(segments),
        rate=pct(int(counts.get(x,0)),len(segments)), n=int(counts.get(x,0)),
        interpretation="상호배타 4개 결과 세그먼트", limitation="비율 분모 n=43") for x in order])


def build_h3(transitions: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    next_click = flags.set_index("search_id")["has_click"]
    work = transitions.copy()
    work["next_has_click"] = work.next_search_id.map(next_click).fillna(False).astype(bool)
    order = ["동일조건 반복", "조건 완화", "검색어 수정", "지역 변경", "조건 강화", "혼합 변경"]
    records = []
    for label in order:
        g = work[work.transition_type.eq(label)]; n = len(g)
        for metric, col in [("next_search_positive_result_rate","next_recovered"),
                            ("next_search_hotel_click_rate","next_has_click")]:
            num = int(g[col].sum())
            records.append(normalized_row(metric=metric, group=label,
                analysis_unit="zero-result search -> immediate next search transition",
                numerator=num, denominator=n, rate=pct(num,n), n=n,
                interpretation="H3 탐색적 결과",
                limitation="유형별 n과 분류 규칙에 민감; 제품 개선의 인과효과로 단정 금지. hotel_click만 상세진입 KPI로 사용"))
    return pd.DataFrame(records)


def compare_reference(base, transitions, summary, segments) -> list[dict]:
    """Reference values diagnose drift only; they never overwrite calculations."""
    actual = {
        "searches": len(base), "zero_transitions": len(transitions), "sessions": len(summary),
        **{f"segment::{k}": v for k,v in segments.result_segment.value_counts().to_dict().items()},
        **{f"transition::{k}": v for k,v in transitions.transition_type.value_counts().to_dict().items()},
    }
    expected = {"searches": EXPECTED["searches"], "zero_transitions": EXPECTED["zero_transitions"],
                "sessions": EXPECTED["sessions"],
                **{f"segment::{k}":v for k,v in EXPECTED["segments"].items()},
                **{f"transition::{k}":v for k,v in EXPECTED["transitions"].items()}}
    return [{"metric": k, "actual": actual.get(k,0), "reference": v,
             "difference": actual.get(k,0)-v,
             "diagnosis": "match" if actual.get(k,0)==v else "check join/sort/denominator/transition definition/file version"}
            for k,v in expected.items()]


def write_results(output_dir: Path, tables: dict[str,pd.DataFrame], manifest: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx = output_dir / "original_296_analysis.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        for sheet, table in tables.items():
            table.to_excel(writer, sheet_name=sheet, index=False)
            table.to_csv(output_dir / f"{sheet}.csv", index=False, encoding="utf-8-sig")
    (output_dir / "analysis_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return xlsx


def main() -> int:
    args = parse_args(); db = args.db.expanduser().resolve(strict=True); before = source_fingerprint(db)
    conn = open_read_only(db)
    try:
        search, filt, event = load_sources(conn)
        search, filt, event = coerce_types(search, filt, event)
        base = build_search_base(search, filt)
        flags = build_event_search_flags(base, event)
        ordered = build_ordered_searches(base)
        transitions = build_zero_transitions(ordered)
        summary = build_session_summary(ordered, flags)
        last_result = ordered.groupby("session_id", sort=False).tail(1).set_index("session_id")["total_result_count"]
        summary["session_final_recovered"] = summary["session_id"].map(last_result).gt(0)
        segment_assignments = build_session_segments(summary)
        comparisons = compare_reference(base, transitions, summary, segment_assignments)
        mismatches = [x for x in comparisons if x["difference"] != 0]
        tables = {
            "overview": build_overview(base,flags,ordered,transitions,summary,conn),
            "A1_filters": build_a1(base), "A2_region": build_a2_region(base),
            "A2_intent": build_a2_intent(base), "B1": build_b1(ordered),
            "B2": build_b2(summary), "B3": build_b3(transitions,summary),
            "segments": build_segments(segment_assignments),
            "H3_transitions": build_h3(transitions,flags),
        }
        # Extend the drift audit to the published numerator/denominator anchors.
        anchors = {
            "A1::amenity_count>=3": (120,136), "A1::amenity_count<3": (27,160),
            "A1::rating_set": (115,152), "A1::rating_unset": (32,144),
            "A1::price_set": (106,146), "A1::price_unset": (41,150),
            "A2_region::Tokyo": (59,118), "A2_region::Osaka": (49,80),
            "A2_region::Kyoto": (6,17), "A2_region::Sapporo": (3,21),
            "A2_region::Fukuoka": (3,15), "A2_region::UNKNOWN": (27,45),
            "B1::zero": (140,147), "B1::positive": (113,149),
            "B3::immediate": (24,140), "B3::final": (21,28),
        }
        actual_pairs = {}
        a1 = tables["A1_filters"].set_index("group")
        for key, group in [("A1::amenity_count>=3","amenity_count>=3"),("A1::amenity_count<3","amenity_count<3"),
                           ("A1::rating_set","set"),("A1::rating_unset","unset")]:
            # 'set'/'unset' appear twice; rating is the first matching metric.
            metric = "user_rating_min set vs unset" if "rating" in key else "amenity_count>=3 vs <3"
            row = tables["A1_filters"].query("metric == @metric and group == @group").iloc[0]
            actual_pairs[key] = (int(row.numerator),int(row.denominator))
        for key, group in [("A1::price_set","set"),("A1::price_unset","unset")]:
            row=tables["A1_filters"].query("metric == 'price set vs unset' and group == @group").iloc[0]
            actual_pairs[key]=(int(row.numerator),int(row.denominator))
        for group,row in tables["A2_region"].set_index("group").iterrows():
            actual_pairs[f"A2_region::{group}"]=(int(row.numerator),int(row.denominator))
        for key,idx in [("B1::zero",0),("B1::positive",1)]:
            row=tables["B1"].iloc[idx]; actual_pairs[key]=(int(row.numerator),int(row.denominator))
        for key,idx in [("B3::immediate",0),("B3::final",1)]:
            row=tables["B3"].iloc[idx]; actual_pairs[key]=(int(row.numerator),int(row.denominator))
        for key,reference in anchors.items():
            actual=actual_pairs[key]
            comparisons.append({"metric":key,"actual":list(actual),"reference":list(reference),
                "difference":[actual[0]-reference[0],actual[1]-reference[1]],
                "diagnosis":"match" if actual==reference else "check join/sort/denominator/transition definition/file version"})
        mismatches = [x for x in comparisons if x["difference"] not in (0,[0,0])]
        # The required normalized columns are retained; additional measure columns are allowed.
        assert not any({"user_name","email"} & set(t.columns) for t in tables.values())
        assert len(base)==296 and len(transitions)==140 and len(summary)==43 and len(segment_assignments)==43
        assert not mismatches, json.dumps(mismatches, ensure_ascii=False)
        manifest = {"generated_at":datetime.now().astimezone().isoformat(), "source_db":str(db),
            "source_fingerprint":before, "sqlite_mode":"URI mode=ro + PRAGMA query_only=ON",
            "reference_comparison":comparisons, "reference_mismatches":mismatches,
            "analysis_units":{"search":296,"zero_transition":140,"session":43},
            "a3_excluded":True,"blank_query_as_typo":False,"booking_as_core_conversion":False,
            "statistical_tests":["Fisher exact two-sided","Mann–Whitney U two-sided"],
            "synthetic_data_generated":False}
        xlsx = write_results(args.output_dir.resolve(), tables, manifest)
    finally:
        conn.close()
    after = source_fingerprint(db)
    assert before == after, "Source DB changed during analysis"
    print(json.dumps({"workbook":str(xlsx),"rows":{k:len(v) for k,v in tables.items()},
                      "reference_mismatches":mismatches,"source_unchanged":True},ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
