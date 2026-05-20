"""Shared MariaDB helpers for OpenStack service databases."""

import json
import os
from typing import Any, Optional

try:
    import pymysql
except Exception:  # pragma: no cover - optional dependency at runtime
    pymysql = None

TRUTHY_VALUES = {"1", "true", "yes", "on"}


def get_mariadb_connection(database: str):
    if pymysql is None:
        raise RuntimeError("PyMySQL is not installed")

    return pymysql.connect(
        host=os.getenv("MARIADB_HOST", "127.0.0.1"),
        port=int(os.getenv("MARIADB_PORT", "3306")),
        user=os.getenv("MARIADB_USER", ""),
        password=os.getenv("MARIADB_PASSWORD", ""),
        database=database,
        charset=os.getenv("MARIADB_CHARSET", "utf8mb4"),
        connect_timeout=int(os.getenv("MARIADB_CONNECT_TIMEOUT", "10")),
        cursorclass=pymysql.cursors.DictCursor,
    )


def table_columns(cur, table_name: str) -> set[str]:
    try:
        cur.execute(f"SHOW COLUMNS FROM `{table_name}`")
        return {row["Field"] for row in cur.fetchall()}
    except Exception:
        return set()


def table_exists(cur, table_name: str) -> bool:
    return bool(table_columns(cur, table_name))


def column_expr(alias: str, columns: set[str], *names: str, default: str = "NULL") -> str:
    prefix = f"{alias}." if alias else ""
    for name in names:
        if name in columns:
            return f"{prefix}{name}"
    return default


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in TRUTHY_VALUES


def json_value(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def str_time(value: Any) -> str:
    return "unknown" if value in (None, "") else str(value)


def scope_project_id(include_all_projects: bool = False, project_id: str = "") -> Optional[str]:
    if project_id:
        return project_id
    if include_all_projects:
        return None
    return (
        os.getenv("MARIADB_PROJECT_ID")
        or os.getenv("OS_PROJECT_ID")
        or os.getenv("OS_TENANT_ID")
        or None
    )
