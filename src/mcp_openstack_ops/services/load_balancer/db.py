"""Octavia MariaDB query helpers."""

from typing import Any, Dict, List, Optional

from ..db import bool_value, column_expr, get_mariadb_connection, scope_project_id, str_time, table_columns, table_exists

OCTAVIA_DATABASE = "octavia"


def get_octavia_connection():
    return get_mariadb_connection(OCTAVIA_DATABASE)


def _rows(table_name: str, order_by: str = "created_at DESC") -> List[Dict[str, Any]]:
    conn = get_octavia_connection()
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, table_name)
            if not columns:
                return []
            order = order_by if order_by.split()[0] in columns else "id ASC"
            cur.execute(f"SELECT * FROM {table_name} ORDER BY {order}")
            return list(cur.fetchall())
    finally:
        conn.close()


def find_load_balancer(identifier: str) -> Optional[Dict[str, Any]]:
    if not identifier:
        return None
    conn = get_octavia_connection()
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, "load_balancer")
            if not columns:
                return None
            name_expr = column_expr("lb", columns, "name", default="''")
            cur.execute(
                f"SELECT * FROM load_balancer lb WHERE lb.id = %s OR {name_expr} = %s LIMIT 1",
                [identifier, identifier],
            )
            return cur.fetchone()
    finally:
        conn.close()


def list_load_balancers(project_id: str = "") -> List[Dict[str, Any]]:
    conn = get_octavia_connection()
    try:
        scope_project = scope_project_id(project_id)
        with conn.cursor() as cur:
            columns = table_columns(cur, "load_balancer")
            if not columns:
                raise RuntimeError("MariaDB table 'load_balancer' is not available")
            project_expr = column_expr("lb", columns, "project_id", default="NULL")
            provider_expr = column_expr("lb", columns, "provider", default="NULL")
            sql = (
                "SELECT lb.id, lb.name, lb.description, lb.vip_address, lb.vip_port_id, "
                "lb.vip_subnet_id, lb.vip_network_id, lb.provisioning_status, lb.operating_status, "
                f"lb.admin_state_up, {project_expr} AS project_id, {provider_expr} AS provider, "
                "lb.created_at, lb.updated_at FROM load_balancer lb WHERE 1=1 "
            )
            params: List[Any] = []
            if scope_project:
                sql += f"AND {project_expr} = %s "
                params.append(scope_project)
            sql += "ORDER BY lb.created_at DESC"
            cur.execute(sql, params)
            return [
                {
                    "id": row.get("id"),
                    "name": row.get("name") or "unnamed",
                    "description": row.get("description") or "",
                    "vip_address": row.get("vip_address"),
                    "vip_port_id": row.get("vip_port_id"),
                    "vip_subnet_id": row.get("vip_subnet_id"),
                    "vip_network_id": row.get("vip_network_id"),
                    "provisioning_status": row.get("provisioning_status") or "unknown",
                    "operating_status": row.get("operating_status") or "unknown",
                    "admin_state_up": bool_value(row.get("admin_state_up")),
                    "project_id": row.get("project_id"),
                    "provider": row.get("provider") or "unknown",
                    "created_at": str_time(row.get("created_at")),
                    "updated_at": str_time(row.get("updated_at")),
                    "data_source": "mariadb",
                }
                for row in cur.fetchall()
            ]
    finally:
        conn.close()


