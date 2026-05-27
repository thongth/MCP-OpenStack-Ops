"""
OpenStack Network (Neutron) Service Functions

This module contains functions for managing networks, subnets, routers,
security groups, floating IPs, and other networking components.
"""

import logging
import ipaddress
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

try:
    import pymysql
except Exception:  # pragma: no cover - optional dependency at runtime
    pymysql = None

# Configure logging
logger = logging.getLogger(__name__)

TRUTHY_VALUES = {"1", "true", "yes", "on"}
NEUTRON_DATABASE = "neutron"


def _get_mariadb_connection():
    if pymysql is None:
        raise RuntimeError("PyMySQL is not installed")

    return pymysql.connect(
        host=os.getenv("MARIADB_HOST", "127.0.0.1"),
        port=int(os.getenv("MARIADB_PORT", "3306")),
        user=os.getenv("MARIADB_USER", ""),
        password=os.getenv("MARIADB_PASSWORD", ""),
        database=NEUTRON_DATABASE,
        charset=os.getenv("MARIADB_CHARSET", "utf8mb4"),
        connect_timeout=int(os.getenv("MARIADB_CONNECT_TIMEOUT", "10")),
        cursorclass=pymysql.cursors.DictCursor,
    )


def _table_columns(cur, table_name: str) -> set[str]:
    try:
        cur.execute(f"SHOW COLUMNS FROM `{table_name}`")
        return {row["Field"] for row in cur.fetchall()}
    except Exception:
        return set()


def _table_exists(cur, table_name: str) -> bool:
    return bool(_table_columns(cur, table_name))


def _column_expr(alias: str, columns: set[str], *names: str, default: str = "NULL") -> str:
    for name in names:
        if name in columns:
            return f"{alias}.{name}"
    return default


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in TRUTHY_VALUES


