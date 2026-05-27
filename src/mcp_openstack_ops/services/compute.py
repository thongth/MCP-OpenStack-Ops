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
CINDER_DATABASE = "cinder"
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

def _get_cinder_mariadb_connection():
    if pymysql is None:
        raise RuntimeError("PyMySQL is not installed")

    return pymysql.connect(
        host=os.getenv("MARIADB_HOST", "127.0.0.1"),
        port=int(os.getenv("MARIADB_PORT", "3306")),
        user=os.getenv("MARIADB_USER", ""),
        password=os.getenv("MARIADB_PASSWORD", ""),
        database=CINDER_DATABASE,
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


def _scope_project_id() -> Optional[str]:
    # MariaDB read tools default to backend-wide reads; pass project_id explicitly to filter.
    return None


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


def _find_nested_value(data: Any, keys: set[str]) -> Any:
    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys and value not in (None, ""):
                return value
        for value in data.values():
            found = _find_nested_value(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_nested_value(value, keys)
            if found not in (None, ""):
                return found
    return None

def _extract_flavor_from_extra(raw_flavor: Any) -> Dict[str, Any]:
    data = _json_value(raw_flavor, default={})
    if not isinstance(data, dict):
        return {}
    return {
        "id": _find_nested_value(data, {"flavorid"}) or _find_nested_value(data, {"flavor_id"}) or _find_nested_value(data, {"id"}),
        "name": _find_nested_value(data, {"name", "original_name"}),
        "vcpus": _find_nested_value(data, {"vcpus"}),
        "ram": _find_nested_value(data, {"memory_mb", "ram"}),
        "disk": _find_nested_value(data, {"root_gb", "disk"}),
        "ephemeral": _find_nested_value(data, {"ephemeral_gb", "ephemeral"}),
        "swap": _find_nested_value(data, {"swap"}),
    }

def _metadata_value(metadata: Dict[str, Dict[str, Any]], instance_id: str, *keys: str) -> Any:
    instance_metadata = metadata.get(instance_id, {})
    for key in keys:
        value = instance_metadata.get(key)
        if value not in (None, ""):
            return value
    return None

def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default

def _get_volume_image_metadata(volume_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not volume_ids:
        return {}

    metadata_by_volume: Dict[str, Dict[str, Any]] = {}
    conn = _get_cinder_mariadb_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(volume_ids))
            if _table_exists(cur, "volume_glance_metadata"):
                columns = _table_columns(cur, "volume_glance_metadata")
                if {"volume_id", "key", "value"}.issubset(columns):
                    deleted_expr = _column_expr("", columns, "deleted", default="0")
                    cur.execute(
                        f"SELECT volume_id, `key`, value FROM volume_glance_metadata "
                        f"WHERE volume_id IN ({placeholders}) "
                        f"AND ({deleted_expr} = 0 OR {deleted_expr} = '0')",
                        volume_ids,
                    )
                    for item in cur.fetchall():
                        metadata_by_volume.setdefault(item["volume_id"], {})[item["key"]] = item.get("value")

            if _table_exists(cur, "volume_metadata"):
                columns = _table_columns(cur, "volume_metadata")
                if {"volume_id", "key", "value"}.issubset(columns):
                    deleted_expr = _column_expr("", columns, "deleted", default="0")
                    cur.execute(
                        f"SELECT volume_id, `key`, value FROM volume_metadata "
                        f"WHERE volume_id IN ({placeholders}) "
                        f"AND ({deleted_expr} = 0 OR {deleted_expr} = '0')",
                        volume_ids,
                    )
                    for item in cur.fetchall():
                        metadata_by_volume.setdefault(item["volume_id"], {}).setdefault(item["key"], item.get("value"))
    except Exception as e:
        logger.warning(f"Failed to get Cinder volume image metadata: {e}")
    finally:
        conn.close()
    return metadata_by_volume

def _image_from_volume_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    image_id = (
        metadata.get("image_id")
        or metadata.get("image_base_image_ref")
        or metadata.get("image_meta_base_image_ref")
        or metadata.get("glance_image_id")
    )
    image_name = (
        metadata.get("image_name")
        or metadata.get("image_meta_name")
        or metadata.get("name")
        or metadata.get("image_os_distro")
    )
    return {"id": image_id, "name": image_name}

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


def get_instance_summary(project_id: str = "") -> Dict[str, Any]:
    """
    Get Nova instance counts without filtering to ACTIVE only.
    """
    conn = _get_nova_mariadb_connection()
    try:
        scope_project_id = project_id or _scope_project_id()
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
                },
                "data_source": "mariadb",
            }
    finally:
        conn.close()