def list_listeners(loadbalancer_id: str = "") -> List[Dict[str, Any]]:
    conn = get_octavia_connection()
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, "listener")
            if not columns:
                return []
            lb_expr = column_expr("l", columns, "load_balancer_id", "loadbalancer_id", default="NULL")
            default_pool_expr = column_expr("l", columns, "default_pool_id", default="NULL")
            sql = (
                "SELECT l.id, l.name, l.description, l.protocol, l.protocol_port, l.admin_state_up, "
                f"{lb_expr} AS loadbalancer_id, {default_pool_expr} AS default_pool_id, "
                "l.created_at, l.updated_at FROM listener l WHERE 1=1 "
            )
            params: List[Any] = []
            if loadbalancer_id:
                sql += f"AND {lb_expr} = %s "
                params.append(loadbalancer_id)
            sql += "ORDER BY l.protocol_port ASC, l.name ASC"
            cur.execute(sql, params)
            return [
                {
                    "id": row.get("id"),
                    "name": row.get("name") or "",
                    "description": row.get("description") or "",
                    "protocol": row.get("protocol"),
                    "protocol_port": row.get("protocol_port"),
                    "admin_state_up": bool_value(row.get("admin_state_up")),
                    "loadbalancer_id": row.get("loadbalancer_id"),
                    "default_pool_id": row.get("default_pool_id"),
                    "created_at": str_time(row.get("created_at")),
                    "updated_at": str_time(row.get("updated_at")),
                    "data_source": "mariadb",
                }
                for row in cur.fetchall()
            ]
    finally:
        conn.close()


def list_pools(listener_id: str = "") -> List[Dict[str, Any]]:
    conn = get_octavia_connection()
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, "pool")
            if not columns:
                return []
            listener_expr = column_expr("p", columns, "listener_id", default="NULL")
            sql = (
                "SELECT p.id, p.name, p.description, p.protocol, p.lb_algorithm, p.admin_state_up, "
                f"{listener_expr} AS listener_id, p.provisioning_status, p.operating_status, p.created_at, p.updated_at "
                "FROM pool p WHERE 1=1 "
            )
            params: List[Any] = []
            if listener_id:
                sql += f"AND {listener_expr} = %s "
                params.append(listener_id)
            sql += "ORDER BY p.created_at DESC"
            cur.execute(sql, params)
            pools = []
            for row in cur.fetchall():
                pool = {
                    "id": row.get("id"),
                    "name": row.get("name") or "",
                    "description": row.get("description") or "",
                    "protocol": row.get("protocol"),
                    "lb_algorithm": row.get("lb_algorithm"),
                    "admin_state_up": bool_value(row.get("admin_state_up")),
                    "listener_id": row.get("listener_id"),
                    "provisioning_status": row.get("provisioning_status"),
                    "operating_status": row.get("operating_status"),
                    "created_at": str_time(row.get("created_at")),
                    "updated_at": str_time(row.get("updated_at")),
                    "data_source": "mariadb",
                }
                pools.append(pool)
            return pools
    finally:
        conn.close()


def list_members(pool_id: str) -> List[Dict[str, Any]]:
    conn = get_octavia_connection()
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, "member")
            if not columns:
                return []
            pool_expr = column_expr("m", columns, "pool_id", default="NULL")
            cur.execute(
                "SELECT m.id, m.name, m.address, m.protocol_port, m.weight, m.admin_state_up, "
                "m.operating_status, m.provisioning_status, m.created_at, m.updated_at "
                f"FROM member m WHERE {pool_expr} = %s ORDER BY m.address ASC, m.protocol_port ASC",
                [pool_id],
            )
            return [
                {
                    "id": row.get("id"),
                    "name": row.get("name") or "",
                    "address": row.get("address"),
                    "protocol_port": row.get("protocol_port"),
                    "weight": row.get("weight") or 1,
                    "admin_state_up": bool_value(row.get("admin_state_up")),
                    "operating_status": row.get("operating_status") or "unknown",
                    "provisioning_status": row.get("provisioning_status") or "unknown",
                    "created_at": str_time(row.get("created_at")),
                    "updated_at": str_time(row.get("updated_at")),
                    "data_source": "mariadb",
                }
                for row in cur.fetchall()
            ]
    finally:
        conn.close()


def list_table(table_name: str) -> List[Dict[str, Any]]:
    return _rows(table_name)


def table_available(table_name: str) -> bool:
    conn = get_octavia_connection()
    try:
        with conn.cursor() as cur:
            return table_exists(cur, table_name)
    finally:
        conn.close()
