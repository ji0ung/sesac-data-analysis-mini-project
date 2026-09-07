#!/usr/bin/env python3
"""Finalize immutable-input verification, limitation record, QA report and analysis handoff."""
import hashlib
import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
EXEC = ROOT / "호텔검색_1만명증강_실행파일manifest_260907_1544_01.json"
QA = ROOT / "호텔검색_1만명증강_전수QA결과_260907_1544_01.json"
RAW = ROOT / "호텔검색_1만명증강_raw_gate_result_260907_1544_01.json"
REDRAW = ROOT / "호텔검색_1만명증강_clone재추첨감사_260907_1544_01.json"
DB = ROOT / "output" / "호텔검색_1만명증강_탐색용AB10000_260907_1544_01.sqlite"
IMM = ROOT / "호텔검색_1만명증강_입력불변성검증_260907_1544_01.json"
RECORD = ROOT / "호텔검색_1만명증강_제한사용기록_260907_1544_01.md"
LIMITS = ROOT / "호텔검색_1만명증강_한계점설명_260907_1544_01.md"
REPORT = ROOT / "호텔검색_1만명증강_전수QA보고서_260907_1544_01.md"
HANDOFF = ROOT / "호텔검색_1만명증강_분석용handoff_manifest_260907_1544_01.json"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def pct(value):
    return f"{value * 100:.4f}%"


def quantile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def reference_time(path):
    connection = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
    rows = connection.execute("""
        WITH ordered AS (
          SELECT session_id, search_time,
                 LAG(search_time) OVER(PARTITION BY session_id ORDER BY search_time, search_id) previous_time
          FROM Search
        )
        SELECT (julianday(search_time)-julianday(previous_time))*86400.0
        FROM ordered WHERE previous_time IS NOT NULL
    """).fetchall()
    connection.close()
    values = [max(0.0, float(row[0])) for row in rows]
    return {
        "n": len(values), "negative": sum(value < 0 for value in values),
        "zero": sum(value < 0.5 for value in values),
        "same_timestamp_rate": sum(value < 0.5 for value in values) / len(values),
        "tail_over_109_rate": sum(value > 109 for value in values) / len(values),
        "p50": quantile(values, .5), "p90": quantile(values, .9),
        "p95": quantile(values, .95), "max": max(values),
    }


