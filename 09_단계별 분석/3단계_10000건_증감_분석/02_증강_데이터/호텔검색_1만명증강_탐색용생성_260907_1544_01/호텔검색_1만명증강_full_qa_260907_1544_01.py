#!/usr/bin/env python3
import csv
import hashlib
import importlib.util
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent
STAGE = ROOT.parent
BUNDLE = STAGE / "호텔검색_1만명증강_결합전이개정및검증_260907_1418_01"
DB = ROOT / "output" / "호텔검색_1만명증강_탐색용AB10000_260907_1544_01.sqlite"
REF = ROOT.parents[1] / "2단계_1000건_증감_분석" / "01_초기생성_QA_전체분석" / "02_관측형합성1000명_실행묶음_260903_1606_01" / "호텔검색_관측형합성1000명_데이터_260903_1606_01_메타삭제_무인덱스_NULL5유지_텍스트최적화_16K.sqlite"
RUNNER = BUNDLE / "호텔검색_1만명증강_evaluation_runner_v06_260907_1418_03.py"
RAW_GATE = ROOT / "호텔검색_1만명증강_raw_gate_result_260907_1544_01.json"
OUT_JSON = ROOT / "호텔검색_1만명증강_전수QA결과_260907_1544_01.json"
OUT_XLSX = ROOT / "호텔검색_1만명증강_기준선비교표_260907_1544_01.xlsx"
OUT_CSV = ROOT / "호텔검색_1만명증강_행수및무결성_260907_1544_01.csv"


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
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def workbook(path, sheets):
    wb = Workbook(); wb.remove(wb.active)
    for title, rows in sheets:
        ws = wb.create_sheet(title[:31]); columns = list(rows[0]) if rows else ["NO_ROWS"]; ws.append(columns)
        for row in rows: ws.append([row.get(c) for c in columns])
        ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def time_profile(connection, arm):
    values = [r[0] for r in connection.execute("""WITH o AS(
      SELECT s.session_id,s.search_sequence,julianday(s.search_time)*86400 t,
      LAG(julianday(s.search_time)*86400)OVER(PARTITION BY s.session_id ORDER BY s.search_sequence)p
      FROM Search s JOIN SessionSynthetic ss USING(session_id) JOIN UserSynthetic u USING(user_id)
      WHERE u.sample_set_type=?) SELECT t-p FROM o WHERE p IS NOT NULL""", (arm,))]
    values.sort()
    q = lambda p: values[round((len(values)-1)*p)] if values else None
    return {"n":len(values),"negative":sum(v<0 for v in values),"zero":sum(abs(v)<1e-6 for v in values),
            "same_timestamp_rate":sum(abs(v)<1e-6 for v in values)/len(values),"tail_over_109_rate":sum(v>109 for v in values)/len(values),
            "p50":q(.5),"p90":q(.9),"p95":q(.95),"max":max(values)}


def length_diversity(connection):
    groups = defaultdict(list)
    for row in connection.execute("""SELECT u.sample_set_type,s.session_id,ss.outcome_segment,s.search_sequence,
      CASE WHEN s.total_result_count=0 THEN 'Z' ELSE 'P' END state,s.action_type,
      COUNT(*)OVER(PARTITION BY s.session_id)n
      FROM Search s JOIN SessionSynthetic ss USING(session_id) JOIN UserSynthetic u USING(user_id)
      ORDER BY u.sample_set_type,s.session_id,s.search_sequence"""):
        groups[(row["sample_set_type"],row["n"],row["session_id"],row["outcome_segment"])].append((row["state"],row["action_type"]))
    buckets = defaultdict(list)
    for (arm,n,sid,outcome), path in groups.items(): buckets[(arm,n)].append((tuple(path),outcome))
    result=[]
    for (arm,n), paths in sorted(buckets.items()):
        count=Counter(paths);total=len(paths);probs=[v/total for v in count.values()]
        result.append({"arm":arm,"session_length":n,"sessions":total,"unique_paths":len(count),"mode_share":max(probs),
                       "hhi":sum(p*p for p in probs),"shannon":-sum(p*math.log(p) for p in probs if p),
                       "duplicate_related_sessions":sum(v for v in count.values() if v>1)})
    return result