def _json_value(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _str_time(value: Any) -> str:
    return "unknown" if value in (None, "") else str(value)


def _scope_project_id(project_id: str = "") -> Optional[str]:
    if project_id:
        return project_id
    # MariaDB read tools default to backend-wide reads; pass project_id explicitly to filter.
    return None


def _range_size(start: Any, end: Any) -> int:
    try:
        return int(ipaddress.ip_address(str(end))) - int(ipaddress.ip_address(str(start))) + 1
    except Exception:
        return 0

def _get_network_group_counts(cur, group_expr: str, from_sql: str, where_sql: str, params: List[Any], label: str) -> List[Dict[str, Any]]:
    if group_expr == "NULL":
        return []
    cur.execute(
        "SELECT COALESCE(group_value, 'unknown') AS value, COUNT(*) AS count FROM ("
        f"SELECT {group_expr} AS group_value {from_sql}{where_sql}"
        ") grouped_resources GROUP BY value ORDER BY count DESC, value ASC",
        params,
    )
    return [{label: row.get("value"), "count": int(row.get("count") or 0)} for row in cur.fetchall()]

def get_network_summary(project_id: str = "") -> Dict[str, Any]:
    """
    Get Neutron network counts without returning full network records.
    """
    conn = _get_mariadb_connection()
    try:
        scope_project_id = _scope_project_id(project_id)
        with conn.cursor() as cur:
            network_columns = _table_columns(cur, "networks")
            external_columns = _table_columns(cur, "externalnetworks")
            if not network_columns:
                raise RuntimeError("MariaDB table 'networks' is not available")

            project_expr = _column_expr("n", network_columns, "project_id", "tenant_id")
            status_expr = _column_expr("n", network_columns, "status", default="'unknown'")
            admin_state_expr = _column_expr("n", network_columns, "admin_state_up", default="1")
            shared_expr = _column_expr("n", network_columns, "shared", default="0")
            external_expr = "CASE WHEN en.network_id IS NULL THEN 0 ELSE 1 END" if "network_id" in external_columns else "0"
            from_sql = "FROM networks n "
            if "network_id" in external_columns:
                from_sql += "LEFT JOIN externalnetworks en ON en.network_id = n.id "

            where = []
            params: List[Any] = []
            if scope_project_id:
                where.append(f"({project_expr} = %s OR {shared_expr} = 1 OR {external_expr} = 1)")
                params.append(scope_project_id)
            where_sql = " WHERE " + " AND ".join(where) if where else ""

            cur.execute(f"SELECT COUNT(*) AS total {from_sql}{where_sql}", params)
            total = int((cur.fetchone() or {}).get("total") or 0)
            by_status = _get_network_group_counts(cur, f"UPPER({status_expr})", from_sql, where_sql, params, "status")
            status_counts = {row["status"]: row["count"] for row in by_status}

            return {
                "resource": "networks",
                "total": total,
                "active": status_counts.get("ACTIVE", 0),
                "down": status_counts.get("DOWN", 0),
                "error": status_counts.get("ERROR", 0),
                "by_status": by_status,
                "by_project_id": _get_network_group_counts(cur, project_expr, from_sql, where_sql, params, "project_id"),
                "by_admin_state_up": _get_network_group_counts(cur, admin_state_expr, from_sql, where_sql, params, "admin_state_up"),
                "by_shared": _get_network_group_counts(cur, shared_expr, from_sql, where_sql, params, "shared"),
                "by_external": _get_network_group_counts(cur, external_expr, from_sql, where_sql, params, "external"),
                "scope": {
                    "project_id": scope_project_id,
                },
                "data_source": "mariadb",
            }
    finally:
        conn.close()


def get_network_agents(agent_type: str = "", host: str = "", alive_only: bool = False) -> List[Dict[str, Any]]:
    """
    Get Neutron network agents visible to current credentials.

    Args:
        agent_type: Optional filter by agent type (substring match)
        host: Optional filter by host (substring match)
        alive_only: If True, return alive agents only

    Returns:
        List of network agent dictionaries
    """
    try:
        conn = _get_mariadb_connection()
        try:
            normalized_type = agent_type.strip().lower()
            normalized_host = host.strip().lower()
            with conn.cursor() as cur:
                columns = _table_columns(cur, "agents")
                if not columns:
                    raise RuntimeError("MariaDB table 'agents' is not available")

                availability_zone_expr = _column_expr("a", columns, "availability_zone", default="NULL")
                configurations_expr = _column_expr("a", columns, "configurations", default="NULL")
                created_expr = _column_expr("a", columns, "created_at", default="NULL")
                started_expr = _column_expr("a", columns, "started_at", default="NULL")
                heartbeat_expr = _column_expr("a", columns, "heartbeat_timestamp", default="NULL")
                cur.execute(
                    "SELECT a.id, a.agent_type, a.binary, a.topic, a.host, a.admin_state_up, "
                    f"{availability_zone_expr} AS availability_zone, "
                    f"{configurations_expr} AS configurations, "
                    f"{created_expr} AS created_at, "
                    f"{started_expr} AS started_at, "
                    f"{heartbeat_expr} AS heartbeat_timestamp "
                    "FROM agents a ORDER BY a.host ASC, a.agent_type ASC"
                )
                agents: List[Dict[str, Any]] = []
                now = datetime.now(timezone.utc)
                for row in cur.fetchall():
                    current_type = row.get("agent_type") or ""
                    current_host = row.get("host") or ""
                    heartbeat = row.get("heartbeat_timestamp")
                    alive = _bool_value(row.get("admin_state_up"))
                    if heartbeat:
                        try:
                            hb = heartbeat
                            if getattr(hb, "tzinfo", None) is None:
                                hb = hb.replace(tzinfo=timezone.utc)
                            alive = alive and (now - hb).total_seconds() < 120
                        except Exception:
                            pass

                    if normalized_type and normalized_type not in current_type.lower():
                        continue
                    if normalized_host and normalized_host not in current_host.lower():
                        continue
                    if alive_only and not alive:
                        continue

                    config = _json_value(row.get("configurations"), {})
                    agents.append({
                        "id": row.get("id"),
                        "agent_type": current_type,
                        "binary": row.get("binary") or "N/A",
                        "host": current_host,
                        "alive": alive,
                        "admin_state_up": _bool_value(row.get("admin_state_up")),
                        "availability_zone": row.get("availability_zone") or config.get("availability_zone", "N/A"),
                        "description": "",
                        "topic": row.get("topic") or "",
                        "started_at": _str_time(row.get("started_at")),
                        "heartbeat_timestamp": _str_time(row.get("heartbeat_timestamp")),
                        "created_at": _str_time(row.get("created_at")),
                        "updated_at": "unknown",
                        "data_source": "mariadb",
                    })
                return agents
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get network agents: {e}")
        return [{"error": str(e)}]


def get_network_details(
    network_name: str = "all",
    project_id: str = "",
    status: str = "",
    name_contains: str = "",
    limit: int = 0,
    offset: int = 0,
    include_subnets: bool = True,
) -> List[Dict[str, Any]]:
    """
    Get detailed information about networks.
    
    Args:
        network_name: Name of specific network or "all" for all networks
    
    Returns:
        List of network dictionaries with detailed information for current project
    """
    try:
        conn = _get_mariadb_connection()
        try:
            scope_project_id = _scope_project_id(project_id)
            status_filter = status.strip().lower() if status else ""
            target_name = network_name.strip().lower()
            name_filter = name_contains.strip().lower()
            safe_limit = max(int(limit or 0), 0)
            safe_offset = max(int(offset or 0), 0)

            with conn.cursor() as cur:
                network_columns = _table_columns(cur, "networks")
                subnet_columns = _table_columns(cur, "subnets")
                external_columns = _table_columns(cur, "externalnetworks")
                segment_columns = _table_columns(cur, "networksegments")
                standard_attr_columns = _table_columns(cur, "standardattributes")
                if not network_columns:
                    raise RuntimeError("MariaDB table 'networks' is not available")

                project_expr = _column_expr("n", network_columns, "project_id", "tenant_id")
                tenant_expr = _column_expr("n", network_columns, "tenant_id", "project_id")
                status_expr = _column_expr("n", network_columns, "status", default="'unknown'")
                admin_state_expr = _column_expr("n", network_columns, "admin_state_up", default="1")
                mtu_expr = _column_expr("n", network_columns, "mtu", default="1500")
                created_expr = "sa.created_at" if {"id", "created_at"}.issubset(standard_attr_columns) and "standard_attr_id" in network_columns else "NULL"
                updated_expr = "sa.updated_at" if {"id", "updated_at"}.issubset(standard_attr_columns) and "standard_attr_id" in network_columns else "NULL"
                shared_expr = _column_expr("n", network_columns, "shared", default="0")
                external_expr = "CASE WHEN en.network_id IS NULL THEN 0 ELSE 1 END" if "network_id" in external_columns else "0"
                segment_type_expr = _column_expr("ns", segment_columns, "network_type", default="NULL")
                segment_phys_expr = _column_expr("ns", segment_columns, "physical_network", default="NULL")
                segment_id_expr = _column_expr("ns", segment_columns, "segmentation_id", default="NULL")

                sql = (
                    "SELECT n.id, n.name, "
                    f"{status_expr} AS status, {admin_state_expr} AS admin_state_up, {shared_expr} AS shared, {mtu_expr} AS mtu, "
                    f"{project_expr} AS project_id, {tenant_expr} AS tenant_id, "
                    f"{created_expr} AS created_at, {updated_expr} AS updated_at, "
                    f"{external_expr} AS external, "
                    f"{segment_type_expr} AS provider_network_type, "
                    f"{segment_phys_expr} AS provider_physical_network, "
                    f"{segment_id_expr} AS provider_segmentation_id "
                    "FROM networks n "
                )
                if "network_id" in external_columns:
                    sql += "LEFT JOIN externalnetworks en ON en.network_id = n.id "
                if segment_columns:
                    sql += "LEFT JOIN networksegments ns ON ns.network_id = n.id "
                if created_expr.startswith("sa.") or updated_expr.startswith("sa."):
                    sql += "LEFT JOIN standardattributes sa ON sa.id = n.standard_attr_id "
                sql += "WHERE 1=1 "

                params: List[Any] = []
                if target_name != "all":
                    sql += "AND (LOWER(n.id) = %s OR LOWER(n.name) = %s) "
                    params.extend([target_name, target_name])
                if name_filter:
                    sql += "AND LOWER(n.name) LIKE %s "
                    params.append(f"%{name_filter}%")
                if status_filter:
                    sql += f"AND LOWER({status_expr}) = %s "
                    params.append(status_filter)
                if scope_project_id:
                    sql += f"AND ({project_expr} = %s OR {shared_expr} = 1 OR {external_expr} = 1) "
                    params.append(scope_project_id)
                sql += "ORDER BY n.name ASC"
                if safe_limit:
                    sql += " LIMIT %s OFFSET %s"
                    params.extend([safe_limit, safe_offset])
                cur.execute(sql, params)
                rows = cur.fetchall()

                network_ids = [row["id"] for row in rows if row.get("id")]
                subnets_by_network: Dict[str, List[Dict[str, Any]]] = {}
                if include_subnets and network_ids and subnet_columns:
                    placeholders = ",".join(["%s"] * len(network_ids))
                    subnet_project_expr = _column_expr("", subnet_columns, "project_id", "tenant_id").lstrip(".")
                    cur.execute(
                        "SELECT id, network_id, name, cidr, ip_version, gateway_ip, enable_dhcp, "
                        f"{subnet_project_expr} AS project_id FROM subnets WHERE network_id IN ({placeholders})",
                        network_ids,
                    )
                    subnet_rows = cur.fetchall()
                    subnet_ids = [row["id"] for row in subnet_rows if row.get("id")]
                    dns_by_subnet: Dict[str, List[str]] = {}
                    pools_by_subnet: Dict[str, List[Dict[str, Any]]] = {}
                    if subnet_ids:
                        subnet_placeholders = ",".join(["%s"] * len(subnet_ids))
                        if {"subnet_id", "address"}.issubset(_table_columns(cur, "dnsnameservers")):
                            cur.execute(
                                f"SELECT subnet_id, address FROM dnsnameservers WHERE subnet_id IN ({subnet_placeholders})",
                                subnet_ids,
                            )
                            for dns_row in cur.fetchall():
                                dns_by_subnet.setdefault(dns_row["subnet_id"], []).append(dns_row["address"])
                        if {"subnet_id", "first_ip", "last_ip"}.issubset(_table_columns(cur, "ipallocationpools")):
                            cur.execute(
                                f"SELECT subnet_id, first_ip, last_ip FROM ipallocationpools WHERE subnet_id IN ({subnet_placeholders})",
                                subnet_ids,
                            )
                            for pool_row in cur.fetchall():
                                pools_by_subnet.setdefault(pool_row["subnet_id"], []).append({
                                    "start": pool_row.get("first_ip"),
                                    "end": pool_row.get("last_ip"),
                                })
                    for subnet in subnet_rows:
                        if scope_project_id and subnet.get("project_id") != scope_project_id:
                            continue
                        subnets_by_network.setdefault(subnet["network_id"], []).append({
                            "id": subnet.get("id"),
                            "name": subnet.get("name") or "unnamed",
                            "cidr": subnet.get("cidr") or "unknown",
                            "ip_version": subnet.get("ip_version") or 4,
                            "gateway_ip": subnet.get("gateway_ip"),
                            "enable_dhcp": _bool_value(subnet.get("enable_dhcp")),
                            "dns_nameservers": dns_by_subnet.get(subnet.get("id"), []),
                            "allocation_pools": pools_by_subnet.get(subnet.get("id"), []),
                        })

                networks = []
                seen_ids = set()
                for row in rows:
                    if row.get("id") in seen_ids:
                        continue
                    seen_ids.add(row.get("id"))
                    subnets = subnets_by_network.get(row.get("id"), [])
                    networks.append({
                        "id": row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "status": row.get("status") or "unknown",
                        "admin_state_up": _bool_value(row.get("admin_state_up")),
                        "shared": _bool_value(row.get("shared")),
                        "external": _bool_value(row.get("external")),
                        "provider_network_type": row.get("provider_network_type"),
                        "provider_physical_network": row.get("provider_physical_network"),
                        "provider_segmentation_id": row.get("provider_segmentation_id"),
                        "mtu": row.get("mtu") or 1500,
                        "tenant_id": row.get("tenant_id"),
                        "project_id": row.get("project_id"),
                        "created_at": _str_time(row.get("created_at")),
                        "updated_at": _str_time(row.get("updated_at")),
                        "subnets": subnets,
                        "subnet_count": len(subnets),
                        "data_source": "mariadb",
                    })
                return networks
        finally:
            conn.close()
        
    except Exception as e:
        logger.error(f"Failed to get network details: {e}")
        return [
            {
                'id': 'net-1', 'name': 'demo-network', 'status': 'ACTIVE',
                'admin_state_up': True, 'shared': False, 'external': False,
                'subnets': [], 'error': str(e)
            }
        ]


def get_security_groups(
    project_id: str = "",
) -> List[Dict[str, Any]]:
    """
    Get list of security groups with rules.
    
    Returns:
        List of security group dictionaries
    """
    try:
        conn = _get_mariadb_connection()
        try:
            scope_project_id = _scope_project_id(project_id)
            with conn.cursor() as cur:
                sg_columns = _table_columns(cur, "securitygroups")
                rule_columns = _table_columns(cur, "securitygrouprules")
                standard_attr_columns = _table_columns(cur, "standardattributes")
                if not sg_columns:
                    raise RuntimeError("MariaDB table 'securitygroups' is not available")

                project_expr = _column_expr("sg", sg_columns, "project_id", "tenant_id")
                tenant_expr = _column_expr("sg", sg_columns, "tenant_id", "project_id")
                created_expr = "sa.created_at" if {"id", "created_at"}.issubset(standard_attr_columns) and "standard_attr_id" in sg_columns else "NULL"
                updated_expr = "sa.updated_at" if {"id", "updated_at"}.issubset(standard_attr_columns) and "standard_attr_id" in sg_columns else "NULL"
                description_expr = _column_expr("sg", sg_columns, "description", default="''")
                sql = (
                    "SELECT sg.id, sg.name, "
                    f"{description_expr} AS description, "
                    f"{project_expr} AS project_id, {tenant_expr} AS tenant_id, "
                    f"{created_expr} AS created_at, {updated_expr} AS updated_at "
                    "FROM securitygroups sg "
                )
                if created_expr.startswith("sa.") or updated_expr.startswith("sa."):
                    sql += "LEFT JOIN standardattributes sa ON sa.id = sg.standard_attr_id "
                params: List[Any] = []
                sql += "WHERE 1=1 "
                if scope_project_id:
                    sql += f"AND {project_expr} = %s "
                    params.append(scope_project_id)
                sql += "ORDER BY sg.name ASC"
                cur.execute(sql, params)
                groups = cur.fetchall()

                rules_by_group: Dict[str, List[Dict[str, Any]]] = {}
                group_ids = [row["id"] for row in groups if row.get("id")]
                if group_ids and rule_columns:
                    placeholders = ",".join(["%s"] * len(group_ids))
                    cur.execute(
                        "SELECT id, security_group_id, direction, protocol, port_range_min, "
                        "port_range_max, remote_ip_prefix, remote_group_id, ethertype "
                        f"FROM securitygrouprules WHERE security_group_id IN ({placeholders})",
                        group_ids,
                    )
                    for rule in cur.fetchall():
                        rules_by_group.setdefault(rule["security_group_id"], []).append({
                            "id": rule.get("id") or "unknown",
                            "direction": rule.get("direction") or "unknown",
                            "protocol": rule.get("protocol") or "any",
                            "port_range_min": rule.get("port_range_min"),
                            "port_range_max": rule.get("port_range_max"),
                            "remote_ip_prefix": rule.get("remote_ip_prefix"),
                            "remote_group_id": rule.get("remote_group_id"),
                            "ethertype": rule.get("ethertype") or "IPv4",
                        })

                security_groups = []
                for group in groups:
                    rules = rules_by_group.get(group.get("id"), [])
                    security_groups.append({
                        "id": group.get("id"),
                        "name": group.get("name") or "unnamed",
                        "description": group.get("description") or "",
                        "tenant_id": group.get("tenant_id"),
                        "project_id": group.get("project_id"),
                        "created_at": _str_time(group.get("created_at")),
                        "updated_at": _str_time(group.get("updated_at")),
                        "rules": rules,
                        "rule_count": len(rules),
                        "data_source": "mariadb",
                    })
                return security_groups
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get security groups: {e}")
        return [
            {
                'id': 'default-sg', 'name': 'default', 'description': 'Default security group',
                'rules': [{'direction': 'ingress', 'protocol': 'tcp', 'port_range_min': 22, 'port_range_max': 22}],
                'error': str(e)
            }
        ]


def get_security_groups_summary(project_id: str = "") -> Dict[str, Any]:
    """
    Get security group and rule counts without returning full rule payloads.
    """
    conn = _get_mariadb_connection()
    try:
        scope_project_id = _scope_project_id(project_id)
        with conn.cursor() as cur:
            sg_columns = _table_columns(cur, "securitygroups")
            rule_columns = _table_columns(cur, "securitygrouprules")
            if not sg_columns:
                raise RuntimeError("MariaDB table 'securitygroups' is not available")

            project_expr = _column_expr("sg", sg_columns, "project_id", "tenant_id")
            from_sql = "FROM securitygroups sg "
            where = []
            params: List[Any] = []
            if scope_project_id:
                where.append(f"{project_expr} = %s")
                params.append(scope_project_id)
            where_sql = " WHERE " + " AND ".join(where) if where else ""

            cur.execute(f"SELECT COUNT(*) AS total {from_sql}{where_sql}", params)
            total = int((cur.fetchone() or {}).get("total") or 0)
            cur.execute(
                f"SELECT COUNT(*) AS default_count {from_sql}{where_sql}{' AND' if where_sql else ' WHERE'} sg.name = %s",
                params + ["default"],
            )
            default_count = int((cur.fetchone() or {}).get("default_count") or 0)

            total_rules = 0
            by_rule_direction: List[Dict[str, Any]] = []
            by_rule_protocol: List[Dict[str, Any]] = []
            if rule_columns:
                rule_from_sql = "FROM securitygrouprules sgr INNER JOIN securitygroups sg ON sg.id = sgr.security_group_id "
                cur.execute(f"SELECT COUNT(*) AS total_rules {rule_from_sql}{where_sql}", params)
                total_rules = int((cur.fetchone() or {}).get("total_rules") or 0)
                by_rule_direction = _get_network_group_counts(cur, "sgr.direction", rule_from_sql, where_sql, params, "direction")
                by_rule_protocol = _get_network_group_counts(cur, "sgr.protocol", rule_from_sql, where_sql, params, "protocol")

            return {
                "resource": "security_groups",
                "total": total,
                "default_groups": default_count,
                "total_rules": total_rules,
                "by_project_id": _get_network_group_counts(cur, project_expr, from_sql, where_sql, params, "project_id"),
                "by_rule_direction": by_rule_direction,
                "by_rule_protocol": by_rule_protocol,
                "scope": {
                    "project_id": scope_project_id,
                },
                "data_source": "mariadb",
            }
    finally:
        conn.close()

def get_floating_ips(
    project_id: str = "",
    status: str = "",
) -> List[Dict[str, Any]]:
    """
    Get list of floating IPs.
    
    Returns:
        List of floating IP dictionaries for current project
    """
    try:
        conn = _get_mariadb_connection()
        try:
            scope_project_id = _scope_project_id(project_id)
            status_filter = status.strip().lower() if status else ""
            with conn.cursor() as cur:
                columns = _table_columns(cur, "floatingips")
                standard_attr_columns = _table_columns(cur, "standardattributes")
                if not columns:
                    raise RuntimeError("MariaDB table 'floatingips' is not available")

                project_expr = _column_expr("f", columns, "project_id", "tenant_id")
                tenant_expr = _column_expr("f", columns, "tenant_id", "project_id")
                status_expr = _column_expr("f", columns, "status", default="'unknown'")
                created_expr = "sa.created_at" if {"id", "created_at"}.issubset(standard_attr_columns) and "standard_attr_id" in columns else "NULL"
                updated_expr = "sa.updated_at" if {"id", "updated_at"}.issubset(standard_attr_columns) and "standard_attr_id" in columns else "NULL"
                description_expr = _column_expr("f", columns, "description", default="''")
                sql = (
                    "SELECT f.id, f.floating_ip_address, f.fixed_ip_address, "
                    f"{_column_expr('f', columns, 'fixed_port_id', 'port_id')} AS port_id, "
                    f"{_column_expr('f', columns, 'floating_port_id')} AS floating_port_id, "
                    f"{_column_expr('f', columns, 'router_id')} AS router_id, "
                    f"{status_expr} AS status, {tenant_expr} AS tenant_id, {project_expr} AS project_id, "
                    f"{_column_expr('f', columns, 'floating_network_id')} AS floating_network_id, "
                    f"{created_expr} AS created_at, {updated_expr} AS updated_at, "
                    f"{description_expr} AS description "
                    "FROM floatingips f "
                )
                if created_expr.startswith("sa.") or updated_expr.startswith("sa."):
                    sql += "LEFT JOIN standardattributes sa ON sa.id = f.standard_attr_id "
                sql += "WHERE 1=1 "
                params: List[Any] = []
                if scope_project_id:
                    sql += f"AND {project_expr} = %s "
                    params.append(scope_project_id)
                if status_filter:
                    sql += f"AND LOWER({status_expr}) = %s "
                    params.append(status_filter)
                sql += "ORDER BY f.floating_ip_address ASC"
                cur.execute(sql, params)

                floating_ips = []
                for row in cur.fetchall():
                    floating_ips.append({
                        "id": row.get("id"),
                        "floating_ip_address": row.get("floating_ip_address") or "unknown",
                        "fixed_ip_address": row.get("fixed_ip_address"),
                        "port_id": row.get("port_id"),
                        "floating_port_id": row.get("floating_port_id"),
                        "router_id": row.get("router_id"),
                        "status": row.get("status") or "unknown",
                        "tenant_id": row.get("tenant_id"),
                        "project_id": row.get("project_id"),
                        "floating_network_id": row.get("floating_network_id"),
                        "created_at": _str_time(row.get("created_at")),
                        "updated_at": _str_time(row.get("updated_at")),
                        "description": row.get("description") or "",
                        "data_source": "mariadb",
                    })
                return floating_ips
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get floating IPs: {e}")
        return [
            {
                'id': 'fip-1', 'floating_ip_address': '192.168.1.100',
                'fixed_ip_address': None, 'status': 'DOWN', 'error': str(e)
            }
        ]


def get_floating_ips_summary(project_id: str = "") -> Dict[str, Any]:
    """
    Get floating IP counts without returning full floating IP records.
    """
    conn = _get_mariadb_connection()
    try:
        scope_project_id = _scope_project_id(project_id)
        with conn.cursor() as cur:
            columns = _table_columns(cur, "floatingips")
            if not columns:
                raise RuntimeError("MariaDB table 'floatingips' is not available")

            project_expr = _column_expr("f", columns, "project_id", "tenant_id")
            status_expr = _column_expr("f", columns, "status", default="'unknown'")
            port_expr = _column_expr("f", columns, "fixed_port_id", "port_id")
            floating_network_expr = _column_expr("f", columns, "floating_network_id")
            router_expr = _column_expr("f", columns, "router_id")
            bound_expr = f"CASE WHEN {port_expr} IS NULL OR {port_expr} = '' THEN 0 ELSE 1 END" if port_expr != "NULL" else "0"
            router_bound_expr = f"CASE WHEN {router_expr} IS NULL OR {router_expr} = '' THEN 0 ELSE 1 END" if router_expr != "NULL" else "0"
            from_sql = "FROM floatingips f "
            where = []
            params: List[Any] = []
            if scope_project_id:
                where.append(f"{project_expr} = %s")
                params.append(scope_project_id)
            where_sql = " WHERE " + " AND ".join(where) if where else ""

            cur.execute(f"SELECT COUNT(*) AS total {from_sql}{where_sql}", params)
            total = int((cur.fetchone() or {}).get("total") or 0)
            by_status = _get_network_group_counts(cur, f"UPPER({status_expr})", from_sql, where_sql, params, "status")
            status_counts = {row["status"]: row["count"] for row in by_status}

            return {
                "resource": "floating_ips",
                "total": total,
                "active": status_counts.get("ACTIVE", 0),
                "down": status_counts.get("DOWN", 0),
                "error": status_counts.get("ERROR", 0),
                "by_status": by_status,
                "by_project_id": _get_network_group_counts(cur, project_expr, from_sql, where_sql, params, "project_id"),
                "by_floating_network_id": _get_network_group_counts(cur, floating_network_expr, from_sql, where_sql, params, "floating_network_id"),
                "by_bound_port": _get_network_group_counts(cur, bound_expr, from_sql, where_sql, params, "bound_port"),
                "by_router_bound": _get_network_group_counts(cur, router_bound_expr, from_sql, where_sql, params, "router_bound"),
                "scope": {
                    "project_id": scope_project_id,
                },
                "data_source": "mariadb",
            }
    finally:
        conn.close()

def get_floating_ip_pools() -> List[Dict[str, Any]]:
    """
    Get list of floating IP pools (external networks).
    
    Returns:
        List of floating IP pool dictionaries
    """
    try:
        conn = _get_mariadb_connection()
        try:
            with conn.cursor() as cur:
                network_columns = _table_columns(cur, "networks")
                external_columns = _table_columns(cur, "externalnetworks")
                subnet_columns = _table_columns(cur, "subnets")
                pool_columns = _table_columns(cur, "ipallocationpools")
                if not network_columns:
                    raise RuntimeError("MariaDB table 'networks' is not available")
                if "network_id" not in external_columns:
                    return []

                cur.execute(
                    "SELECT n.id, n.name, n.admin_state_up "
                    "FROM networks n INNER JOIN externalnetworks en ON en.network_id = n.id "
                    "ORDER BY n.name ASC"
                )
                networks = cur.fetchall()
                network_ids = [row["id"] for row in networks if row.get("id")]
                total_by_network: Dict[str, int] = {network_id: 0 for network_id in network_ids}
                used_by_network: Dict[str, int] = {network_id: 0 for network_id in network_ids}

                if network_ids and subnet_columns and pool_columns:
                    placeholders = ",".join(["%s"] * len(network_ids))
                    cur.execute(
                        "SELECT s.network_id, p.first_ip, p.last_ip "
                        "FROM subnets s INNER JOIN ipallocationpools p ON p.subnet_id = s.id "
                        f"WHERE s.network_id IN ({placeholders})",
                        network_ids,
                    )
                    for row in cur.fetchall():
                        total_by_network[row["network_id"]] = total_by_network.get(row["network_id"], 0) + _range_size(row.get("first_ip"), row.get("last_ip"))

                if network_ids and _table_exists(cur, "floatingips"):
                    placeholders = ",".join(["%s"] * len(network_ids))
                    cur.execute(
                        f"SELECT floating_network_id, COUNT(*) AS used_count FROM floatingips WHERE floating_network_id IN ({placeholders}) GROUP BY floating_network_id",
                        network_ids,
                    )
                    for row in cur.fetchall():
                        used_by_network[row["floating_network_id"]] = int(row.get("used_count") or 0)

                pools = []
                for network in networks:
                    total_ips = total_by_network.get(network.get("id"), 0)
                    used_ips = used_by_network.get(network.get("id"), 0)
                    pools.append({
                        "id": network.get("id"),
                        "name": network.get("name") or "unnamed",
                        "network_id": network.get("id"),
                        "total_ips": total_ips,
                        "used_ips": used_ips,
                        "available_ips": max(total_ips - used_ips, 0),
                        "admin_state_up": _bool_value(network.get("admin_state_up")),
                        "data_source": "mariadb",
                    })
                return pools
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get floating IP pools: {e}")
        return [{
            'id': 'pool-error',
            'name': 'Error retrieving pools',
            'error': str(e)
        }]


def get_routers(
    project_id: str = "",
    status: str = "",
) -> List[Dict[str, Any]]:
    """
    Get list of routers with detailed information.
    
    Returns:
        List of router dictionaries for current project
    """
    try:
        conn = _get_mariadb_connection()
        try:
            scope_project_id = _scope_project_id(project_id)
            status_filter = status.strip().lower() if status else ""
            with conn.cursor() as cur:
                router_columns = _table_columns(cur, "routers")
                port_columns = _table_columns(cur, "ports")
                standard_attr_columns = _table_columns(cur, "standardattributes")
                if not router_columns:
                    raise RuntimeError("MariaDB table 'routers' is not available")

                project_expr = _column_expr("r", router_columns, "project_id", "tenant_id")
                tenant_expr = _column_expr("r", router_columns, "tenant_id", "project_id")
                status_expr = _column_expr("r", router_columns, "status", default="'unknown'")
                created_expr = "sa.created_at" if {"id", "created_at"}.issubset(standard_attr_columns) and "standard_attr_id" in router_columns else "NULL"
                updated_expr = "sa.updated_at" if {"id", "updated_at"}.issubset(standard_attr_columns) and "standard_attr_id" in router_columns else "NULL"
                description_expr = _column_expr("r", router_columns, "description", default="''")
                sql = (
                    "SELECT r.id, r.name, "
                    f"{status_expr} AS status, r.admin_state_up, {tenant_expr} AS tenant_id, {project_expr} AS project_id, "
                    f"{created_expr} AS created_at, {updated_expr} AS updated_at, "
                    f"{description_expr} AS description, "
                    f"{_column_expr('r', router_columns, 'ha', default='0')} AS ha, "
                    f"{_column_expr('r', router_columns, 'distributed', default='0')} AS distributed, "
                    f"{_column_expr('r', router_columns, 'gw_port_id')} AS gw_port_id "
                    "FROM routers r "
                )
                if created_expr.startswith("sa.") or updated_expr.startswith("sa."):
                    sql += "LEFT JOIN standardattributes sa ON sa.id = r.standard_attr_id "
                sql += "WHERE 1=1 "
                params: List[Any] = []
                if scope_project_id:
                    sql += f"AND {project_expr} = %s "
                    params.append(scope_project_id)
                if status_filter:
                    sql += f"AND LOWER({status_expr}) = %s "
                    params.append(status_filter)
                sql += "ORDER BY r.name ASC"
                cur.execute(sql, params)
                router_rows = cur.fetchall()

                router_ids = [row["id"] for row in router_rows if row.get("id")]
                interfaces_by_router: Dict[str, List[Dict[str, Any]]] = {}
                gateway_by_router: Dict[str, Dict[str, Any]] = {}
                if router_ids and port_columns:
                    placeholders = ",".join(["%s"] * len(router_ids))
                    cur.execute(
                        "SELECT id, network_id, device_id, device_owner FROM ports "
                        f"WHERE device_id IN ({placeholders}) AND device_owner LIKE 'network:router%%'",
                        router_ids,
                    )
                    ports = cur.fetchall()
                    port_ids = [row["id"] for row in ports if row.get("id")]
                    fixed_by_port: Dict[str, List[Dict[str, Any]]] = {}
                    if port_ids and _table_exists(cur, "ipallocations"):
                        port_placeholders = ",".join(["%s"] * len(port_ids))
                        cur.execute(
                            f"SELECT port_id, subnet_id, ip_address FROM ipallocations WHERE port_id IN ({port_placeholders})",
                            port_ids,
                        )
                        for ip_row in cur.fetchall():
                            fixed_by_port.setdefault(ip_row["port_id"], []).append({
                                "subnet_id": ip_row.get("subnet_id"),
                                "ip_address": ip_row.get("ip_address"),
                            })
                    for port in ports:
                        fixed_ips = fixed_by_port.get(port.get("id"), [])
                        if str(port.get("device_owner") or "").startswith("network:router_interface"):
                            first_ip = fixed_ips[0] if fixed_ips else {}
                            interfaces_by_router.setdefault(port["device_id"], []).append({
                                "port_id": port.get("id"),
                                "subnet_id": first_ip.get("subnet_id", "unknown"),
                                "ip_address": first_ip.get("ip_address", "unknown"),
                            })
                        elif str(port.get("device_owner") or "") == "network:router_gateway":
                            gateway_by_router[port["device_id"]] = {
                                "network_id": port.get("network_id"),
                                "external_fixed_ips": fixed_ips,
                            }

                routers = []
                for router in router_rows:
                    interfaces = interfaces_by_router.get(router.get("id"), [])
                    routers.append({
                        "id": router.get("id"),
                        "name": router.get("name") or "unnamed",
                        "status": router.get("status") or "unknown",
                        "admin_state_up": _bool_value(router.get("admin_state_up")),
                        "external_gateway_info": gateway_by_router.get(router.get("id")),
                        "tenant_id": router.get("tenant_id"),
                        "project_id": router.get("project_id"),
                        "created_at": _str_time(router.get("created_at")),
                        "updated_at": _str_time(router.get("updated_at")),
                        "description": router.get("description") or "",
                        "ha": _bool_value(router.get("ha")),
                        "distributed": _bool_value(router.get("distributed")),
                        "interfaces": interfaces,
                        "interface_count": len(interfaces),
                        "data_source": "mariadb",
                    })
                return routers
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get routers: {e}")
        return [
            {
                'id': 'router-1', 'name': 'demo-router', 'status': 'ACTIVE',
                'admin_state_up': True, 'interfaces': [], 'error': str(e)
            }
        ]

def get_routers_summary(project_id: str = "") -> Dict[str, Any]:
    """
    Get router counts without returning full router/interface details.
    """
    conn = _get_mariadb_connection()
    try:
        scope_project_id = _scope_project_id(project_id)
        with conn.cursor() as cur:
            router_columns = _table_columns(cur, "routers")
            if not router_columns:
                raise RuntimeError("MariaDB table 'routers' is not available")

            project_expr = _column_expr("r", router_columns, "project_id", "tenant_id")
            status_expr = _column_expr("r", router_columns, "status", default="'unknown'")
            admin_state_expr = _column_expr("r", router_columns, "admin_state_up", default="1")
            ha_expr = _column_expr("r", router_columns, "ha", default="0")
            distributed_expr = _column_expr("r", router_columns, "distributed", default="0")
            gw_port_expr = _column_expr("r", router_columns, "gw_port_id")
            gateway_expr = f"CASE WHEN {gw_port_expr} IS NULL OR {gw_port_expr} = '' THEN 0 ELSE 1 END" if gw_port_expr != "NULL" else "0"
            from_sql = "FROM routers r "
            where = []
            params: List[Any] = []
            if scope_project_id:
                where.append(f"{project_expr} = %s")
                params.append(scope_project_id)
            where_sql = " WHERE " + " AND ".join(where) if where else ""

            cur.execute(f"SELECT COUNT(*) AS total {from_sql}{where_sql}", params)
            total = int((cur.fetchone() or {}).get("total") or 0)
            by_status = _get_network_group_counts(cur, f"UPPER({status_expr})", from_sql, where_sql, params, "status")
            status_counts = {row["status"]: row["count"] for row in by_status}

            return {
                "resource": "routers",
                "total": total,
                "active": status_counts.get("ACTIVE", 0),
                "down": status_counts.get("DOWN", 0),
                "error": status_counts.get("ERROR", 0),
                "by_status": by_status,
                "by_project_id": _get_network_group_counts(cur, project_expr, from_sql, where_sql, params, "project_id"),
                "by_admin_state_up": _get_network_group_counts(cur, admin_state_expr, from_sql, where_sql, params, "admin_state_up"),
                "by_ha": _get_network_group_counts(cur, ha_expr, from_sql, where_sql, params, "ha"),
                "by_distributed": _get_network_group_counts(cur, distributed_expr, from_sql, where_sql, params, "distributed"),
                "by_external_gateway": _get_network_group_counts(cur, gateway_expr, from_sql, where_sql, params, "external_gateway"),
                "scope": {
                    "project_id": scope_project_id,
                },
                "data_source": "mariadb",
            }
    finally:
        conn.close()

def _get_network_ports_from_mariadb(
    project_id: str = "",
    status: str = "",
    port_name: str = "",
) -> List[Dict[str, Any]]:
    conn = _get_mariadb_connection()
    try:
        scope_project_id = _scope_project_id(project_id)
        status_filter = status.strip().lower() if status else ""
        target = port_name.strip().lower()
        with conn.cursor() as cur:
            port_columns = _table_columns(cur, "ports")
            standard_attr_columns = _table_columns(cur, "standardattributes")
            if not port_columns:
                raise RuntimeError("MariaDB table 'ports' is not available")

            project_expr = _column_expr("p", port_columns, "project_id", "tenant_id")
            status_expr = _column_expr("p", port_columns, "status", default="'unknown'")
            created_expr = "sa.created_at" if {"id", "created_at"}.issubset(standard_attr_columns) and "standard_attr_id" in port_columns else "NULL"
            updated_expr = "sa.updated_at" if {"id", "updated_at"}.issubset(standard_attr_columns) and "standard_attr_id" in port_columns else "NULL"
            sql = (
                "SELECT p.id, p.name, p.network_id, "
                f"{status_expr} AS status, p.admin_state_up, p.device_id, p.device_owner, "
                f"{_column_expr('p', port_columns, 'mac_address')} AS mac_address, "
                f"{project_expr} AS project_id, {created_expr} AS created_at, {updated_expr} AS updated_at "
                "FROM ports p "
            )
            if created_expr.startswith("sa.") or updated_expr.startswith("sa."):
                sql += "LEFT JOIN standardattributes sa ON sa.id = p.standard_attr_id "
            sql += "WHERE 1=1 "
            params: List[Any] = []
            if target:
                sql += "AND (LOWER(p.id) = %s OR LOWER(p.name) = %s) "
                params.extend([target, target])
            if scope_project_id:
                sql += f"AND {project_expr} = %s "
                params.append(scope_project_id)
            if status_filter:
                sql += f"AND LOWER({status_expr}) = %s "
                params.append(status_filter)
            sql += "ORDER BY p.name ASC, p.id ASC"
            cur.execute(sql, params)
            rows = cur.fetchall()

            port_ids = [row["id"] for row in rows if row.get("id")]
            fixed_by_port: Dict[str, List[Dict[str, Any]]] = {}
            sg_by_port: Dict[str, List[str]] = {}
            if port_ids:
                placeholders = ",".join(["%s"] * len(port_ids))
                if _table_exists(cur, "ipallocations"):
                    cur.execute(
                        f"SELECT port_id, subnet_id, ip_address FROM ipallocations WHERE port_id IN ({placeholders})",
                        port_ids,
                    )
                    for ip_row in cur.fetchall():
                        fixed_by_port.setdefault(ip_row["port_id"], []).append({
                            "subnet_id": ip_row.get("subnet_id"),
                            "ip_address": ip_row.get("ip_address"),
                        })
                sg_columns = _table_columns(cur, "securitygroupportbindings")
                if {"port_id", "security_group_id"}.issubset(sg_columns):
                    cur.execute(
                        f"SELECT port_id, security_group_id FROM securitygroupportbindings WHERE port_id IN ({placeholders})",
                        port_ids,
                    )
                    for sg_row in cur.fetchall():
                        sg_by_port.setdefault(sg_row["port_id"], []).append(sg_row["security_group_id"])

            ports = []
            for row in rows:
                ports.append({
                    "id": row.get("id"),
                    "name": row.get("name") or "unnamed",
                    "network_id": row.get("network_id") or "unknown",
                    "status": row.get("status") or "unknown",
                    "admin_state_up": _bool_value(row.get("admin_state_up")),
                    "device_id": row.get("device_id") or "",
                    "device_owner": row.get("device_owner") or "",
                    "mac_address": row.get("mac_address") or "unknown",
                    "project_id": row.get("project_id"),
                    "fixed_ips": fixed_by_port.get(row.get("id"), []),
                    "security_groups": sg_by_port.get(row.get("id"), []),
                    "created_at": _str_time(row.get("created_at")),
                    "updated_at": _str_time(row.get("updated_at")),
                    "data_source": "mariadb",
                })
            return ports
    finally:
        conn.close()


def get_network_ports(
    project_id: str = "",
    status: str = "",
    port_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Return network ports from MariaDB with optional filters."""
    try:
        if port_name:
            ports = _get_network_ports_from_mariadb(port_name=port_name)
            if ports:
                return {'success': True, 'port': ports[0]}

            return {
                'success': False,
                'message': f'Port "{port_name}" not found'
            }

        ports = _get_network_ports_from_mariadb(
            project_id=str(project_id or ''),
            status=str(status or ''),
        )
        return {
            'success': True,
            'ports': ports,
            'count': len(ports)
        }

    except Exception as e:
        logger.error(f"Failed to get network ports: {e}")
        return {
            'success': False,
            'message': f'Failed to get network ports: {str(e)}',
            'error': str(e)
        }


