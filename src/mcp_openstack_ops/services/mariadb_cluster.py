"""Read-only MariaDB cluster monitoring helpers."""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .db import get_mariadb_connection

logger = logging.getLogger(__name__)

DEFAULT_DATABASE = "information_schema"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _connect():
    return get_mariadb_connection(DEFAULT_DATABASE)


def _execute_rows(sql: str, params: Optional[List[Any]] = None) -> tuple[List[Dict[str, Any]], str]:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return [_json_safe(dict(row)) for row in cur.fetchall()], ""
    except Exception as e:
        logger.warning("MariaDB monitoring query failed: %s", e)
        return [], str(e)
    finally:
        conn.close()


def _show_global(kind: str, names: Optional[List[str]] = None, prefix: str = "") -> tuple[Dict[str, Any], List[str]]:
    conn = _connect()
    values: Dict[str, Any] = {}
    warnings: List[str] = []
    try:
        with conn.cursor() as cur:
            if names:
                for name in names:
                    try:
                        cur.execute(f"SHOW GLOBAL {kind} LIKE %s", [name])
                        row = cur.fetchone()
                        if row:
                            values[row.get("Variable_name")] = row.get("Value")
                    except Exception as e:
                        warnings.append(f"SHOW GLOBAL {kind} {name}: {str(e)}")
            elif prefix:
                cur.execute(f"SHOW GLOBAL {kind} LIKE %s", [prefix])
                values.update({row.get("Variable_name"): row.get("Value") for row in cur.fetchall()})
            else:
                cur.execute(f"SHOW GLOBAL {kind}")
                values.update({row.get("Variable_name"): row.get("Value") for row in cur.fetchall()})
    except Exception as e:
        warnings.append(str(e))
    finally:
        conn.close()
    return _json_safe(values), warnings


