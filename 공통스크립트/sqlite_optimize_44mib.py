#!/usr/bin/env python3
"""Create the 44.719 MiB analysis/share SQLite layout without modifying the input."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

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
DROP_COLUMNS = {"data_origin"}
KST_COLUMNS = {
    ("event", "event_at"),
    ("event", "session_end_time"),
    ("search", "search_time"),
    ("user", "signup_at"),
}
REQUIRED_NULL_COLUMNS = {
    ("event", "review_completed_at"),
    ("event", "review_text"),
    ("search_filter", "property_type"),
    ("search_filter", "property_grade"),
    ("user", "age_group"),
}
PAGE_SIZE = 16_384
KNOWN_SOURCE_SHA256 = "db80db7048add9c0c4cb1a985e67a77ae99bef3a30ce32bedb70cc0ee61dc896"
KNOWN_RESULT_BYTES = 46_891_008


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def open_read_only(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    return connection


def scalar(connection: sqlite3.Connection, sql: str, parameters: Sequence[object] = ()) -> object:
    return connection.execute(sql, parameters).fetchone()[0]


def user_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def table_columns(connection: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
    rows = connection.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
    return [(row[1], row[2] or "") for row in rows]


def validate_source(connection: sqlite3.Connection) -> dict[str, list[tuple[str, str]]]:
    present = user_tables(connection)
    missing_tables = sorted(set(TABLES) - present)
    if missing_tables:
        raise ValueError(f"필수 테이블이 없습니다: {', '.join(missing_tables)}")

    schemas: dict[str, list[tuple[str, str]]] = {}
    for table in TABLES:
        columns = table_columns(connection, table)
        names = {name for name, _ in columns}
        if "data_origin" not in names:
            raise ValueError(f"{table}.data_origin이 없어 이미 변환됐거나 입력 형식이 다릅니다.")
        schemas[table] = [(name, declared_type) for name, declared_type in columns if name not in DROP_COLUMNS]

    missing_null_columns = sorted(
        f"{table}.{column}"
        for table, column in REQUIRED_NULL_COLUMNS
        if column not in {name for name, _ in schemas[table]}
    )
    if missing_null_columns:
        raise ValueError("보존 대상 NULL 컬럼이 없습니다: " + ", ".join(missing_null_columns))
    return schemas


def create_schema(connection: sqlite3.Connection, schemas: dict[str, list[tuple[str, str]]]) -> None:
    for table in TABLES:
        definitions = []
        for name, declared_type in schemas[table]:
            definitions.append(
                f"{quote_identifier(name)} {declared_type}".rstrip()
            )
        connection.execute(
            f"CREATE TABLE {quote_identifier(table)} ({', '.join(definitions)})"
        )


def attach_source(connection: sqlite3.Connection, source: Path) -> None:
    # ATTACH URI percent-encoding is unreliable for Windows paths containing
    # Korean characters. A bound absolute path handles those paths correctly.
    # The script only issues SELECT statements against the attached src schema,
    # and the source hash is checked before and after the run.
    connection.execute("ATTACH DATABASE ? AS src", (str(source.resolve()),))


def transformed_expression(table: str, column: str) -> str:
    identifier = quote_identifier(column)
    if (table, column) in KST_COLUMNS:
        return (
            f"CASE WHEN {identifier} LIKE '% KST' "
            f"THEN substr({identifier}, 1, length({identifier}) - 4) "
            f"ELSE {identifier} END"
        )
    return identifier


def copy_rows(
    connection: sqlite3.Connection,
    schemas: dict[str, list[tuple[str, str]]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        names = [name for name, _ in schemas[table]]
        target_columns = ", ".join(quote_identifier(name) for name in names)
        source_expressions = ", ".join(
            transformed_expression(table, name) for name in names
        )
        connection.execute(
            f"INSERT INTO main.{quote_identifier(table)} ({target_columns}) "
            f"SELECT {source_expressions} FROM src.{quote_identifier(table)}"
        )
        counts[table] = int(scalar(connection, "SELECT changes()"))
    return counts


def canonical_value(value: object) -> object:
    if value is None:
        return ["null", None]
    if isinstance(value, bytes):
        return ["blob", value.hex()]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        return ["real", value.hex()]
    return ["text", str(value)]


def digest_rows(rows: Iterable[Sequence[object]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        payload = json.dumps(
            [canonical_value(value) for value in row],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def table_digest(
    connection: sqlite3.Connection,
    table: str,
    columns: list[str],
    transform_kst: bool,
) -> str:
    if transform_kst:
        expressions = ", ".join(transformed_expression(table, name) for name in columns)
    else:
        expressions = ", ".join(quote_identifier(name) for name in columns)
    cursor = connection.execute(
        f"SELECT {expressions} FROM {quote_identifier(table)} ORDER BY rowid"
    )
    return digest_rows(cursor)


def verify(
    source: Path,
    output: Path,
    schemas: dict[str, list[tuple[str, str]]],
    source_sha_before: str,
    elapsed_seconds: float,
) -> dict[str, object]:
    source_sha_after = sha256_file(source)
    output_sha = sha256_file(output)
    source_db = open_read_only(source)
    output_db = open_read_only(output)
    try:
        table_results = {}
        exact = True
        for table in TABLES:
            columns = [name for name, _ in schemas[table]]
            source_count = int(scalar(source_db, f"SELECT COUNT(*) FROM {quote_identifier(table)}"))
            output_count = int(scalar(output_db, f"SELECT COUNT(*) FROM {quote_identifier(table)}"))
            source_digest = table_digest(source_db, table, columns, transform_kst=True)
            output_digest = table_digest(output_db, table, columns, transform_kst=False)
            matched = source_count == output_count and source_digest == output_digest
            exact = exact and matched
            table_results[table] = {
                "source_rows": source_count,
                "output_rows": output_count,
                "projected_transformed_sha256": source_digest,
                "output_sha256": output_digest,
                "matched": matched,
            }

        output_tables = user_tables(output_db)
        indexes = [
            row[0]
            for row in output_db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        data_origin_locations = []
        pk_columns = []
        for table in TABLES:
            for row in output_db.execute(f"PRAGMA table_info({quote_identifier(table)})"):
                if row[1] == "data_origin":
                    data_origin_locations.append(f"{table}.{row[1]}")
                if row[5]:
                    pk_columns.append(f"{table}.{row[1]}")

        kst_remaining = {}
        for table, column in sorted(KST_COLUMNS):
            count = int(
                scalar(
                    output_db,
                    f"SELECT COUNT(*) FROM {quote_identifier(table)} "
                    f"WHERE {quote_identifier(column)} LIKE '% KST'",
                )
            )
            kst_remaining[f"{table}.{column}"] = count

        null_column_checks = {}
        for table, column in sorted(REQUIRED_NULL_COLUMNS):
            exists = column in {name for name, _ in table_columns(output_db, table)}
            non_null = (
                int(
                    scalar(
                        output_db,
                        f"SELECT COUNT(*) FROM {quote_identifier(table)} "
                        f"WHERE {quote_identifier(column)} IS NOT NULL",
                    )
                )
                if exists
                else None
            )
            null_column_checks[f"{table}.{column}"] = {
                "exists": exists,
                "non_null_rows": non_null,
            }

        integrity = str(scalar(output_db, "PRAGMA integrity_check"))
        page_size = int(scalar(output_db, "PRAGMA page_size"))
        page_count = int(scalar(output_db, "PRAGMA page_count"))
        freelist_count = int(scalar(output_db, "PRAGMA freelist_count"))
        size_bytes = output.stat().st_size

        checks = {
            "source_unchanged": source_sha_before == source_sha_after,
            "tables_exact": output_tables == set(TABLES),
            "projected_values_exact": exact,
            "no_user_indexes": not indexes,
            "no_pk_constraints": not pk_columns,
            "data_origin_removed": not data_origin_locations,
            "kst_suffix_removed": all(value == 0 for value in kst_remaining.values()),
            "null_columns_preserved": all(
                item["exists"] for item in null_column_checks.values()
            ),
            "page_size_16384": page_size == PAGE_SIZE,
            "freelist_zero": freelist_count == 0,
            "integrity_ok": integrity == "ok",
        }
        passed = all(checks.values())
        return {
            "status": "PASS" if passed else "FAIL",
            "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": str(source.resolve()),
            "output": str(output.resolve()),
            "source_sha256_before": source_sha_before,
            "source_sha256_after": source_sha_after,
            "known_source_sha256_match": source_sha_before == KNOWN_SOURCE_SHA256,
            "output_sha256": output_sha,
            "output_size_bytes": size_bytes,
            "output_size_mib": round(size_bytes / 1024 / 1024, 6),
            "known_result_bytes_match": size_bytes == KNOWN_RESULT_BYTES,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "page_size": page_size,
            "page_count": page_count,
            "freelist_count": freelist_count,
            "integrity_check": integrity,
            "user_indexes": indexes,
            "pk_columns": pk_columns,
            "data_origin_locations": data_origin_locations,
            "kst_remaining": kst_remaining,
            "null_column_checks": null_column_checks,
            "tables": table_results,
            "checks": checks,
        }
    finally:
        source_db.close()
        output_db.close()


def build(source: Path, output: Path, verification: Path) -> dict[str, object]:
    source = source.resolve()
    output = output.resolve()
    verification = verification.resolve()

    if not source.is_file():
        raise FileNotFoundError(f"입력 파일이 없습니다: {source}")
    if source == output:
        raise ValueError("입력과 출력 경로는 달라야 합니다.")
    if output.exists():
        raise FileExistsError(f"출력 파일이 이미 있습니다: {output}")
    if verification.exists():
        raise FileExistsError(f"검증 파일이 이미 있습니다: {verification}")
    output.parent.mkdir(parents=True, exist_ok=True)
    verification.parent.mkdir(parents=True, exist_ok=True)

    source_sha_before = sha256_file(source)
    source_db = open_read_only(source)
    try:
        schemas = validate_source(source_db)
    finally:
        source_db.close()

    started = time.perf_counter()
    try:
        output_db = sqlite3.connect(output)
        try:
            output_db.execute(f"PRAGMA page_size={PAGE_SIZE}")
            output_db.execute("PRAGMA journal_mode=DELETE")
            output_db.execute("PRAGMA synchronous=OFF")
            output_db.execute("PRAGMA temp_store=MEMORY")
            attach_source(output_db, source)
            output_db.execute("BEGIN IMMEDIATE")
            create_schema(output_db, schemas)
            copy_rows(output_db, schemas)
            output_db.commit()
            output_db.execute("DETACH DATABASE src")
            output_db.execute("VACUUM")
            output_db.execute("PRAGMA synchronous=FULL")
            output_db.commit()
        finally:
            output_db.close()

        elapsed = time.perf_counter() - started
        report = verify(source, output, schemas, source_sha_before, elapsed)
        verification.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if report["status"] != "PASS":
            raise RuntimeError(f"검증 실패: {verification}")
        return report
    except Exception:
        if output.exists():
            output.unlink()
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="93.363 MiB 원본에서 44.719 MiB 분석·공유용 SQLite를 생성합니다."
    )
    parser.add_argument("--input", required=True, type=Path, help="원본 SQLite 경로")
    parser.add_argument("--output", required=True, type=Path, help="새 경량 SQLite 경로")
    parser.add_argument(
        "--verification",
        type=Path,
        help="검증 JSON 경로. 생략하면 출력 파일명 뒤에 .verification.json을 붙입니다.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verification = args.verification or Path(str(args.output) + ".verification.json")
    try:
        report = build(args.input, args.output, verification)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": report["status"],
                "output": report["output"],
                "output_size_mib": report["output_size_mib"],
                "output_sha256": report["output_sha256"],
                "verification": str(verification.resolve()),
                "source_unchanged": report["checks"]["source_unchanged"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
