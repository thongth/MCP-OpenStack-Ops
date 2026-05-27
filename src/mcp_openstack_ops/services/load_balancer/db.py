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
            select_sql, from_sql = _load_balancer_select(cur)
            cur.execute(f"{select_sql} {from_sql}WHERE lb.id = %s OR {name_expr} = %s LIMIT 1", [identifier, identifier])
            row = cur.fetchone()
            return _serialize_load_balancer(row) if row else None
    finally:
        conn.close()

def find_load_balancers_by_vip(vip_address: str) -> List[Dict[str, Any]]:
    if not vip_address:
        return []
    conn = get_octavia_connection()
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, "load_balancer")
            if not columns:
                return []
            select_sql, from_sql = _load_balancer_select(cur)
            vip_address_expr, _ = _vip_lookup_exprs(cur)
            cur.execute(f"{select_sql} {from_sql}WHERE {vip_address_expr} = %s ORDER BY lb.id ASC", [vip_address])
            return [_serialize_load_balancer(row) for row in cur.fetchall()]
    finally:
        conn.close()

def find_load_balancers_by_vip_port(vip_port_id: str) -> List[Dict[str, Any]]:
    if not vip_port_id:
        return []
    conn = get_octavia_connection()
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, "load_balancer")
            if not columns:
                return []
            select_sql, from_sql = _load_balancer_select(cur)
            _, vip_port_expr = _vip_lookup_exprs(cur)
            cur.execute(f"{select_sql} {from_sql}WHERE {vip_port_expr} = %s ORDER BY lb.id ASC", [vip_port_id])
            return [_serialize_load_balancer(row) for row in cur.fetchall()]
    finally:
        conn.close()

def _vip_lookup_exprs(cur) -> tuple[str, str]:
    columns = table_columns(cur, "load_balancer")
    vip_columns = table_columns(cur, "vip")
    use_vip_table = bool(vip_columns and "load_balancer_id" in vip_columns)
    vip_address_expr = column_expr("lb", columns, "vip_address", default="NULL")
    vip_port_expr = column_expr("lb", columns, "vip_port_id", default="NULL")
    if use_vip_table:
        if vip_address_expr == "NULL":
            vip_address_expr = column_expr("v", vip_columns, "ip_address", "vip_address", "address", default="NULL")
        if vip_port_expr == "NULL":
            vip_port_expr = column_expr("v", vip_columns, "port_id", "vip_port_id", default="NULL")
    return vip_address_expr, vip_port_expr


def _load_balancer_select(cur) -> tuple[str, str]:
    columns = table_columns(cur, "load_balancer")
    vip_columns = table_columns(cur, "vip")
    use_vip_table = bool(vip_columns and "load_balancer_id" in vip_columns)

    name_expr = column_expr("lb", columns, "name", default="NULL")
    description_expr = column_expr("lb", columns, "description", default="NULL")
    project_expr = column_expr("lb", columns, "project_id", default="NULL")
    provider_expr = column_expr("lb", columns, "provider", default="NULL")
    provisioning_expr = column_expr("lb", columns, "provisioning_status", default="NULL")
    operating_expr = column_expr("lb", columns, "operating_status", default="NULL")
    admin_state_expr = column_expr("lb", columns, "admin_state_up", "enabled", default="1")
    created_expr = column_expr("lb", columns, "created_at", default="NULL")
    updated_expr = column_expr("lb", columns, "updated_at", default="NULL")

    vip_address_expr = column_expr("lb", columns, "vip_address", default="NULL")
    vip_port_expr = column_expr("lb", columns, "vip_port_id", default="NULL")
    vip_subnet_expr = column_expr("lb", columns, "vip_subnet_id", default="NULL")
    vip_network_expr = column_expr("lb", columns, "vip_network_id", default="NULL")
    if use_vip_table:
        if vip_address_expr == "NULL":
            vip_address_expr = column_expr("v", vip_columns, "ip_address", "vip_address", "address", default="NULL")
        if vip_port_expr == "NULL":
            vip_port_expr = column_expr("v", vip_columns, "port_id", "vip_port_id", default="NULL")
        if vip_subnet_expr == "NULL":
            vip_subnet_expr = column_expr("v", vip_columns, "subnet_id", "vip_subnet_id", default="NULL")
        if vip_network_expr == "NULL":
            vip_network_expr = column_expr("v", vip_columns, "network_id", "vip_network_id", default="NULL")

    select_sql = (
        "SELECT lb.id, "
        f"{name_expr} AS name, {description_expr} AS description, "
        f"{vip_address_expr} AS vip_address, {vip_port_expr} AS vip_port_id, "
        f"{vip_subnet_expr} AS vip_subnet_id, {vip_network_expr} AS vip_network_id, "
        f"{provisioning_expr} AS provisioning_status, {operating_expr} AS operating_status, "
        f"{admin_state_expr} AS admin_state_up, {project_expr} AS project_id, {provider_expr} AS provider, "
        f"{created_expr} AS created_at, {updated_expr} AS updated_at"
    )
    from_sql = "FROM load_balancer lb "
    if use_vip_table:
        from_sql += "LEFT JOIN vip v ON v.load_balancer_id = lb.id "
    return select_sql, from_sql


