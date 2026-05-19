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


def _scope_project_id(include_all_projects: bool = False, project_id: str = "") -> Optional[str]:
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


def _range_size(start: Any, end: Any) -> int:
    try:
        return int(ipaddress.ip_address(str(end))) - int(ipaddress.ip_address(str(start))) + 1
    except Exception:
        return 0


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
    include_all_projects: bool = False,
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
            scope_project_id = _scope_project_id(include_all_projects, project_id)
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


def set_networks(action: str, network_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage networks (create, delete, update, list).
    
    Args:
        action: Action to perform (create, delete, update, list)
        network_name: Name of the network (required for create/delete/update)
        **kwargs: Additional parameters
    
    Returns:
        Result of the network operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'create':
            if not network_name or not network_name.strip():
                return {
                    'success': False,
                    'message': 'Network name is required for create action'
                }
            
            # Network creation parameters
            create_params = {
                'name': network_name,
                'admin_state_up': kwargs.get('admin_state_up', True)
            }
            
            # Optional parameters
            if kwargs.get('description'):
                create_params['description'] = kwargs['description']
            if kwargs.get('shared') is not None:
                create_params['is_shared'] = kwargs['shared']
            if kwargs.get('external') is not None:
                create_params['is_router_external'] = kwargs['external']
            if kwargs.get('provider_network_type'):
                create_params['provider_network_type'] = kwargs['provider_network_type']
            if kwargs.get('provider_physical_network'):
                create_params['provider_physical_network'] = kwargs['provider_physical_network']
            if kwargs.get('provider_segmentation_id'):
                create_params['provider_segmentation_id'] = kwargs['provider_segmentation_id']
            if kwargs.get('mtu'):
                create_params['mtu'] = kwargs['mtu']
            
            network = conn.network.create_network(**create_params)
            return {
                'success': True,
                'message': f'Network "{network_name}" created successfully',
                'network': {
                    'id': network.id,
                    'name': network.name,
                    'status': network.status,
                    'admin_state_up': network.is_admin_state_up
                }
            }
            
        elif action.lower() == 'delete':
            if not network_name or not network_name.strip():
                return {
                    'success': False,
                    'message': 'Network name or ID is required for delete action'
                }
            
            # Find the network using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id, get_openstack_connection
            conn = get_openstack_connection()
            
            network = find_resource_by_name_or_id(
                conn.network.networks(), 
                network_name, 
                "Network"
            )

            if not network:
                return {
                    'success': False,
                    'message': f'Network "{network_name}" not found or not accessible in current project'
                }

            conn.network.delete_network(network)
            return {
                'success': True,
                'message': f'Network "{network_name}" deleted successfully'
            }
            
        elif action.lower() == 'update':
            if not network_name or not network_name.strip():
                return {
                    'success': False,
                    'message': 'Network name or ID is required for update action'
                }
            
            # Find the network
            network = None
            for net in conn.network.networks():
                if getattr(net, 'name', '') == network_name or net.id == network_name:
                    network = net
                    break
            
            if not network:
                return {
                    'success': False,
                    'message': f'Network "{network_name}" not found'
                }
            
            # Update parameters
            update_params = {}
            if kwargs.get('description') is not None:
                update_params['description'] = kwargs['description']
            if kwargs.get('admin_state_up') is not None:
                update_params['admin_state_up'] = kwargs['admin_state_up']
            if kwargs.get('shared') is not None:
                update_params['is_shared'] = kwargs['shared']
            if kwargs.get('mtu'):
                update_params['mtu'] = kwargs['mtu']
            
            if update_params:
                updated_network = conn.network.update_network(network, **update_params)
                return {
                    'success': True,
                    'message': f'Network "{network_name}" updated successfully',
                    'network': {
                        'id': updated_network.id,
                        'name': updated_network.name,
                        'status': updated_network.status,
                        'admin_state_up': updated_network.is_admin_state_up
                    }
                }
            else:
                return {
                    'success': False,
                    'message': 'No update parameters provided'
                }
        
        elif action.lower() == 'list':
            # Use existing get_network_details function
            return get_network_details("all")
            
        else:
            return {
                'success': False,
                'message': f'Unsupported action: {action}. Supported actions: create, delete, update, list'
            }
    
    except Exception as e:
        logger.error(f"Network management failed: {e}")
        return {
            'success': False,
            'message': f'Network management failed: {str(e)}'
        }


def get_security_groups(
    include_all_projects: bool = False,
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
            scope_project_id = _scope_project_id(include_all_projects, project_id)
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


def get_floating_ips(
    include_all_projects: bool = False,
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
            scope_project_id = _scope_project_id(include_all_projects, project_id)
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


def set_floating_ip(action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage floating IPs (allocate, release, associate, disassociate).
    
    Args:
        action: Action to perform (allocate, release, associate, disassociate, list)
        **kwargs: Additional parameters depending on action
    
    Returns:
        Result of the floating IP operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            floating_ips = []
            for fip in conn.network.ips():
                floating_ips.append({
                    'id': fip.id,
                    'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(fip, 'fixed_ip_address', None),
                    'port_id': getattr(fip, 'port_id', None),
                    'status': getattr(fip, 'status', 'unknown')
                })
            return {
                'success': True,
                'floating_ips': floating_ips,
                'count': len(floating_ips)
            }
            
        elif action.lower() == 'allocate':
            network_name = kwargs.get('network', kwargs.get('network_name'))
            subnet_id = kwargs.get('subnet_id')
            
            if not network_name:
                return {
                    'success': False,
                    'message': 'network parameter is required for allocate action'
                }
            
            # Find the external network
            external_network = None
            for network in conn.network.networks():
                if (getattr(network, 'name', '') == network_name or network.id == network_name) and \
                   getattr(network, 'is_router_external', False):
                    external_network = network
                    break
            
            if not external_network:
                return {
                    'success': False,
                    'message': f'External network "{network_name}" not found'
                }
            
            create_params = {
                'floating_network_id': external_network.id
            }
            
            if subnet_id:
                create_params['subnet_id'] = subnet_id
            
            fip = conn.network.create_ip(**create_params)
            
            return {
                'success': True,
                'message': f'Floating IP allocated successfully',
                'floating_ip': {
                    'id': fip.id,
                    'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                    'status': getattr(fip, 'status', 'unknown'),
                    'floating_network_id': getattr(fip, 'floating_network_id', 'unknown')
                }
            }
            
        elif action.lower() == 'release':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for release action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            conn.network.delete_ip(fip)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} released successfully'
            }
            
        elif action.lower() == 'associate':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            port_id = kwargs.get('port_id')
            fixed_ip_address = kwargs.get('fixed_ip_address')
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required'
                }
                
            if not port_id:
                return {
                    'success': False,
                    'message': 'port_id is required for associate action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            update_params = {'port_id': port_id}
            if fixed_ip_address:
                update_params['fixed_ip_address'] = fixed_ip_address
            
            updated_fip = conn.network.update_ip(fip, **update_params)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} associated successfully',
                'floating_ip': {
                    'id': updated_fip.id,
                    'floating_ip_address': getattr(updated_fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(updated_fip, 'fixed_ip_address', None),
                    'port_id': getattr(updated_fip, 'port_id', None)
                }
            }
            
        elif action.lower() == 'disassociate':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            updated_fip = conn.network.update_ip(fip, port_id=None)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} disassociated successfully'
            }
        
        elif action.lower() == 'show':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for show action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            return {
                'success': True,
                'floating_ip': {
                    'id': fip.id,
                    'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(fip, 'fixed_ip_address', None),
                    'port_id': getattr(fip, 'port_id', None),
                    'router_id': getattr(fip, 'router_id', None),
                    'status': getattr(fip, 'status', 'unknown'),
                    'tenant_id': getattr(fip, 'tenant_id', 'unknown'),
                    'project_id': getattr(fip, 'project_id', 'unknown'),
                    'floating_network_id': getattr(fip, 'floating_network_id', 'unknown'),
                    'description': getattr(fip, 'description', ''),
                    'created_at': str(getattr(fip, 'created_at', 'unknown')),
                    'updated_at': str(getattr(fip, 'updated_at', 'unknown'))
                }
            }
            
        elif action.lower() == 'set':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for set action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            # Update parameters
            update_params = {}
            if kwargs.get('description') is not None:
                update_params['description'] = kwargs['description']
            if kwargs.get('port_id') is not None:
                update_params['port_id'] = kwargs['port_id']
            if kwargs.get('fixed_ip_address') is not None:
                update_params['fixed_ip_address'] = kwargs['fixed_ip_address']
            
            if not update_params:
                return {
                    'success': False,
                    'message': 'No update parameters provided'
                }
            
            updated_fip = conn.network.update_ip(fip, **update_params)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} updated successfully',
                'floating_ip': {
                    'id': updated_fip.id,
                    'floating_ip_address': getattr(updated_fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(updated_fip, 'fixed_ip_address', None),
                    'port_id': getattr(updated_fip, 'port_id', None),
                    'description': getattr(updated_fip, 'description', '')
                }
            }
            
        elif action.lower() == 'unset':
            floating_ip_id = kwargs.get('floating_ip_id', kwargs.get('id'))
            floating_ip_address = kwargs.get('floating_ip_address', kwargs.get('ip'))
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for unset action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            # Unset parameters (clear them)
            update_params = {}
            unset_properties = kwargs.get('properties', [])
            
            if 'description' in unset_properties:
                update_params['description'] = ''
            if 'port' in unset_properties:
                update_params['port_id'] = None
                update_params['fixed_ip_address'] = None
            
            if not update_params:
                return {
                    'success': False,
                    'message': 'No properties specified to unset'
                }
            
            updated_fip = conn.network.update_ip(fip, **update_params)
            
            return {
                'success': True,
                'message': f'Floating IP {getattr(fip, "floating_ip_address", fip.id)} properties unset successfully',
                'floating_ip': {
                    'id': updated_fip.id,
                    'floating_ip_address': getattr(updated_fip, 'floating_ip_address', 'unknown'),
                    'fixed_ip_address': getattr(updated_fip, 'fixed_ip_address', None),
                    'port_id': getattr(updated_fip, 'port_id', None)
                }
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: allocate, release, associate, disassociate, list, show, set, unset'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage floating IP: {e}")
        return {
            'success': False,
            'message': f'Failed to manage floating IP: {str(e)}',
            'error': str(e)
        }


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


def set_floating_ip_port_forwarding(action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage floating IP port forwarding rules.
    
    Args:
        action: Action to perform (create, delete, list, show, set)
        **kwargs: Additional parameters depending on action
    
    Returns:
        Result of the port forwarding operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            floating_ip_id = kwargs.get('floating_ip_id')
            floating_ip_address = kwargs.get('floating_ip_address')
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required for list action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            # Get port forwarding rules for this floating IP
            port_forwardings = []
            try:
                for pf in conn.network.port_forwardings(floatingip=fip.id):
                    port_forwardings.append({
                        'id': pf.id,
                        'protocol': getattr(pf, 'protocol', 'unknown'),
                        'external_port': getattr(pf, 'external_port', 0),
                        'internal_port': getattr(pf, 'internal_port', 0),
                        'internal_ip_address': getattr(pf, 'internal_ip_address', 'unknown'),
                        'internal_port_id': getattr(pf, 'internal_port_id', None),
                        'description': getattr(pf, 'description', '')
                    })
            except Exception as e:
                logger.warning(f"Could not retrieve port forwarding rules: {e}")
                # Return empty list if port forwarding is not supported
                
            return {
                'success': True,
                'floating_ip_id': fip.id,
                'floating_ip_address': getattr(fip, 'floating_ip_address', 'unknown'),
                'port_forwardings': port_forwardings,
                'count': len(port_forwardings)
            }
            
        elif action.lower() == 'create':
            floating_ip_id = kwargs.get('floating_ip_id')
            floating_ip_address = kwargs.get('floating_ip_address')
            protocol = kwargs.get('protocol', 'tcp')
            external_port = kwargs.get('external_port')
            internal_port = kwargs.get('internal_port')
            internal_ip_address = kwargs.get('internal_ip_address')
            internal_port_id = kwargs.get('internal_port_id')
            description = kwargs.get('description', '')
            
            if not floating_ip_id and not floating_ip_address:
                return {
                    'success': False,
                    'message': 'floating_ip_id or floating_ip_address is required'
                }
                
            if not external_port or not internal_port:
                return {
                    'success': False,
                    'message': 'external_port and internal_port are required for create action'
                }
            
            # Find the floating IP
            fip = None
            for f in conn.network.ips():
                if (floating_ip_id and f.id == floating_ip_id) or \
                   (floating_ip_address and getattr(f, 'floating_ip_address', '') == floating_ip_address):
                    fip = f
                    break
            
            if not fip:
                return {
                    'success': False,
                    'message': 'Floating IP not found'
                }
            
            create_params = {
                'protocol': protocol,
                'external_port': external_port,
                'internal_port': internal_port
            }
            
            if internal_ip_address:
                create_params['internal_ip_address'] = internal_ip_address
            if internal_port_id:
                create_params['internal_port_id'] = internal_port_id
            if description:
                create_params['description'] = description
            
            try:
                pf = conn.network.create_port_forwarding(floatingip=fip.id, **create_params)
                return {
                    'success': True,
                    'message': f'Port forwarding rule created successfully',
                    'port_forwarding': {
                        'id': pf.id,
                        'protocol': getattr(pf, 'protocol', protocol),
                        'external_port': getattr(pf, 'external_port', external_port),
                        'internal_port': getattr(pf, 'internal_port', internal_port),
                        'internal_ip_address': getattr(pf, 'internal_ip_address', internal_ip_address)
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create port forwarding rule: {str(e)}',
                    'note': 'Port forwarding may not be supported in this OpenStack deployment'
                }
                
        elif action.lower() == 'delete':
            floating_ip_id = kwargs.get('floating_ip_id')
            port_forwarding_id = kwargs.get('port_forwarding_id')
            
            if not floating_ip_id or not port_forwarding_id:
                return {
                    'success': False,
                    'message': 'floating_ip_id and port_forwarding_id are required for delete action'
                }
            
            try:
                conn.network.delete_port_forwarding(port_forwarding_id, floatingip=floating_ip_id)
                return {
                    'success': True,
                    'message': f'Port forwarding rule deleted successfully'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to delete port forwarding rule: {str(e)}'
                }
                
        elif action.lower() == 'show':
            floating_ip_id = kwargs.get('floating_ip_id')
            port_forwarding_id = kwargs.get('port_forwarding_id')
            
            if not floating_ip_id or not port_forwarding_id:
                return {
                    'success': False,
                    'message': 'floating_ip_id and port_forwarding_id are required for show action'
                }
            
            try:
                pf = conn.network.get_port_forwarding(port_forwarding_id, floatingip=floating_ip_id)
                return {
                    'success': True,
                    'port_forwarding': {
                        'id': pf.id,
                        'protocol': getattr(pf, 'protocol', 'unknown'),
                        'external_port': getattr(pf, 'external_port', 0),
                        'internal_port': getattr(pf, 'internal_port', 0),
                        'internal_ip_address': getattr(pf, 'internal_ip_address', 'unknown'),
                        'internal_port_id': getattr(pf, 'internal_port_id', None),
                        'description': getattr(pf, 'description', ''),
                        'created_at': str(getattr(pf, 'created_at', 'unknown')),
                        'updated_at': str(getattr(pf, 'updated_at', 'unknown'))
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to get port forwarding rule: {str(e)}'
                }
                
        elif action.lower() == 'set':
            floating_ip_id = kwargs.get('floating_ip_id')
            port_forwarding_id = kwargs.get('port_forwarding_id')
            
            if not floating_ip_id or not port_forwarding_id:
                return {
                    'success': False,
                    'message': 'floating_ip_id and port_forwarding_id are required for set action'
                }
            
            update_params = {}
            if kwargs.get('description') is not None:
                update_params['description'] = kwargs['description']
            if kwargs.get('internal_ip_address'):
                update_params['internal_ip_address'] = kwargs['internal_ip_address']
            if kwargs.get('internal_port'):
                update_params['internal_port'] = kwargs['internal_port']
            if kwargs.get('internal_port_id'):
                update_params['internal_port_id'] = kwargs['internal_port_id']
            
            if not update_params:
                return {
                    'success': False,
                    'message': 'No update parameters provided'
                }
            
            try:
                pf = conn.network.update_port_forwarding(
                    port_forwarding_id, 
                    floatingip=floating_ip_id, 
                    **update_params
                )
                return {
                    'success': True,
                    'message': f'Port forwarding rule updated successfully',
                    'port_forwarding': {
                        'id': pf.id,
                        'protocol': getattr(pf, 'protocol', 'unknown'),
                        'external_port': getattr(pf, 'external_port', 0),
                        'internal_port': getattr(pf, 'internal_port', 0),
                        'internal_ip_address': getattr(pf, 'internal_ip_address', 'unknown')
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to update port forwarding rule: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unsupported action: {action}. Supported actions: create, delete, list, show, set'
            }
            
    except Exception as e:
        logger.error(f"Port forwarding management failed: {e}")
        return {
            'success': False,
            'message': f'Port forwarding management failed: {str(e)}'
        }


def get_routers(
    include_all_projects: bool = False,
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
            scope_project_id = _scope_project_id(include_all_projects, project_id)
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

def _get_network_ports_from_mariadb(
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
    port_name: str = "",
) -> List[Dict[str, Any]]:
    conn = _get_mariadb_connection()
    try:
        scope_project_id = _scope_project_id(include_all_projects, project_id)
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


def set_network_ports(action: str, port_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage network ports.
    
    Args:
        action: Action to perform (list, show, create, delete, update)
        port_name: Name or ID of port (for specific operations)
        **kwargs: Additional parameters
    
    Returns:
        Result of the port operation
    """
    try:
        if action.lower() == 'list':
            include_all_projects = bool(kwargs.get('include_all_projects', False))
            project_id = str(kwargs.get('project_id', '') or '')
            status_filter = str(kwargs.get('status', '') or '')
            ports = _get_network_ports_from_mariadb(
                include_all_projects=include_all_projects,
                project_id=project_id,
                status=status_filter,
            )
            return {
                'success': True,
                'ports': ports,
                'count': len(ports)
            }
            
        elif action.lower() == 'show':
            if not port_name:
                return {
                    'success': False,
                    'message': 'port_name is required for show action'
                }

            ports = _get_network_ports_from_mariadb(port_name=port_name)
            if ports:
                return {'success': True, 'port': ports[0]}

            return {
                'success': False,
                'message': f'Port "{port_name}" not found'
            }
            
        elif action.lower() == 'create':
            from ..connection import get_openstack_connection
            conn = get_openstack_connection()
            network_id = kwargs.get('network_id')
            name = kwargs.get('name', port_name)
            
            if not network_id:
                return {
                    'success': False,
                    'message': 'network_id is required for create action'
                }
            
            create_params = {'network_id': network_id}
            if name:
                create_params['name'] = name
            
            # Optional parameters
            if 'admin_state_up' in kwargs:
                create_params['is_admin_state_up'] = kwargs['admin_state_up']
            if 'fixed_ips' in kwargs:
                create_params['fixed_ips'] = kwargs['fixed_ips']
            if 'security_groups' in kwargs:
                create_params['security_group_ids'] = kwargs['security_groups']
            
            port = conn.network.create_port(**create_params)
            
            return {
                'success': True,
                'message': f'Port "{name or port.id}" created successfully',
                'port': {
                    'id': port.id,
                    'name': getattr(port, 'name', 'unnamed'),
                    'network_id': getattr(port, 'network_id', 'unknown'),
                    'status': getattr(port, 'status', 'unknown'),
                    'mac_address': getattr(port, 'mac_address', 'unknown')
                }
            }
            
        elif action.lower() == 'delete':
            from ..connection import get_openstack_connection
            conn = get_openstack_connection()
            if not port_name:
                return {
                    'success': False,
                    'message': 'port_name is required for delete action'
                }
            
            # Find the port using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id
            
            port = find_resource_by_name_or_id(
                conn.network.ports(), 
                port_name, 
                "Network Port"
            )
            
            if not port:
                return {
                    'success': False,
                    'message': f'Port "{port_name}" not found or not accessible in current project'
                }
                    
            conn.network.delete_port(port)
            return {
                'success': True,
                'message': f'Port "{port_name}" deleted successfully'
            }
            
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, show, create, delete'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage network port: {e}")
        return {
            'success': False,
            'message': f'Failed to manage network port: {str(e)}',
            'error': str(e)
        }


def set_subnets(action: str, subnet_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage network subnets.
    
    Args:
        action: Action to perform (list, show, create, delete, update)
        subnet_name: Name or ID of subnet (for specific operations)
        **kwargs: Additional parameters
    
    Returns:
        Result of the subnet operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            subnets = []
            for subnet in conn.network.subnets():
                subnets.append({
                    'id': subnet.id,
                    'name': getattr(subnet, 'name', 'unnamed'),
                    'network_id': getattr(subnet, 'network_id', 'unknown'),
                    'cidr': getattr(subnet, 'cidr', 'unknown'),
                    'ip_version': getattr(subnet, 'ip_version', 4),
                    'gateway_ip': getattr(subnet, 'gateway_ip', None),
                    'enable_dhcp': getattr(subnet, 'is_dhcp_enabled', False),
                    'allocation_pools': getattr(subnet, 'allocation_pools', []),
                    'dns_nameservers': getattr(subnet, 'dns_nameservers', [])
                })
            return {
                'success': True,
                'subnets': subnets,
                'count': len(subnets)
            }
            
        elif action.lower() == 'show':
            if not subnet_name:
                return {
                    'success': False,
                    'message': 'subnet_name is required for show action'
                }
            
            # Find the subnet
            for subnet in conn.network.subnets():
                if getattr(subnet, 'name', '') == subnet_name or subnet.id == subnet_name:
                    return {
                        'success': True,
                        'subnet': {
                            'id': subnet.id,
                            'name': getattr(subnet, 'name', 'unnamed'),
                            'network_id': getattr(subnet, 'network_id', 'unknown'),
                            'cidr': getattr(subnet, 'cidr', 'unknown'),
                            'ip_version': getattr(subnet, 'ip_version', 4),
                            'gateway_ip': getattr(subnet, 'gateway_ip', None),
                            'enable_dhcp': getattr(subnet, 'is_dhcp_enabled', False),
                            'allocation_pools': getattr(subnet, 'allocation_pools', []),
                            'dns_nameservers': getattr(subnet, 'dns_nameservers', []),
                            'host_routes': getattr(subnet, 'host_routes', []),
                            'created_at': str(getattr(subnet, 'created_at', 'unknown')),
                            'updated_at': str(getattr(subnet, 'updated_at', 'unknown'))
                        }
                    }
            
            return {
                'success': False,
                'message': f'Subnet "{subnet_name}" not found'
            }
            
        elif action.lower() == 'create':
            network_id = kwargs.get('network_id')
            cidr = kwargs.get('cidr')
            name = kwargs.get('name', subnet_name)
            
            if not network_id:
                return {
                    'success': False,
                    'message': 'network_id is required for create action'
                }
                
            if not cidr:
                return {
                    'success': False,
                    'message': 'cidr is required for create action'
                }
            
            create_params = {
                'network_id': network_id,
                'cidr': cidr,
                'ip_version': kwargs.get('ip_version', 4)
            }
            
            if name:
                create_params['name'] = name
            if 'gateway_ip' in kwargs:
                create_params['gateway_ip'] = kwargs['gateway_ip']
            if 'enable_dhcp' in kwargs:
                create_params['is_dhcp_enabled'] = kwargs['enable_dhcp']
            if 'dns_nameservers' in kwargs:
                create_params['dns_nameservers'] = kwargs['dns_nameservers']
            if 'allocation_pools' in kwargs:
                create_params['allocation_pools'] = kwargs['allocation_pools']
            
            subnet = conn.network.create_subnet(**create_params)
            
            return {
                'success': True,
                'message': f'Subnet "{name or subnet.id}" created successfully',
                'subnet': {
                    'id': subnet.id,
                    'name': getattr(subnet, 'name', 'unnamed'),
                    'network_id': getattr(subnet, 'network_id', 'unknown'),
                    'cidr': getattr(subnet, 'cidr', 'unknown'),
                    'gateway_ip': getattr(subnet, 'gateway_ip', None)
                }
            }
            
        elif action.lower() == 'delete':
            if not subnet_name:
                return {
                    'success': False,
                    'message': 'subnet_name is required for delete action'
                }
            
            # Find the subnet using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id
            
            subnet = find_resource_by_name_or_id(
                conn.network.subnets(), 
                subnet_name, 
                "Subnet"
            )
            
            if not subnet:
                return {
                    'success': False,
                    'message': f'Subnet "{subnet_name}" not found or not accessible in current project'
                }
            
            conn.network.delete_subnet(subnet)
            return {
                'success': True,
                'message': f'Subnet "{subnet_name}" deleted successfully'
            }
            
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, show, create, delete'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage subnet: {e}")
        return {
            'success': False,
            'message': f'Failed to manage subnet: {str(e)}',
            'error': str(e)
        }