def main():
    for p in (OUT_JSON,OUT_XLSX,OUT_CSV):
        if p.exists(): raise FileExistsError(p)
    runner=load(RUNNER,"runner"); c=ro(DB); one=lambda sql:c.execute(sql).fetchone()[0]
    tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    row_counts=[{"table":t,"rows":one('SELECT COUNT(*) FROM "'+t+'"')} for t in tables]
    checks=[]
    def check(name,value,expected=0): checks.append({"check":name,"value":value,"expected":expected,"status":"PASS" if value==expected else "FAIL"})
    check("integrity_check",c.execute("pragma integrity_check").fetchone()[0],"ok")
    check("foreign_key_violations",len(c.execute("pragma foreign_key_check").fetchall()))
    check("users",one("SELECT COUNT(*) FROM UserSynthetic"),10000);check("sessions",one("SELECT COUNT(*) FROM SessionSynthetic"),10000)
    check("control_users",one("SELECT COUNT(*) FROM UserSynthetic WHERE sample_set_type='control'"),5000);check("treatment_users",one("SELECT COUNT(*) FROM UserSynthetic WHERE sample_set_type='treatment'"),5000)
    check("complete_pairs",one("SELECT COUNT(*) FROM(SELECT pair_id FROM UserSynthetic GROUP BY pair_id HAVING COUNT(*)=2 AND COUNT(DISTINCT sample_set_type)=2)"),5000)
    check("required_user_null",one("SELECT COUNT(*) FROM UserSynthetic WHERE pair_id IS NULL OR sample_set_type IS NULL OR sample_stratum IS NULL OR simulation_run_id IS NULL OR random_seed IS NULL OR source_session_id IS NULL OR treatment_scenario IS NULL OR generation_model_version IS NULL"))
    check("required_session_null",one("SELECT COUNT(*) FROM SessionSynthetic WHERE user_id IS NULL OR pair_id IS NULL OR started_at IS NULL OR ended_at IS NULL OR outcome_segment IS NULL OR treatment_exposed IS NULL"))
    check("search_filter_not_1to1",one("SELECT ABS((SELECT COUNT(*) FROM Search)-(SELECT COUNT(*) FROM SearchFilter))")+one("SELECT COUNT(*) FROM Search s LEFT JOIN SearchFilter f USING(search_id) WHERE f.search_id IS NULL"))
    check("result_count_mismatch",one("SELECT COUNT(*) FROM Search s LEFT JOIN(SELECT search_id,COUNT(*) n FROM SearchResult GROUP BY search_id)r USING(search_id) WHERE s.total_result_count<>COALESCE(r.n,0)"))
    check("duplicate_result_rank",one("SELECT COUNT(*) FROM(SELECT search_id,result_rank,COUNT(*)n FROM SearchResult GROUP BY 1,2 HAVING n>1)"))
    check("impression_result_mismatch",one("SELECT ABS((SELECT COUNT(*) FROM SearchResult)-(SELECT COUNT(*) FROM ActionEvent WHERE event_type='hotel_impression'))"))
    check("selected_hotel_not_exposed",one("SELECT COUNT(*) FROM ActionEvent e WHERE e.event_type IN('hotel_click','hotel_detail_view') AND NOT EXISTS(SELECT 1 FROM SearchResult r WHERE r.search_id=e.search_id AND r.hotel_id=e.hotel_id)"))
    check("event_search_orphan",one("SELECT COUNT(*) FROM ActionEvent e LEFT JOIN Search s USING(search_id) WHERE e.search_id IS NOT NULL AND s.search_id IS NULL"))
    check("event_before_search",one("SELECT COUNT(*) FROM ActionEvent e JOIN Search s USING(search_id) WHERE e.event_at<s.search_time"))
    check("event_after_session_end",one("SELECT COUNT(*) FROM ActionEvent e JOIN SessionSynthetic ss USING(session_id) WHERE e.event_at>ss.ended_at"))
    check("search_time_inversion",one("SELECT COUNT(*) FROM(WITH x AS(SELECT session_id,search_time,LAG(search_time)OVER(PARTITION BY session_id ORDER BY search_sequence)p FROM Search)SELECT 1 FROM x WHERE search_time<p)"))
    check("pair_pre_attribute_mismatch",one("SELECT COUNT(*) FROM(SELECT pair_id FROM UserSynthetic GROUP BY pair_id HAVING COUNT(DISTINCT sample_stratum)>1 OR COUNT(DISTINCT source_session_id)>1)"))
    check("control_treatment_leakage",one("SELECT COUNT(*) FROM SessionSynthetic ss JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type='control' AND ss.treatment_exposed<>0"))
    check("treatment_exposure_without_zero",one("SELECT COUNT(*) FROM SessionSynthetic ss JOIN UserSynthetic u USING(user_id) WHERE u.sample_set_type='treatment' AND ss.treatment_exposed=1 AND NOT EXISTS(SELECT 1 FROM Search s WHERE s.session_id=ss.session_id AND s.total_result_count=0)"))
    check("booking_rows",one("SELECT COUNT(*) FROM Booking"));check("null5_age_group_nonnull",one("SELECT COUNT(*) FROM UserSynthetic WHERE age_group IS NOT NULL"))
    check("null5_property_type_nonnull",one("SELECT COUNT(*) FROM SearchFilter WHERE property_type IS NOT NULL"));check("null5_property_grade_nonnull",one("SELECT COUNT(*) FROM SearchFilter WHERE property_grade IS NOT NULL"))
    check("null5_review_completed_nonnull",one("SELECT COUNT(*) FROM ActionEvent WHERE review_completed_at IS NOT NULL"));check("null5_review_text_nonnull",one("SELECT COUNT(*) FROM ActionEvent WHERE review_text IS NOT NULL"))
    check("random_seed_other",one("SELECT COUNT(*) FROM UserSynthetic WHERE random_seed<>2434815518"));check("run_seed_other",one("SELECT COUNT(*) FROM SimulationRun WHERE random_seed<>2434815518"))
    metrics=[]
    ref_values={"search_zero_rate":(3434,6900),"zero_followup_rate":(3271,3434),"immediate_recovery_transition_rate":(558,3271),"first_zero_immediate_recovery_rate":(69,628),"final_recovery_rate":(488,651),"card_h_search_rate":(680,3466),"card_h_event_rows":(2580,None)}
    for metric,(n,d) in ref_values.items():metrics.append({"source":"reference","arm":None,"metric":metric,"numerator":n,"denominator":d,"value":None if d is None else n/d})
    arm_data={}
    for arm in ("control","treatment"):
        arm_data[arm]={"metrics":runner.scoped_metrics(DB,arm),"transitions":runner.transitions(DB,arm),"time":time_profile(c,arm)}
        for metric,row in arm_data[arm]["metrics"].items():metrics.append({"source":"exploratory_10000","arm":arm,"metric":metric,"numerator":row["numerator"],"denominator":row["denominator"],"value":row["value"]})
    raw=json.loads(RAW_GATE.read_text(encoding="utf8"));diversity=length_diversity(c)
    action_rows=[dict(r) for r in c.execute("SELECT u.sample_set_type arm,s.action_type,COUNT(*) searches,SUM(s.total_result_count=0) zero_searches FROM Search s JOIN SessionSynthetic ss USING(session_id) JOIN UserSynthetic u USING(user_id) GROUP BY 1,2 ORDER BY 1,2")]
    metadata=dict(c.execute("SELECT key,value FROM _generation_metadata"));c.close()
    control_zero=arm_data["control"]["metrics"]["search_zero_rate"]["value"]
    raw_pass=raw["status"]=="PASS"; structural_pass=all(x["status"]=="PASS" for x in checks)
    range_pass=.487615<=control_zero<=.515865
    limited="LIMITED_USE_READY" if raw_pass and structural_pass and range_pass else "HOLD"
    result={"classification":"synthetic exploratory A/B scenario; not observed causal effect","limited_use_status":limited,
            "strict_calibration_status":"HOLD","exception_code":"ZERO_RATE_SEED_COVERAGE_16_OF_20","raw_gate_result":raw,
            "control_zero_observed_evaluation_range":[.487615,.515865],"control_zero_within_observed_range":range_pass,
            "database":{"path":str(DB.resolve()),"sha256":sha(DB),"bytes":DB.stat().st_size,"MB":DB.stat().st_size/1e6,"MiB":DB.stat().st_size/1048576},
            "row_counts":row_counts,"checks":checks,"metrics":metrics,"arm_profiles":arm_data,"action_distribution":action_rows,
            "length_diversity":diversity,"generation_metadata":metadata,"unresolved":["strict calibration remains HOLD","single-seed zero-rate stability limitation","control average searches 6.7144 versus reference 6.9"]}
    OUT_JSON.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    workbook(OUT_XLSX,[("baseline_metrics",metrics),("checks",checks),("row_counts",row_counts),("actions",action_rows),("length_diversity",diversity)])
    with OUT_CSV.open("w",newline="",encoding="utf-8-sig") as h:
        rows=row_counts+[{"table":"QA_FAIL_COUNT","rows":sum(x["status"]=="FAIL" for x in checks)}];w=csv.DictWriter(h,fieldnames=["table","rows"]);w.writeheader();w.writerows(rows)
    print(json.dumps({"limited_use_status":limited,"db":result["database"],"qa_failures":[x for x in checks if x["status"]=="FAIL"],"control":arm_data["control"],"treatment":arm_data["treatment"]},ensure_ascii=False))


if __name__=="__main__": main()
