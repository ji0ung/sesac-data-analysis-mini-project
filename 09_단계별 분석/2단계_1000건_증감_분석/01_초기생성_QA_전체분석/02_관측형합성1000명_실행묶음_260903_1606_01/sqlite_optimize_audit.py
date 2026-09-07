#!/usr/bin/env python3
"""SQLite 원본을 변경하지 않고 점검 후 VACUUM INTO 복사본을 만든다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


TEMP_NAME = re.compile(
    r"(^|_)(temp|tmp|stg|stage|scratch|backup|bak|old|quality_checks?|import_metadata)($|_)",
    re.IGNORECASE,
)
TIME_NAME = re.compile(r"(_at|_date|_time|_deadline)$", re.IGNORECASE)


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def scalar(connection: sqlite3.Connection, sql: str):
    return connection.execute(sql).fetchone()[0]


def affinity(declared_type: str) -> str:
    declared_type = (declared_type or "").upper()
    if "INT" in declared_type:
        return "INTEGER"
    if any(token in declared_type for token in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if "BLOB" in declared_type or not declared_type:
        return "BLOB"
    if any(token in declared_type for token in ("REAL", "FLOA", "DOUB")):
        return "REAL"
    return "NUMERIC"


def allowed_storage_types(column_affinity: str) -> set[str]:
    return {
        "INTEGER": {"integer", "null"},
        "TEXT": {"text", "null"},
        "REAL": {"real", "integer", "null"},
        "BLOB": {"blob", "text", "integer", "real", "null"},
        "NUMERIC": {"integer", "real", "null"},
    }[column_affinity]


def logical_dump_hash(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for line in connection.iterdump():
        digest.update(line.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def inspect_database(path: Path, include_dump_hash: bool) -> dict:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        table_rows = {
            table: scalar(connection, f"SELECT COUNT(*) FROM {quote_identifier(table)}")
            for table in table_names
        }

        temporary_candidates = [
            {"table": table, "rows": table_rows[table]}
            for table in table_names
            if TEMP_NAME.search(table)
        ]
        empty_tables = [table for table in table_names if table_rows[table] == 0]

        index_groups: dict[tuple, list[str]] = defaultdict(list)
        custom_indexes = []
        for table in table_names:
            for index_row in connection.execute(
                f"PRAGMA index_list({quote_identifier(table)})"
            ):
                index_name = index_row[1]
                origin = index_row[3]
                if origin != "c":
                    continue  # PK/UNIQUE 자동 인덱스는 삭제 후보가 아니다.
                key_columns = tuple(
                    (row[1], row[2], row[3], row[4])
                    for row in connection.execute(
                        f"PRAGMA index_xinfo({quote_identifier(index_name)})"
                    )
                    if row[5] == 1
                )
                sql = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
                    (index_name,),
                ).fetchone()[0]
                where_clause = ""
                if sql and re.search(r"\bWHERE\b", sql, re.IGNORECASE):
                    where_clause = re.split(r"\bWHERE\b", sql, 1, flags=re.IGNORECASE)[1].strip()
                signature = (
                    table,
                    bool(index_row[2]),
                    bool(index_row[4]),
                    key_columns,
                    where_clause,
                )
                index_groups[signature].append(index_name)
                custom_indexes.append(
                    {"name": index_name, "table": table, "key_columns": key_columns}
                )
        duplicate_indexes = [names for names in index_groups.values() if len(names) > 1]

        type_mismatches = []
        timestamp_columns = []
        text_storage = []
        for table in table_names:
            for column in connection.execute(
                f"PRAGMA table_xinfo({quote_identifier(table)})"
            ):
                column_name = column[1]
                declared_type = column[2]
                column_affinity = affinity(declared_type)
                storage = {
                    row[0]: row[1]
                    for row in connection.execute(
                        f"SELECT typeof({quote_identifier(column_name)}), COUNT(*) "
                        f"FROM {quote_identifier(table)} "
                        f"GROUP BY typeof({quote_identifier(column_name)})"
                    )
                }
                mismatch_rows = sum(
                    count
                    for storage_type, count in storage.items()
                    if storage_type not in allowed_storage_types(column_affinity)
                )
                if mismatch_rows:
                    type_mismatches.append(
                        {
                            "table": table,
                            "column": column_name,
                            "declared_type": declared_type,
                            "storage_types": storage,
                            "mismatch_rows": mismatch_rows,
                        }
                    )

                if column_affinity == "TEXT":
                    nonnull, distinct_values, characters, max_length = connection.execute(
                        f"SELECT COUNT({quote_identifier(column_name)}), "
                        f"COUNT(DISTINCT {quote_identifier(column_name)}), "
                        f"COALESCE(SUM(LENGTH({quote_identifier(column_name)})), 0), "
                        f"MAX(LENGTH({quote_identifier(column_name)})) "
                        f"FROM {quote_identifier(table)}"
                    ).fetchone()
                    text_storage.append(
                        {
                            "table": table,
                            "column": column_name,
                            "nonnull": nonnull,
                            "distinct": distinct_values,
                            "characters": characters,
                            "max_length": max_length,
                        }
                    )

                if column_affinity == "TEXT" and TIME_NAME.search(column_name):
                    row = connection.execute(
                        f"SELECT COUNT({quote_identifier(column_name)}), "
                        f"MIN(LENGTH({quote_identifier(column_name)})), "
                        f"MAX(LENGTH({quote_identifier(column_name)})), "
                        f"SUM(CASE WHEN {quote_identifier(column_name)} IS NOT NULL "
                        f"AND {quote_identifier(column_name)}<>'' "
                        f"AND julianday({quote_identifier(column_name)}) IS NULL "
                        f"THEN 1 ELSE 0 END), "
                        f"SUM(CASE WHEN LENGTH({quote_identifier(column_name)})>19 "
                        f"THEN 1 ELSE 0 END) "
                        f"FROM {quote_identifier(table)}"
                    ).fetchone()
                    timestamp_columns.append(
                        {
                            "table": table,
                            "column": column_name,
                            "nonnull": row[0],
                            "min_length": row[1],
                            "max_length": row[2],
                            "sqlite_unparseable": row[3] or 0,
                            "longer_than_seconds": row[4] or 0,
                        }
                    )

        result = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "page_count": scalar(connection, "PRAGMA page_count"),
            "page_size": scalar(connection, "PRAGMA page_size"),
            "freelist_count": scalar(connection, "PRAGMA freelist_count"),
            "integrity_check": scalar(connection, "PRAGMA integrity_check"),
            "table_rows": table_rows,
            "temporary_table_candidates": temporary_candidates,
            "empty_tables_for_review_only": empty_tables,
            "custom_indexes": custom_indexes,
            "exact_duplicate_custom_indexes": duplicate_indexes,
            "type_affinity_mismatches": type_mismatches,
            "timestamp_columns": timestamp_columns,
            "largest_text_columns": sorted(
                text_storage, key=lambda item: item["characters"], reverse=True
            )[:15],
        }
        if include_dump_hash:
            result["logical_dump_sha256"] = logical_dump_hash(connection)
        return result
    finally:
        connection.close()


def vacuum_into(source: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"출력 파일이 이미 존재합니다: {output}")
    before = (source.stat().st_size, source.stat().st_mtime_ns)
    connection = sqlite3.connect(source)
    try:
        if scalar(connection, "PRAGMA integrity_check") != "ok":
            raise RuntimeError("원본 무결성 검사를 통과하지 못했습니다.")
        escaped_output = str(output.resolve()).replace("'", "''")
        connection.execute(f"VACUUM INTO '{escaped_output}'")
    finally:
        connection.close()
    after = (source.stat().st_size, source.stat().st_mtime_ns)
    if before != after:
        raise RuntimeError("원본 파일 크기 또는 수정 시각이 변경되었습니다.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="점검할 원본 SQLite 파일")
    parser.add_argument("--output", type=Path, help="VACUUM INTO 출력 파일")
    parser.add_argument(
        "--audit-only", action="store_true", help="파일을 생성하지 않고 점검만 수행"
    )
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    source_report = inspect_database(source, include_dump_hash=not args.audit_only)
    report = {"source": source_report}
    if not args.audit_only:
        output = (args.output or source.with_name(source.stem + "_경량.sqlite")).resolve()
        vacuum_into(source, output)
        output_report = inspect_database(output, include_dump_hash=True)
        report["optimized"] = output_report
        report["validation"] = {
            "integrity_ok": output_report["integrity_check"] == "ok",
            "row_counts_match": source_report["table_rows"]
            == output_report["table_rows"],
            "logical_dump_hash_match": source_report["logical_dump_sha256"]
            == output_report["logical_dump_sha256"],
            "saved_bytes": source_report["bytes"] - output_report["bytes"],
            "reduction_percent": round(
                (source_report["bytes"] - output_report["bytes"])
                / source_report["bytes"]
                * 100,
                6,
            ),
        }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
