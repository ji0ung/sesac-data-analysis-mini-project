#!/usr/bin/env python3
"""Read-only aggregation for PROMPT 2.11. It never generates or mutates source/evaluation DBs."""
import collections
import hashlib
import importlib.util
import json
import math
import sqlite3
import statistics
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent
EVAL = ROOT / "evaluation"
DEV = ROOT / "development"
REFERENCE = ROOT.parents[1] / "2단계_1000건_증감_분석" / "01_초기생성_QA_전체분석" / "02_관측형합성1000명_실행묶음_260903_1606_01" / "호텔검색_관측형합성1000명_데이터_260903_1606_01_메타삭제_무인덱스_NULL5유지_텍스트최적화_16K.sqlite"
RUNNER = ROOT / "호텔검색_1만명증강_evaluation_runner_v06_260907_1418_03.py"
OUT_DB = ROOT / "호텔검색_1만명증강_통합평가결과_260907_1418_03.sqlite"
OUT_XLSX = ROOT / "호텔검색_1만명증강_통합평가집계_260907_1418_03.xlsx"
OUT_TRANSITION = ROOT / "호텔검색_1만명증강_기준및생성전이표_260907_1418_03.xlsx"
OUT_DIVERSITY = ROOT / "호텔검색_1만명증강_clone다양성평가_260907_1418_03.xlsx"
OUT_JSON = ROOT / "호텔검색_1만명증강_통합평가결과_260907_1418_03.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ro(path):
    connection = sqlite3.connect("file:" + Path(path).resolve().as_posix() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma query_only=on")
    return connection


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diversity(values):
    counts = collections.Counter(values)
    n = sum(counts.values())
    probabilities = [v / n for v in counts.values()] if n else []
    return {
        "n": n,
        "unique": len(counts),
        "unique_ratio": len(counts) / n if n else None,
        "mode_share": max(probabilities, default=0),
        "hhi": sum(x * x for x in probabilities),
        "shannon": -sum(x * math.log(x) for x in probabilities if x),
        "frequency_1": sum(v == 1 for v in counts.values()),
        "frequency_2": sum(v == 2 for v in counts.values()),
        "frequency_3plus": sum(v >= 3 for v in counts.values()),
    }


def workbook(path, sheets):
    if path.exists():
        raise FileExistsError(path)
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets:
        ws = wb.create_sheet(title[:31])
        if not rows:
            ws.append(["NO_ROWS"])
            continue
        columns = list(rows[0])
        ws.append(columns)
        for row in rows:
            ws.append([row.get(column) for column in columns])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def reference_transitions():
    c = ro(REFERENCE)
    state = c.execute(
        """
        WITH o AS (
          SELECT session_id,total_result_count,
                 LEAD(total_result_count) OVER(PARTITION BY session_id ORDER BY search_time,search_id) nxt
          FROM search
        )
        SELECT SUM(total_result_count=0 AND nxt=0),SUM(total_result_count=0 AND nxt>0),
               SUM(total_result_count=0 AND nxt IS NULL),SUM(total_result_count>0 AND nxt=0),
               SUM(total_result_count>0 AND nxt>0),SUM(total_result_count>0 AND nxt IS NULL),COUNT(*)
        FROM o
        """
    ).fetchone()
    session = c.execute(
        """
        WITH o AS (
          SELECT *,ROW_NUMBER() OVER(PARTITION BY session_id ORDER BY search_time,search_id) rn,
                 ROW_NUMBER() OVER(PARTITION BY session_id ORDER BY search_time DESC,search_id DESC) rr,
                 MAX(total_result_count=0) OVER(PARTITION BY session_id) ever_zero
          FROM search
        )
        SELECT SUM(rn=1 AND total_result_count=0),SUM(rn=1 AND total_result_count>0),
               COUNT(DISTINCT CASE WHEN rn=1 AND total_result_count>0 AND ever_zero=1 THEN session_id END),
               COUNT(DISTINCT CASE WHEN ever_zero=1 THEN session_id END),
               COUNT(DISTINCT CASE WHEN ever_zero=0 THEN session_id END),
               SUM(rr=1 AND ever_zero=1 AND total_result_count>0),
               SUM(rr=1 AND ever_zero=1 AND total_result_count=0),COUNT(*)*1.0/COUNT(DISTINCT session_id)
        FROM o
        """
    ).fetchone()
    first = c.execute(
        """
        WITH o AS (
          SELECT *,LEAD(total_result_count) OVER(PARTITION BY session_id ORDER BY search_time,search_id) nxt
          FROM search
        ), z AS (
          SELECT *,ROW_NUMBER() OVER(PARTITION BY session_id ORDER BY search_time,search_id) zr
          FROM o WHERE total_result_count=0
        )
        SELECT SUM(zr=1 AND nxt=0),SUM(zr=1 AND nxt>0),SUM(zr=1 AND nxt IS NULL) FROM z
        """
    ).fetchone()
    c.close()
    return {
        "Z_to_Z": state[0], "Z_to_P": state[1], "Z_to_END": state[2],
        "P_to_Z": state[3], "P_to_P": state[4], "P_to_END": state[5], "searches": state[6],
        "first_Z": session[0], "first_P": session[1], "first_P_then_Z": session[2],
        "ever_Z": session[3], "never_Z": session[4], "final_recovered": session[5],
        "final_Z": session[6], "average_searches": session[7],
        "first_Z_to_Z": first[0], "first_Z_to_P": first[1], "first_Z_to_END": first[2],
    }


def time_profile(db_path, arm):
    c = ro(db_path)
    seconds = [
        x[0]
        for x in c.execute(
            """
            WITH o AS (
              SELECT s.session_id,s.search_sequence,julianday(s.search_time)*86400 t,
                     LAG(julianday(s.search_time)*86400) OVER(PARTITION BY s.session_id ORDER BY s.search_sequence) p
              FROM Search s JOIN SessionSynthetic ss USING(session_id)
              JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type=?
            ) SELECT ROUND(t-p,6) FROM o WHERE p IS NOT NULL
            """, (arm,)
        )
    ]
    c.close()
    ordered = sorted(seconds)
    def q(p):
        return ordered[min(len(ordered)-1, int((len(ordered)-1)*p))] if ordered else None
    return {
        "n": len(seconds), "negative": sum(x < 0 for x in seconds), "zero": sum(x == 0 for x in seconds),
        "same_timestamp_rate": sum(x == 0 for x in seconds)/len(seconds) if seconds else None,
        "tail_over_109_rate": sum(x > 109 for x in seconds)/len(seconds) if seconds else None,
        "p50": q(.50), "p90": q(.90), "p95": q(.95), "max": max(seconds, default=None),
    }


def path_diversity(db_path, arm):
    c = ro(db_path)
    sessions = collections.defaultdict(list)
    for row in c.execute(
        """
        SELECT s.session_id,s.search_sequence,s.total_result_count,s.query_text,s.destination,s.action_type,
               f.price,f.amenity_count,f.region,ss.outcome_segment
        FROM Search s JOIN SearchFilter f USING(search_id)
        JOIN SessionSynthetic ss USING(session_id) JOIN UserSynthetic u USING(user_id)
        WHERE u.sample_set_type=? ORDER BY s.session_id,s.search_sequence
        """, (arm,)
    ):
        sessions[row["session_id"]].append(row)
    c.close()
    signatures, condition_paths, templates = [], [], []
    for rows in sessions.values():
        cp, states = [], []
        for row in rows:
            query_family = row["query_text"].split("-")[0]
            signature = (query_family,row["destination"],row["action_type"],row["price"],row["amenity_count"],row["region"])
            signatures.append(signature)
            cp.append(signature)
            states.append("Z" if row["total_result_count"] == 0 else "P")
        condition_paths.append(tuple(cp))
        templates.append((len(rows), rows[-1]["outcome_segment"], tuple(states)))
    return {
        "condition_signature": diversity(signatures),
        "condition_path": diversity(condition_paths),
        "template_cluster_derived": diversity(templates),
    }


def control_fingerprint(db_path):
    c = ro(db_path)
    h = hashlib.sha256()
    queries = [
        "SELECT pair_id,sample_stratum,source_session_id FROM UserSynthetic WHERE sample_set_type='control' ORDER BY pair_id",
        "SELECT u.pair_id,s.search_sequence,s.total_result_count,s.query_text,s.destination,s.action_type,f.price,f.amenity_count,f.region FROM Search s JOIN SearchFilter f USING(search_id) JOIN SessionSynthetic ss USING(session_id) JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type='control' ORDER BY u.pair_id,s.search_sequence",
        "SELECT u.pair_id,s.search_sequence,r.result_rank,r.hotel_id,r.room_id FROM SearchResult r JOIN Search s USING(search_id) JOIN SessionSynthetic ss USING(session_id) JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type='control' ORDER BY u.pair_id,s.search_sequence,r.result_rank",
        "SELECT u.pair_id,COALESCE(s.search_sequence,0),e.event_type,e.hotel_id,ROUND((julianday(e.event_at)-julianday(ss.started_at))*86400,6) FROM ActionEvent e JOIN SessionSynthetic ss USING(session_id) JOIN UserSynthetic u USING(user_id) LEFT JOIN Search s USING(search_id) WHERE u.sample_set_type='control' ORDER BY u.pair_id,COALESCE(s.search_sequence,999),e.event_at,e.event_id",
    ]
    for sql in queries:
        for row in c.execute(sql):
            h.update(json.dumps(tuple(row),ensure_ascii=False,separators=(",",":"),default=str).encode("utf-8"))
            h.update(b"\n")
    c.close()
    return h.hexdigest()


def main():
    for path in (OUT_DB, OUT_XLSX, OUT_TRANSITION, OUT_DIVERSITY, OUT_JSON):
        if path.exists():
            raise FileExistsError(path)
    runner = load(RUNNER, "audit_runner")
    sidecars = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(EVAL.glob("*.sidecar.json"))]
    assert len(sidecars) == 30
    expected = [row for row in sidecars if row["scenario"] == "expected"]
    assert len(expected) == 20
    metrics = ["search_zero_rate","zero_followup_rate","immediate_recovery_transition_rate","first_zero_immediate_recovery_rate","final_recovery_rate","card_h_search_rate"]
    seed_rows = []
    for row in sidecars:
        for arm in ("control", "treatment"):
            for metric in metrics + ["card_h_event_rows"]:
                value = row[f"{arm}_metrics"][metric]
                seed_rows.append({"scenario":row["scenario"],"seed":row["seed"],"arm":arm,"metric":metric,**value})
    summaries = []
    for metric in metrics:
        values = [row["control_metrics"][metric]["value"] for row in expected]
        numerators = sum(row["control_metrics"][metric]["numerator"] for row in expected)
        denominators = sum(row["control_metrics"][metric]["denominator"] for row in expected)
        lo, hi = runner.INTERVALS.get(metric, (None, None))
        passes = sum(row["control_metrics"][metric]["interval_pass"] is True for row in expected)
        summaries.append({"metric":metric,"reference_lower":lo,"reference_upper":hi,"mean":statistics.fmean(values),"minimum":min(values),"maximum":max(values),"pooled_numerator":numerators,"pooled_denominator":denominators,"pooled_value":numerators/denominators,"pass_seeds":passes,"required_pass_seeds":18 if metric in runner.INTERVALS else None,"status":"PASS" if metric not in runner.INTERVALS or (passes>=18 and lo<=statistics.fmean(values)<=hi and lo<=numerators/denominators<=hi) else "HOLD"})
    reference = reference_transitions()
    transition_rows = [{"source":"reference","scenario":"observed_synthetic_reference","seed":None,"arm":None,**reference}]
    for row in sidecars:
        for arm in ("control","treatment"):
            copy = {k:v for k,v in row[f"{arm}_transitions"].items() if k != "length_distribution"}
            transition_rows.append({"source":"evaluation","scenario":row["scenario"],"seed":row["seed"],"arm":arm,**copy})
    pooled_transition = {key:sum(row["control_transitions"][key] for row in expected) for key in ("Z_to_Z","Z_to_P","Z_to_END","P_to_Z","P_to_P","P_to_END","searches","first_Z","first_P","ever_Z","never_Z","final_recovered","final_Z","first_Z_to_Z","first_Z_to_P","first_Z_to_END")}
    pooled_transition["average_searches"] = sum(row["control_transitions"]["searches"] for row in expected)/20000

    common_seed = []
    for seed in range(260901,260906):
        matches = [row for row in sidecars if row["seed"] == seed]
        fps = {row["scenario"]:control_fingerprint(row["db_path"]) for row in matches}
        common_seed.append({"seed":seed,**fps,"identical":len(set(fps.values()))==1})

    scenario_rows = []
    for scenario in ("conservative","expected","optimistic"):
        rows = [row for row in sidecars if row["scenario"] == scenario and row["seed"] <= 260905]
        for metric in ("search_zero_rate","immediate_recovery_transition_rate","final_recovery_rate","card_h_search_rate"):
            scenario_rows.append({"scenario":scenario,"arm":"treatment","metric":metric,"mean":statistics.fmean(row["treatment_metrics"][metric]["value"] for row in rows)})

    clone_rows, diversity_rows, time_rows = [], [], []
    for row in sidecars:
        clones = row["integrated_gate"]["clones"]
        clone_rows.append({"scenario":row["scenario"],"seed":row["seed"],"gate":row["integrated_gate"]["status"],"clone_a":clones["clone_a_rows"],"control_clone_b":clones["control_clone_b"],"control_clone_c":clones["control_clone_c"],"treatment_clone_b":clones["treatment_clone_b"],"treatment_clone_c":clones["treatment_clone_c"],"reference_exact_session":clones["reference_exact_session_clone"],"reference_exact_relative_path":clones["reference_exact_relative_path_clone"],"reference_delay_diagnostic":clones["reference_exact_delay_vector_clone"]})
        if row["scenario"] == "expected":
            for arm in ("control","treatment"):
                stored = clones["diversity_path"][arm]
                derived = path_diversity(row["db_path"], arm)
                for definition, values in derived.items():
                    diversity_rows.append({"scenario":row["scenario"],"seed":row["seed"],"arm":arm,"definition":definition,**values})
                diversity_rows.append({"scenario":row["scenario"],"seed":row["seed"],"arm":arm,"definition":"behavior_path_approved_clone_adapter","n":1000,"unique":stored["diversity_unique"],"unique_ratio":stored["diversity_unique"]/1000,"mode_share":stored["diversity_top_share"],"hhi":stored["diversity_hhi"],"shannon":stored["diversity_shannon"],"frequency_1":None,"frequency_2":None,"frequency_3plus":None})
                time_rows.append({"scenario":row["scenario"],"seed":row["seed"],"arm":arm,**time_profile(row["db_path"],arm)})

    candidate_rows = []
    for candidate in (1,2,3):
        prefix = "dev_expected" if candidate == 1 else f"dev{candidate}_expected"
        for seed in (260801,260802,260803):
            path = DEV / f"{prefix}_{seed}.sqlite"
            m = runner.scoped_metrics(path,"control")
            t = runner.transitions(path,"control")
            candidate_rows.append({"candidate":candidate,"seed":seed,"zero_rate":m["search_zero_rate"]["value"],"followup_rate":m["zero_followup_rate"]["value"],"immediate_rate":m["immediate_recovery_transition_rate"]["value"],"first_zero_immediate_rate":m["first_zero_immediate_recovery_rate"]["value"],"final_recovery_rate":m["final_recovery_rate"]["value"],"card_h":m["card_h_search_rate"]["value"],"ever_zero_sessions":t["ever_Z"],"first_zero_sessions":t["first_Z"],"average_searches":t["average_searches"]})

    strata = collections.Counter()
    for row in expected:
        c = ro(row["db_path"])
        strata.update(dict(c.execute("SELECT sample_stratum,COUNT(*) FROM UserSynthetic WHERE sample_set_type='control' GROUP BY sample_stratum")))
        c.close()
    sparse_rows = [{"sample_stratum":key,"expected_mean_per_1000_control":value/20,"projected_n_per_5000_control":value/4,"classification":"sparse" if value/4<30 else "adequate"} for key,value in sorted(strata.items())]

    db = sqlite3.connect(OUT_DB)
    def create_insert(name, rows):
        if not rows: return
        columns = list(rows[0])
        db.execute(f'CREATE TABLE "{name}" (' + ','.join(f'"{c}"' for c in columns) + ')')
        db.executemany(f'INSERT INTO "{name}" VALUES ('+','.join('?' for _ in columns)+')', [[r.get(c) if not isinstance(r.get(c),(dict,list)) else json.dumps(r.get(c),ensure_ascii=False) for c in columns] for r in rows])
    for name, rows in (("seed_metrics",seed_rows),("metric_summary",summaries),("transitions",transition_rows),("common_seed_control",common_seed),("scenario_mechanism",scenario_rows),("clone_audit",clone_rows),("diversity",diversity_rows),("time_profile",time_rows),("development_candidates",candidate_rows),("sparse_projection",sparse_rows)):
        create_insert(name,rows)
    db.commit(); db.close()

    workbook(OUT_XLSX,[("metric_summary",summaries),("seed_metrics",seed_rows),("scenario_mechanism",scenario_rows),("common_seed_control",common_seed),("time_profile",time_rows),("sparse_projection",sparse_rows)])
    workbook(OUT_TRANSITION,[("reference_and_seed",transition_rows),("development_candidates",candidate_rows),("pooled_expected_control",[pooled_transition])])
    workbook(OUT_DIVERSITY,[("clone",clone_rows),("diversity",diversity_rows)])
    result = {
        "classification":"synthetic scenario simulation; not observed A/B",
        "evaluation_runs":len(sidecars),"integrated_gate_pass":sum(r["integrated_gate"]["status"]=="PASS" for r in sidecars),
        "expected_runs":len(expected),"metric_summary":summaries,"reference_transitions":reference,
        "pooled_expected_control_transitions":pooled_transition,"common_seed_control":common_seed,
        "scenario_treatment_means":scenario_rows,
        "clone_totals":{key:sum(row[key] for row in clone_rows) for key in ("clone_a","control_clone_b","control_clone_c","treatment_clone_b","treatment_clone_c","reference_exact_session","reference_exact_relative_path")},
        "production_seed_used":False,"production_run_count":0,
        "calibration_validation":"PASS" if all(row["status"]=="PASS" for row in summaries if row["metric"] in runner.INTERVALS) else "HOLD",
        "hold_reason":"search_zero_rate individual-seed pass count below predeclared 18/20" if next(x for x in summaries if x["metric"]=="search_zero_rate")["status"]=="HOLD" else None,
        "files":{}
    }
    OUT_JSON.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"summary":summaries,"calibration_validation":result["calibration_validation"],"common_seed_identical":all(x["identical"] for x in common_seed),"scenario":scenario_rows,"clone_totals":result["clone_totals"]},ensure_ascii=False))


if __name__ == "__main__":
    main()