def write_new(path, text):
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main():
    execution = json.loads(EXEC.read_text(encoding="utf-8"))
    qa = json.loads(QA.read_text(encoding="utf-8"))
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    redraw = json.loads(REDRAW.read_text(encoding="utf-8"))
    files = execution["files"]
    current = []
    for role, item in files.items():
        actual = sha256(item["path"])
        current.append({"role": role, "path": item["path"], "approved_sha256": item["sha256"], "actual_sha256": actual, "match": actual == item["sha256"]})
    strict = json.loads(Path(files["handoff"]["path"]).read_text(encoding="utf-8"))
    strict_frozen = []
    for item in strict["frozen_inputs"]:
        actual = sha256(item["path"])
        strict_frozen.append({"role": item["role"], "path": item["path"], "approved_sha256": item["approved_sha256"], "actual_sha256": actual, "match": actual == item["approved_sha256"]})
    evaluation_dbs = []
    for run in strict["runs"]:
        actual = sha256(run["db_path"])
        evaluation_dbs.append({"scenario": run["scenario"], "seed": run["seed"], "path": run["db_path"], "approved_sha256": run["db_sha256_recorded"], "actual_sha256": actual, "match": actual == run["db_sha256_recorded"]})
    unchanged = all(item["match"] for item in current + strict_frozen + evaluation_dbs)
    reference_time_profile = reference_time(files["ref"]["path"])
    immutability = {
        "checked_at_kst": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "execution_manifest_files": current,
        "prior_handoff_frozen_inputs": strict_frozen,
        "prior_evaluation_databases": evaluation_dbs,
        "counts": {"execution_dependencies": len(current), "prior_frozen_inputs": len(strict_frozen), "prior_evaluation_databases": len(evaluation_dbs)},
        "all_unchanged": unchanged,
        "production_database_sha256": sha256(DB),
    }
    write_new(IMM, json.dumps(immutability, ensure_ascii=False, indent=2) + "\n")
    if not unchanged:
        raise RuntimeError("approved input changed")

    metric_rows = qa["metrics"]
    metric = {(row["source"], row.get("arm"), row["metric"]): row for row in metric_rows}
    ref = lambda name: metric[("reference", None, name)]
    ctl = lambda name: metric[("exploratory_10000", "control", name)]
    trt = lambda name: metric[("exploratory_10000", "treatment", name)]
    ctl_profile = qa["arm_profiles"]["control"]
    trt_profile = qa["arm_profiles"]["treatment"]
    db_size = DB.stat().st_size
    db_info = {"path": str(DB), "sha256": sha256(DB), "bytes": db_size, "MB": db_size / 1_000_000, "MiB": db_size / 1_048_576}

    record = f"""# 10,000명 탐색용 A/B 제한 사용 기록

- 제한 사용 상태: `ACCEPTED_FOR_EXPLORATORY_SIMULATION_WITH_LIMITATIONS`
- 실행 결과 상태: `LIMITED_USE_READY`
- 엄격 교정 상태: `HOLD` (변경하지 않음)
- 예외 코드: `ZERO_RATE_SEED_COVERAGE_16_OF_20`
- 사전 기준: 20개 expected seed 중 18개 통과 필요
- 실제 결과: 16/20 통과
- 기준 DB 검색 0건률: 3,434/6,900 = {pct(3434/6900)}
- 독립 평가 pooled control 0건률: 69,173/137,731 = {pct(69173/137731)} (차이 +0.4551%p)
- 이번 고정 seed control 0건률: 16,761/33,572 = {pct(ctl('search_zero_rate')['value'])}
- 기존 평가에서 관측된 범위: 48.7615%~51.5865% (예측구간이나 정식 허용구간이 아님)
- 고정 seed: `2434815518`; 10,000명 전체 생성 1회; 재생성 0회

허용 용도는 교육·발표용 대시보드, 탐색적 세그먼트 분석, 가정 기반 A/B 시나리오 비교다. 실제 서비스 인과효과, 실제 관측 사용자 10,000명, 표본 편향 해소, 정보량 증가 또는 원본 신뢰구간 축소의 근거로 사용하면 안 된다.
"""
    write_new(RECORD, record)

    limits = f"""# 10,000명 탐색용 A/B 데이터 한계점과 후속 영향

## 판정 경계

이 DB는 구조·무결성 gate를 통과한 **합성 시나리오 데이터**이며 실제 A/B 실험 결과가 아니다. 엄격 calibration은 검색 0건률 seed coverage가 16/20으로 사전 기준 18/20에 미달해 계속 `HOLD`다. 이번 `LIMITED_USE_READY`는 이 단일 재현성 한계를 명시적으로 수용한 탐색용 승인일 뿐 production 승인이나 calibration PASS가 아니다.

## 남은 한계와 10,000명 데이터에 미치는 영향

1. **seed 민감도**: 이번 DB는 seed 2434815518의 단일 draw다. control 0건률 {pct(ctl('search_zero_rate')['value'])}는 과거 평가 관측 범위 안이지만, 독립 seed 중 4개가 엄격 구간을 벗어났다. 따라서 단일 DB에서 얻은 세부 순위나 작은 차이는 다른 seed에서 바뀔 수 있다.
2. **검색량 차이**: control은 세션당 6.7144회로 기준 6.9000회보다 0.1856회(-2.69%) 적다. 검색 grain 지표의 총 노출량과 희소 셀 표본 수가 기준보다 줄 수 있으며, user/session grain과 search grain의 해석을 섞으면 안 된다.
3. **합성 n의 허위 정밀도**: 10,000행의 사용자와 65,355건의 검색은 모형 반복 표본이다. 원본 1,000명의 정보량이 10배로 늘어난 것이 아니므로 일반적인 행 독립 가정의 p-value나 좁아진 신뢰구간을 근거로 확증하면 과도한 정밀도다. 불확실성은 원본 후험·다중 seed·시나리오 간 변동으로 제시해야 한다.
4. **처치 효과의 가정 의존성**: treatment의 0건률 {pct(trt('search_zero_rate')['value'])}, 즉시 회복률 {pct(trt('immediate_recovery_transition_rate')['value'])}, 최종 회복률 {pct(trt('final_recovery_rate')['value'])}는 동결된 expected 효과 가정의 결과다. 실제 인과 uplift가 아니며, 처치 노출은 직전 0건 상태에 의존해 단순 전체군 평균이 노출자 효과와 다르다.
5. **경로·길이 구조**: 최대 검색 수는 31로 절단된다. 길이 1 경로는 가능한 상태가 두 가지뿐이어서 자연 중복률이 매우 높다. 이를 기계적 clone으로 오판하면 안 되며, 길이별 HHI·entropy와 CLONE-A/B/C를 함께 봐야 한다.
6. **이벤트 로깅 구조**: 생성기는 `hotel_click`과 `hotel_detail_view`를 반복 횟수별로 쌍으로 만든다. Card H 주 KPI는 고유 search 기준 detail_view만 사용하고, 두 이벤트를 독립적인 연속 전환 단계로 더하지 않는다. 이벤트 행 수는 반복 탐색 강도 보조값이다.
7. **희소 세그먼트**: 원본의 희소 셀과 작은 행동 유형 n은 합성 n으로 신뢰성이 회복되지 않는다. 세그먼트 결과에는 원본 n, 합성 n, seed/scenario 범위와 희소성 플래그를 병기해야 한다.
8. **일반화 한계**: 기준 DB의 표본 선택·측정·로깅 편향이 생성 모형에 상속된다. HOTEL/ROOM과 노출 후보도 모형의 닫힌 세계 안에서 재사용되므로 외부 호텔 시장이나 실제 사용자 모집단으로 일반화할 수 없다.
9. **BOOKING 부재**: BOOKING은 0행이며 예약·매출 KPI를 추론하거나 보완 생성해서는 안 된다.

## 후속 분석 및 최종 계획서 필수 표기

- 제목·그림·표마다 가능한 곳에 `합성 탐색 시뮬레이션 / 실제 A/B 아님`을 표시한다.
- control/treatment 차이는 **시나리오 대비값**으로 부르고, 인과효과·검증된 uplift라는 표현을 금지한다.
- 모든 KPI에 grain, 분자, 분모, 기준 DB 값, 단일 seed, strict HOLD를 병기한다.
- search grain 결과에는 세션당 검색 수 차이를, treatment 결과에는 노출 조건을 주석으로 둔다.
- 통계 불확실성은 합성 행 bootstrap만으로 축소하지 말고 원본 후험 및 독립 seed 분포를 사용한다.
- 희소 셀은 병합 또는 `HOLD/탐색적` 표시를 하고 합성 표본 수만으로 유의성을 주장하지 않는다.
- Card H-SEARCH와 Card H-EVENT를 분리하고, 클릭과 상세 이벤트를 두 개의 독립 퍼널 전환으로 합산하지 않는다.
- 최종 1만 명 증강 계획서와 보고서의 `한계·해석 제한·재현성` 절에 이 문서의 9개 항목을 그대로 승계한다.
"""
    write_new(LIMITS, limits)

    report = f"""# 10,000명 탐색용 A/B 전수 QA 보고서

## 최종 판정

- raw integrated gate: `{raw['status']}`
- strict calibration: `HOLD`
- limited-use: `LIMITED_USE_READY`
- 전수 QA 실패: 0건

## 구조 및 무결성

- USER 10,000; SESSION 10,000; control 5,000; treatment 5,000; 완전 pair 5,000
- SQLite integrity_check=ok; FK 0; 시간 역전 0; 세션 종료 후 이벤트 0
- SEARCH–FILTER 1:1 위반 0; 결과 수 불일치 0; 중복 rank 0; 미노출 호텔 선택 0
- 사전 pair 속성 불일치 0; treatment leakage 0; NULL5 위반 0; BOOKING 0
- ActionEvent 2,152,148; Search 65,355; SearchResult 2,023,419; SearchTransition 55,355

## 기준선 비교

| 지표 | 기준 DB | control | 차이(%p) | treatment |
|---|---:|---:|---:|---:|
| 검색 0건률 | 3,434/6,900 = {pct(ref('search_zero_rate')['value'])} | 16,761/33,572 = {pct(ctl('search_zero_rate')['value'])} | {(ctl('search_zero_rate')['value']-ref('search_zero_rate')['value'])*100:+.4f} | 13,853/31,783 = {pct(trt('search_zero_rate')['value'])} |
| 0건 후속검색률 | 3,271/3,434 = {pct(ref('zero_followup_rate')['value'])} | 15,935/16,761 = {pct(ctl('zero_followup_rate')['value'])} | {(ctl('zero_followup_rate')['value']-ref('zero_followup_rate')['value'])*100:+.4f} | 13,249/13,853 = {pct(trt('zero_followup_rate')['value'])} |
| 즉시 회복 전이율 | 558/3,271 = {pct(ref('immediate_recovery_transition_rate')['value'])} | 2,693/15,935 = {pct(ctl('immediate_recovery_transition_rate')['value'])} | {(ctl('immediate_recovery_transition_rate')['value']-ref('immediate_recovery_transition_rate')['value'])*100:+.4f} | 2,918/13,249 = {pct(trt('immediate_recovery_transition_rate')['value'])} |
| 첫 Z 즉시 회복률 | 69/628 = {pct(ref('first_zero_immediate_recovery_rate')['value'])} | 351/3,073 = {pct(ctl('first_zero_immediate_recovery_rate')['value'])} | {(ctl('first_zero_immediate_recovery_rate')['value']-ref('first_zero_immediate_recovery_rate')['value'])*100:+.4f} | 487/3,067 = {pct(trt('first_zero_immediate_recovery_rate')['value'])} |
| 최종 회복률 | 488/651 = {pct(ref('final_recovery_rate')['value'])} | 2,376/3,202 = {pct(ctl('final_recovery_rate')['value'])} | {(ctl('final_recovery_rate')['value']-ref('final_recovery_rate')['value'])*100:+.4f} | 2,560/3,164 = {pct(trt('final_recovery_rate')['value'])} |
| Z 경험 세션률 | 651/1,000 = 65.1000% | 3,202/5,000 = 64.0400% | -1.0600 | 3,164/5,000 = 63.2800% |
| Card H-SEARCH | 680/3,466 = {pct(ref('card_h_search_rate')['value'])} | 3,330/16,811 = {pct(ctl('card_h_search_rate')['value'])} | {(ctl('card_h_search_rate')['value']-ref('card_h_search_rate')['value'])*100:+.4f} | 3,504/17,930 = {pct(trt('card_h_search_rate')['value'])} |
| Card H-EVENT | 2,580행; 3.7941/상세검색 | 13,016행; {13016/3330:.4f}/상세검색 | 보조량 | 13,671행; {13671/3504:.4f}/상세검색 |

세션당 검색 수는 기준 6.9000, control 6.7144, treatment 6.3566이다. 기준 inter-arrival은 n={reference_time_profile['n']:,}, p50={reference_time_profile['p50']:.1f}s, p90={reference_time_profile['p90']:.1f}s, p95={reference_time_profile['p95']:.1f}s, >109s={pct(reference_time_profile['tail_over_109_rate'])}; control은 p50={ctl_profile['time']['p50']:.1f}s, p90={ctl_profile['time']['p90']:.1f}s, p95={ctl_profile['time']['p95']:.1f}s, >109s={pct(ctl_profile['time']['tail_over_109_rate'])}; treatment는 p50={trt_profile['time']['p50']:.1f}s, p90={trt_profile['time']['p90']:.1f}s, p95={trt_profile['time']['p95']:.1f}s, >109s={pct(trt_profile['time']['tail_over_109_rate'])}다.

## Clone 및 다양성

- CLONE-A/B/C: 전부 0건
- 기준 DB exact session clone 0건; exact relative path clone 0건
- delay-vector 단독 일치 7건은 business path 동일성이 없어 진단값이며 clone으로 판정하지 않음
- 내부 충돌 재추첨: control 0회, treatment 4회; 실패 0회; 결정론적 replay와 DB 검색/0건 수 완전 일치
- DIVERSITY-PATH control: unique 2,997, top share 20.74%, HHI 0.04538656, Shannon 6.41296
- DIVERSITY-PATH treatment: unique 2,330, top share 22.06%, HHI 0.05109872, Shannon 6.02349
- 길이 1의 높은 자연 중복은 제한된 상태 공간 때문이며 실제 clone 검사와 분리함

## 불변성

실행 manifest 13개 의존성, 이전 handoff의 동결 입력 {len(strict_frozen)}개, 독립 평가 DB 30개가 모두 승인 SHA-256과 일치했다. 생성 DB는 clone replay 전후 SHA-256이 동일하다.
"""
    write_new(REPORT, report)

    artifact_paths = [EXEC, QA, RAW, REDRAW, IMM, RECORD, LIMITS, REPORT,
                      ROOT / "호텔검색_1만명증강_기준선비교표_260907_1544_01.xlsx",
                      ROOT / "호텔검색_1만명증강_행수및무결성_260907_1544_01.csv",
                      ROOT / "호텔검색_1만명증강_제한사용authorization_260907_1544_01.json",
                      ROOT / "호텔검색_1만명증강_exploratory_wrapper_260907_1544_01.py",
                      DB]
    artifacts = [{"name": path.name, "path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in artifact_paths]
    handoff = {
        "step": "PROMPT 3-L", "classification": "synthetic exploratory A/B scenario; not observed causal effect",
        "strict_calibration_status": "HOLD", "strict_calibration_passed": False,
        "strict_exception_code": "ZERO_RATE_SEED_COVERAGE_16_OF_20",
        "limited_use_authorization": "ACCEPTED_FOR_EXPLORATORY_SIMULATION_WITH_LIMITATIONS",
        "limited_use_status": "LIMITED_USE_READY", "raw_gate_result": raw["status"],
        "production_approval": False, "general_production_execution_authorized": False,
        "analysis_authorized": True, "analysis_scope": ["education/presentation dashboard", "exploratory segment analysis", "assumption-based A/B scenario contrast"],
        "prohibited_claims": ["observed A/B causal effect", "10,000 observed users", "bias removal", "information gain or narrowed source confidence interval", "strict calibration PASS"],
        "generation": {"seed": 2434815518, "full_runs": 1, "regenerations": 0, "users": 10000, "sessions": 10000, "control": 5000, "treatment": 5000, "pairs": 5000, "scenario": "expected"},
        "database": db_info, "row_counts": qa["row_counts"], "metrics": qa["metrics"],
        "reference_time_distribution": reference_time_profile,
        "raw_integrated_gate": raw, "clone_redraw_audit": redraw,
        "qa_failures": qa.get("qa_failures", []), "full_qa_checks": qa["checks"],
        "input_immutability": {"path": str(IMM), "sha256": sha256(IMM), "all_unchanged": True, "prior_evaluation_db_count": 30},
        "execution_dependencies": current, "artifacts": artifacts,
        "unresolved_limitations": [
            "strict zero-rate seed coverage remains 16/20 versus required 18/20",
            "single production-seed draw is seed-sensitive",
            "control searches/session 6.7144 versus reference 6.9000",
            "synthetic n does not increase source information or justify narrower confidence intervals",
            "treatment effects are configured assumptions and exposure is post-zero conditional",
            "source sampling/logging bias and sparse-cell uncertainty are inherited",
            "BOOKING is absent and must not be inferred",
        ],
        "limitation_document": {"path": str(LIMITS), "sha256": sha256(LIMITS)},
        "next_step": "PROMPT 4-L analysis allowed within limited-use scope",
        "self_hash_policy": "handoff manifest SHA-256 is calculated externally and is not embedded in itself",
    }
    write_new(HANDOFF, json.dumps(handoff, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "LIMITED_USE_READY", "database": db_info, "handoff": {"path": str(HANDOFF), "sha256": sha256(HANDOFF)}, "inputs_unchanged": unchanged}, ensure_ascii=False))


if __name__ == "__main__":
    main()