def _int_value(values: Dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(float(values.get(key, default) or default))
    except (TypeError, ValueError):
        return default


def _float_value(values: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(values.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _percent(used: Any, total: Any) -> Optional[float]:
    try:
        used_number = float(used)
        total_number = float(total)
    except (TypeError, ValueError):
        return None
    if total_number <= 0:
        return None
    return round((used_number / total_number) * 100, 2)


def _base_status() -> tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    status_names = [
        "Aborted_clients",
        "Aborted_connects",
        "Bytes_received",
        "Bytes_sent",
        "Connections",
        "Created_tmp_disk_tables",
        "Created_tmp_tables",
        "Max_used_connections",
        "Open_tables",
        "Opened_tables",
        "Queries",
        "Questions",
        "Slow_queries",
        "Threads_cached",
        "Threads_connected",
        "Threads_created",
        "Threads_running",
        "Uptime",
        "wsrep_cluster_size",
        "wsrep_cluster_status",
        "wsrep_connected",
        "wsrep_local_recv_queue",
        "wsrep_local_send_queue",
        "wsrep_local_state_comment",
        "wsrep_ready",
    ]
    variable_names = [
        "hostname",
        "max_connections",
        "read_only",
        "slow_query_log",
        "long_query_time",
        "version",
        "version_comment",
        "wsrep_on",
        "wsrep_provider",
        "wsrep_cluster_name",
        "wsrep_node_name",
        "wsrep_node_address",
    ]
    status, status_warnings = _show_global("STATUS", status_names)
    variables, variable_warnings = _show_global("VARIABLES", variable_names)
    return status, variables, status_warnings + variable_warnings


def mariadb_cluster_health() -> Dict[str, Any]:
    status, variables, warnings = _base_status()
    max_connections = _int_value(variables, "max_connections")
    threads_connected = _int_value(status, "Threads_connected")
    max_used_connections = _int_value(status, "Max_used_connections")
    cluster_size = _int_value(status, "wsrep_cluster_size")
    wsrep_ready = str(status.get("wsrep_ready", "")).upper()
    cluster_status = str(status.get("wsrep_cluster_status", "")).lower()

    alerts = _build_alerts(status, variables)
    health_state = "healthy"
    if any(alert.get("severity") == "critical" for alert in alerts):
        health_state = "critical"
    elif alerts:
        health_state = "warning"

    return {
        "success": True,
        "health_state": health_state,
        "node": {
            "hostname": variables.get("hostname"),
            "version": variables.get("version"),
            "version_comment": variables.get("version_comment"),
            "read_only": variables.get("read_only"),
            "uptime_seconds": _int_value(status, "Uptime"),
        },
        "cluster": {
            "wsrep_on": variables.get("wsrep_on"),
            "wsrep_ready": status.get("wsrep_ready"),
            "wsrep_cluster_status": status.get("wsrep_cluster_status"),
            "wsrep_cluster_size": cluster_size,
            "wsrep_local_state_comment": status.get("wsrep_local_state_comment"),
            "is_primary": cluster_status == "primary",
            "is_ready": wsrep_ready == "ON",
        },
        "connections": {
            "threads_connected": threads_connected,
            "threads_running": _int_value(status, "Threads_running"),
            "max_connections": max_connections,
            "max_used_connections": max_used_connections,
            "connection_usage_percent": _percent(threads_connected, max_connections),
            "peak_connection_usage_percent": _percent(max_used_connections, max_connections),
        },
        "query_counters": {
            "queries": _int_value(status, "Queries"),
            "questions": _int_value(status, "Questions"),
            "slow_queries": _int_value(status, "Slow_queries"),
        },
        "alerts": alerts,
        "warnings": warnings,
        "data_source": "mariadb",
    }


def mariadb_cluster_replication_overview() -> Dict[str, Any]:
    status, variables, warnings = _base_status()
    replica_rows, replica_warning = _execute_rows("SHOW REPLICA STATUS")
    if replica_warning:
        fallback_rows, fallback_warning = _execute_rows("SHOW SLAVE STATUS")
        replica_rows = fallback_rows
        if fallback_warning:
            warnings.extend([f"SHOW REPLICA STATUS: {replica_warning}", f"SHOW SLAVE STATUS: {fallback_warning}"])

    return {
        "success": True,
        "galera": {
            "wsrep_on": variables.get("wsrep_on"),
            "cluster_name": variables.get("wsrep_cluster_name"),
            "node_name": variables.get("wsrep_node_name"),
            "node_address": variables.get("wsrep_node_address"),
            "cluster_size": status.get("wsrep_cluster_size"),
            "cluster_status": status.get("wsrep_cluster_status"),
            "connected": status.get("wsrep_connected"),
            "ready": status.get("wsrep_ready"),
            "local_state": status.get("wsrep_local_state_comment"),
            "local_recv_queue": status.get("wsrep_local_recv_queue"),
            "local_send_queue": status.get("wsrep_local_send_queue"),
        },
        "async_replication": replica_rows,
        "warnings": warnings,
        "data_source": "mariadb",
    }


def mariadb_cluster_connection_stats() -> Dict[str, Any]:
    status, variables, warnings = _base_status()
    max_connections = _int_value(variables, "max_connections")
    return {
        "success": True,
        "connection_stats": {
            "threads_connected": _int_value(status, "Threads_connected"),
            "threads_running": _int_value(status, "Threads_running"),
            "threads_cached": _int_value(status, "Threads_cached"),
            "threads_created": _int_value(status, "Threads_created"),
            "connections": _int_value(status, "Connections"),
            "max_connections": max_connections,
            "max_used_connections": _int_value(status, "Max_used_connections"),
            "connection_usage_percent": _percent(status.get("Threads_connected"), max_connections),
            "aborted_clients": _int_value(status, "Aborted_clients"),
            "aborted_connects": _int_value(status, "Aborted_connects"),
            "bytes_received": _int_value(status, "Bytes_received"),
            "bytes_sent": _int_value(status, "Bytes_sent"),
        },
        "warnings": warnings,
        "data_source": "mariadb",
    }


def mariadb_cluster_query_performance() -> Dict[str, Any]:
    status, variables, warnings = _base_status()
    command_status, command_warnings = _show_global("STATUS", prefix="Com_%")
    warnings.extend(command_warnings)
    uptime = max(_int_value(status, "Uptime"), 1)
    queries = _int_value(status, "Queries")
    tmp_tables = _int_value(status, "Created_tmp_tables")
    tmp_disk_tables = _int_value(status, "Created_tmp_disk_tables")
    return {
        "success": True,
        "query_performance": {
            "queries": queries,
            "questions": _int_value(status, "Questions"),
            "queries_per_second": round(queries / uptime, 2),
            "slow_queries": _int_value(status, "Slow_queries"),
            "slow_query_log": variables.get("slow_query_log"),
            "long_query_time": _float_value(variables, "long_query_time"),
            "created_tmp_tables": tmp_tables,
            "created_tmp_disk_tables": tmp_disk_tables,
            "tmp_disk_table_percent": _percent(tmp_disk_tables, tmp_tables),
            "open_tables": _int_value(status, "Open_tables"),
            "opened_tables": _int_value(status, "Opened_tables"),
            "commands": command_status,
        },
        "warnings": warnings,
        "data_source": "mariadb",
    }


def mariadb_cluster_storage_utilization() -> Dict[str, Any]:
    rows, warning = _execute_rows(
        """
        SELECT
            table_schema,
            COUNT(*) AS table_count,
            COALESCE(SUM(table_rows), 0) AS row_estimate,
            COALESCE(SUM(data_length), 0) AS data_bytes,
            COALESCE(SUM(index_length), 0) AS index_bytes,
            COALESCE(SUM(data_length + index_length), 0) AS total_bytes
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
        GROUP BY table_schema
        ORDER BY total_bytes DESC
        """
    )
    total_bytes = sum(int(row.get("total_bytes") or 0) for row in rows)
    return {
        "success": not bool(warning),
        "storage": {
            "total_bytes": total_bytes,
            "schemas": rows,
        },
        "warnings": [warning] if warning else [],
        "data_source": "mariadb",
    }


def mariadb_cluster_capacity_summary() -> Dict[str, Any]:
    health = mariadb_cluster_health()
    storage = mariadb_cluster_storage_utilization()
    top_tables = mariadb_cluster_top_tables(limit=10)
    return {
        "success": True,
        "capacity": {
            "connections": health.get("connections", {}),
            "storage": storage.get("storage", {}),
            "largest_tables": top_tables.get("tables", []),
            "alerts": health.get("alerts", []),
        },
        "warnings": health.get("warnings", []) + storage.get("warnings", []) + top_tables.get("warnings", []),
        "data_source": "mariadb",
    }


def mariadb_cluster_top_slow_queries(limit: int = 10) -> Dict[str, Any]:
    safe_limit = max(1, min(int(limit or 10), 100))
    rows, warning = _execute_rows(
        f"""
        SELECT
            schema_name,
            digest,
            digest_text,
            count_star,
            ROUND(sum_timer_wait / 1000000000000, 6) AS total_seconds,
            ROUND(avg_timer_wait / 1000000000000, 6) AS avg_seconds,
            ROUND(max_timer_wait / 1000000000000, 6) AS max_seconds,
            sum_rows_examined,
            sum_rows_sent,
            first_seen,
            last_seen
        FROM performance_schema.events_statements_summary_by_digest
        WHERE digest_text IS NOT NULL
        ORDER BY sum_timer_wait DESC
        LIMIT {safe_limit}
        """
    )
    return {
        "success": not bool(warning),
        "queries": rows,
        "limit": safe_limit,
        "warnings": [warning] if warning else [],
        "data_source": "mariadb",
    }


def mariadb_cluster_top_tables(limit: int = 20) -> Dict[str, Any]:
    safe_limit = max(1, min(int(limit or 20), 200))
    rows, warning = _execute_rows(
        f"""
        SELECT
            table_schema,
            table_name,
            engine,
            table_rows AS row_estimate,
            data_length,
            index_length,
            data_length + index_length AS total_bytes,
            create_time,
            update_time
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
        ORDER BY total_bytes DESC
        LIMIT {safe_limit}
        """
    )
    return {
        "success": not bool(warning),
        "tables": rows,
        "limit": safe_limit,
        "warnings": [warning] if warning else [],
        "data_source": "mariadb",
    }


def mariadb_cluster_alerts() -> Dict[str, Any]:
    status, variables, warnings = _base_status()
    alerts = _build_alerts(status, variables)
    return {
        "success": True,
        "alerts": alerts,
        "alert_count": len(alerts),
        "warnings": warnings,
        "data_source": "mariadb",
    }


def mariadb_cluster_wsrep_status() -> Dict[str, Any]:
    status, status_warnings = _show_global("STATUS", prefix="wsrep_%")
    variables, variable_warnings = _show_global("VARIABLES", prefix="wsrep_%")
    return {
        "success": True,
        "wsrep_status": status,
        "wsrep_variables": variables,
        "warnings": status_warnings + variable_warnings,
        "data_source": "mariadb",
    }


def _build_alerts(status: Dict[str, Any], variables: Dict[str, Any]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    max_connections = _int_value(variables, "max_connections")
    threads_connected = _int_value(status, "Threads_connected")
    max_used_connections = _int_value(status, "Max_used_connections")
    connection_usage = _percent(threads_connected, max_connections)
    peak_usage = _percent(max_used_connections, max_connections)

    if str(variables.get("wsrep_on", "")).upper() == "ON":
        if str(status.get("wsrep_ready", "")).upper() != "ON":
            alerts.append({"severity": "critical", "code": "wsrep_not_ready", "message": "Galera wsrep_ready is not ON"})
        if str(status.get("wsrep_cluster_status", "")).lower() not in {"primary", ""}:
            alerts.append({"severity": "critical", "code": "wsrep_non_primary", "message": "Galera cluster status is not Primary"})
        if _int_value(status, "wsrep_cluster_size") <= 1:
            alerts.append({"severity": "warning", "code": "wsrep_single_node", "message": "Galera cluster size is 1 or unavailable"})

    if connection_usage is not None and connection_usage >= 90:
        alerts.append({"severity": "critical", "code": "connections_high", "message": "Current connection usage is above 90%", "value": connection_usage})
    elif connection_usage is not None and connection_usage >= 75:
        alerts.append({"severity": "warning", "code": "connections_elevated", "message": "Current connection usage is above 75%", "value": connection_usage})

    if peak_usage is not None and peak_usage >= 90:
        alerts.append({"severity": "warning", "code": "peak_connections_high", "message": "Peak connection usage has exceeded 90%", "value": peak_usage})

    if _int_value(status, "Aborted_connects") > 0:
        alerts.append({"severity": "warning", "code": "aborted_connects", "message": "Aborted connections detected", "value": _int_value(status, "Aborted_connects")})
    if _int_value(status, "Slow_queries") > 0:
        alerts.append({"severity": "info", "code": "slow_queries", "message": "Slow queries detected", "value": _int_value(status, "Slow_queries")})

    recv_queue = _float_value(status, "wsrep_local_recv_queue")
    send_queue = _float_value(status, "wsrep_local_send_queue")
    if recv_queue > 0:
        alerts.append({"severity": "warning", "code": "wsrep_recv_queue", "message": "Galera receive queue is non-zero", "value": recv_queue})
    if send_queue > 0:
        alerts.append({"severity": "warning", "code": "wsrep_send_queue", "message": "Galera send queue is non-zero", "value": send_queue})
    return alerts
