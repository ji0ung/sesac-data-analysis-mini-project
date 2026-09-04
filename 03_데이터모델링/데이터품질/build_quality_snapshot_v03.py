from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = DATA_DIR / "이전버전" / "데이터셋" / "2026-09-03_v02"
TARGET_DIR = DATA_DIR / "현행데이터"
SOURCE_VERSION = "v02"
TARGET_VERSION = "v03"
DATE = "2026-09-03"

EXPECTED_INVALID_SEARCH_IDS = {
    "Q0CqLhuf7C",
    "Q333t6naRT",
    "Q3Hfff0KOt",
    "QDX2vny39Z",
    "QN1X76RVBO",
    "QX121uaX47",
    "QYMZRtxiN1",
    "QZ0FLsEEjB",
    "QdPLnzMcro",
}
EXPECTED_UNLINKED_CLICK_IDS = {"EUDMKVOFRk", "EglOupSyiI"}
TABLES = (
    "booking",
    "event",
    "hotel",
    "room",
    "search",
    "search_filter",
    "search_result",
    "user",
)


def find_one(pattern: str) -> Path:
    matches = list(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one match for {pattern!r}, found {len(matches)}")
    return matches[0]


def target_path(source: Path) -> Path:
    return TARGET_DIR / source.name.replace(f"_{SOURCE_VERSION}_", f"_{TARGET_VERSION}_", 1)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_search_csv(source: Path, target: Path) -> None:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or []) + ["invalid_stay_date_flag"]
        rows = []
        invalid_ids = set()
        for row in reader:
            invalid = int(row["checkout_date"] < row["checkin_date"])
            row["invalid_stay_date_flag"] = str(invalid)
            if invalid:
                invalid_ids.add(row["search_id"])
            rows.append(row)
    if len(rows) != 296 or invalid_ids != EXPECTED_INVALID_SEARCH_IDS:
        raise RuntimeError("Search quality check failed; refusing to create v03.")
    write_csv(target, fieldnames, rows)


def build_event_csv(source: Path, result_source: Path, target: Path) -> None:
    with result_source.open(encoding="utf-8-sig", newline="") as handle:
        result_pairs = {
            (row["search_id"], row["hotel_id"])
            for row in csv.DictReader(handle)
        }
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or []) + ["click_in_result_flag"]
        rows = []
        click_count = 0
        unlinked_ids = set()
        for row in reader:
            if row["event_type"] == "hotel_click":
                click_count += 1
                linked = int((row["search_id"], row["hotel_id"]) in result_pairs)
                row["click_in_result_flag"] = str(linked)
                if not linked:
                    unlinked_ids.add(row["event_id"])
            else:
                row["click_in_result_flag"] = ""
            rows.append(row)
    if len(rows) != 10_432 or click_count != 231 or unlinked_ids != EXPECTED_UNLINKED_CLICK_IDS:
        raise RuntimeError("Event quality check failed; refusing to create v03.")
    write_csv(target, fieldnames, rows)


def build_database(source: Path, target: Path) -> None:
    shutil.copy2(source, target)
    connection = sqlite3.connect(target)
    try:
        search_columns = {row[1] for row in connection.execute("PRAGMA table_info(search)")}
        event_columns = {row[1] for row in connection.execute("PRAGMA table_info(event)")}
        if "invalid_stay_date_flag" not in search_columns:
            connection.execute(
                "ALTER TABLE search ADD COLUMN invalid_stay_date_flag INTEGER NOT NULL DEFAULT 0"
            )
        if "click_in_result_flag" not in event_columns:
            connection.execute("ALTER TABLE event ADD COLUMN click_in_result_flag INTEGER")

        connection.execute(
            """
            UPDATE search
            SET invalid_stay_date_flag = CASE
                WHEN date(checkout_date) < date(checkin_date) THEN 1
                ELSE 0
            END
            """
        )
        connection.execute("UPDATE event SET click_in_result_flag = NULL")
        connection.execute(
            """
            UPDATE event
            SET click_in_result_flag = CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM search_result AS sr
                    WHERE sr.search_id = event.search_id
                      AND sr.hotel_id = event.hotel_id
                ) THEN 1
                ELSE 0
            END
            WHERE event_type = 'hotel_click'
            """
        )
        connection.commit()

        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("SQLite integrity_check failed.")
        invalid_ids = {
            row[0]
            for row in connection.execute(
                "SELECT search_id FROM search WHERE invalid_stay_date_flag = 1"
            )
        }
        unlinked_ids = {
            row[0]
            for row in connection.execute(
                "SELECT event_id FROM event WHERE event_type = 'hotel_click' AND click_in_result_flag = 0"
            )
        }
        non_click_with_flag = connection.execute(
            "SELECT COUNT(*) FROM event WHERE event_type <> 'hotel_click' AND click_in_result_flag IS NOT NULL"
        ).fetchone()[0]
        if invalid_ids != EXPECTED_INVALID_SEARCH_IDS:
            raise RuntimeError("SQLite search flags do not match the validated IDs.")
        if unlinked_ids != EXPECTED_UNLINKED_CLICK_IDS:
            raise RuntimeError("SQLite click flags do not match the validated IDs.")
        if non_click_with_flag != 0:
            raise RuntimeError("Non-click events must have NULL click_in_result_flag.")
    finally:
        connection.close()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    csv_sources = {
        table: find_one(f"{table}_{DATE}_{SOURCE_VERSION}_*.csv")
        for table in TABLES
    }
    db_source = find_one(f"travel_data_filtered_complete_{DATE}_{SOURCE_VERSION}_*.sqlite")

    targets = []
    for table, source in csv_sources.items():
        target = target_path(source)
        if table == "search":
            build_search_csv(source, target)
        elif table == "event":
            build_event_csv(source, csv_sources["search_result"], target)
        else:
            shutil.copy2(source, target)
        targets.append(target)

    db_target = target_path(db_source)
    build_database(db_source, db_target)
    targets.append(db_target)

    result = {
        "dataset_version": f"{DATE}_{TARGET_VERSION}",
        "files": [
            {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(targets)
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