def _serialize_load_balancer(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
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


def list_load_balancers(project_id: str = "") -> List[Dict[str, Any]]:
    conn = get_octavia_connection()
    try:
        scope_project = scope_project_id(project_id)
        with conn.cursor() as cur:
            columns = table_columns(cur, "load_balancer")
            if not columns:
                raise RuntimeError("MariaDB table 'load_balancer' is not available")
            project_expr = column_expr("lb", columns, "project_id", default="NULL")
            select_sql, from_sql = _load_balancer_select(cur)
            sql = f"{select_sql} {from_sql}WHERE 1=1 "
            params: List[Any] = []
            if scope_project:
                sql += f"AND {project_expr} = %s "
                params.append(scope_project)
            order_expr = column_expr("lb", columns, "created_at", default="lb.id")
            sql += f"ORDER BY {order_expr} DESC"
            cur.execute(sql, params)
            return [_serialize_load_balancer(row) for row in cur.fetchall()]
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
            name_expr = column_expr("l", columns, "name", default="NULL")
            description_expr = column_expr("l", columns, "description", default="NULL")
            protocol_expr = column_expr("l", columns, "protocol", default="NULL")
            protocol_port_expr = column_expr("l", columns, "protocol_port", default="NULL")
            admin_state_expr = column_expr("l", columns, "admin_state_up", "enabled", default="1")
            default_pool_expr = column_expr("l", columns, "default_pool_id", default="NULL")
            created_expr = column_expr("l", columns, "created_at", default="NULL")
            updated_expr = column_expr("l", columns, "updated_at", default="NULL")
            protocol_port_order = column_expr("l", columns, "protocol_port", default="l.id")
            name_order = column_expr("l", columns, "name", default="l.id")
            sql = (
                f"SELECT l.id, {name_expr} AS name, {description_expr} AS description, "
                f"{protocol_expr} AS protocol, {protocol_port_expr} AS protocol_port, "
                f"{admin_state_expr} AS admin_state_up, "
                f"{lb_expr} AS loadbalancer_id, {default_pool_expr} AS default_pool_id, "
                f"{created_expr} AS created_at, {updated_expr} AS updated_at FROM listener l WHERE 1=1 "
            )
            params: List[Any] = []
            if loadbalancer_id:
                sql += f"AND {lb_expr} = %s "
                params.append(loadbalancer_id)
            sql += f"ORDER BY {protocol_port_order} ASC, {name_order} ASC"
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
            name_expr = column_expr("p", columns, "name", default="NULL")
            description_expr = column_expr("p", columns, "description", default="NULL")
            protocol_expr = column_expr("p", columns, "protocol", default="NULL")
            lb_algorithm_expr = column_expr("p", columns, "lb_algorithm", default="NULL")
            admin_state_expr = column_expr("p", columns, "admin_state_up", "enabled", default="1")
            provisioning_expr = column_expr("p", columns, "provisioning_status", default="NULL")
            operating_expr = column_expr("p", columns, "operating_status", default="NULL")
            created_expr = column_expr("p", columns, "created_at", default="NULL")
            updated_expr = column_expr("p", columns, "updated_at", default="NULL")
            created_order = column_expr("p", columns, "created_at", default="p.id")
            sql = (
                f"SELECT p.id, {name_expr} AS name, {description_expr} AS description, "
                f"{protocol_expr} AS protocol, {lb_algorithm_expr} AS lb_algorithm, "
                f"{admin_state_expr} AS admin_state_up, {listener_expr} AS listener_id, "
                f"{provisioning_expr} AS provisioning_status, {operating_expr} AS operating_status, "
                f"{created_expr} AS created_at, {updated_expr} AS updated_at "
                "FROM pool p WHERE 1=1 "
            )
            params: List[Any] = []
            if listener_id:
                sql += f"AND {listener_expr} = %s "
                params.append(listener_id)
            sql += f"ORDER BY {created_order} DESC"
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
            name_expr = column_expr("m", columns, "name", default="NULL")
            address_expr = column_expr("m", columns, "address", "ip_address", "member_address", default="NULL")
            subnet_expr = column_expr("m", columns, "subnet_id", default="NULL")
            protocol_port_expr = column_expr("m", columns, "protocol_port", default="NULL")
            weight_expr = column_expr("m", columns, "weight", default="1")
            admin_state_expr = column_expr("m", columns, "admin_state_up", "enabled", default="1")
            operating_expr = column_expr("m", columns, "operating_status", default="NULL")
            provisioning_expr = column_expr("m", columns, "provisioning_status", default="NULL")
            created_expr = column_expr("m", columns, "created_at", default="NULL")
            updated_expr = column_expr("m", columns, "updated_at", default="NULL")
            address_order = column_expr("m", columns, "address", "ip_address", "member_address", default="m.id")
            port_order = column_expr("m", columns, "protocol_port", default="m.id")
            cur.execute(
                f"SELECT m.id, {name_expr} AS name, {address_expr} AS address, {subnet_expr} AS subnet_id, "
                f"{protocol_port_expr} AS protocol_port, {weight_expr} AS weight, "
                f"{admin_state_expr} AS admin_state_up, {operating_expr} AS operating_status, "
                f"{provisioning_expr} AS provisioning_status, {created_expr} AS created_at, {updated_expr} AS updated_at "
                f"FROM member m WHERE {pool_expr} = %s ORDER BY {address_order} ASC, {port_order} ASC",
                [pool_id],
            )
            return [
                {
                    "id": row.get("id"),
                    "name": row.get("name") or "",
                    "address": row.get("address"),
                    "subnet_id": row.get("subnet_id"),
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
