"""Read-only Barbican MariaDB query helpers."""

import json
import logging
from typing import Any, Dict, List, Optional

from .db import column_expr, get_mariadb_connection, str_time, table_columns

logger = logging.getLogger(__name__)

BARBICAN_DATABASE = "barbican"


def _get_barbican_connection():
    return get_mariadb_connection(BARBICAN_DATABASE)


def _json_value(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _normalize_pagination(limit: int = 50, offset: int = 0) -> tuple[int, int]:
    try:
        limit = int(limit)
    except Exception:
        limit = 50
    try:
        offset = int(offset)
    except Exception:
        offset = 0
    return max(0, min(limit, 200)), max(0, offset)


def _normalize_identifier(identifier: str) -> str:
    return str(identifier or "").strip().rstrip("/").split("/")[-1]


def _apply_limit_offset(sql: str, params: List[Any], limit: int, offset: int) -> tuple[str, List[Any]]:
    limit, offset = _normalize_pagination(limit, offset)
    if limit > 0:
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
    return sql, params


def _deleted_filter(alias: str, columns: set[str]) -> str:
    deleted_expr = column_expr(alias, columns, "deleted", default="NULL")
    if deleted_expr == "NULL":
        return ""
    return f"AND ({deleted_expr} = 0 OR {deleted_expr} = '0' OR {deleted_expr} IS NULL) "


def _count(cur, table_name: str, alias: str, where_sql: str, params: List[Any]) -> int:
    cur.execute(f"SELECT COUNT(*) AS count FROM {table_name} {alias} WHERE 1=1 {where_sql}", params)
    row = cur.fetchone() or {}
    return int(row.get("count") or 0)


def _select_project_expr(cur, alias: str, columns: set[str]) -> str:
    project_expr = column_expr(alias, columns, "project_id", "tenant_id", default="NULL")
    project_columns = table_columns(cur, "projects")
    if project_expr == "NULL" and "project_id" in columns and project_columns and "id" in project_columns:
        external_expr = column_expr("p", project_columns, "external_id", "project_id", "tenant_id", default="p.id")
        return external_expr
    return project_expr


def _project_join(cur, alias: str, columns: set[str]) -> str:
    project_columns = table_columns(cur, "projects")
    if "project_id" not in columns or not project_columns or "id" not in project_columns:
        return ""
    if "external_id" in project_columns:
        return f"LEFT JOIN projects p ON p.id = {alias}.project_id "
    return ""


def _find_secret(cur, query: str) -> Optional[Dict[str, Any]]:
    result = _query_secrets(cur, query=query, limit=1, offset=0, detailed=True)
    return result[0] if result else None


def _find_container(cur, query: str) -> Optional[Dict[str, Any]]:
    result = _query_containers(cur, query=query, limit=1, offset=0, detailed=True)
    return result[0] if result else None


def _find_order(cur, query: str) -> Optional[Dict[str, Any]]:
    result = _query_orders(cur, query=query, limit=1, offset=0, detailed=True)
    return result[0] if result else None


def _secret_content_types(cur, secret_ids: List[str]) -> Dict[str, Dict[str, str]]:
    columns = table_columns(cur, "secret_store_metadata")
    if not secret_ids or not {"secret_id", "key", "value"}.issubset(columns):
        return {secret_id: {} for secret_id in secret_ids}
    placeholders = ",".join(["%s"] * len(secret_ids))
    cur.execute(
        f"SELECT secret_id, `key`, value FROM secret_store_metadata WHERE secret_id IN ({placeholders})",
        secret_ids,
    )
    metadata = {secret_id: {} for secret_id in secret_ids}
    for row in cur.fetchall():
        metadata.setdefault(row.get("secret_id"), {})[str(row.get("key"))] = row.get("value")
    return metadata


def _container_secret_refs(cur, container_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    columns = table_columns(cur, "container_secret")
    if not container_ids or not {"container_id", "secret_id"}.issubset(columns):
        return {container_id: [] for container_id in container_ids}

    name_expr = column_expr("cs", columns, "name", default="NULL")
    placeholders = ",".join(["%s"] * len(container_ids))
    cur.execute(
        f"SELECT cs.container_id, cs.secret_id, {name_expr} AS name "
        f"FROM container_secret cs WHERE cs.container_id IN ({placeholders}) "
        "ORDER BY cs.container_id ASC, name ASC",
        container_ids,
    )
    refs = {container_id: [] for container_id in container_ids}
    for row in cur.fetchall():
        refs.setdefault(row.get("container_id"), []).append({
            "name": row.get("name") or "",
            "secret_id": row.get("secret_id"),
        })
    return refs


def _query_secrets(
    cur,
    query: str = "",
    name: str = "",
    secret_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
    detailed: bool = False,
) -> List[Dict[str, Any]]:
    columns = table_columns(cur, "secrets")
    if not columns:
        raise RuntimeError("MariaDB table 'secrets' is not available in barbican database")

    name_expr = column_expr("s", columns, "name", default="NULL")
    secret_type_expr = column_expr("s", columns, "secret_type", default="NULL")
    status_expr = column_expr("s", columns, "status", default="NULL")
    algorithm_expr = column_expr("s", columns, "algorithm", default="NULL")
    bit_length_expr = column_expr("s", columns, "bit_length", default="NULL")
    mode_expr = column_expr("s", columns, "mode", default="NULL")
    expiration_expr = column_expr("s", columns, "expiration", default="NULL")
    creator_expr = column_expr("s", columns, "creator_id", default="NULL")
    created_expr = column_expr("s", columns, "created_at", "created", default="NULL")
    updated_expr = column_expr("s", columns, "updated_at", "updated", default="NULL")
    project_expr = _select_project_expr(cur, "s", columns)
    project_join = _project_join(cur, "s", columns)
    order_expr = column_expr("s", columns, "created_at", "created", default="s.id")

    where_sql = _deleted_filter("s", columns)
    params: List[Any] = []
    if query:
        where_sql += f"AND (s.id = %s OR {name_expr} = %s) "
        params.extend([query, query])
    if name:
        where_sql += f"AND {name_expr} = %s "
        params.append(name)
    if secret_type:
        where_sql += f"AND {secret_type_expr} = %s "
        params.append(secret_type)
    if status:
        where_sql += f"AND LOWER({status_expr}) = %s "
        params.append(status.strip().lower())
    if project_id and project_expr != "NULL":
        where_sql += f"AND {project_expr} = %s "
        params.append(project_id)

    sql = (
        f"SELECT s.id, {name_expr} AS name, {secret_type_expr} AS secret_type, {status_expr} AS status, "
        f"{algorithm_expr} AS algorithm, {bit_length_expr} AS bit_length, {mode_expr} AS mode, "
        f"{expiration_expr} AS expiration, {creator_expr} AS creator_id, {project_expr} AS project_id, "
        f"{created_expr} AS created_at, {updated_expr} AS updated_at "
        f"FROM secrets s {project_join}WHERE 1=1 {where_sql}ORDER BY {order_expr} DESC"
    )
    sql, page_params = _apply_limit_offset(sql, list(params), limit, offset)
    cur.execute(sql, page_params)
    rows = cur.fetchall()
    content_types = _secret_content_types(cur, [row.get("id") for row in rows if row.get("id")])
    secrets = []
    for row in rows:
        item = {
            "id": row.get("id"),
            "name": row.get("name") or "",
            "secret_type": row.get("secret_type"),
            "content_types": content_types.get(row.get("id"), {}),
            "algorithm": row.get("algorithm"),
            "bit_length": row.get("bit_length"),
            "mode": row.get("mode"),
            "status": row.get("status"),
            "created_at": str_time(row.get("created_at")),
            "updated_at": str_time(row.get("updated_at")),
            "expiration": str_time(row.get("expiration")) if row.get("expiration") else None,
            "creator_id": row.get("creator_id"),
            "project_id": row.get("project_id"),
            "payload_omitted": True,
            "data_source": "mariadb",
        }
        if detailed:
            item["metadata"] = {}
        secrets.append(item)
    return secrets


def _query_containers(
    cur,
    query: str = "",
    name: str = "",
    container_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
    detailed: bool = False,
) -> List[Dict[str, Any]]:
    columns = table_columns(cur, "containers")
    if not columns:
        raise RuntimeError("MariaDB table 'containers' is not available in barbican database")

    name_expr = column_expr("c", columns, "name", default="NULL")
    type_expr = column_expr("c", columns, "type", default="NULL")
    status_expr = column_expr("c", columns, "status", default="NULL")
    creator_expr = column_expr("c", columns, "creator_id", default="NULL")
    created_expr = column_expr("c", columns, "created_at", "created", default="NULL")
    updated_expr = column_expr("c", columns, "updated_at", "updated", default="NULL")
    project_expr = _select_project_expr(cur, "c", columns)
    project_join = _project_join(cur, "c", columns)
    order_expr = column_expr("c", columns, "created_at", "created", default="c.id")

    where_sql = _deleted_filter("c", columns)
    params: List[Any] = []
    if query:
        where_sql += f"AND (c.id = %s OR {name_expr} = %s) "
        params.extend([query, query])
    if name:
        where_sql += f"AND {name_expr} = %s "
        params.append(name)
    if container_type:
        where_sql += f"AND {type_expr} = %s "
        params.append(container_type)
    if status:
        where_sql += f"AND LOWER({status_expr}) = %s "
        params.append(status.strip().lower())
    if project_id and project_expr != "NULL":
        where_sql += f"AND {project_expr} = %s "
        params.append(project_id)

    sql = (
        f"SELECT c.id, {name_expr} AS name, {type_expr} AS type, {status_expr} AS status, "
        f"{creator_expr} AS creator_id, {project_expr} AS project_id, "
        f"{created_expr} AS created_at, {updated_expr} AS updated_at "
        f"FROM containers c {project_join}WHERE 1=1 {where_sql}ORDER BY {order_expr} DESC"
    )
    sql, page_params = _apply_limit_offset(sql, list(params), limit, offset)
    cur.execute(sql, page_params)
    rows = cur.fetchall()
    secret_refs = _container_secret_refs(cur, [row.get("id") for row in rows if row.get("id")])
    containers = []
    for row in rows:
        item = {
            "id": row.get("id"),
            "name": row.get("name") or "",
            "type": row.get("type"),
            "status": row.get("status"),
            "created_at": str_time(row.get("created_at")),
            "updated_at": str_time(row.get("updated_at")),
            "creator_id": row.get("creator_id"),
            "project_id": row.get("project_id"),
            "secret_refs": secret_refs.get(row.get("id"), []),
            "payload_omitted": True,
            "data_source": "mariadb",
        }
        if detailed:
            item["metadata"] = {}
        containers.append(item)
    return containers


def _query_orders(
    cur,
    query: str = "",
    order_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
    detailed: bool = False,
) -> List[Dict[str, Any]]:
    columns = table_columns(cur, "orders")
    if not columns:
        raise RuntimeError("MariaDB table 'orders' is not available in barbican database")

    name_expr = column_expr("o", columns, "name", default="NULL")
    type_expr = column_expr("o", columns, "type", "order_type", default="NULL")
    status_expr = column_expr("o", columns, "status", default="NULL")
    secret_expr = column_expr("o", columns, "secret_id", default="NULL")
    container_expr = column_expr("o", columns, "container_id", default="NULL")
    creator_expr = column_expr("o", columns, "creator_id", default="NULL")
    created_expr = column_expr("o", columns, "created_at", "created", default="NULL")
    updated_expr = column_expr("o", columns, "updated_at", "updated", default="NULL")
    meta_expr = column_expr("o", columns, "meta", default="NULL")
    error_status_expr = column_expr("o", columns, "error_status_code", default="NULL")
    error_reason_expr = column_expr("o", columns, "error_reason", default="NULL")
    project_expr = _select_project_expr(cur, "o", columns)
    project_join = _project_join(cur, "o", columns)
    order_expr = column_expr("o", columns, "created_at", "created", default="o.id")

    where_sql = _deleted_filter("o", columns)
    params: List[Any] = []
    if query:
        where_sql += f"AND (o.id = %s OR {name_expr} = %s) "
        params.extend([query, query])
    if order_type:
        where_sql += f"AND {type_expr} = %s "
        params.append(order_type)
    if status:
        where_sql += f"AND LOWER({status_expr}) = %s "
        params.append(status.strip().lower())
    if project_id and project_expr != "NULL":
        where_sql += f"AND {project_expr} = %s "
        params.append(project_id)

    sql = (
        f"SELECT o.id, {name_expr} AS name, {type_expr} AS type, {status_expr} AS status, "
        f"{secret_expr} AS secret_id, {container_expr} AS container_id, {creator_expr} AS creator_id, "
        f"{project_expr} AS project_id, {meta_expr} AS meta, {error_status_expr} AS error_status_code, "
        f"{error_reason_expr} AS error_reason, {created_expr} AS created_at, {updated_expr} AS updated_at "
        f"FROM orders o {project_join}WHERE 1=1 {where_sql}ORDER BY {order_expr} DESC"
    )
    sql, page_params = _apply_limit_offset(sql, list(params), limit, offset)
    cur.execute(sql, page_params)
    rows = cur.fetchall()
    orders = []
    for row in rows:
        item = {
            "id": row.get("id"),
            "name": row.get("name") or "",
            "type": row.get("type"),
            "status": row.get("status"),
            "created_at": str_time(row.get("created_at")),
            "updated_at": str_time(row.get("updated_at")),
            "secret_id": row.get("secret_id"),
            "container_id": row.get("container_id"),
            "creator_id": row.get("creator_id"),
            "project_id": row.get("project_id"),
            "error_status_code": row.get("error_status_code"),
            "error_reason": row.get("error_reason"),
            "data_source": "mariadb",
        }
        if detailed:
            item["metadata"] = _json_value(row.get("meta"), {})
        orders.append(item)
    return orders


def get_barbican_secrets(
    name: str = "",
    secret_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List Barbican secret metadata from MariaDB without returning payloads."""
    try:
        conn = _get_barbican_connection()
        try:
            with conn.cursor() as cur:
                columns = table_columns(cur, "secrets")
                project_expr = _select_project_expr(cur, "s", columns) if columns else "NULL"
                where_sql = _deleted_filter("s", columns)
                params: List[Any] = []
                if name:
                    where_sql += f"AND {column_expr('s', columns, 'name', default='NULL')} = %s "
                    params.append(name)
                if secret_type:
                    where_sql += f"AND {column_expr('s', columns, 'secret_type', default='NULL')} = %s "
                    params.append(secret_type)
                if status:
                    where_sql += f"AND LOWER({column_expr('s', columns, 'status', default='NULL')}) = %s "
                    params.append(status.strip().lower())
                if project_id and project_expr != "NULL":
                    where_sql += f"AND {project_expr} = %s "
                    params.append(project_id)
                total = _count(cur, f"secrets s {_project_join(cur, 's', columns)}", "", where_sql, params)
                secrets = _query_secrets(cur, name=name, secret_type=secret_type, status=status, project_id=project_id, limit=limit, offset=offset)
        finally:
            conn.close()
        return {"success": True, "secrets": secrets, "count": len(secrets), "total_count": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error("Failed to list Barbican secrets: %s", e)
        return {"success": False, "message": str(e), "secrets": [], "count": 0, "total_count": 0}


def get_barbican_secret_details(secret_id_or_ref: str) -> Dict[str, Any]:
    """Get Barbican secret metadata from MariaDB without returning payloads."""
    try:
        query = _normalize_identifier(secret_id_or_ref)
        if not query:
            return {"success": False, "message": "secret_id_or_ref is required", "secret": None, "found": False}
        conn = _get_barbican_connection()
        try:
            with conn.cursor() as cur:
                secret = _find_secret(cur, query)
        finally:
            conn.close()
        return {"success": True, "secret": secret, "found": bool(secret)}
    except Exception as e:
        logger.error("Failed to get Barbican secret details: %s", e)
        return {"success": False, "message": str(e), "secret": None, "found": False}


def get_barbican_containers(
    name: str = "",
    container_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List Barbican container metadata from MariaDB without returning payloads."""
    try:
        conn = _get_barbican_connection()
        try:
            with conn.cursor() as cur:
                columns = table_columns(cur, "containers")
                project_expr = _select_project_expr(cur, "c", columns) if columns else "NULL"
                where_sql = _deleted_filter("c", columns)
                params: List[Any] = []
                if name:
                    where_sql += f"AND {column_expr('c', columns, 'name', default='NULL')} = %s "
                    params.append(name)
                if container_type:
                    where_sql += f"AND {column_expr('c', columns, 'type', default='NULL')} = %s "
                    params.append(container_type)
                if status:
                    where_sql += f"AND LOWER({column_expr('c', columns, 'status', default='NULL')}) = %s "
                    params.append(status.strip().lower())
                if project_id and project_expr != "NULL":
                    where_sql += f"AND {project_expr} = %s "
                    params.append(project_id)
                total = _count(cur, f"containers c {_project_join(cur, 'c', columns)}", "", where_sql, params)
                containers = _query_containers(cur, name=name, container_type=container_type, status=status, project_id=project_id, limit=limit, offset=offset)
        finally:
            conn.close()
        return {"success": True, "containers": containers, "count": len(containers), "total_count": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error("Failed to list Barbican containers: %s", e)
        return {"success": False, "message": str(e), "containers": [], "count": 0, "total_count": 0}


def get_barbican_container_details(container_id_or_ref: str) -> Dict[str, Any]:
    """Get Barbican container metadata from MariaDB without returning payloads."""
    try:
        query = _normalize_identifier(container_id_or_ref)
        if not query:
            return {"success": False, "message": "container_id_or_ref is required", "container": None, "found": False}
        conn = _get_barbican_connection()
        try:
            with conn.cursor() as cur:
                container = _find_container(cur, query)
        finally:
            conn.close()
        return {"success": True, "container": container, "found": bool(container)}
    except Exception as e:
        logger.error("Failed to get Barbican container details: %s", e)
        return {"success": False, "message": str(e), "container": None, "found": False}


def get_barbican_orders(
    order_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List Barbican orders from MariaDB."""
    try:
        conn = _get_barbican_connection()
        try:
            with conn.cursor() as cur:
                columns = table_columns(cur, "orders")
                project_expr = _select_project_expr(cur, "o", columns) if columns else "NULL"
                where_sql = _deleted_filter("o", columns)
                params: List[Any] = []
                if order_type:
                    where_sql += f"AND {column_expr('o', columns, 'type', 'order_type', default='NULL')} = %s "
                    params.append(order_type)
                if status:
                    where_sql += f"AND LOWER({column_expr('o', columns, 'status', default='NULL')}) = %s "
                    params.append(status.strip().lower())
                if project_id and project_expr != "NULL":
                    where_sql += f"AND {project_expr} = %s "
                    params.append(project_id)
                total = _count(cur, f"orders o {_project_join(cur, 'o', columns)}", "", where_sql, params)
                orders = _query_orders(cur, order_type=order_type, status=status, project_id=project_id, limit=limit, offset=offset)
        finally:
            conn.close()
        return {"success": True, "orders": orders, "count": len(orders), "total_count": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error("Failed to list Barbican orders: %s", e)
        return {"success": False, "message": str(e), "orders": [], "count": 0, "total_count": 0}


def get_barbican_order_details(order_id_or_ref: str) -> Dict[str, Any]:
    """Get Barbican order details from MariaDB."""
    try:
        query = _normalize_identifier(order_id_or_ref)
        if not query:
            return {"success": False, "message": "order_id_or_ref is required", "order": None, "found": False}
        conn = _get_barbican_connection()
        try:
            with conn.cursor() as cur:
                order = _find_order(cur, query)
        finally:
            conn.close()
        return {"success": True, "order": order, "found": bool(order)}
    except Exception as e:
        logger.error("Failed to get Barbican order details: %s", e)
        return {"success": False, "message": str(e), "order": None, "found": False}
