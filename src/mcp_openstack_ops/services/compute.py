"""
OpenStack Compute (Nova) Service Functions

This module contains functions for managing instances, flavors, server groups,
server events, and other compute-related components.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional

try:
    import pymysql
except Exception:  # pragma: no cover - optional dependency at runtime
    pymysql = None

# Configure logging
logger = logging.getLogger(__name__)

NOVA_DATABASE = "nova"
TRUTHY_VALUES = {"1", "true", "yes", "on"}


def _get_nova_mariadb_connection():
    if pymysql is None:
        raise RuntimeError("PyMySQL is not installed")

    return pymysql.connect(
        host=os.getenv("MARIADB_HOST", "127.0.0.1"),
        port=int(os.getenv("MARIADB_PORT", "3306")),
        user=os.getenv("MARIADB_USER", ""),
        password=os.getenv("MARIADB_PASSWORD", ""),
        database=NOVA_DATABASE,
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
    prefix = f"{alias}." if alias else ""
    for name in names:
        if name in columns:
            return f"{prefix}{name}"
    return default


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


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in TRUTHY_VALUES


def _scope_project_id(include_all_projects: bool = False) -> Optional[str]:
    if include_all_projects:
        return None
    return (
        os.getenv("MARIADB_PROJECT_ID")
        or os.getenv("OS_PROJECT_ID")
        or os.getenv("OS_TENANT_ID")
        or None
    )


def _parse_networks(network_info: Any) -> List[Dict[str, Any]]:
    data = _json_value(network_info, default=[])
    if isinstance(data, dict):
        data = data.get("network_info") or data.get("networks") or data.get("devices") or []
    if not isinstance(data, list):
        return []

    networks: Dict[str, Dict[str, Any]] = {}
    for vif in data:
        if not isinstance(vif, dict):
            continue
        network = vif.get("network") or {}
        network_name = (
            network.get("label")
            or network.get("id")
            or vif.get("network_name")
            or vif.get("net_name")
            or "unknown"
        )
        entry = networks.setdefault(str(network_name), {"network": str(network_name), "addresses": []})
        mac_addr = vif.get("address") or vif.get("mac_address")
        for subnet in network.get("subnets", []) or []:
            for ip in subnet.get("ips", []) or []:
                entry["addresses"].append({
                    "addr": ip.get("address"),
                    "type": "fixed",
                    "version": ip.get("version", 4),
                    "mac_addr": mac_addr or "unknown",
                })
    return list(networks.values())


def _power_state_label(value: Any) -> str:
    labels = {
        0: "NOSTATE",
        1: "RUNNING",
        3: "PAUSED",
        4: "SHUTDOWN",
        6: "CRASHED",
        7: "SUSPENDED",
    }
    try:
        int_value = int(value or 0)
    except Exception:
        return f"UNKNOWN({value})"
    return labels.get(int_value, f"UNKNOWN({int_value})")


def _get_compute_group_counts(cur, group_expr: str, where_sql: str, params: List[Any], label: str) -> List[Dict[str, Any]]:
    if group_expr == "NULL":
        return []
    cur.execute(
        "SELECT COALESCE(group_value, 'unknown') AS value, COUNT(*) AS count FROM ("
        f"SELECT {group_expr} AS group_value FROM instances i{where_sql}"
        ") grouped_instances GROUP BY value ORDER BY count DESC, value ASC",
        params,
    )
    return [{label: row.get("value"), "count": int(row.get("count") or 0)} for row in cur.fetchall()]


def get_instance_summary(include_all_projects: bool = False, project_id: str = "") -> Dict[str, Any]:
    """
    Get Nova instance counts without filtering to ACTIVE only.
    """
    conn = _get_nova_mariadb_connection()
    try:
        scope_project_id = project_id or _scope_project_id(include_all_projects)
        with conn.cursor() as cur:
            columns = _table_columns(cur, "instances")
            if not columns:
                raise RuntimeError("MariaDB table 'instances' is not available")

            deleted_expr = _column_expr("i", columns, "deleted", default="0")
            status_expr = _column_expr("i", columns, "vm_state", default="'unknown'")
            project_expr = _column_expr("i", columns, "project_id")
            az_expr = _column_expr("i", columns, "availability_zone", default="NULL")
            host_expr = _column_expr("i", columns, "host", default="NULL")
            power_expr = _column_expr("i", columns, "power_state", default="0")

            where = []
            params: List[Any] = []
            if deleted_expr != "0":
                where.append(f"({deleted_expr} = 0 OR {deleted_expr} = '0')")
            if scope_project_id:
                where.append(f"{project_expr} = %s")
                params.append(scope_project_id)
            where_sql = " WHERE " + " AND ".join(where) if where else ""

            cur.execute(f"SELECT COUNT(*) AS total FROM instances i{where_sql}", params)
            total = int((cur.fetchone() or {}).get("total") or 0)

            by_status = _get_compute_group_counts(cur, f"UPPER({status_expr})", where_sql, params, "status")
            status_counts = {row["status"]: row["count"] for row in by_status}
            error_count = sum(status_counts.get(status, 0) for status in ("ERROR", "CRASHED"))

            return {
                "resource": "instances",
                "total": total,
                "active": status_counts.get("ACTIVE", 0),
                "error": error_count,
                "by_status": by_status,
                "by_project_id": _get_compute_group_counts(cur, project_expr, where_sql, params, "project_id"),
                "by_availability_zone": _get_compute_group_counts(cur, az_expr, where_sql, params, "availability_zone"),
                "by_host": _get_compute_group_counts(cur, host_expr, where_sql, params, "host"),
                "by_power_state": _get_compute_group_counts(cur, power_expr, where_sql, params, "power_state"),
                "scope": {
                    "project_id": scope_project_id,
                    "include_all_projects": include_all_projects,
                },
                "data_source": "mariadb",
            }
    finally:
        conn.close()


def get_instance_details(
    instance_names: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0,
    include_all: bool = False
) -> Dict[str, Any]:
    """
    Get detailed information about OpenStack instances with pagination support.
    
    Args:
        instance_names: List of instance names to filter (optional)
        limit: Maximum number of instances to return (default: 50, max: 200)
        offset: Number of instances to skip for pagination (default: 0)
        include_all: If True, return all instances ignoring limit (default: False)
    
    Returns:
        Dictionary containing instances and metadata
    """
    try:
        if limit > 200:
            limit = 200
        if limit < 1:
            limit = 1
        if offset < 0:
            offset = 0

        conn = _get_nova_mariadb_connection()
        try:
            scope_project_id = _scope_project_id(include_all)
            with conn.cursor() as cur:
                instance_columns = _table_columns(cur, "instances")
                if not instance_columns:
                    raise RuntimeError("MariaDB table 'instances' is not available")

                uuid_expr = _column_expr("i", instance_columns, "uuid")
                name_expr = _column_expr("i", instance_columns, "display_name", "hostname", default="NULL")
                status_expr = _column_expr("i", instance_columns, "vm_state", default="'unknown'")
                task_expr = _column_expr("i", instance_columns, "task_state", default="NULL")
                power_expr = _column_expr("i", instance_columns, "power_state", default="0")
                project_expr = _column_expr("i", instance_columns, "project_id")
                deleted_expr = _column_expr("i", instance_columns, "deleted", default="0")
                type_id_expr = _column_expr("i", instance_columns, "instance_type_id", default="NULL")
                image_expr = _column_expr("i", instance_columns, "image_ref", default="NULL")
                az_expr = _column_expr("i", instance_columns, "availability_zone", default="NULL")
                host_expr = _column_expr("i", instance_columns, "host", default="NULL")
                node_expr = _column_expr("i", instance_columns, "node", "hypervisor_hostname", default="NULL")
                key_expr = _column_expr("i", instance_columns, "key_name", default="NULL")
                user_expr = _column_expr("i", instance_columns, "user_id", default="NULL")
                progress_expr = _column_expr("i", instance_columns, "progress", default="0")
                config_drive_expr = _column_expr("i", instance_columns, "config_drive", default="0")
                locked_expr = _column_expr("i", instance_columns, "locked", default="0")

                joins = ""
                select_network_info = "NULL AS network_info"
                if _table_exists(cur, "instance_info_caches"):
                    cache_columns = _table_columns(cur, "instance_info_caches")
                    if {"instance_uuid", "network_info"}.issubset(cache_columns):
                        joins += " LEFT JOIN instance_info_caches iic ON iic.instance_uuid = i.uuid"
                        select_network_info = "iic.network_info AS network_info"

                select_flavor = (
                    "NULL AS flavor_id, NULL AS flavor_name, 0 AS vcpus, 0 AS memory_mb, "
                    "0 AS root_gb, 0 AS ephemeral_gb, 0 AS swap"
                )
                if _table_exists(cur, "instance_types"):
                    flavor_columns = _table_columns(cur, "instance_types")
                    flavor_deleted_expr = _column_expr("it", flavor_columns, "deleted", default="0")
                    joins += (
                        " LEFT JOIN instance_types it ON it.id = "
                        f"{type_id_expr} AND ({flavor_deleted_expr} = 0 OR {flavor_deleted_expr} = '0')"
                    )
                    select_flavor = (
                        "it.id AS flavor_id, it.name AS flavor_name, it.vcpus, "
                        "it.memory_mb, it.root_gb, it.ephemeral_gb, it.swap"
                    )

                where = []
                params: List[Any] = []
                if deleted_expr != "0":
                    where.append(f"({deleted_expr} = 0 OR {deleted_expr} = '0')")
                if scope_project_id:
                    where.append(f"{project_expr} = %s")
                    params.append(scope_project_id)
                if instance_names:
                    placeholders = ",".join(["%s"] * len(instance_names))
                    where.append(f"({uuid_expr} IN ({placeholders}) OR {name_expr} IN ({placeholders}))")
                    params.extend(instance_names)
                    params.extend(instance_names)
                where_sql = " WHERE " + " AND ".join(where) if where else ""

                count_sql = f"SELECT COUNT(*) AS total FROM instances i{joins}{where_sql}"
                cur.execute(count_sql, params)
                total_count = int((cur.fetchone() or {}).get("total") or 0)

                page_sql = (
                    "SELECT "
                    f"{uuid_expr} AS id, {name_expr} AS name, {status_expr} AS status, "
                    f"{power_expr} AS power_state, {task_expr} AS task_state, {status_expr} AS vm_state, "
                    "i.created_at, i.updated_at, "
                    f"{_column_expr('i', instance_columns, 'launched_at')} AS launched_at, "
                    f"{host_expr} AS host, {node_expr} AS hypervisor_hostname, {az_expr} AS availability_zone, "
                    f"{key_expr} AS key_name, {project_expr} AS tenant_id, {user_expr} AS user_id, "
                    f"{progress_expr} AS progress, {config_drive_expr} AS config_drive, {locked_expr} AS locked, "
                    f"{image_expr} AS image_id, {select_network_info}, {select_flavor} "
                    f"FROM instances i{joins}{where_sql} ORDER BY i.created_at DESC"
                )
                page_params = list(params)
                if not include_all:
                    page_sql += " LIMIT %s OFFSET %s"
                    page_params.extend([limit, offset])
                cur.execute(page_sql, page_params)
                rows = cur.fetchall()

                instance_ids = [row["id"] for row in rows if row.get("id")]
                volumes_by_instance: Dict[str, List[str]] = {}
                if instance_ids and _table_exists(cur, "block_device_mapping"):
                    bdm_columns = _table_columns(cur, "block_device_mapping")
                    if {"instance_uuid", "volume_id"}.issubset(bdm_columns):
                        placeholders = ",".join(["%s"] * len(instance_ids))
                        bdm_deleted_expr = _column_expr("", bdm_columns, "deleted", default="0")
                        cur.execute(
                            f"SELECT instance_uuid, volume_id FROM block_device_mapping "
                            f"WHERE instance_uuid IN ({placeholders}) AND volume_id IS NOT NULL "
                            f"AND ({bdm_deleted_expr} = 0 OR {bdm_deleted_expr} = '0')",
                            instance_ids,
                        )
                        for bdm in cur.fetchall():
                            volumes_by_instance.setdefault(bdm["instance_uuid"], []).append(bdm["volume_id"])

                instances = []
                for row in rows:
                    power_state = row.get("power_state") or 0
                    image_id = row.get("image_id")
                    instances.append({
                        "id": row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "status": str(row.get("status") or "unknown").upper(),
                        "power_state": power_state,
                        "power_state_label": _power_state_label(power_state),
                        "task_state": row.get("task_state"),
                        "vm_state": row.get("vm_state") or "unknown",
                        "created": _str_time(row.get("created_at")),
                        "updated": _str_time(row.get("updated_at")),
                        "launched_at": _str_time(row.get("launched_at")) if row.get("launched_at") else None,
                        "host": row.get("host") or "unknown",
                        "hypervisor_hostname": row.get("hypervisor_hostname") or "unknown",
                        "availability_zone": row.get("availability_zone") or "unknown",
                        "flavor": {
                            "id": row.get("flavor_id") or "unknown",
                            "name": row.get("flavor_name") or "unknown",
                            "vcpus": row.get("vcpus") or 0,
                            "ram": row.get("memory_mb") or 0,
                            "disk": row.get("root_gb") or 0,
                            "ephemeral": row.get("ephemeral_gb") or 0,
                            "swap": row.get("swap") or 0,
                        },
                        "image": {"id": image_id or "unknown", "name": "unknown"},
                        "key_name": row.get("key_name"),
                        "networks": _parse_networks(row.get("network_info")),
                        "security_groups": [],
                        "tenant_id": row.get("tenant_id"),
                        "project_id": row.get("tenant_id"),
                        "user_id": row.get("user_id") or "unknown",
                        "metadata": {},
                        "fault": None,
                        "progress": row.get("progress") or 0,
                        "config_drive": _bool_value(row.get("config_drive")),
                        "locked": _bool_value(row.get("locked")),
                        "attached_volumes": volumes_by_instance.get(row.get("id"), []),
                        "data_source": "mariadb",
                    })

            has_next = (offset + limit) < total_count
            has_prev = offset > 0
            next_offset = offset + limit if has_next else None
            prev_offset = max(0, offset - limit) if has_prev else None

            result = {
                'instances': instances,
                'count': len(instances),
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_next': has_next,
                'has_prev': has_prev,
                'next_offset': next_offset,
                'prev_offset': prev_offset
            }

            if instance_names:
                result['filtered_by_names'] = instance_names

            return result
        finally:
            conn.close()
        
    except Exception as e:
        logger.error(f"Failed to get instance details: {e}")
        return {
            'instances': [],
            'count': 0,
            'total_count': 0,
            'error': str(e),
            'success': False
        }


def get_instance_by_name(instance_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a single instance by name.
    
    Args:
        instance_name: Name of the instance
        
    Returns:
        Instance details or None if not found
    """
    try:
        result = get_instance_details([instance_name], limit=1)
        instances = result.get('instances', [])
        return instances[0] if instances else None
    except Exception as e:
        logger.error(f"Failed to get instance by name: {e}")
        return None


