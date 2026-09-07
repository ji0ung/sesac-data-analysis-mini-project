import importlib.util
import json
import os
import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT.parent
V06 = ROOT / "호텔검색_1만명증강_generator_sequential_v06_260907_1418_03.py"
AUTH_WRAPPER = STAGE / "호텔검색_1만명증강_승인인터페이스수정및교정_260907_1351_01" / "호텔검색_1만명증강_generator_authorized_v03_260907_1351_01.py"
CONTRACT = STAGE / "호텔검색_1만명증강_검증체인통합_260907_1326_01" / "호텔검색_1만명증강_지표정의_260907_1326_01.yaml"
CALCULATOR = STAGE / "호텔검색_1만명증강_검증체인통합_260907_1326_01" / "호텔검색_1만명증강_공통지표계산기_260907_1326_01.py"
REFERENCE = ROOT.parents[1] / "2단계_1000건_증감_분석" / "01_초기생성_QA_전체분석" / "02_관측형합성1000명_실행묶음_260903_1606_01" / "호텔검색_관측형합성1000명_데이터_260903_1606_01_메타삭제_무인덱스_NULL5유지_텍스트최적화_16K.sqlite"
SMOKE = ROOT / "tests" / "sequential_smoke_200_candidate3.sqlite"
CONFIG = ROOT / "호텔검색_1만명증강_config_expected_v06_260907_1418_03.yaml"
AUTH = ROOT / "호텔검색_1만명증강_evaluation_authorization_expected_260907_1418_03.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRng:
    def __init__(self, values):
        self.values = iter(values)

    def random(self):
        return next(self.values)


class Prompt211Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import yaml
        cls.generator = load(V06, "v06_test")
        cls.auth = load(AUTH_WRAPPER, "auth_test")
        cls.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    def plan(self, values, first_zero):
        return self.generator.sequential_plan(
            FakeRng(values), self.config, {}, {"first_zero": first_zero}, "control", "expected"
        )

    def test_p_to_z_is_reachable(self):
        states, _ = self.plan([0.9, 0.30, 0.01], False)
        self.assertEqual(states[:2], ["FIRST_SEARCH_POSITIVE", "FOLLOWUP_ZERO"])

    def test_z_to_z_is_reachable(self):
        states, _ = self.plan([0.9, 0.10, 0.01], True)
        self.assertEqual(states[:2], ["FIRST_SEARCH_ZERO", "FOLLOWUP_ZERO"])

    def test_z_to_p_is_reachable(self):
        states, outcome = self.plan([0.9, 0.95, 0.01], True)
        self.assertEqual(states[:2], ["FIRST_SEARCH_ZERO", "IMMEDIATE_RECOVERY"])
        self.assertEqual(outcome, "SG3")

    def test_end_from_z_does_not_flip_last_state(self):
        states, outcome = self.plan([0.9, 0.01], True)
        self.assertEqual(states, ["FIRST_SEARCH_ZERO"])
        self.assertEqual(outcome, "SG4")

    def test_same_seed_plan_is_logically_reproducible(self):
        import random
        one = self.generator.sequential_plan(random.Random(77), self.config, {}, arm="control")
        two = self.generator.sequential_plan(random.Random(77), self.config, {}, arm="control")
        self.assertEqual(one, two)

    def test_production_seed_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.auth.validate_authorization(AUTH, "calibration", 2000, 2434815518, "expected", ROOT / "evaluation" / "never.sqlite", CONFIG)

    def test_unapproved_seed_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.auth.validate_authorization(AUTH, "calibration", 2000, 260999, "expected", ROOT / "evaluation" / "never.sqlite", CONFIG)

    def test_reference_contract_recalculation(self):
        calculator = load(CALCULATOR, "calculator_test")
        metrics = {x["metric_id"]: x for x in calculator.calculate(REFERENCE, CONTRACT, "reference")}
        self.assertEqual((metrics["search_zero_rate"]["numerator"], metrics["search_zero_rate"]["denominator"]), (3434, 6900))
        self.assertEqual((metrics["zero_followup_rate"]["numerator"], metrics["zero_followup_rate"]["denominator"]), (3271, 3434))
        self.assertEqual((metrics["immediate_recovery_transition_rate"]["numerator"], metrics["immediate_recovery_transition_rate"]["denominator"]), (558, 3271))
        self.assertEqual((metrics["first_zero_immediate_recovery_rate"]["numerator"], metrics["first_zero_immediate_recovery_rate"]["denominator"]), (69, 628))
        self.assertEqual((metrics["final_recovery_rate"]["numerator"], metrics["final_recovery_rate"]["denominator"]), (488, 651))
        self.assertEqual((metrics["card_h_search_rate"]["numerator"], metrics["card_h_search_rate"]["denominator"]), (680, 3466))

    def test_smoke_relational_pair_and_booking_qa(self):
        c = sqlite3.connect("file:" + SMOKE.resolve().as_posix() + "?mode=ro", uri=True)
        self.assertEqual(c.execute("pragma integrity_check").fetchone()[0], "ok")
        self.assertEqual(c.execute("pragma foreign_key_check").fetchall(), [])
        self.assertEqual(c.execute("select count(*) from UserSynthetic").fetchone()[0], 200)
        self.assertEqual(c.execute("select count(*) from Booking").fetchone()[0], 0)
        self.assertEqual(c.execute("select count(*) from (select pair_id from UserSynthetic group by pair_id having count(*)=2 and count(distinct sample_set_type)=2)").fetchone()[0], 100)
        self.assertEqual(c.execute("select count(*) from (select pair_id from UserSynthetic group by pair_id having count(distinct sample_stratum)>1 or count(distinct source_session_id)>1)").fetchone()[0], 0)
        c.close()

    def test_card_h_search_and_event_grains_are_separate(self):
        c = sqlite3.connect("file:" + SMOKE.resolve().as_posix() + "?mode=ro", uri=True)
        searches = c.execute("select count(distinct e.search_id) from SearchResult r join ActionEvent e on e.search_id=r.search_id and e.hotel_id=r.hotel_id where r.result_rank=1 and e.event_type='hotel_detail_view'").fetchone()[0]
        events = c.execute("select count(*) from SearchResult r join ActionEvent e on e.search_id=r.search_id and e.hotel_id=r.hotel_id where r.result_rank=1 and e.event_type='hotel_detail_view'").fetchone()[0]
        self.assertGreaterEqual(events, searches)
        c.close()

    def test_preserved_collision_and_new_zero_collision(self):
        prior = json.loads((STAGE / "호텔검색_1만명증강_승인인터페이스수정및교정_260907_1351_01" / "호텔검색_1만명증강_진단교정결과_260907_1351_01.json").read_text(encoding="utf-8"))
        self.assertEqual(prior["seeds"][0]["control_clone_b"], 2)
        self.assertEqual(prior["seeds"][0]["control_clone_c"], 2)
        sidecars = sorted((ROOT / "evaluation").glob("evaluation_expected_*.sidecar.json"))
        self.assertEqual(len(sidecars), 20)
        for path in sidecars:
            row = json.loads(path.read_text(encoding="utf-8"))["integrated_gate"]["clones"]
            self.assertEqual(row["control_clone_b"] + row["control_clone_c"] + row["treatment_clone_b"] + row["treatment_clone_c"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
