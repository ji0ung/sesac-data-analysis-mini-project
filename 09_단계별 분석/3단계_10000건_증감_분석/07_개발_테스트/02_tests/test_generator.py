from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
GENERATOR_PATH = HERE / "02_generator.py"
CONFIG_PATH = HERE / "02_base_config.yaml"
DRYRUN_PATH = HERE / "02_dryrun_200.sqlite"

spec = importlib.util.spec_from_file_location("dryrun_generator", GENERATOR_PATH)
generator = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(generator)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class GeneratedDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.conn = sqlite3.connect(f"file:{DRYRUN_PATH.as_posix()}?mode=ro", uri=True)
        cls.conn.execute("PRAGMA query_only=ON")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.close()

    def scalar(self, sql: str):
        return self.conn.execute(sql).fetchone()[0]

    def test_integrity_and_foreign_keys(self):
        self.assertEqual(self.scalar("PRAGMA integrity_check"), "ok")
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_primary_keys_have_no_duplicates_or_nulls(self):
        tables = [
            "SimulationRun", "UserProfile", "ExperimentAssignment", "Search",
            "SearchResult", "ActionEvent", "SearchTransition", "SessionSummary",
            "_generation_metadata",
        ]
        for table in tables:
            info = self.conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            pk = [row[1] for row in info if row[5]]
            self.assertTrue(pk, table)
            expression = "||'|'||".join(
                f'COALESCE(CAST("{column}" AS TEXT),"<NULL>")' for column in pk
            )
            duplicate_n = self.scalar(
                f'SELECT COUNT(*)-COUNT(DISTINCT {expression}) FROM "{table}"'
            )
            self.assertEqual(duplicate_n, 0, table)
            for column in pk:
                self.assertEqual(
                    self.scalar(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NULL'),
                    0,
                    f"{table}.{column}",
                )

    def test_one_to_one_contracts(self):
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM UserProfile"), 200)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM ExperimentAssignment"), 200)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM SessionSummary"), 200)
        self.assertEqual(self.scalar("SELECT COUNT(DISTINCT pair_id) FROM UserProfile"), 100)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM (SELECT pair_id FROM UserProfile GROUP BY pair_id HAVING COUNT(*)<>2 OR COUNT(DISTINCT arm)<>2)"
            ),
            0,
        )

    def test_pair_pre_attributes_are_equal(self):
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM (
                  SELECT pair_id FROM UserProfile
                  GROUP BY pair_id
                  HAVING COUNT(DISTINCT COALESCE(age_group,'<NULL>'))<>1
                     OR COUNT(DISTINCT COALESCE(destination,'<NULL>'))<>1
                     OR COUNT(DISTINCT filter_state_segment)<>1
                     OR COUNT(DISTINCT intent_segment)<>1
                     OR COUNT(DISTINCT template_search_id)<>1
                     OR COUNT(DISTINCT template_signature)<>1
                )
                """
            ),
            0,
        )

    def test_arm_balance(self):
        rows = dict(self.conn.execute("SELECT arm,COUNT(*) FROM UserProfile GROUP BY arm"))
        self.assertEqual(rows, {"control": 100, "treatment": 100})
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM (
                  SELECT intent_segment,
                    SUM(arm='control') c, SUM(arm='treatment') t
                  FROM UserProfile GROUP BY intent_segment HAVING c<>t
                )
                """
            ),
            0,
        )

    def test_result_count_and_exposure_links(self):
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM Search s
                WHERE s.total_result_count <> (
                  SELECT COUNT(*) FROM SearchResult r WHERE r.search_id=s.search_id
                )
                """
            ),
            0,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*)-COUNT(DISTINCT search_id||'|'||hotel_id) FROM SearchResult"
            ),
            0,
        )

    def test_time_order(self):
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM Search s JOIN SessionSummary ss USING(session_id)
                WHERE s.search_at < ss.session_start_at OR s.search_at >= ss.session_end_at
                """
            ),
            0,
        )
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM ActionEvent e JOIN SessionSummary s USING(session_id)
                WHERE e.event_at<s.session_start_at OR e.event_at>s.session_end_at
                """
            ),
            0,
        )
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM Search s
                WHERE (SELECT COUNT(*) FROM ActionEvent e
                       WHERE e.search_id=s.search_id AND e.event_type='search_submit')<>1
                   OR (SELECT MIN(e.event_at) FROM ActionEvent e
                       WHERE e.search_id=s.search_id AND e.event_type='search_submit')<>s.search_at
                """
            ),
            0,
        )
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM SearchTransition t
                JOIN Search a ON a.search_id=t.from_search_id
                JOIN Search b ON b.search_id=t.to_search_id
                WHERE b.search_at<=a.search_at
                   OR CAST(ROUND((julianday(substr(b.search_at,1,19))-julianday(substr(a.search_at,1,19)))*86400) AS INTEGER)<>t.interarrival_seconds
                """
            ),
            0,
        )
        self.assertEqual(
            self.scalar(
                """
                WITH e AS (
                  SELECT session_id,event_at,
                    LAG(event_at) OVER(PARTITION BY session_id ORDER BY event_at,action_event_id) prev
                  FROM ActionEvent
                ) SELECT COUNT(*) FROM e WHERE event_at<prev
                """
            ),
            0,
        )

    def test_no_selection_before_exposure(self):
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM ActionEvent e
                WHERE e.event_type IN ('hotel_click','hotel_detail_view')
                  AND NOT EXISTS (
                    SELECT 1 FROM SearchResult r
                    WHERE r.search_id=e.search_id AND r.hotel_id=e.hotel_id
                      AND r.exposed_at<e.event_at
                  )
                """
            ),
            0,
        )
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM ActionEvent d
                WHERE d.event_type='hotel_detail_view'
                  AND NOT EXISTS (
                    SELECT 1 FROM ActionEvent c
                    WHERE c.search_id=d.search_id AND c.hotel_id=d.hotel_id
                      AND c.event_type='hotel_click' AND c.event_at<d.event_at
                  )
                """
            ),
            0,
        )

    def test_no_detail_before_recovery(self):
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM SearchTransition WHERE detail_after_recovery_flag>recovered_flag"
            ),
            0,
        )
        self.assertEqual(
            self.scalar(
                """
                SELECT COUNT(*) FROM SearchTransition t JOIN Search s ON s.search_id=t.to_search_id
                WHERE t.detail_after_recovery_flag=1 AND s.total_result_count=0
                """
            ),
            0,
        )

    def test_booking_is_prohibited(self):
        names = {
            row[0] for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertNotIn("Booking", names)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM ActionEvent WHERE event_type LIKE 'booking_%'"
            ),
            0,
        )

    def test_outcome_is_post_treatment_only(self):
        assignment_columns = {
            row[1] for row in self.conn.execute("PRAGMA table_info(ExperimentAssignment)")
        }
        self.assertNotIn("outcome_segment", assignment_columns)
        self.assertNotIn("SG1", dict(self.conn.execute("SELECT key,value FROM _generation_metadata")).get("scenario_assumption", ""))

    def test_template_concentration_cap(self):
        config = generator.load_config(CONFIG_PATH)
        pair_count = self.scalar("SELECT COUNT(DISTINCT pair_id) FROM UserProfile")
        cap = max(1, __import__("math").ceil(pair_count * config["generation"]["max_template_share"]))
        maximum = self.scalar(
            """
            SELECT MAX(n) FROM (
              SELECT template_search_id,COUNT(DISTINCT pair_id) n
              FROM UserProfile GROUP BY template_search_id
            )
            """
        )
        self.assertLessEqual(maximum, cap)

    def test_no_exact_source_row_clone(self):
        config = generator.load_config(CONFIG_PATH)
        source_path = generator.resolve_from_config(CONFIG_PATH, config["source"]["observed_db"])
        source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
        source.execute("PRAGMA query_only=ON")
        source_times = {row[0] for row in source.execute("SELECT search_time FROM search")}
        generated_times = {row[0] for row in self.conn.execute("SELECT search_at FROM Search")}
        source.close()
        self.assertTrue(source_times.isdisjoint(generated_times))

    def test_no_exact_session_path_clone(self):
        # Mechanical clone requires the same template signature, zero/nonzero path,
        # and exact relative offsets. Generated positive lognormal offsets are checked
        # against the source session that contains the template.
        config = generator.load_config(CONFIG_PATH)
        source_path = generator.resolve_from_config(CONFIG_PATH, config["source"]["observed_db"])
        source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
        source.execute("PRAGMA query_only=ON")
        template_session = dict(source.execute("SELECT search_id,session_id FROM search"))
        source_paths = {}
        for session_id in set(template_session.values()):
            rows = source.execute(
                "SELECT search_time,total_result_count FROM search WHERE session_id=? ORDER BY search_time,search_id",
                (session_id,),
            ).fetchall()
            flags = tuple(int(r[1] > 0) for r in rows)
            gaps = tuple(
                int(
                    (
                        __import__("datetime").datetime.strptime(rows[i][0][:19], "%Y-%m-%d %H:%M:%S")
                        - __import__("datetime").datetime.strptime(rows[i-1][0][:19], "%Y-%m-%d %H:%M:%S")
                    ).total_seconds()
                )
                for i in range(1, len(rows))
            )
            source_paths[session_id] = (flags, gaps)
        clones = 0
        for user_id, template_id in self.conn.execute(
            "SELECT user_id,template_search_id FROM UserProfile"
        ):
            rows = self.conn.execute(
                "SELECT search_at,total_result_count FROM Search WHERE user_id=? ORDER BY search_seq",
                (user_id,),
            ).fetchall()
            flags = tuple(int(r[1] > 0) for r in rows)
            gaps = tuple(
                int(
                    (
                        __import__("datetime").datetime.strptime(rows[i][0][:19], "%Y-%m-%d %H:%M:%S")
                        - __import__("datetime").datetime.strptime(rows[i-1][0][:19], "%Y-%m-%d %H:%M:%S")
                    ).total_seconds()
                )
                for i in range(1, len(rows))
            )
            clones += int((flags, gaps) == source_paths[template_session[template_id]])
        source.close()
        self.assertEqual(clones, 0)


class GeneratorBehaviorTests(unittest.TestCase):
    def test_config_schema(self):
        config = generator.load_config(CONFIG_PATH)
        self.assertEqual(config["full_design"]["control_users"], 5000)
        self.assertEqual(config["full_design"]["treatment_users"], 5000)
        self.assertEqual(config["dry_run"]["max_total_users"], 200)

    def test_full_generation_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                generator.generate(CONFIG_PATH, Path(directory) / "blocked.sqlite", 10000)

    def test_output_overwrite_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "exists.sqlite"
            target.write_bytes(b"sentinel")
            with self.assertRaises(FileExistsError):
                generator.generate(CONFIG_PATH, target, 20)
            self.assertEqual(target.read_bytes(), b"sentinel")

    def test_reproducibility(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.sqlite"
            second = Path(directory) / "second.sqlite"
            generator.generate(CONFIG_PATH, first, 20)
            generator.generate(CONFIG_PATH, second, 20)
            self.assertEqual(digest(first), digest(second))


if __name__ == "__main__":
    unittest.main()
