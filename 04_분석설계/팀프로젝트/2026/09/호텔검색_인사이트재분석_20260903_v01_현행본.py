"""2026-09-03 v03 호텔 검색 데이터의 핵심 인사이트를 재현한다.

실행:
    python 04_분석설계/팀프로젝트/2026/09/호텔검색_인사이트재분석_20260903_v01_현행본.py

표준 출력은 보고서 수치를 검증할 수 있는 JSON이다. 원천 DB는 읽기 전용으로 연다.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu


ROOT = Path(__file__).resolve().parents[4]
DB_PATH = (
    ROOT
    / "03_데이터모델링"
    / "현행데이터"
    / "travel_data_filtered_complete_2026-09-03_v03_비식별.sqlite"
)


def null_safe_equal(left: object, right: object) -> bool:
    return bool((pd.isna(left) and pd.isna(right)) or left == right)


def safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else math.nan


def rounded_rate(numerator: int, denominator: int) -> float:
    return round(100 * safe_rate(numerator, denominator), 1)


def condition_summary(frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    numerator = int(frame.loc[mask, "is_zero"].sum())
    denominator = int(mask.sum())
    complement_numerator = int(frame.loc[~mask, "is_zero"].sum())
    complement_denominator = int((~mask).sum())
    rate = 100 * safe_rate(numerator, denominator)
    complement_rate = 100 * safe_rate(complement_numerator, complement_denominator)
    return {
        "zero_results": numerator,
        "searches": denominator,
        "zero_result_rate_pct": round(rate, 1),
        "comparison_zero_results": complement_numerator,
        "comparison_searches": complement_denominator,
        "comparison_rate_pct": round(complement_rate, 1),
        "difference_pp": round(rate - complement_rate, 1),
        "risk_ratio": round(rate / complement_rate, 2),
    }


def constraint_direction(row: dict[str, Any]) -> tuple[bool, bool]:
    """가격·최소평점·편의시설의 완화/강화 여부를 반환한다."""
    relaxed: list[bool] = []
    stricter: list[bool] = []

    for field in ("user_rating_min", "amenity_count"):
        before, after = row[field], row[f"next_{field}"]
        relaxed.append(
            (not pd.isna(before) and pd.isna(after))
            or (
                not pd.isna(before)
                and not pd.isna(after)
                and float(after) < float(before)
            )
        )
        stricter.append(
            (pd.isna(before) and not pd.isna(after))
            or (
                not pd.isna(before)
                and not pd.isna(after)
                and float(after) > float(before)
            )
        )

    before, after = row["price"], row["next_price"]
    relaxed.append(
        (not pd.isna(before) and pd.isna(after))
        or (
            not pd.isna(before)
            and not pd.isna(after)
            and float(after) > float(before)
        )
    )
    stricter.append(
        (pd.isna(before) and not pd.isna(after))
        or (
            not pd.isna(before)
            and not pd.isna(after)
            and float(after) < float(before)
        )
    )
    return any(relaxed), any(stricter)


def classify_transition(row: dict[str, Any], condition_fields: list[str]) -> str:
    """상호배타적 분류. 앞선 규칙이 우선하며 혼합 방향은 별도 보존한다."""
    if all(
        null_safe_equal(row[field], row[f"next_{field}"])
        for field in condition_fields
    ):
        return "동일 조건"
    if not null_safe_equal(row["region"], row["next_region"]):
        return "지역 변경"
    if not null_safe_equal(row["query_text"], row["next_query_text"]):
        return "키워드 변경"

    relaxed, stricter = constraint_direction(row)
    if relaxed and not stricter:
        return "조건 완화"
    if stricter and not relaxed:
        return "조건 강화"
    if relaxed and stricter:
        return "완화·강화 혼합"
    return "기타"


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)

    connection = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        search = pd.read_sql_query("SELECT * FROM search", connection)
        search_filter = pd.read_sql_query("SELECT * FROM search_filter", connection)
        search_result = pd.read_sql_query("SELECT * FROM search_result", connection)
        event = pd.read_sql_query("SELECT * FROM event", connection)

        quality = {
            "search_rows": len(search),
            "search_filter_rows": len(search_filter),
            "search_result_rows": len(search_result),
            "event_rows": len(event),
            "search_primary_key_duplicates": int(search["search_id"].duplicated().sum()),
            "filter_search_id_duplicates": int(
                search_filter["search_id"].duplicated().sum()
            ),
            "invalid_stay_date_rows": int(search["invalid_stay_date_flag"].sum()),
            "invalid_stay_date_nulls": int(
                search["invalid_stay_date_flag"].isna().sum()
            ),
            "hotel_click_rows": int((event["event_type"] == "hotel_click").sum()),
            "valid_exposure_click_rows": int(
                (
                    (event["event_type"] == "hotel_click")
                    & (event["click_in_result_flag"] == 1)
                ).sum()
            ),
            "unmatched_click_rows": int(
                (
                    (event["event_type"] == "hotel_click")
                    & (event["click_in_result_flag"] == 0)
                ).sum()
            ),
            "non_click_rows_with_flag": int(
                (
                    (event["event_type"] != "hotel_click")
                    & event["click_in_result_flag"].notna()
                ).sum()
            ),
        }
        expected = {
            "search_rows": 296,
            "search_filter_rows": 296,
            "search_primary_key_duplicates": 0,
            "filter_search_id_duplicates": 0,
            "invalid_stay_date_rows": 9,
            "invalid_stay_date_nulls": 0,
            "hotel_click_rows": 231,
            "valid_exposure_click_rows": 229,
            "unmatched_click_rows": 2,
            "non_click_rows_with_flag": 0,
        }
        failures = {
            key: {"actual": quality[key], "expected": value}
            for key, value in expected.items()
            if quality[key] != value
        }
        if failures:
            raise RuntimeError(f"데이터 품질 검증 실패: {failures}")

        searches = search.merge(
            search_filter,
            on="search_id",
            how="left",
            validate="one_to_one",
            suffixes=("", "_filter"),
        )
        if len(searches) != len(search):
            raise RuntimeError("search-filter 결합 후 행 수가 보존되지 않았다.")

        searches["search_at"] = pd.to_datetime(
            searches["search_time"].str.replace(" KST", "", regex=False),
            errors="raise",
        )
        searches = searches.sort_values(
            ["session_id", "search_at", "search_id"], kind="stable"
        ).reset_index(drop=True)
        searches["is_zero"] = searches["total_result_count"].eq(0)

        condition_results = {
            "amenity_count_ge_3": condition_summary(
                searches, searches["amenity_count"].ge(3)
            ),
            "minimum_rating_set": condition_summary(
                searches, searches["user_rating_min"].notna()
            ),
            "price_filter_set": condition_summary(
                searches, searches["price"].notna()
            ),
        }

        next_fields = [
            "search_id",
            "total_result_count",
            "query_text",
            "guest_count",
            "destination",
            "property_type",
            "property_grade",
            "user_rating_min",
            "price",
            "amenity_count",
            "region",
        ]
        for field in next_fields:
            searches[f"next_{field}"] = searches.groupby("session_id")[field].shift(
                -1
            )
        searches["has_next_search"] = searches["next_search_id"].notna()

        followup_table = pd.crosstab(searches["is_zero"], searches["has_next_search"])
        zero_followup = int(followup_table.loc[True, True])
        zero_no_followup = int(followup_table.loc[True, False])
        nonzero_followup = int(followup_table.loc[False, True])
        nonzero_no_followup = int(followup_table.loc[False, False])
        fisher = fisher_exact(
            [[zero_followup, zero_no_followup], [nonzero_followup, nonzero_no_followup]],
            alternative="two-sided",
        )
        followup = {
            "zero_result": {
                "with_next_search": zero_followup,
                "searches": zero_followup + zero_no_followup,
                "rate_pct": rounded_rate(
                    zero_followup, zero_followup + zero_no_followup
                ),
            },
            "nonzero_result": {
                "with_next_search": nonzero_followup,
                "searches": nonzero_followup + nonzero_no_followup,
                "rate_pct": rounded_rate(
                    nonzero_followup, nonzero_followup + nonzero_no_followup
                ),
            },
            "difference_pp": round(
                100
                * (
                    safe_rate(zero_followup, zero_followup + zero_no_followup)
                    - safe_rate(
                        nonzero_followup, nonzero_followup + nonzero_no_followup
                    )
                ),
                1,
            ),
            "odds_ratio": round(float(fisher.statistic), 2),
            "fisher_exact_p_value": float(fisher.pvalue),
        }

        zero_pairs = searches.loc[
            searches["is_zero"] & searches["has_next_search"]
        ].copy()
        immediate_recovered = int(zero_pairs["next_total_result_count"].gt(0).sum())

        session_zero = searches.groupby("session_id")["is_zero"].any()
        sessions_with_zero = session_zero[session_zero].index
        zero_session_rows = searches[searches["session_id"].isin(sessions_with_zero)]
        final_searches = zero_session_rows.groupby("session_id", as_index=False).tail(1)
        final_recovered = int(final_searches["total_result_count"].gt(0).sum())
        recovery = {
            "immediate_transition": {
                "recovered": immediate_recovered,
                "zero_to_next_transitions": len(zero_pairs),
                "rate_pct": rounded_rate(immediate_recovered, len(zero_pairs)),
            },
            "within_session": {
                "recovered_sessions": final_recovered,
                "sessions_experiencing_zero": len(sessions_with_zero),
                "rate_pct": rounded_rate(final_recovered, len(sessions_with_zero)),
            },
            "warning": "서로 다른 분석 단위와 분모이므로 두 비율의 증감률을 계산하지 않음",
        }

        detail_search_ids = set(
            event.loc[
                (event["event_type"] == "hotel_detail_view")
                & event["search_id"].notna(),
                "search_id",
            ].unique()
        )
        condition_fields = [
            "query_text",
            "guest_count",
            "destination",
            "property_type",
            "property_grade",
            "user_rating_min",
            "price",
            "amenity_count",
            "region",
        ]
        transition_rows = zero_pairs.to_dict("records")
        for row in transition_rows:
            row["method"] = classify_transition(row, condition_fields)
            row["recovered"] = bool(row["next_total_result_count"] > 0)
            row["detail_entered"] = row["next_search_id"] in detail_search_ids

        method_order = [
            "동일 조건",
            "지역 변경",
            "키워드 변경",
            "조건 완화",
            "조건 강화",
            "완화·강화 혼합",
            "기타",
        ]
        method_results: dict[str, Any] = {}
        for method in method_order:
            selected = [row for row in transition_rows if row["method"] == method]
            if not selected:
                continue
            recovered = sum(row["recovered"] for row in selected)
            detailed = sum(row["detail_entered"] for row in selected)
            method_results[method] = {
                "transitions": len(selected),
                "recovered": recovered,
                "recovery_rate_pct": rounded_rate(recovered, len(selected)),
                "detail_entries": detailed,
                "detail_entry_rate_pct": rounded_rate(detailed, len(selected)),
            }

        if sum(item["transitions"] for item in method_results.values()) != len(
            zero_pairs
        ):
            raise RuntimeError("재검색 방법 분류가 전체 전환 수와 일치하지 않는다.")
        if sum(item["recovered"] for item in method_results.values()) != immediate_recovered:
            raise RuntimeError("방법별 회복 합계가 전체 즉시 회복 수와 일치하지 않는다.")

        search_counts = searches.groupby("session_id").size()
        zero_group_counts = search_counts.loc[sessions_with_zero]
        nonzero_group_counts = search_counts.loc[session_zero[~session_zero].index]
        mann_whitney = mannwhitneyu(
            zero_group_counts, nonzero_group_counts, alternative="two-sided"
        )
        persistence = {
            "zero_experienced_sessions": {
                "sessions": len(zero_group_counts),
                "mean_searches": round(float(zero_group_counts.mean()), 2),
                "median_searches": round(float(zero_group_counts.median()), 2),
            },
            "no_zero_sessions": {
                "sessions": len(nonzero_group_counts),
                "mean_searches": round(float(nonzero_group_counts.mean()), 2),
                "median_searches": round(float(nonzero_group_counts.median()), 2),
            },
            "mann_whitney_u": float(mann_whitney.statistic),
            "p_value": float(mann_whitney.pvalue),
            "interpretation": "선택·의도 교란 가능성이 있어 인과효과가 아닌 보조 관찰값",
        }

        detail_pairs = set(
            event.loc[
                (event["event_type"] == "hotel_detail_view")
                & event["search_id"].notna()
                & event["hotel_id"].notna(),
                ["search_id", "hotel_id"],
            ].itertuples(index=False, name=None)
        )
        result_pairs = set(
            search_result[["search_id", "hotel_id"]].itertuples(index=False, name=None)
        )
        quality["detail_pairs_without_search_result"] = len(detail_pairs - result_pairs)
        valid_click_pairs = set(
            event.loc[
                (event["event_type"] == "hotel_click")
                & (event["click_in_result_flag"] == 1),
                ["search_id", "hotel_id"],
            ].itertuples(index=False, name=None)
        )
        quality["valid_click_pair_duplicates"] = quality[
            "valid_exposure_click_rows"
        ] - len(valid_click_pairs)
        ranked_results = search_result.merge(
            search[["search_id", "session_id"]],
            on="search_id",
            how="left",
            validate="many_to_one",
        )
        valid_click_events = event.loc[
            (event["event_type"] == "hotel_click")
            & (event["click_in_result_flag"] == 1),
            ["event_id", "search_id", "hotel_id"],
        ]
        click_events_with_rank = valid_click_events.merge(
            search_result[["search_id", "hotel_id", "result_rank"]],
            on=["search_id", "hotel_id"],
            how="inner",
            validate="many_to_one",
        )
        rank_results: dict[str, Any] = {}
        for rank in range(1, 6):
            slice_frame = ranked_results.loc[ranked_results["result_rank"] == rank]
            denominator = len(slice_frame)
            numerator = sum(
                pair in valid_click_pairs
                for pair in slice_frame[["search_id", "hotel_id"]].itertuples(
                    index=False, name=None
                )
            )
            click_event_count = int(
                (click_events_with_rank["result_rank"] == rank).sum()
            )
            rank_results[str(rank)] = {
                "unique_clicked_results": int(numerator),
                "exposed_results": denominator,
                "unique_exposure_click_rate_pct": rounded_rate(numerator, denominator),
                "click_events": click_event_count,
                "click_events_per_exposure_pct": rounded_rate(
                    click_event_count, denominator
                ),
            }

        search_submit_users = event.loc[
            (event["event_type"] == "search_submit") & event["user_id"].notna(),
            "user_id",
        ].nunique()
        coverage = {
            "search_period_kst": {
                "start": searches["search_at"].min().strftime("%Y-%m-%d %H:%M:%S"),
                "end": searches["search_at"].max().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "searches": len(searches),
            "search_sessions": int(searches["session_id"].nunique()),
            "linked_search_users": int(search_submit_users),
            "zero_result_searches": int(searches["is_zero"].sum()),
            "zero_to_next_transitions": len(zero_pairs),
            "session_start_events": int(
                (event["event_type"] == "session_start").sum()
            ),
            "session_end_events": int((event["event_type"] == "session_end").sum()),
        }

        result = {
            "analysis": {
                "dataset_version": "2026-09-03_v03",
                "database": DB_PATH.relative_to(ROOT).as_posix(),
                "database_sha256": hashlib.sha256(DB_PATH.read_bytes()).hexdigest(),
                "python_version": sys.version.split()[0],
                "pandas_version": pd.__version__,
                "scipy_version": __import__("scipy").__version__,
                "timezone": "Asia/Seoul",
            },
            "quality_checks": quality,
            "coverage": coverage,
            "zero_result_by_condition": condition_results,
            "followup_after_search": followup,
            "recovery": recovery,
            "requery_method": method_results,
            "session_search_persistence": persistence,
            "detail_entry_by_rank": rank_results,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