def get_instance_details(
    instance_names: Optional[List[str]] = None,
    limit: int = 50,
    offset: int = 0,
    include_all: bool = False,
    task_state: str = "",
) -> Dict[str, Any]:
    """
    Get detailed information about OpenStack instances with pagination support.
    
    Args:
        instance_names: List of instance names to filter (optional)
        limit: Maximum number of instances to return (default: 50, max: 200)
        offset: Number of instances to skip for pagination (default: 0)
        include_all: If True, return all instances ignoring limit (default: False)
        task_state: Optional Nova task_state filter such as deleting
    
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
            scope_project_id = _scope_project_id()
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
                    "NULL AS flavor_id, NULL AS flavor_public_id, NULL AS flavor_name, 0 AS vcpus, 0 AS memory_mb, "
                    "0 AS root_gb, 0 AS ephemeral_gb, 0 AS swap"
                )
                if _table_exists(cur, "instance_types"):
                    flavor_columns = _table_columns(cur, "instance_types")
                    flavor_deleted_expr = _column_expr("it", flavor_columns, "deleted", default="0")
                    flavor_public_id_expr = _column_expr("it", flavor_columns, "flavorid", default="it.id")
                    joins += (
                        " LEFT JOIN instance_types it ON it.id = "
                        f"{type_id_expr} AND ({flavor_deleted_expr} = 0 OR {flavor_deleted_expr} = '0')"
                    )
                    select_flavor = (
                        f"it.id AS flavor_id, {flavor_public_id_expr} AS flavor_public_id, it.name AS flavor_name, it.vcpus, "
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
                if task_state:
                    where.append(f"LOWER(COALESCE({task_expr}, '')) = %s")
                    params.append(task_state.strip().lower())
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
                boot_volume_by_instance: Dict[str, str] = {}
                flavor_by_instance: Dict[str, Dict[str, Any]] = {}
                metadata_by_instance: Dict[str, Dict[str, Any]] = {}
                if instance_ids and _table_exists(cur, "block_device_mapping"):
                    bdm_columns = _table_columns(cur, "block_device_mapping")
                    if {"instance_uuid", "volume_id"}.issubset(bdm_columns):
                        placeholders = ",".join(["%s"] * len(instance_ids))
                        bdm_deleted_expr = _column_expr("", bdm_columns, "deleted", default="0")
                        boot_index_expr = _column_expr("", bdm_columns, "boot_index", default="NULL")
                        cur.execute(
                            f"SELECT instance_uuid, volume_id, {boot_index_expr} AS boot_index FROM block_device_mapping "
                            f"WHERE instance_uuid IN ({placeholders}) AND volume_id IS NOT NULL "
                            f"AND ({bdm_deleted_expr} = 0 OR {bdm_deleted_expr} = '0')",
                            instance_ids,
                        )
                        for bdm in cur.fetchall():
                            volumes_by_instance.setdefault(bdm["instance_uuid"], []).append(bdm["volume_id"])
                            if str(bdm.get("boot_index")) == "0":
                                boot_volume_by_instance[bdm["instance_uuid"]] = bdm["volume_id"]

                if instance_ids and _table_exists(cur, "instance_extra"):
                    extra_columns = _table_columns(cur, "instance_extra")
                    if {"instance_uuid", "flavor"}.issubset(extra_columns):
                        placeholders = ",".join(["%s"] * len(instance_ids))
                        extra_deleted_expr = _column_expr("", extra_columns, "deleted", default="0")
                        cur.execute(
                            f"SELECT instance_uuid, flavor FROM instance_extra "
                            f"WHERE instance_uuid IN ({placeholders}) "
                            f"AND ({extra_deleted_expr} = 0 OR {extra_deleted_expr} = '0')",
                            instance_ids,
                        )
                        for extra in cur.fetchall():
                            flavor_by_instance[extra["instance_uuid"]] = _extract_flavor_from_extra(extra.get("flavor"))

                if instance_ids and _table_exists(cur, "instance_system_metadata"):
                    metadata_columns = _table_columns(cur, "instance_system_metadata")
                    if {"instance_uuid", "key", "value"}.issubset(metadata_columns):
                        placeholders = ",".join(["%s"] * len(instance_ids))
                        metadata_deleted_expr = _column_expr("", metadata_columns, "deleted", default="0")
                        cur.execute(
                            f"SELECT instance_uuid, `key`, value FROM instance_system_metadata "
                            f"WHERE instance_uuid IN ({placeholders}) "
                            f"AND ({metadata_deleted_expr} = 0 OR {metadata_deleted_expr} = '0')",
                            instance_ids,
                        )
                        for item in cur.fetchall():
                            metadata_by_instance.setdefault(item["instance_uuid"], {})[item["key"]] = item.get("value")

                attached_volume_ids = sorted({volume_id for volume_ids in volumes_by_instance.values() for volume_id in volume_ids})
                volume_image_metadata = _get_volume_image_metadata(attached_volume_ids)

                instances = []
                for row in rows:
                    instance_id = row.get("id")
                    power_state = row.get("power_state") or 0
                    extra_flavor = flavor_by_instance.get(instance_id, {})
                    image_id = row.get("image_id") or _metadata_value(
                        metadata_by_instance,
                        instance_id,
                        "image_base_image_ref",
                        "image_id",
                    )
                    image_name = _metadata_value(
                        metadata_by_instance,
                        instance_id,
                        "image_name",
                        "image_meta_name",
                        "image_os_distro",
                    )
                    boot_volume_id = boot_volume_by_instance.get(instance_id)
                    if not boot_volume_id:
                        attached_volume_ids_for_instance = volumes_by_instance.get(instance_id, [])
                        boot_volume_id = attached_volume_ids_for_instance[0] if attached_volume_ids_for_instance else None
                    volume_image = _image_from_volume_metadata(volume_image_metadata.get(boot_volume_id, {})) if boot_volume_id else {}
                    image_id = image_id or volume_image.get("id")
                    image_name = image_name or volume_image.get("name")
                    instances.append({
                        "id": instance_id,
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
                            "id": extra_flavor.get("id")
                            or row.get("flavor_public_id")
                            or row.get("flavor_id")
                            or _metadata_value(metadata_by_instance, instance_id, "instance_type_flavorid", "instance_type_id")
                            or "unknown",
                            "name": row.get("flavor_name")
                            or extra_flavor.get("name")
                            or _metadata_value(metadata_by_instance, instance_id, "instance_type_name")
                            or "unknown",
                            "vcpus": _coerce_int(row.get("vcpus") or extra_flavor.get("vcpus") or _metadata_value(metadata_by_instance, instance_id, "instance_type_vcpus")),
                            "ram": _coerce_int(row.get("memory_mb") or extra_flavor.get("ram") or _metadata_value(metadata_by_instance, instance_id, "instance_type_memory_mb")),
                            "disk": _coerce_int(row.get("root_gb") or extra_flavor.get("disk") or _metadata_value(metadata_by_instance, instance_id, "instance_type_root_gb")),
                            "ephemeral": _coerce_int(row.get("ephemeral_gb") or extra_flavor.get("ephemeral") or _metadata_value(metadata_by_instance, instance_id, "instance_type_ephemeral_gb")),
                            "swap": _coerce_int(row.get("swap") or extra_flavor.get("swap") or _metadata_value(metadata_by_instance, instance_id, "instance_type_swap")),
                        },
                        "image": {
                            "id": image_id or "unknown",
                            "name": image_name or "unknown",
                            "source": "boot_volume_metadata" if volume_image.get("id") or volume_image.get("name") else "nova",
                            "boot_volume_id": boot_volume_id,
                        },
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
                        "attached_volumes": volumes_by_instance.get(instance_id, []),
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
            if task_state:
                result['filtered_by_task_state'] = task_state

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
            or str(instance.get('vm_state') or '').lower() == status_lower
            or str(instance.get('task_state') or '').lower() == status_lower
        ]
        
    except Exception as e:
        logger.error(f"Failed to get instances by status: {e}")
        return []


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