def get_instance_by_id(instance_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single instance by ID.
    
    Args:
        instance_id: ID of the instance
        
    Returns:
        Instance details or None if not found
    """
    try:
        result = get_instance_details([instance_id], limit=1)
        instances = result.get('instances', [])
        return instances[0] if instances else None
    except Exception as e:
        logger.error(f"Failed to get instance by ID: {e}")
        return None


def search_instances(
    search_term: str,
    search_fields: Optional[List[str]] = None,
    limit: int = 50,
    include_inactive: bool = False
) -> List[Dict[str, Any]]:
    """
    Search for instances by various fields.
    
    Args:
        search_term: Term to search for
        search_fields: Fields to search in (default: name, id)
        limit: Maximum results to return
        include_inactive: Include non-active instances
        
    Returns:
        List of matching instances
    """
    try:
        if search_fields is None:
            search_fields = ['name', 'id']
        
        matching_instances = []
        all_instances_result = get_instance_details(limit=limit*2, include_all=True)
        all_instances = all_instances_result.get('instances', [])
        
        search_term_lower = search_term.lower()
        
        for instance in all_instances:
            # Skip inactive instances if not requested
            if not include_inactive and instance.get('status', '').lower() not in ['active', 'running']:
                continue
                
            match_found = False
            
            for field in search_fields:
                field_value = str(instance.get(field, '')).lower()
                if search_term_lower in field_value:
                    match_found = True
                    break
                    
                # Special handling for nested fields
                if field == 'ip':
                    for network in instance.get('networks', []):
                        for addr in network.get('addresses', []):
                            if search_term_lower in addr.get('addr', '').lower():
                                match_found = True
                                break
                        if match_found:
                            break
                elif field == 'flavor_name':
                    flavor = instance.get('flavor', {})
                    if search_term_lower in str(flavor.get('name', '')).lower():
                        match_found = True
                elif field == 'image_name':
                    image = instance.get('image', {})
                    if search_term_lower in str(image.get('name', '')).lower():
                        match_found = True
            
            if match_found:
                matching_instances.append(instance)
                
            if len(matching_instances) >= limit:
                break
        
        return matching_instances
        
    except Exception as e:
        logger.error(f"Failed to search instances: {e}")
        return []


def get_instances_by_status(status: str) -> List[Dict[str, Any]]:
    """
    Get instances filtered by status.
    
    Args:
        status: Status to filter by (ACTIVE, SHUTOFF, ERROR, etc.)
        
    Returns:
        List of instances with matching status
    """
    try:
        result = get_instance_details(include_all=True)
        instances = result.get('instances', [])
        
        status_lower = status.lower()
        return [
            instance for instance in instances 
            if instance.get('status', '').lower() == status_lower
        ]
        
    except Exception as e:
        logger.error(f"Failed to get instances by status: {e}")
        return []


def set_instance(instance_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage instances (start, stop, reboot, delete, create, etc.).
    
    Args:
        instance_name: Name of the instance
        action: Action to perform
        **kwargs: Additional parameters depending on action
    
    Returns:
        Result of the instance operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection, find_resource_by_name_or_id
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            result = get_instance_details(limit=kwargs.get('limit', 50))
            return {
                'success': True,
                'instances': result.get('instances', []),
                'count': result.get('count', 0),
                'total_count': result.get('total_count', 0)
            }
            
        elif action.lower() == 'create':
            # Required parameters
            flavor_name = kwargs.get('flavor', kwargs.get('flavor_name'))
            image_name = kwargs.get('image', kwargs.get('image_name'))
            network_names = kwargs.get('networks', kwargs.get('network_names', []))
            
            if not flavor_name:
                return {
                    'success': False,
                    'message': 'Flavor parameter is required for create action. Please specify a flavor (e.g., m1.small, m1.medium).'
                }
                
            if not image_name:
                # Get available images for error message
                try:
                    all_images = list(conn.image.images())
                    active_images = [img.name for img in all_images if img.status == 'active'][:10]  # Show first 10
                    available_list = '\n'.join(f"  • {img}" for img in active_images)
                    more_available = f"\n  ... and {len([img for img in all_images if img.status == 'active']) - 10} more" if len([img for img in all_images if img.status == 'active']) > 10 else ""
                    
                    return {
                        'success': False,
                        'message': f'Image parameter is required for VM creation.\n\n**Available Images:**\n{available_list}{more_available}\n\nPlease specify one using the image parameter (e.g., image="ubuntu-22.04").'
                    }
                except Exception as e:
                    logger.error(f"Failed to retrieve available images: {e}")
                    return {
                        'success': False,
                        'message': 'Image parameter is required for VM creation. Please specify an image name (e.g., ubuntu-22.04, rocky-9, centos-8).'
                    }
            
            # Find flavor using secure project-scoped lookup
            flavor = find_resource_by_name_or_id(
                conn.compute.flavors(), 
                flavor_name, 
                "Flavor"
            )

            if not flavor:
                return {
                    'success': False,
                    'message': f'Flavor "{flavor_name}" not found or not accessible in current project'
                }
            
            # Find image using secure project-scoped lookup
            image = find_resource_by_name_or_id(
                conn.image.images(), 
                image_name, 
                "Image"
            )

            if not image:
                return {
                    'success': False,
                    'message': f'Image "{image_name}" not found or not accessible in current project'
                }
            
            # Handle networks with secure project-scoped lookup
            networks = []
            if network_names:
                if isinstance(network_names, str):
                    network_names = [network_names]
                    
                for network_name in network_names:
                    network = find_resource_by_name_or_id(
                        conn.network.networks(), 
                        network_name, 
                        "Network"
                    )
                    
                    if network:
                        networks.append({'uuid': network.id})
                    else:
                        return {
                            'success': False,
                            'message': f'Network "{network_name}" not found or not accessible in current project'
                        }
            
            # Optional parameters
            key_name = kwargs.get('key_name', kwargs.get('keypair'))
            security_groups = kwargs.get('security_groups', kwargs.get('security_group'))
            availability_zone = kwargs.get('availability_zone', kwargs.get('az'))
            user_data = kwargs.get('user_data')
            metadata = kwargs.get('metadata', {})
            
            # Handle security groups
            if security_groups:
                if isinstance(security_groups, str):
                    security_groups = [security_groups]
            
            create_params = {
                'name': instance_name,
                'flavor_id': flavor.id,
                'image_id': image.id
            }
            
            if networks:
                create_params['networks'] = networks
            if key_name:
                create_params['key_name'] = key_name
            if security_groups:
                create_params['security_groups'] = [{'name': sg} for sg in security_groups]
            if availability_zone:
                create_params['availability_zone'] = availability_zone
            if user_data:
                create_params['user_data'] = user_data
            if metadata:
                create_params['metadata'] = metadata
            
            try:
                server = conn.compute.create_server(**create_params)
                
                return {
                    'success': True,
                    'message': f'Instance "{instance_name}" creation started',
                    'instance': {
                        'id': server.id,
                        'name': getattr(server, 'name', 'unnamed'),
                        'status': getattr(server, 'status', 'unknown'),
                        'flavor': {'id': flavor.id, 'name': getattr(flavor, 'name', 'unknown')},
                        'image': {'id': image.id, 'name': getattr(image, 'name', 'unknown')}
                    }
                }
            except Exception as create_error:
                logger.error(f"Failed to create instance '{instance_name}': {create_error}")
                return {
                    'success': False,
                    'message': f'Instance creation failed: {str(create_error)}'
                }
            
        # Find existing instance for other actions using secure lookup
        server = find_resource_by_name_or_id(
            conn.compute.servers(), 
            instance_name, 
            "Instance"
        )
        
        if not server:
            return {
                'success': False,
                'message': f'Instance "{instance_name}" not found or not accessible in current project'
            }
        
        if action.lower() in ['start', 'boot', 'power_on']:
            conn.compute.start_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" started'
            }
            
        elif action.lower() in ['stop', 'shutdown', 'power_off']:
            conn.compute.stop_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" stopped'
            }
            
        elif action.lower() in ['reboot', 'restart']:
            reboot_type = kwargs.get('type', 'SOFT')  # SOFT or HARD
            conn.compute.reboot_server(server, reboot_type)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" reboot initiated ({reboot_type})'
            }
            
        elif action.lower() == 'pause':
            conn.compute.pause_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" paused'
            }
            
        elif action.lower() == 'unpause':
            conn.compute.unpause_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" unpaused'
            }
            
        elif action.lower() == 'suspend':
            conn.compute.suspend_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" suspended'
            }
            
        elif action.lower() == 'resume':
            conn.compute.resume_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" resumed'
            }
            
        elif action.lower() in ['delete', 'terminate']:
            force = kwargs.get('force', False)
            if force:
                conn.compute.force_delete_server(server)
                return {
                    'success': True,
                    'message': f'Instance "{instance_name}" force deleted'
                }
            else:
                conn.compute.delete_server(server)
                return {
                    'success': True,
                    'message': f'Instance "{instance_name}" deleted'
                }
                
        elif action.lower() == 'resize':
            new_flavor_name = kwargs.get('flavor', kwargs.get('new_flavor'))
            if not new_flavor_name:
                return {
                    'success': False,
                    'message': 'flavor parameter is required for resize action'
                }
            
            # Find new flavor
            new_flavor = None
            for flv in conn.compute.flavors():
                if getattr(flv, 'name', '') == new_flavor_name or flv.id == new_flavor_name:
                    new_flavor = flv
                    break
            
            if not new_flavor:
                return {
                    'success': False,
                    'message': f'New flavor "{new_flavor_name}" not found'
                }
            
            conn.compute.resize_server(server, new_flavor.id)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" resize initiated to {new_flavor_name}'
            }
            
        elif action.lower() == 'confirm_resize':
            conn.compute.confirm_server_resize(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" resize confirmed'
            }
            
        elif action.lower() == 'revert_resize':
            conn.compute.revert_server_resize(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" resize reverted'
            }
            
        elif action.lower() == 'snapshot':
            snapshot_name = kwargs.get('snapshot_name', f'{instance_name}-snapshot')
            metadata = kwargs.get('metadata', {})
            
            snapshot = conn.compute.create_server_image(server, name=snapshot_name, metadata=metadata)
            return {
                'success': True,
                'message': f'Snapshot "{snapshot_name}" creation started',
                'snapshot_id': snapshot
            }
            
        elif action.lower() == 'console':
            console_type = kwargs.get('type', 'novnc')  # novnc, xvpvnc, spice-html5, rdp-html5, serial
            
            try:
                console = conn.compute.get_server_console_url(server, console_type)
                return {
                    'success': True,
                    'console': {
                        'type': console_type,
                        'url': console.get('url', 'unknown')
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to get console URL: {str(e)}'
                }
                
        elif action.lower() == 'shelve':
            conn.compute.shelve_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" shelved'
            }
            
        elif action.lower() == 'unshelve':
            conn.compute.unshelve_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" unshelved'
            }
            
        elif action.lower() == 'lock':
            conn.compute.lock_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" locked'
            }
            
        elif action.lower() == 'unlock':
            conn.compute.unlock_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" unlocked'
            }
            
        elif action.lower() == 'rescue':
            rescue_image_id = kwargs.get('rescue_image_id')
            admin_pass = kwargs.get('admin_pass')
            
            rescue_params = {}
            if rescue_image_id:
                rescue_params['image_id'] = rescue_image_id
            if admin_pass:
                rescue_params['admin_pass'] = admin_pass
                
            conn.compute.rescue_server(server, **rescue_params)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" put in rescue mode'
            }
            
        elif action.lower() == 'unrescue':
            conn.compute.unrescue_server(server)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" restored from rescue mode'
            }
            
        elif action.lower() == 'rebuild':
            image_name = kwargs.get('image', kwargs.get('image_name'))
            if not image_name:
                return {
                    'success': False,
                    'message': 'image parameter is required for rebuild action'
                }
                
            # Find image
            image = None
            for img in conn.image.images():
                if getattr(img, 'name', '') == image_name or img.id == image_name:
                    image = img
                    break
            
            if not image:
                return {
                    'success': False,
                    'message': f'Image "{image_name}" not found'
                }
                
            rebuild_params = {
                'image_id': image.id,
                'name': kwargs.get('new_name', getattr(server, 'name', '')),
                'admin_pass': kwargs.get('admin_pass'),
                'preserve_ephemeral': kwargs.get('preserve_ephemeral', False),
                'metadata': kwargs.get('metadata', {}),
                'personality': kwargs.get('personality', [])
            }
            
            # Remove None values
            rebuild_params = {k: v for k, v in rebuild_params.items() if v is not None}
            
            conn.compute.rebuild_server(server, **rebuild_params)
            return {
                'success': True,
                'message': f'Instance "{instance_name}" rebuild initiated with image {image_name}'
            }
                
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, start, stop, reboot, pause, unpause, suspend, resume, delete, resize, confirm_resize, revert_resize, snapshot, console, shelve, unshelve, lock, unlock, rescue, unrescue, rebuild, list'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage instance: {e}")
        return {
            'success': False,
            'message': f'Failed to manage instance: {str(e)}',
            'error': str(e)
        }


def get_flavor_list() -> List[Dict[str, Any]]:
    """
    Get list of available flavors with detailed information.
    
    Returns:
        List of flavor dictionaries
    """
    try:
        conn = _get_nova_mariadb_connection()
        try:
            with conn.cursor() as cur:
                columns = _table_columns(cur, "instance_types")
                if not columns:
                    raise RuntimeError("MariaDB table 'instance_types' is not available")

                deleted_expr = _column_expr("it", columns, "deleted", default="0")
                public_expr = _column_expr("it", columns, "is_public", default="1")
                desc_expr = _column_expr("it", columns, "description", default="''")
                cur.execute(
                    "SELECT it.id, it.name, it.vcpus, it.memory_mb, it.root_gb, "
                    "it.ephemeral_gb, it.swap, it.rxtx_factor, "
                    f"{public_expr} AS is_public, {desc_expr} AS description "
                    "FROM instance_types it "
                    f"WHERE ({deleted_expr} = 0 OR {deleted_expr} = '0') "
                    "ORDER BY it.name ASC"
                )
                rows = cur.fetchall()

                specs_by_flavor: Dict[Any, Dict[str, Any]] = {}
                flavor_ids = [row["id"] for row in rows if row.get("id")]
                if flavor_ids and _table_exists(cur, "instance_type_extra_specs"):
                    spec_columns = _table_columns(cur, "instance_type_extra_specs")
                    if {"instance_type_id", "key", "value"}.issubset(spec_columns):
                        placeholders = ",".join(["%s"] * len(flavor_ids))
                        spec_deleted_expr = _column_expr("", spec_columns, "deleted", default="0")
                        cur.execute(
                            f"SELECT instance_type_id, `key`, value FROM instance_type_extra_specs "
                            f"WHERE instance_type_id IN ({placeholders}) "
                            f"AND ({spec_deleted_expr} = 0 OR {spec_deleted_expr} = '0')",
                            flavor_ids,
                        )
                        for spec in cur.fetchall():
                            specs_by_flavor.setdefault(spec["instance_type_id"], {})[spec["key"]] = spec.get("value")

                return [
                    {
                        "id": row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "vcpus": row.get("vcpus") or 0,
                        "ram": row.get("memory_mb") or 0,
                        "disk": row.get("root_gb") or 0,
                        "ephemeral": row.get("ephemeral_gb") or 0,
                        "swap": row.get("swap") or 0,
                        "rxtx_factor": row.get("rxtx_factor") or 1.0,
                        "is_public": _bool_value(row.get("is_public")),
                        "extra_specs": specs_by_flavor.get(row.get("id"), {}),
                        "description": row.get("description") or "",
                        "data_source": "mariadb",
                    }
                    for row in rows
                ]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get flavor list: {e}")
        return [
            {
                'id': 'flavor-1', 'name': 'demo-flavor', 'vcpus': 1, 'ram': 512, 
                'disk': 1, 'is_public': True, 'error': str(e)
            }
        ]


def get_server_events(instance_name: str, limit: int = 50) -> Dict[str, Any]:
    """
    Get server action/event history.
    
    Args:
        instance_name: Name or ID of the server
        limit: Maximum number of events to return
        
    Returns:
        Dictionary containing server events
    """
    try:
        if limit > 200:
            limit = 200
        if limit < 1:
            limit = 1

        conn = _get_nova_mariadb_connection()
        try:
            with conn.cursor() as cur:
                instance = get_instance_by_id(instance_name) or get_instance_by_name(instance_name)
                if not instance:
                    return {
                        'success': False,
                        'message': f'Server "{instance_name}" not found',
                        'events': []
                    }
                server_id = instance.get("id")

                action_columns = _table_columns(cur, "instance_actions")
                if not action_columns:
                    raise RuntimeError("MariaDB table 'instance_actions' is not available")

                events_by_request: Dict[str, List[Dict[str, Any]]] = {}
                if _table_exists(cur, "instance_actions_events"):
                    event_columns = _table_columns(cur, "instance_actions_events")
                    if {"action_id", "event"}.issubset(event_columns):
                        cur.execute(
                            "SELECT iae.action_id, iae.event, iae.start_time, iae.finish_time, "
                            "iae.result, iae.traceback "
                            "FROM instance_actions_events iae "
                            "JOIN instance_actions ia ON ia.id = iae.action_id "
                            "WHERE ia.instance_uuid = %s "
                            "ORDER BY iae.start_time DESC",
                            [server_id],
                        )
                        for row in cur.fetchall():
                            events_by_request.setdefault(str(row.get("action_id")), []).append({
                                "event": row.get("event") or "unknown",
                                "start_time": _str_time(row.get("start_time")),
                                "finish_time": _str_time(row.get("finish_time")) if row.get("finish_time") else None,
                                "result": row.get("result") or "unknown",
                                "traceback": row.get("traceback"),
                            })

                cur.execute(
                    "SELECT id, action, instance_uuid, request_id, user_id, project_id, "
                    "start_time, finish_time, message "
                    "FROM instance_actions WHERE instance_uuid = %s "
                    "ORDER BY start_time DESC LIMIT %s",
                    [server_id, limit],
                )
                events = [
                    {
                        "action": row.get("action") or "unknown",
                        "instance_uuid": row.get("instance_uuid") or server_id,
                        "request_id": row.get("request_id") or "unknown",
                        "user_id": row.get("user_id") or "unknown",
                        "project_id": row.get("project_id") or "unknown",
                        "start_time": _str_time(row.get("start_time")),
                        "finish_time": _str_time(row.get("finish_time")) if row.get("finish_time") else None,
                        "message": row.get("message") or "",
                        "details": {},
                        "events": events_by_request.get(str(row.get("id")), []),
                        "data_source": "mariadb",
                    }
                    for row in cur.fetchall()
                ]

                return {
                    'success': True,
                    'server_name': instance.get("name", "unnamed"),
                    'server_id': server_id,
                    'events': events,
                    'count': len(events)
                }
        finally:
            conn.close()
        
    except Exception as e:
        logger.error(f"Failed to get server events: {e}")
        return {
            'success': False,
            'message': f'Failed to get server events for "{instance_name}": {str(e)}',
            'events': [],
            'error': str(e)
        }


def get_server_groups() -> List[Dict[str, Any]]:
    """
    Get list of server groups.
    
    Returns:
        List of server group dictionaries
    """
    try:
        conn = _get_nova_mariadb_connection()
        try:
            with conn.cursor() as cur:
                columns = _table_columns(cur, "instance_groups")
                if not columns:
                    raise RuntimeError("MariaDB table 'instance_groups' is not available")

                deleted_expr = _column_expr("ig", columns, "deleted", default="0")
                cur.execute(
                    "SELECT ig.id, ig.uuid, ig.name, ig.project_id, ig.user_id, "
                    "ig.created_at, ig.updated_at "
                    "FROM instance_groups ig "
                    f"WHERE ({deleted_expr} = 0 OR {deleted_expr} = '0') "
                    "ORDER BY ig.created_at DESC"
                )
                rows = cur.fetchall()
                group_ids = [row["id"] for row in rows if row.get("id")]

                members_by_group: Dict[Any, List[str]] = {}
                if group_ids and _table_exists(cur, "instance_group_member"):
                    member_columns = _table_columns(cur, "instance_group_member")
                    if {"group_id", "instance_uuid"}.issubset(member_columns):
                        placeholders = ",".join(["%s"] * len(group_ids))
                        member_deleted_expr = _column_expr("", member_columns, "deleted", default="0")
                        cur.execute(
                            f"SELECT group_id, instance_uuid FROM instance_group_member "
                            f"WHERE group_id IN ({placeholders}) "
                            f"AND ({member_deleted_expr} = 0 OR {member_deleted_expr} = '0')",
                            group_ids,
                        )
                        for row in cur.fetchall():
                            members_by_group.setdefault(row["group_id"], []).append(row["instance_uuid"])

                policies_by_group: Dict[Any, List[str]] = {}
                if group_ids and _table_exists(cur, "instance_group_policy"):
                    policy_columns = _table_columns(cur, "instance_group_policy")
                    if {"group_id", "policy"}.issubset(policy_columns):
                        placeholders = ",".join(["%s"] * len(group_ids))
                        policy_deleted_expr = _column_expr("", policy_columns, "deleted", default="0")
                        cur.execute(
                            f"SELECT group_id, policy FROM instance_group_policy "
                            f"WHERE group_id IN ({placeholders}) "
                            f"AND ({policy_deleted_expr} = 0 OR {policy_deleted_expr} = '0')",
                            group_ids,
                        )
                        for row in cur.fetchall():
                            policies_by_group.setdefault(row["group_id"], []).append(row["policy"])

                server_groups = []
                for row in rows:
                    members = members_by_group.get(row.get("id"), [])
                    server_groups.append({
                        "id": row.get("uuid") or row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "policies": policies_by_group.get(row.get("id"), []),
                        "members": members,
                        "member_count": len(members),
                        "metadata": {},
                        "project_id": row.get("project_id") or "unknown",
                        "user_id": row.get("user_id") or "unknown",
                        "created_at": _str_time(row.get("created_at")),
                        "updated_at": _str_time(row.get("updated_at")),
                        "data_source": "mariadb",
                    })
                return server_groups
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get server groups: {e}")
        return []


def set_server_group(group_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage server groups (create, delete, list, show).
    
    Args:
        group_name: Name of the server group
        action: Action to perform (create, delete, list, show)
        **kwargs: Additional parameters
        
    Returns:
        Result of the server group operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'create':
            policies = kwargs.get('policies', kwargs.get('policy', ['affinity']))
            if isinstance(policies, str):
                policies = [policies]
                
            # Validate policies
            valid_policies = ['affinity', 'anti-affinity', 'soft-affinity', 'soft-anti-affinity']
            for policy in policies:
                if policy not in valid_policies:
                    return {
                        'success': False,
                        'message': f'Invalid policy "{policy}". Valid policies: {valid_policies}'
                    }
            
            server_group = conn.compute.create_server_group(
                name=group_name,
                policies=policies
            )
            
            return {
                'success': True,
                'message': f'Server group "{group_name}" created',
                'server_group': {
                    'id': server_group.id,
                    'name': getattr(server_group, 'name', 'unnamed'),
                    'policies': getattr(server_group, 'policies', policies),
                    'members': getattr(server_group, 'members', [])
                }
            }
            
        elif action.lower() == 'delete':
            # Find server group using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id
            
            server_group = find_resource_by_name_or_id(
                conn.compute.server_groups(), 
                group_name, 
                "Server Group"
            )

            if not server_group:
                return {
                    'success': False,
                    'message': f'Server group "{group_name}" not found or not accessible in current project'
                }

            conn.compute.delete_server_group(server_group)
            return {
                'success': True,
                'message': f'Server group "{group_name}" deleted'
            }
            
        elif action.lower() == 'list':
            return {
                'success': True,
                'server_groups': get_server_groups()
            }
            
        elif action.lower() == 'show':
            # Find server group
            server_group = None
            for sg in conn.compute.server_groups():
                if getattr(sg, 'name', '') == group_name or sg.id == group_name:
                    server_group = sg
                    break
            
            if not server_group:
                return {
                    'success': False,
                    'message': f'Server group "{group_name}" not found'
                }
            
            return {
                'success': True,
                'server_group': {
                    'id': server_group.id,
                    'name': getattr(server_group, 'name', 'unnamed'),
                    'policies': getattr(server_group, 'policies', []),
                    'members': getattr(server_group, 'members', []),
                    'metadata': getattr(server_group, 'metadata', {}),
                    'project_id': getattr(server_group, 'project_id', 'unknown'),
                    'user_id': getattr(server_group, 'user_id', 'unknown')
                }
            }
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete, list, show'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server group: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server group: {str(e)}',
            'error': str(e)
        }


def set_server_network(instance_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage server network operations (add network, remove network, add port, remove port).
    
    Args:
        instance_name: Name or ID of the server
        action: Action to perform (add_network, remove_network, add_port, remove_port)
        **kwargs: Additional parameters
        
    Returns:
        Result of the network operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server
        server = None
        for srv in conn.compute.servers():
            if getattr(srv, 'name', '') == instance_name or srv.id == instance_name:
                server = srv
                break
        
        if not server:
            return {
                'success': False,
                'message': f'Server "{instance_name}" not found'
            }
        
        if action.lower() == 'add_network':
            network_name = kwargs.get('network', kwargs.get('network_name'))
            if not network_name:
                return {
                    'success': False,
                    'message': 'network parameter is required for add_network action'
                }
            
            # Find network
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
            
            # Create port and attach to server
            port_params = {
                'network_id': network.id,
                'name': f'{instance_name}-port-{network.id[:8]}'
            }
            
            # Optional fixed IP
            fixed_ip = kwargs.get('fixed_ip')
            if fixed_ip:
                port_params['fixed_ips'] = [{'ip_address': fixed_ip}]
            
            port = conn.network.create_port(**port_params)
            conn.compute.create_server_interface(server, port_id=port.id)
            
            return {
                'success': True,
                'message': f'Network "{network_name}" added to server "{instance_name}"',
                'port_id': port.id
            }
            
        elif action.lower() == 'remove_network':
            network_name = kwargs.get('network', kwargs.get('network_name'))
            if not network_name:
                return {
                    'success': False,
                    'message': 'network parameter is required for remove_network action'
                }
            
            # Find network
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
            
            # Get server interfaces and remove ports from this network
            removed_ports = []
            for interface in conn.compute.server_interfaces(server):
                if getattr(interface, 'net_id', '') == network.id:
                    conn.compute.delete_server_interface(interface, server)
                    removed_ports.append(interface.port_id)
            
            if not removed_ports:
                return {
                    'success': False,
                    'message': f'No interfaces found for network "{network_name}" on server "{instance_name}"'
                }
            
            return {
                'success': True,
                'message': f'Network "{network_name}" removed from server "{instance_name}"',
                'removed_ports': removed_ports
            }
            
        elif action.lower() == 'add_port':
            port_id = kwargs.get('port', kwargs.get('port_id'))
            if not port_id:
                return {
                    'success': False,
                    'message': 'port parameter is required for add_port action'
                }
            
            # Check if port exists
            try:
                port = conn.network.get_port(port_id)
                if not port:
                    return {
                        'success': False,
                        'message': f'Port "{port_id}" not found'
                    }
            except Exception:
                return {
                    'success': False,
                    'message': f'Port "{port_id}" not found'
                }
            
            conn.compute.create_server_interface(server, port_id=port_id)
            
            return {
                'success': True,
                'message': f'Port "{port_id}" added to server "{instance_name}"'
            }
            
        elif action.lower() == 'remove_port':
            port_id = kwargs.get('port', kwargs.get('port_id'))
            if not port_id:
                return {
                    'success': False,
                    'message': 'port parameter is required for remove_port action'
                }
            
            # Find interface with this port
            interface = None
            for intf in conn.compute.server_interfaces(server):
                if getattr(intf, 'port_id', '') == port_id:
                    interface = intf
                    break
            
            if not interface:
                return {
                    'success': False,
                    'message': f'Port "{port_id}" not found on server "{instance_name}"'
                }
            
            conn.compute.delete_server_interface(interface, server)
            
            return {
                'success': True,
                'message': f'Port "{port_id}" removed from server "{instance_name}"'
            }
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: add_network, remove_network, add_port, remove_port'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server network: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server network: {str(e)}',
            'error': str(e)
        }


def set_server_floating_ip(instance_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage server floating IP operations (add, remove).
    
    Args:
        instance_name: Name or ID of the server
        action: Action to perform (add, remove)
        **kwargs: Additional parameters
        
    Returns:
        Result of the floating IP operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server
        server = None
        for srv in conn.compute.servers():
            if getattr(srv, 'name', '') == instance_name or srv.id == instance_name:
                server = srv
                break
        
        if not server:
            return {
                'success': False,
                'message': f'Server "{instance_name}" not found'
            }
        
        if action.lower() == 'add':
            floating_ip = kwargs.get('floating_ip', kwargs.get('ip'))
            fixed_ip = kwargs.get('fixed_ip')
            
            if not floating_ip:
                return {
                    'success': False,
                    'message': 'floating_ip parameter is required for add action'
                }
            
            # Find floating IP
            fip_obj = None
            for fip in conn.network.ips():
                if getattr(fip, 'floating_ip_address', '') == floating_ip or fip.id == floating_ip:
                    fip_obj = fip
                    break
            
            if not fip_obj:
                return {
                    'success': False,
                    'message': f'Floating IP "{floating_ip}" not found'
                }
            
            # Get server ports to find target fixed IP
            if not fixed_ip:
                # Use first available private IP
                addresses = getattr(server, 'addresses', {})
                for network_name, addrs in addresses.items():
                    for addr in addrs:
                        if addr.get('OS-EXT-IPS:type') == 'fixed':
                            fixed_ip = addr['addr']
                            break
                    if fixed_ip:
                        break
            
            if not fixed_ip:
                return {
                    'success': False,
                    'message': 'Could not determine fixed IP address. Please specify fixed_ip parameter'
                }
            
            # Find port with this fixed IP
            port_id = None
            for interface in conn.compute.server_interfaces(server):
                port = conn.network.get_port(interface.port_id)
                for fixed_ip_info in getattr(port, 'fixed_ips', []):
                    if fixed_ip_info.get('ip_address') == fixed_ip:
                        port_id = port.id
                        break
                if port_id:
                    break
            
            if not port_id:
                return {
                    'success': False,
                    'message': f'Could not find port with fixed IP "{fixed_ip}" on server'
                }
            
            # Associate floating IP
            conn.network.update_ip(fip_obj, port_id=port_id, fixed_ip_address=fixed_ip)
            
            return {
                'success': True,
                'message': f'Floating IP "{floating_ip}" added to server "{instance_name}" (fixed IP: {fixed_ip})'
            }
            
        elif action.lower() == 'remove':
            floating_ip = kwargs.get('floating_ip', kwargs.get('ip'))
            
            if not floating_ip:
                return {
                    'success': False,
                    'message': 'floating_ip parameter is required for remove action'
                }
            
            # Find floating IP
            fip_obj = None
            for fip in conn.network.ips():
                if getattr(fip, 'floating_ip_address', '') == floating_ip or fip.id == floating_ip:
                    fip_obj = fip
                    break
            
            if not fip_obj:
                return {
                    'success': False,
                    'message': f'Floating IP "{floating_ip}" not found'
                }
            
            # Disassociate floating IP
            conn.network.update_ip(fip_obj, port_id=None, fixed_ip_address=None)
            
            return {
                'success': True,
                'message': f'Floating IP "{floating_ip}" removed from server "{instance_name}"'
            }
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: add, remove'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server floating IP: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server floating IP: {str(e)}',
            'error': str(e)
        }


def set_server_fixed_ip(instance_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage server fixed IP operations (add, remove).
    
    Args:
        instance_name: Name or ID of the server
        action: Action to perform (add, remove)
        **kwargs: Additional parameters
        
    Returns:
        Result of the fixed IP operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server
        server = None
        for srv in conn.compute.servers():
            if getattr(srv, 'name', '') == instance_name or srv.id == instance_name:
                server = srv
                break
        
        if not server:
            return {
                'success': False,
                'message': f'Server "{instance_name}" not found'
            }
        
        if action.lower() == 'add':
            network_name = kwargs.get('network', kwargs.get('network_name'))
            fixed_ip = kwargs.get('fixed_ip', kwargs.get('ip'))
            
            if not network_name:
                return {
                    'success': False,
                    'message': 'network parameter is required for add action'
                }
            
            # Find network
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
            
            # Create port with fixed IP
            port_params = {
                'network_id': network.id,
                'name': f'{instance_name}-fixed-ip-port'
            }
            
            if fixed_ip:
                port_params['fixed_ips'] = [{'ip_address': fixed_ip}]
            
            port = conn.network.create_port(**port_params)
            conn.compute.create_server_interface(server, port_id=port.id)
            
            # Get assigned IP
            assigned_ip = port.fixed_ips[0]['ip_address'] if port.fixed_ips else 'unknown'
            
            return {
                'success': True,
                'message': f'Fixed IP "{assigned_ip}" added to server "{instance_name}" on network "{network_name}"',
                'fixed_ip': assigned_ip,
                'port_id': port.id
            }
            
        elif action.lower() == 'remove':
            fixed_ip = kwargs.get('fixed_ip', kwargs.get('ip'))
            
            if not fixed_ip:
                return {
                    'success': False,
                    'message': 'fixed_ip parameter is required for remove action'
                }
            
            # Find port with this fixed IP
            port_to_remove = None
            for interface in conn.compute.server_interfaces(server):
                port = conn.network.get_port(interface.port_id)
                for fixed_ip_info in getattr(port, 'fixed_ips', []):
                    if fixed_ip_info.get('ip_address') == fixed_ip:
                        port_to_remove = interface
                        break
                if port_to_remove:
                    break
            
            if not port_to_remove:
                return {
                    'success': False,
                    'message': f'Fixed IP "{fixed_ip}" not found on server "{instance_name}"'
                }
            
            # Remove interface and port
            conn.compute.delete_server_interface(port_to_remove, server)
            
            return {
                'success': True,
                'message': f'Fixed IP "{fixed_ip}" removed from server "{instance_name}"'
            }
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: add, remove'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server fixed IP: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server fixed IP: {str(e)}',
            'error': str(e)
        }


def set_server_security_group(instance_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage server security group operations (add, remove).
    
    Args:
        instance_name: Name or ID of the server
        action: Action to perform (add, remove)
        **kwargs: Additional parameters
        
    Returns:
        Result of the security group operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server
        server = None
        for srv in conn.compute.servers():
            if getattr(srv, 'name', '') == instance_name or srv.id == instance_name:
                server = srv
                break
        
        if not server:
            return {
                'success': False,
                'message': f'Server "{instance_name}" not found'
            }
        
        security_group = kwargs.get('security_group', kwargs.get('group'))
        if not security_group:
            return {
                'success': False,
                'message': 'security_group parameter is required'
            }
        
        # Find security group
        sg_obj = None
        for sg in conn.network.security_groups():
            if getattr(sg, 'name', '') == security_group or sg.id == security_group:
                sg_obj = sg
                break
        
        if not sg_obj:
            return {
                'success': False,
                'message': f'Security group "{security_group}" not found'
            }
        
        if action.lower() == 'add':
            conn.compute.add_security_group_to_server(server, sg_obj)
            return {
                'success': True,
                'message': f'Security group "{security_group}" added to server "{instance_name}"'
            }
            
        elif action.lower() == 'remove':
            conn.compute.remove_security_group_from_server(server, sg_obj)
            return {
                'success': True,
                'message': f'Security group "{security_group}" removed from server "{instance_name}"'
            }
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: add, remove'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server security group: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server security group: {str(e)}',
            'error': str(e)
        }
    """
    Manage server groups.
    
    Args:
        group_name: Name of the server group
        action: Action to perform (list, create, delete, show)
        **kwargs: Additional parameters
        
    Returns:
        Result of the server group operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            server_groups = get_server_groups()
            return {
                'success': True,
                'server_groups': server_groups,
                'count': len(server_groups)
            }
            
        elif action.lower() == 'create':
            policies = kwargs.get('policies', ['anti-affinity'])
            if isinstance(policies, str):
                policies = [policies]
            
            try:
                group = conn.compute.create_server_group(
                    name=group_name,
                    policies=policies
                )
                
                return {
                    'success': True,
                    'message': f'Server group "{group_name}" created',
                    'server_group': {
                        'id': group.id,
                        'name': getattr(group, 'name', 'unnamed'),
                        'policies': list(getattr(group, 'policies', [])),
                        'members': []
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create server group: {str(e)}'
                }
                
        elif action.lower() == 'delete':
            # Find the server group
            server_group = None
            for group in conn.compute.server_groups():
                if getattr(group, 'name', '') == group_name or group.id == group_name:
                    server_group = group
                    break
            
            if not server_group:
                return {
                    'success': False,
                    'message': f'Server group "{group_name}" not found'
                }
            
            try:
                conn.compute.delete_server_group(server_group)
                return {
                    'success': True,
                    'message': f'Server group "{group_name}" deleted'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to delete server group: {str(e)}'
                }
                
        elif action.lower() == 'show':
            # Find and show specific server group
            server_group = None
            for group in conn.compute.server_groups():
                if getattr(group, 'name', '') == group_name or group.id == group_name:
                    server_group = group
                    break
            
            if not server_group:
                return {
                    'success': False,
                    'message': f'Server group "{group_name}" not found'
                }
            
            members = getattr(server_group, 'members', []) or []
            return {
                'success': True,
                'server_group': {
                    'id': server_group.id,
                    'name': getattr(server_group, 'name', 'unnamed'),
                    'policies': list(getattr(server_group, 'policies', [])),
                    'members': list(members),
                    'member_count': len(members),
                    'metadata': getattr(server_group, 'metadata', {}),
                    'project_id': getattr(server_group, 'project_id', 'unknown'),
                    'user_id': getattr(server_group, 'user_id', 'unknown'),
                    'created_at': str(getattr(server_group, 'created_at', 'unknown')),
                    'updated_at': str(getattr(server_group, 'updated_at', 'unknown'))
                }
            }
            
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, create, delete, show'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server group: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server group: {str(e)}',
            'error': str(e)
        }


def set_flavor(flavor_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage flavors (create, delete, set properties).
    
    Args:
        flavor_name: Name of the flavor
        action: Action to perform
        **kwargs: Additional parameters
        
    Returns:
        Result of the flavor operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            flavors = get_flavor_list()
            return {
                'success': True,
                'flavors': flavors,
                'count': len(flavors)
            }
            
        elif action.lower() == 'create':
            # Required parameters
            vcpus = kwargs.get('vcpus', kwargs.get('cpu', 1))
            ram = kwargs.get('ram', kwargs.get('memory', 512))  # MB
            disk = kwargs.get('disk', kwargs.get('root_disk', 1))  # GB
            
            # Optional parameters
            ephemeral = kwargs.get('ephemeral', 0)
            swap = kwargs.get('swap', 0)
            rxtx_factor = kwargs.get('rxtx_factor', 1.0)
            is_public = kwargs.get('is_public', True)
            flavor_id = kwargs.get('flavor_id', kwargs.get('id'))
            description = kwargs.get('description', '')
            
            try:
                create_params = {
                    'name': flavor_name,
                    'ram': int(ram),
                    'vcpus': int(vcpus),
                    'disk': int(disk),
                    'ephemeral': int(ephemeral),
                    'swap': int(swap),
                    'rxtx_factor': float(rxtx_factor),
                    'is_public': bool(is_public)
                }
                
                if flavor_id:
                    create_params['flavorid'] = str(flavor_id)
                if description:
                    create_params['description'] = description
                
                flavor = conn.compute.create_flavor(**create_params)
                
                # Set extra specs if provided
                extra_specs = kwargs.get('extra_specs', {})
                if extra_specs and isinstance(extra_specs, dict):
                    try:
                        conn.compute.create_flavor_extra_specs(flavor, extra_specs)
                    except Exception as e:
                        logger.warning(f"Failed to set extra specs: {e}")
                
                return {
                    'success': True,
                    'message': f'Flavor "{flavor_name}" created',
                    'flavor': {
                        'id': flavor.id,
                        'name': getattr(flavor, 'name', 'unnamed'),
                        'vcpus': getattr(flavor, 'vcpus', 0),
                        'ram': getattr(flavor, 'ram', 0),
                        'disk': getattr(flavor, 'disk', 0),
                        'is_public': getattr(flavor, 'is_public', True)
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create flavor: {str(e)}'
                }
                
        elif action.lower() == 'delete':
            # Find the flavor using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id
            
            flavor = find_resource_by_name_or_id(
                conn.compute.flavors(), 
                flavor_name, 
                "Flavor"
            )

            if not flavor:
                return {
                    'success': False,
                    'message': f'Flavor "{flavor_name}" not found or not accessible in current project'
                }

            try:
                conn.compute.delete_flavor(flavor)
                return {
                    'success': True,
                    'message': f'Flavor "{flavor_name}" deleted'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to delete flavor: {str(e)}'
                }
                
        elif action.lower() == 'set_extra_specs':
            # Find the flavor
            flavor = None
            for flv in conn.compute.flavors():
                if getattr(flv, 'name', '') == flavor_name or flv.id == flavor_name:
                    flavor = flv
                    break
            
            if not flavor:
                return {
                    'success': False,
                    'message': f'Flavor "{flavor_name}" not found'
                }
            
            extra_specs = kwargs.get('extra_specs', {})
            if not extra_specs or not isinstance(extra_specs, dict):
                return {
                    'success': False,
                    'message': 'extra_specs parameter is required and must be a dictionary'
                }
            
            try:
                conn.compute.create_flavor_extra_specs(flavor, extra_specs)
                return {
                    'success': True,
                    'message': f'Extra specs set for flavor "{flavor_name}"',
                    'extra_specs': extra_specs
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to set extra specs: {str(e)}'
                }
                
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, create, delete, set_extra_specs'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage flavor: {e}")
        return {
            'success': False,
            'message': f'Failed to manage flavor: {str(e)}',
            'error': str(e)
        }


def set_server_migration(instance_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage server migration operations (migrate, evacuate, confirm, revert, etc.).
    
    Args:
        instance_name: Name or ID of the server
        action: Action to perform (migrate, evacuate, confirm, revert, list, show, abort, force_complete)
        **kwargs: Additional parameters
        
    Returns:
        Result of the migration operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server for most actions
        if action.lower() not in ['list']:
            server = None
            for srv in conn.compute.servers():
                if getattr(srv, 'name', '') == instance_name or srv.id == instance_name:
                    server = srv
                    break
            
            if not server:
                return {
                    'success': False,
                    'message': f'Server "{instance_name}" not found'
                }
        
        if action.lower() == 'migrate':
            host = kwargs.get('host')
            block_migration = kwargs.get('block_migration', 'auto')
            
            # Live migrate server
            migrate_params = {}
            if host:
                migrate_params['host'] = host
            if block_migration != 'auto':
                migrate_params['block_migration'] = block_migration
            
            conn.compute.live_migrate_server(server, **migrate_params)
            
            return {
                'success': True,
                'message': f'Live migration initiated for server "{instance_name}"' + (f' to host "{host}"' if host else '')
            }
            
        elif action.lower() == 'evacuate':
            host = kwargs.get('host')
            admin_pass = kwargs.get('admin_pass')
            on_shared_storage = kwargs.get('on_shared_storage', False)
            
            evacuate_params = {}
            if host:
                evacuate_params['host'] = host
            if admin_pass:
                evacuate_params['admin_pass'] = admin_pass
            evacuate_params['on_shared_storage'] = on_shared_storage
            
            conn.compute.evacuate_server(server, **evacuate_params)
            
            return {
                'success': True,
                'message': f'Evacuation initiated for server "{instance_name}"' + (f' to host "{host}"' if host else '')
            }
            
        elif action.lower() == 'confirm':
            # This is for confirming resize, but can be extended for migration confirm
            conn.compute.confirm_server_resize(server)
            return {
                'success': True,
                'message': f'Migration/resize confirmed for server "{instance_name}"'
            }
            
        elif action.lower() == 'revert':
            # This is for reverting resize, but can be extended for migration revert
            conn.compute.revert_server_resize(server)
            return {
                'success': True,
                'message': f'Migration/resize reverted for server "{instance_name}"'
            }
            
        elif action.lower() == 'list':
            # List migrations for a specific server or all servers
            migrations = []
            try:
                if instance_name:
                    # Get migrations for specific server
                    for migration in conn.compute.server_migrations(server.id):
                        migrations.append({
                            'id': getattr(migration, 'id', 'unknown'),
                            'server_id': getattr(migration, 'server_id', server.id),
                            'status': getattr(migration, 'status', 'unknown'),
                            'migration_type': getattr(migration, 'migration_type', 'unknown'),
                            'source_node': getattr(migration, 'source_node', 'unknown'),
                            'dest_node': getattr(migration, 'dest_node', 'unknown'),
                            'created_at': str(getattr(migration, 'created_at', 'unknown')),
                            'updated_at': str(getattr(migration, 'updated_at', 'unknown'))
                        })
                else:
                    # Get all migrations (admin required)
                    for migration in conn.compute.migrations():
                        migrations.append({
                            'id': getattr(migration, 'id', 'unknown'),
                            'server_id': getattr(migration, 'instance_uuid', 'unknown'),
                            'status': getattr(migration, 'status', 'unknown'),
                            'migration_type': getattr(migration, 'migration_type', 'unknown'),
                            'source_node': getattr(migration, 'source_node', 'unknown'),
                            'dest_node': getattr(migration, 'dest_node', 'unknown'),
                            'created_at': str(getattr(migration, 'created_at', 'unknown')),
                            'updated_at': str(getattr(migration, 'updated_at', 'unknown'))
                        })
            except Exception as e:
                logger.warning(f"Could not list migrations: {e}")
                
            return {
                'success': True,
                'migrations': migrations,
                'count': len(migrations)
            }
            
        elif action.lower() == 'show':
            migration_id = kwargs.get('migration_id')
            if not migration_id:
                return {
                    'success': False,
                    'message': 'migration_id parameter is required for show action'
                }
            
            try:
                migration = conn.compute.get_server_migration(server.id, migration_id)
                return {
                    'success': True,
                    'migration': {
                        'id': getattr(migration, 'id', 'unknown'),
                        'server_id': getattr(migration, 'server_id', server.id),
                        'status': getattr(migration, 'status', 'unknown'),
                        'migration_type': getattr(migration, 'migration_type', 'unknown'),
                        'source_node': getattr(migration, 'source_node', 'unknown'),
                        'dest_node': getattr(migration, 'dest_node', 'unknown'),
                        'created_at': str(getattr(migration, 'created_at', 'unknown')),
                        'updated_at': str(getattr(migration, 'updated_at', 'unknown')),
                        'links': getattr(migration, 'links', [])
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Migration "{migration_id}" not found: {str(e)}'
                }
                
        elif action.lower() == 'abort':
            migration_id = kwargs.get('migration_id')
            if not migration_id:
                return {
                    'success': False,
                    'message': 'migration_id parameter is required for abort action'
                }
            
            try:
                conn.compute.abort_server_migration(server.id, migration_id)
                return {
                    'success': True,
                    'message': f'Migration "{migration_id}" aborted for server "{instance_name}"'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to abort migration "{migration_id}": {str(e)}'
                }
                
        elif action.lower() == 'force_complete':
            migration_id = kwargs.get('migration_id')
            if not migration_id:
                return {
                    'success': False,
                    'message': 'migration_id parameter is required for force_complete action'
                }
            
            try:
                conn.compute.force_complete_server_migration(server.id, migration_id)
                return {
                    'success': True,
                    'message': f'Migration "{migration_id}" force completed for server "{instance_name}"'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to force complete migration "{migration_id}": {str(e)}'
                }
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: migrate, evacuate, confirm, revert, list, show, abort, force_complete'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server migration: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server migration: {str(e)}',
            'error': str(e)
        }


def set_server_properties(instance_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage server properties and metadata (set, unset).
    
    Args:
        instance_name: Name or ID of the server
        action: Action to perform (set, unset)
        **kwargs: Additional parameters
        
    Returns:
        Result of the property operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server
        server = None
        for srv in conn.compute.servers():
            if getattr(srv, 'name', '') == instance_name or srv.id == instance_name:
                server = srv
                break
        
        if not server:
            return {
                'success': False,
                'message': f'Server "{instance_name}" not found'
            }
        
        if action.lower() == 'set':
            # Server properties that can be updated
            update_params = {}
            
            if 'name' in kwargs:
                update_params['name'] = kwargs['name']
            if 'description' in kwargs:
                update_params['description'] = kwargs['description']
            
            # Metadata updates
            if 'metadata' in kwargs:
                metadata = kwargs['metadata']
                if isinstance(metadata, dict):
                    update_params['metadata'] = metadata
                else:
                    return {
                        'success': False,
                        'message': 'metadata parameter must be a dictionary'
                    }
            
            # Individual property updates
            property_keys = ['property']
            for key in kwargs:
                if key.startswith('property_'):
                    prop_name = key[9:]  # Remove 'property_' prefix
                    if 'metadata' not in update_params:
                        update_params['metadata'] = {}
                    update_params['metadata'][prop_name] = kwargs[key]
            
            if not update_params:
                return {
                    'success': False,
                    'message': 'No properties to update. Specify name, description, metadata, or property_* parameters'
                }
            
            conn.compute.update_server(server, **update_params)
            
            updated_fields = list(update_params.keys())
            return {
                'success': True,
                'message': f'Server "{instance_name}" properties updated: {", ".join(updated_fields)}'
            }
            
        elif action.lower() == 'unset':
            # Properties to unset
            unset_metadata = kwargs.get('metadata', kwargs.get('properties', []))
            if isinstance(unset_metadata, str):
                unset_metadata = [unset_metadata]
            
            if not unset_metadata:
                return {
                    'success': False,
                    'message': 'No properties to unset. Specify metadata or properties parameter'
                }
            
            # Get current metadata
            current_metadata = getattr(server, 'metadata', {})
            
            # Remove specified keys
            updated_metadata = current_metadata.copy()
            removed_keys = []
            for key in unset_metadata:
                if key in updated_metadata:
                    del updated_metadata[key]
                    removed_keys.append(key)
            
            if not removed_keys:
                return {
                    'success': False,
                    'message': f'None of the specified properties were found: {unset_metadata}'
                }
            
            # Update server with new metadata
            conn.compute.update_server(server, metadata=updated_metadata)
            
            return {
                'success': True,
                'message': f'Server "{instance_name}" properties unset: {", ".join(removed_keys)}'
            }
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: set, unset'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server properties: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server properties: {str(e)}',
            'error': str(e)
        }


def create_server_backup(instance_name: str, backup_name: str, **kwargs) -> Dict[str, Any]:
    """
    Create a backup image of a server.
    
    Args:
        instance_name: Name or ID of the server
        backup_name: Name for the backup image
        **kwargs: Additional parameters
        
    Returns:
        Result of the backup operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server
        server = None
        for srv in conn.compute.servers():
            if getattr(srv, 'name', '') == instance_name or srv.id == instance_name:
                server = srv
                break
        
        if not server:
            return {
                'success': False,
                'message': f'Server "{instance_name}" not found'
            }
        
        # Create backup (same as snapshot but with backup metadata)
        metadata = kwargs.get('metadata', {})
        metadata.update({
            'backup_type': 'daily',  # or weekly, etc.
            'source_server': getattr(server, 'name', 'unknown'),
            'source_server_id': server.id,
            'backup_created': str(conn.current_time) if hasattr(conn, 'current_time') else 'unknown'
        })
        
        backup_type = kwargs.get('backup_type', 'daily')
        rotation = kwargs.get('rotation', 1)
        
        backup_id = conn.compute.create_server_backup(
            server,
            name=backup_name,
            backup_type=backup_type,
            rotation=rotation
        )
        
        return {
            'success': True,
            'message': f'Backup "{backup_name}" creation started for server "{instance_name}"',
            'backup_id': backup_id,
            'backup_type': backup_type,
            'rotation': rotation
        }
        
    except Exception as e:
        logger.error(f"Failed to create server backup: {e}")
        return {
            'success': False,
            'message': f'Failed to create server backup: {str(e)}',
            'error': str(e)
        }


def create_server_dump(instance_name: str, **kwargs) -> Dict[str, Any]:
    """
    Create a dump file for a server (if supported by the compute driver).
    
    Args:
        instance_name: Name or ID of the server
        **kwargs: Additional parameters
        
    Returns:
        Result of the dump operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server
        server = None
        for srv in conn.compute.servers():
            if getattr(srv, 'name', '') == instance_name or srv.id == instance_name:
                server = srv
                break
        
        if not server:
            return {
                'success': False,
                'message': f'Server "{instance_name}" not found'
            }
        
        # Note: Server dump is not directly supported by OpenStack SDK
        # This would typically require direct API calls or vendor-specific implementations
        return {
            'success': False,
            'message': 'Server dump creation is not supported by the current OpenStack SDK. This feature requires vendor-specific implementation.',
            'note': 'Consider using server backup or snapshot instead'
        }
        
    except Exception as e:
        logger.error(f"Failed to create server dump: {e}")
        return {
            'success': False,
            'message': f'Failed to create server dump: {str(e)}',
            'error': str(e)
        }
