"""
OpenStack Storage (Cinder) Service Functions

This module contains functions for managing volumes, snapshots, backups,
volume types, and other storage-related components.
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional

try:
    import pymysql
except Exception:  # pragma: no cover - optional dependency at runtime
    pymysql = None

# Configure logging
logger = logging.getLogger(__name__)

TRUTHY_VALUES = {"1", "true", "yes", "on"}
CINDER_DATABASE = "cinder"


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


def _normalize_pagination(limit: int = 100, offset: int = 0) -> tuple[int, int]:
    try:
        limit = int(limit)
    except Exception:
        limit = 100
    try:
        offset = int(offset)
    except Exception:
        offset = 0
    if limit < 0:
        limit = 100
    if limit > 500:
        limit = 500
    if offset < 0:
        offset = 0
    return limit, offset

def _apply_limit_offset(sql: str, params: List[Any], limit: int, offset: int) -> tuple[str, List[Any]]:
    limit, offset = _normalize_pagination(limit, offset)
    if limit > 0:
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
    return sql, params

def _select_fields(items: List[Dict[str, Any]], fields: str = "") -> List[Dict[str, Any]]:
    requested = [field.strip() for field in fields.split(",") if field.strip()]
    if not requested:
        return items
    return [{field: item.get(field) for field in requested if field in item} for item in items]

def _get_group_counts(
    cur,
    table_name: str,
    alias: str,
    columns: set[str],
    group_expr: str,
    where_sql: str,
    params: List[Any],
    label: str,
) -> List[Dict[str, Any]]:
    if group_expr == "NULL":
        return []
    cur.execute(
        f"SELECT COALESCE({group_expr}, 'unknown') AS value, COUNT(*) AS count "
        f"FROM {table_name} {alias}{where_sql} "
        f"GROUP BY value ORDER BY count DESC, value ASC",
        params,
    )
    return [{label: row.get("value"), "count": int(row.get("count") or 0)} for row in cur.fetchall()]

def _storage_summary(table_name: str, alias: str, resource: str, project_id: str = "") -> Dict[str, Any]:
    conn = _get_cinder_mariadb_connection()
    try:
        scope_project_id = _scope_project_id(project_id)
        with conn.cursor() as cur:
            columns = _table_columns(cur, table_name)
            if not columns:
                raise RuntimeError(f"MariaDB table '{table_name}' is not available")

            deleted_expr = _column_expr(alias, columns, "deleted", default="0")
            status_expr = _column_expr(alias, columns, "status", default="'unknown'")
            project_expr = _column_expr(alias, columns, "project_id", "tenant_id")
            az_expr = _column_expr(alias, columns, "availability_zone", default="NULL")
            fail_reason_expr = _column_expr(alias, columns, "fail_reason", default="NULL")

            where = []
            params: List[Any] = []
            if deleted_expr != "0":
                where.append(f"({deleted_expr} = 0 OR {deleted_expr} = '0')")
            if scope_project_id:
                where.append(f"{project_expr} = %s")
                params.append(scope_project_id)
            where_sql = " WHERE " + " AND ".join(where) if where else ""

            cur.execute(f"SELECT COUNT(*) AS total FROM {table_name} {alias}{where_sql}", params)
            total = int((cur.fetchone() or {}).get("total") or 0)

            return {
                "resource": resource,
                "total": total,
                "scope": {
                    "project_id": scope_project_id,
                },
                "by_status": _get_group_counts(cur, table_name, alias, columns, status_expr, where_sql, params, "status"),
                "by_project_id": _get_group_counts(cur, table_name, alias, columns, project_expr, where_sql, params, "project_id"),
                "by_availability_zone": _get_group_counts(cur, table_name, alias, columns, az_expr, where_sql, params, "availability_zone"),
                "by_fail_reason": _get_group_counts(cur, table_name, alias, columns, fail_reason_expr, where_sql, params, "fail_reason"),
                "data_source": "mariadb",
            }
    finally:
        conn.close()

def get_volume_summary(project_id: str = "") -> Dict[str, Any]:
    return _storage_summary("volumes", "v", "volumes", project_id)

def get_volume_snapshot_summary(project_id: str = "") -> Dict[str, Any]:
    return _storage_summary("snapshots", "s", "snapshots", project_id)

def get_volume_backup_summary(project_id: str = "") -> Dict[str, Any]:
    return _storage_summary("backups", "b", "backups", project_id)

def get_volume_list(
    project_id: str = "",
    status: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> List[Dict[str, Any]]:
    """
    Get list of volumes with detailed information.
    
    Returns:
        List of volume dictionaries
    """
    try:
        conn = _get_cinder_mariadb_connection()
        try:
            scope_project_id = _scope_project_id(project_id)
            status_filter = status.strip().lower() if status else ""
            with conn.cursor() as cur:
                columns = _table_columns(cur, "volumes")
                if not columns:
                    raise RuntimeError("MariaDB table 'volumes' is not available")

                name_expr = _column_expr("v", columns, "name", "display_name", default="NULL")
                desc_expr = _column_expr("v", columns, "description", "display_description", default="''")
                project_expr = _column_expr("v", columns, "project_id", "tenant_id")
                tenant_expr = _column_expr("v", columns, "tenant_id", "project_id")
                type_expr = _column_expr("v", columns, "volume_type_id", "volume_type", default="NULL")
                bootable_expr = _column_expr("v", columns, "bootable", default="0")
                multiattach_expr = _column_expr("v", columns, "multiattach", default="0")
                encrypted_expr = _column_expr("v", columns, "encryption_key_id", default="NULL")
                deleted_expr = _column_expr("v", columns, "deleted", default="0")
                status_expr = _column_expr("v", columns, "status", default="'unknown'")
                sql = (
                    "SELECT v.id, "
                    f"{name_expr} AS name, {status_expr} AS status, v.size, {type_expr} AS volume_type, "
                    f"{bootable_expr} AS bootable, {multiattach_expr} AS multiattach, "
                    f"{encrypted_expr} AS encryption_key_id, v.availability_zone, "
                    f"{project_expr} AS project_id, {tenant_expr} AS tenant_id, "
                    "v.created_at, v.updated_at, "
                    f"{desc_expr} AS description, "
                    f"{_column_expr('v', columns, 'source_volid')} AS source_volid, "
                    f"{_column_expr('v', columns, 'snapshot_id')} AS snapshot_id, "
                    f"{_column_expr('v', columns, 'image_id')} AS image_id "
                    "FROM volumes v WHERE 1=1 "
                )
                params: List[Any] = []
                if deleted_expr != "0":
                    sql += f"AND ({deleted_expr} = 0 OR {deleted_expr} = '0') "
                if scope_project_id:
                    sql += f"AND {project_expr} = %s "
                    params.append(scope_project_id)
                if status_filter:
                    sql += f"AND LOWER({status_expr}) = %s "
                    params.append(status_filter)
                sql += "ORDER BY v.created_at DESC"
                sql, params = _apply_limit_offset(sql, params, limit, offset)
                cur.execute(sql, params)
                rows = cur.fetchall()

                volume_ids = [row["id"] for row in rows if row.get("id")]
                attachments_by_volume: Dict[str, List[Dict[str, Any]]] = {}
                metadata_by_volume: Dict[str, Dict[str, Any]] = {}
                if volume_ids:
                    placeholders = ",".join(["%s"] * len(volume_ids))
                    attachment_columns = _table_columns(cur, "volume_attachment")
                    if attachment_columns:
                        attachment_deleted_expr = _column_expr("", attachment_columns, "deleted", default="0")
                        attachment_id_expr = _column_expr("", attachment_columns, "id", default="NULL")
                        instance_uuid_expr = _column_expr("", attachment_columns, "instance_uuid", default="NULL")
                        attached_host_expr = _column_expr("", attachment_columns, "attached_host", default="NULL")
                        mountpoint_expr = _column_expr("", attachment_columns, "mountpoint", default="NULL")
                        attach_time_expr = _column_expr("", attachment_columns, "attach_time", "created_at", default="NULL")
                        cur.execute(
                            "SELECT "
                            f"{attachment_id_expr} AS id, volume_id, "
                            f"{instance_uuid_expr} AS instance_uuid, "
                            f"{attached_host_expr} AS attached_host, "
                            f"{mountpoint_expr} AS mountpoint, "
                            f"{attach_time_expr} AS attach_time "
                            f"FROM volume_attachment WHERE volume_id IN ({placeholders}) "
                            f"AND ({attachment_deleted_expr} = 0 OR {attachment_deleted_expr} = '0')",
                            volume_ids,
                        )
                        for attachment in cur.fetchall():
                            attachments_by_volume.setdefault(attachment["volume_id"], []).append({
                                "server_id": attachment.get("instance_uuid"),
                                "attachment_id": attachment.get("id"),
                                "device": attachment.get("mountpoint"),
                                "attached_at": _str_time(attachment.get("attach_time")),
                                "attached_host": attachment.get("attached_host"),
                            })
                    metadata_columns = _table_columns(cur, "volume_metadata")
                    if {"volume_id", "key", "value"}.issubset(metadata_columns):
                        metadata_deleted_expr = _column_expr("", metadata_columns, "deleted", default="0")
                        cur.execute(
                            f"SELECT volume_id, `key`, value FROM volume_metadata WHERE volume_id IN ({placeholders}) "
                            f"AND ({metadata_deleted_expr} = 0 OR {metadata_deleted_expr} = '0')",
                            volume_ids,
                        )
                        for meta in cur.fetchall():
                            metadata_by_volume.setdefault(meta["volume_id"], {})[meta["key"]] = meta.get("value")

                volumes = []
                for row in rows:
                    attachments = attachments_by_volume.get(row.get("id"), [])
                    volumes.append({
                        "id": row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "status": row.get("status") or "unknown",
                        "size": row.get("size") or 0,
                        "volume_type": row.get("volume_type") or "unknown",
                        "bootable": _bool_value(row.get("bootable")),
                        "encrypted": bool(row.get("encryption_key_id")),
                        "multiattach": _bool_value(row.get("multiattach")),
                        "availability_zone": row.get("availability_zone") or "unknown",
                        "tenant_id": row.get("tenant_id"),
                        "project_id": row.get("project_id"),
                        "created_at": _str_time(row.get("created_at")),
                        "updated_at": _str_time(row.get("updated_at")),
                        "description": row.get("description") or "",
                        "metadata": metadata_by_volume.get(row.get("id"), {}),
                        "source_volid": row.get("source_volid"),
                        "snapshot_id": row.get("snapshot_id"),
                        "image_id": row.get("image_id"),
                        "attachments": attachments,
                        "attachment_count": len(attachments),
                        "data_source": "mariadb",
                    })
                return _select_fields(volumes, fields)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get volume list: {e}")
        return [
            {
                'id': 'vol-1', 'name': 'demo-volume', 'status': 'available',
                'size': 10, 'volume_type': 'unknown', 'attachments': [], 'error': str(e)
            }
        ]


def set_volume(volume_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage volumes (create, delete, extend, attach, detach, snapshot).
    
    Args:
        volume_name: Name of the volume
        action: Action to perform
        **kwargs: Additional parameters depending on action
    
    Returns:
        Result of the volume operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            volumes = []
            for volume in conn.volume.volumes():
                volumes.append({
                    'id': volume.id,
                    'name': getattr(volume, 'name', 'unnamed'),
                    'status': getattr(volume, 'status', 'unknown'),
                    'size': getattr(volume, 'size', 0),
                    'volume_type': getattr(volume, 'volume_type', 'unknown'),
                    'bootable': getattr(volume, 'is_bootable', False)
                })
            return {
                'success': True,
                'volumes': volumes,
                'count': len(volumes)
            }
            
        elif action.lower() == 'create':
            size = kwargs.get('size', 1)
            volume_type = kwargs.get('volume_type', kwargs.get('type'))
            description = kwargs.get('description', '')
            image_id = kwargs.get('image_id', kwargs.get('image'))
            snapshot_id = kwargs.get('snapshot_id', kwargs.get('snapshot'))
            availability_zone = kwargs.get('availability_zone', kwargs.get('az'))
            
            create_params = {
                'name': volume_name,
                'size': int(size),
                'description': description
            }
            
            if volume_type:
                create_params['volume_type'] = volume_type
            if image_id:
                create_params['image_id'] = image_id
            if snapshot_id:
                create_params['snapshot_id'] = snapshot_id
            if availability_zone:
                create_params['availability_zone'] = availability_zone
            
            volume = conn.volume.create_volume(**create_params)
            
            return {
                'success': True,
                'message': f'Volume "{volume_name}" created successfully',
                'volume': {
                    'id': volume.id,
                    'name': getattr(volume, 'name', 'unnamed'),
                    'status': getattr(volume, 'status', 'unknown'),
                    'size': getattr(volume, 'size', 0),
                    'volume_type': getattr(volume, 'volume_type', 'unknown')
                }
            }
            
        elif action.lower() == 'delete':
            # Find the volume using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id, get_openstack_connection
            conn = get_openstack_connection()
            
            volume = find_resource_by_name_or_id(
                conn.volume.volumes(), 
                volume_name, 
                "Volume"
            )

            if not volume:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" not found or not accessible in current project'
                }
            
            # Check if volume is attached
            if getattr(volume, 'attachments', []):
                force = kwargs.get('force', False)
                if not force:
                    return {
                        'success': False,
                        'message': f'Volume "{volume_name}" is attached. Use force=True to delete anyway'
                    }
            
            conn.volume.delete_volume(volume, force=kwargs.get('force', False))
            
            return {
                'success': True,
                'message': f'Volume "{volume_name}" deleted successfully'
            }
            
        elif action.lower() == 'extend':
            new_size = kwargs.get('size', kwargs.get('new_size'))
            if not new_size:
                return {
                    'success': False,
                    'message': 'size parameter is required for extend action'
                }
            
            # Find the volume
            volume = None
            for vol in conn.volume.volumes():
                if getattr(vol, 'name', '') == volume_name or vol.id == volume_name:
                    volume = vol
                    break
            
            if not volume:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" not found'
                }
            
            current_size = getattr(volume, 'size', 0)
            new_size = int(new_size)
            
            if new_size <= current_size:
                return {
                    'success': False,
                    'message': f'New size ({new_size}GB) must be greater than current size ({current_size}GB)'
                }
            
            conn.volume.extend_volume(volume, size=new_size)
            
            return {
                'success': True,
                'message': f'Volume "{volume_name}" extended from {current_size}GB to {new_size}GB'
            }
            
        elif action.lower() == 'attach':
            instance_id = kwargs.get('instance_id', kwargs.get('server_id'))
            device = kwargs.get('device')
            
            if not instance_id:
                return {
                    'success': False,
                    'message': 'instance_id parameter is required for attach action'
                }
            
            # Find the volume
            volume = None
            for vol in conn.volume.volumes():
                if getattr(vol, 'name', '') == volume_name or vol.id == volume_name:
                    volume = vol
                    break
            
            if not volume:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" not found'
                }
            
            attach_params = {'server_id': instance_id}
            if device:
                attach_params['device'] = device
            
            conn.compute.create_volume_attachment(volume.id, **attach_params)
            
            return {
                'success': True,
                'message': f'Volume "{volume_name}" attached to instance "{instance_id}"'
            }
            
        elif action.lower() == 'detach':
            # Find the volume
            volume = None
            for vol in conn.volume.volumes():
                if getattr(vol, 'name', '') == volume_name or vol.id == volume_name:
                    volume = vol
                    break
            
            if not volume:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" not found'
                }
            
            attachments = getattr(volume, 'attachments', [])
            if not attachments:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" is not attached'
                }
            
            # Detach from all servers
            for attachment in attachments:
                server_id = attachment.get('server_id')
                if server_id:
                    conn.compute.delete_volume_attachment(volume.id, server_id)
            
            return {
                'success': True,
                'message': f'Volume "{volume_name}" detached successfully'
            }
            
        elif action.lower() == 'snapshot':
            snapshot_name = kwargs.get('snapshot_name', f'{volume_name}-snapshot')
            description = kwargs.get('description', f'Snapshot of {volume_name}')
            force = kwargs.get('force', False)
            
            # Find the volume
            volume = None
            for vol in conn.volume.volumes():
                if getattr(vol, 'name', '') == volume_name or vol.id == volume_name:
                    volume = vol
                    break
            
            if not volume:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" not found'
                }
            
            snapshot = conn.volume.create_snapshot(
                volume_id=volume.id,
                name=snapshot_name,
                description=description,
                force=force
            )
            
            return {
                'success': True,
                'message': f'Snapshot "{snapshot_name}" created successfully',
                'snapshot': {
                    'id': snapshot.id,
                    'name': getattr(snapshot, 'name', 'unnamed'),
                    'status': getattr(snapshot, 'status', 'unknown'),
                    'volume_id': getattr(snapshot, 'volume_id', 'unknown')
                }
            }
            
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete, extend, attach, detach, snapshot, list'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage volume: {e}")
        return {
            'success': False,
            'message': f'Failed to manage volume: {str(e)}',
            'error': str(e)
        }


def get_volume_types() -> List[Dict[str, Any]]:
    """
    Get list of volume types.
    
    Returns:
        List of volume type dictionaries
    """
    try:
        conn = _get_cinder_mariadb_connection()
        try:
            with conn.cursor() as cur:
                columns = _table_columns(cur, "volume_types")
                if not columns:
                    raise RuntimeError("MariaDB table 'volume_types' is not available")

                desc_expr = _column_expr("vt", columns, "description", default="''")
                public_expr = _column_expr("vt", columns, "is_public", default="1")
                deleted_expr = _column_expr("vt", columns, "deleted", default="0")
                cur.execute(
                    "SELECT vt.id, vt.name, "
                    f"{desc_expr} AS description, {public_expr} AS is_public, "
                    "vt.created_at, vt.updated_at "
                    "FROM volume_types vt "
                    f"WHERE ({deleted_expr} = 0 OR {deleted_expr} = '0') "
                    "ORDER BY vt.name ASC"
                )
                rows = cur.fetchall()
                type_ids = [row["id"] for row in rows if row.get("id")]
                specs_by_type: Dict[str, Dict[str, Any]] = {}
                if type_ids and {"volume_type_id", "key", "value"}.issubset(_table_columns(cur, "volume_type_extra_specs")):
                    placeholders = ",".join(["%s"] * len(type_ids))
                    cur.execute(
                        f"SELECT volume_type_id, `key`, value FROM volume_type_extra_specs WHERE volume_type_id IN ({placeholders})",
                        type_ids,
                    )
                    for spec in cur.fetchall():
                        specs_by_type.setdefault(spec["volume_type_id"], {})[spec["key"]] = spec.get("value")

                return [
                    {
                        "id": row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "description": row.get("description") or "",
                        "is_public": _bool_value(row.get("is_public")),
                        "extra_specs": specs_by_type.get(row.get("id"), {}),
                        "created_at": _str_time(row.get("created_at")),
                        "updated_at": _str_time(row.get("updated_at")),
                        "data_source": "mariadb",
                    }
                    for row in rows
                ]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get volume types: {e}")
        return [
            {
                'id': 'type-1', 'name': 'standard', 'description': 'Standard volume type',
                'is_public': True, 'extra_specs': {}, 'error': str(e)
            }
        ]


def get_volume_snapshots(
    project_id: str = "",
    status: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> List[Dict[str, Any]]:
    """
    Get list of volume snapshots.
    
    Returns:
        List of snapshot dictionaries
    """
    try:
        conn = _get_cinder_mariadb_connection()
        try:
            scope_project_id = _scope_project_id(project_id)
            status_filter = status.strip().lower() if status else ""
            with conn.cursor() as cur:
                columns = _table_columns(cur, "snapshots")
                if not columns:
                    raise RuntimeError("MariaDB table 'snapshots' is not available")

                name_expr = _column_expr("s", columns, "name", "display_name", default="NULL")
                desc_expr = _column_expr("s", columns, "description", "display_description", default="''")
                project_expr = _column_expr("s", columns, "project_id", "tenant_id")
                size_expr = _column_expr("s", columns, "volume_size", "size", default="0")
                deleted_expr = _column_expr("s", columns, "deleted", default="0")
                status_expr = _column_expr("s", columns, "status", default="'unknown'")
                sql = (
                    "SELECT s.id, "
                    f"{name_expr} AS name, {desc_expr} AS description, {status_expr} AS status, "
                    f"{size_expr} AS size, s.volume_id, {project_expr} AS project_id, "
                    "s.created_at, s.updated_at "
                    "FROM snapshots s WHERE 1=1 "
                )
                params: List[Any] = []
                if deleted_expr != "0":
                    sql += f"AND ({deleted_expr} = 0 OR {deleted_expr} = '0') "
                if scope_project_id:
                    sql += f"AND {project_expr} = %s "
                    params.append(scope_project_id)
                if status_filter:
                    sql += f"AND LOWER({status_expr}) = %s "
                    params.append(status_filter)
                sql += "ORDER BY s.created_at DESC"
                sql, params = _apply_limit_offset(sql, params, limit, offset)
                cur.execute(sql, params)
                rows = cur.fetchall()

                snapshot_ids = [row["id"] for row in rows if row.get("id")]
                metadata_by_snapshot: Dict[str, Dict[str, Any]] = {}
                metadata_columns = _table_columns(cur, "snapshot_metadata")
                if snapshot_ids and {"snapshot_id", "key", "value"}.issubset(metadata_columns):
                    placeholders = ",".join(["%s"] * len(snapshot_ids))
                    metadata_deleted_expr = _column_expr("", metadata_columns, "deleted", default="0")
                    cur.execute(
                        f"SELECT snapshot_id, `key`, value FROM snapshot_metadata WHERE snapshot_id IN ({placeholders}) "
                        f"AND ({metadata_deleted_expr} = 0 OR {metadata_deleted_expr} = '0')",
                        snapshot_ids,
                    )
                    for meta in cur.fetchall():
                        metadata_by_snapshot.setdefault(meta["snapshot_id"], {})[meta["key"]] = meta.get("value")

                snapshots = [
                    {
                        "id": row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "description": row.get("description") or "",
                        "status": row.get("status") or "unknown",
                        "size": row.get("size") or 0,
                        "volume_id": row.get("volume_id") or "unknown",
                        "project_id": row.get("project_id"),
                        "created_at": _str_time(row.get("created_at")),
                        "updated_at": _str_time(row.get("updated_at")),
                        "metadata": metadata_by_snapshot.get(row.get("id"), {}),
                        "data_source": "mariadb",
                    }
                    for row in rows
                ]
                return _select_fields(snapshots, fields)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get volume snapshots: {e}")
        return [
            {
                'id': 'snap-1', 'name': 'demo-snapshot', 'status': 'available',
                'size': 10, 'volume_id': 'vol-1', 'error': str(e)
            }
        ]


def get_volume_backups(
    project_id: str = "",
    status: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> List[Dict[str, Any]]:
    """
    Get list of volume backups.

    Returns:
        List of backup dictionaries
    """
    try:
        scope_project_id = _scope_project_id(project_id)
        status_filter = status.strip().lower() if status else ""
        conn = _get_cinder_mariadb_connection()
        try:
            with conn.cursor() as cur:
                columns = _table_columns(cur, "backups")
                if not columns:
                    raise RuntimeError("MariaDB table 'backups' is not available")

                name_expr = _column_expr("b", columns, "name", "display_name", default="NULL")
                desc_expr = _column_expr("b", columns, "description", "display_description", default="''")
                project_expr = _column_expr("b", columns, "project_id", "tenant_id")
                deleted_expr = _column_expr("b", columns, "deleted", default="0")
                status_expr = _column_expr("b", columns, "status", default="'unknown'")
                size_expr = _column_expr("b", columns, "size", default="0")
                updated_at_expr = _column_expr("b", columns, "updated_at", default="NULL")
                availability_zone_expr = _column_expr("b", columns, "availability_zone", default="NULL")
                fail_reason_expr = _column_expr("b", columns, "fail_reason", default="NULL")
                snapshot_id_expr = _column_expr("b", columns, "snapshot_id", default="NULL")
                parent_id_expr = _column_expr("b", columns, "parent_id", default="NULL")
                sql = (
                    "SELECT b.id, "
                    f"{name_expr} AS name, {status_expr} AS status, {size_expr} AS size, b.volume_id, "
                    f"{project_expr} AS project_id, b.created_at, {updated_at_expr} AS updated_at, "
                    f"{desc_expr} AS description, {availability_zone_expr} AS availability_zone, "
                    f"{fail_reason_expr} AS fail_reason, {snapshot_id_expr} AS snapshot_id, "
                    f"{parent_id_expr} AS parent_id "
                    "FROM backups b WHERE 1=1 "
                )
                params: List[Any] = []
                if deleted_expr != "0":
                    sql += f"AND ({deleted_expr} = 0 OR {deleted_expr} = '0') "
                if scope_project_id:
                    sql += f"AND {project_expr} = %s "
                    params.append(scope_project_id)
                if status_filter:
                    sql += f"AND LOWER({status_expr}) = %s "
                    params.append(status_filter)
                sql += "ORDER BY b.created_at DESC"
                sql, params = _apply_limit_offset(sql, params, limit, offset)
                cur.execute(sql, params)
                backups = [
                    {
                        "id": row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "status": row.get("status") or "unknown",
                        "size": row.get("size") or 0,
                        "volume_id": row.get("volume_id") or "unknown",
                        "project_id": row.get("project_id"),
                        "created_at": _str_time(row.get("created_at")),
                        "updated_at": _str_time(row.get("updated_at")),
                        "description": row.get("description") or "",
                        "availability_zone": row.get("availability_zone"),
                        "fail_reason": row.get("fail_reason"),
                        "snapshot_id": row.get("snapshot_id"),
                        "parent_id": row.get("parent_id"),
                        "data_source": "mariadb",
                    }
                    for row in cur.fetchall()
                ]
                return _select_fields(backups, fields)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get volume backups: {e}")
        return [
            {
                'id': 'backup-1', 'name': 'demo-backup', 'status': 'available',
                'size': 10, 'volume_id': 'vol-1', 'error': str(e)
            }
        ]

def set_snapshot(snapshot_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage volume snapshots (create, delete, restore).
    
    Args:
        snapshot_name: Name of the snapshot
        action: Action to perform
        **kwargs: Additional parameters
    
    Returns:
        Result of the snapshot operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            snapshots = []
            for snapshot in conn.volume.snapshots():
                snapshots.append({
                    'id': snapshot.id,
                    'name': getattr(snapshot, 'name', 'unnamed'),
                    'status': getattr(snapshot, 'status', 'unknown'),
                    'size': getattr(snapshot, 'size', 0),
                    'volume_id': getattr(snapshot, 'volume_id', 'unknown')
                })
            return {
                'success': True,
                'snapshots': snapshots,
                'count': len(snapshots)
            }
            
        elif action.lower() == 'create':
            volume_id = kwargs.get('volume_id')
            description = kwargs.get('description', f'Snapshot {snapshot_name}')
            force = kwargs.get('force', False)
            
            if not volume_id:
                return {
                    'success': False,
                    'message': 'volume_id is required for create action'
                }
            
            snapshot = conn.volume.create_snapshot(
                volume_id=volume_id,
                name=snapshot_name,
                description=description,
                force=force
            )
            
            return {
                'success': True,
                'message': f'Snapshot "{snapshot_name}" created successfully',
                'snapshot': {
                    'id': snapshot.id,
                    'name': getattr(snapshot, 'name', 'unnamed'),
                    'status': getattr(snapshot, 'status', 'unknown'),
                    'volume_id': getattr(snapshot, 'volume_id', 'unknown')
                }
            }
            
        elif action.lower() == 'delete':
            # Find the snapshot
            snapshot = None
            for snap in conn.volume.snapshots():
                if getattr(snap, 'name', '') == snapshot_name or snap.id == snapshot_name:
                    snapshot = snap
                    break
            
            if not snapshot:
                return {
                    'success': False,
                    'message': f'Snapshot "{snapshot_name}" not found'
                }
            
            conn.volume.delete_snapshot(snapshot)
            
            return {
                'success': True,
                'message': f'Snapshot "{snapshot_name}" deleted successfully'
            }
            
        elif action.lower() == 'restore':
            volume_name = kwargs.get('volume_name', kwargs.get('name'))
            volume_size = kwargs.get('volume_size', kwargs.get('size'))
            
            if not volume_name:
                return {
                    'success': False,
                    'message': 'volume_name is required for restore action'
                }
            
            # Find the snapshot
            snapshot = None
            for snap in conn.volume.snapshots():
                if getattr(snap, 'name', '') == snapshot_name or snap.id == snapshot_name:
                    snapshot = snap
                    break
            
            if not snapshot:
                return {
                    'success': False,
                    'message': f'Snapshot "{snapshot_name}" not found'
                }
            
            create_params = {
                'name': volume_name,
                'size': volume_size or getattr(snapshot, 'size', 1),
                'snapshot_id': snapshot.id
            }
            
            volume = conn.volume.create_volume(**create_params)
            
            return {
                'success': True,
                'message': f'Volume "{volume_name}" created from snapshot "{snapshot_name}"',
                'volume': {
                    'id': volume.id,
                    'name': getattr(volume, 'name', 'unnamed'),
                    'status': getattr(volume, 'status', 'unknown'),
                    'size': getattr(volume, 'size', 0)
                }
            }
            
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete, restore, list'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage snapshot: {e}")
        return {
            'success': False,
            'message': f'Failed to manage snapshot: {str(e)}',
            'error': str(e)
        }


def set_volume_backups(
    action: str,
    backup_name: Optional[str] = None,
    project_id: str = "",
    status: str = "",
    **kwargs
) -> Dict[str, Any]:
    """
    Manage volume backups.
    
    Args:
        action: Action to perform (list, create, delete, restore)
        backup_name: Name of backup (for specific operations)
        **kwargs: Additional parameters
    
    Returns:
        Result of the backup operation
    """
    try:
        if action.lower() == 'list':
            scope_project_id = _scope_project_id(project_id)
            backups = get_volume_backups(
                project_id=project_id,
                status=status,
            )
            
            return {
                'success': True,
                'backups': backups,
                'count': len(backups),
                'scope': {
                    'project_id': scope_project_id,
                }
            }
            
        elif action.lower() == 'create':
            from ..connection import get_openstack_connection
            conn = get_openstack_connection()
            volume_id = kwargs.get('volume_id')
            description = kwargs.get('description', f'Backup {backup_name}')
            
            if not backup_name:
                return {
                    'success': False,
                    'message': 'backup_name is required for create action'
                }
                
            if not volume_id:
                return {
                    'success': False,
                    'message': 'volume_id is required for create action'
                }
            
            try:
                backup = conn.volume.create_backup(
                    volume_id=volume_id,
                    name=backup_name,
                    description=description
                )
                
                return {
                    'success': True,
                    'message': f'Backup "{backup_name}" created successfully',
                    'backup': {
                        'id': backup.id,
                        'name': getattr(backup, 'name', 'unnamed'),
                        'status': getattr(backup, 'status', 'unknown'),
                        'volume_id': getattr(backup, 'volume_id', 'unknown')
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create backup: {str(e)}'
                }
                
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, create'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage backup: {e}")
        return {
            'success': False,
            'message': f'Failed to manage backup: {str(e)}',
            'error': str(e)
        }


def set_volume_groups(action: str, group_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage volume groups (consistency groups).
    
    Args:
        action: Action to perform (list, create, delete)
        group_name: Name of group (for specific operations)
        **kwargs: Additional parameters
    
    Returns:
        Result of the group operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            groups = []
            try:
                for group in conn.volume.groups():
                    groups.append({
                        'id': group.id,
                        'name': getattr(group, 'name', 'unnamed'),
                        'status': getattr(group, 'status', 'unknown'),
                        'description': getattr(group, 'description', ''),
                        'group_type': getattr(group, 'group_type', 'unknown'),
                        'volume_types': getattr(group, 'volume_types', []),
                        'created_at': str(getattr(group, 'created_at', 'unknown'))
                    })
            except Exception as e:
                logger.warning(f"Volume groups may not be supported: {e}")
                return {
                    'success': False,
                    'message': 'Volume groups not supported or available',
                    'groups': []
                }
            
            return {
                'success': True,
                'groups': groups,
                'count': len(groups)
            }
            
        else:
            return {
                'success': False,
                'message': f'Action "{action}" not implemented for volume groups'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage volume group: {e}")
        return {
            'success': False,
            'message': f'Failed to manage volume group: {str(e)}',
            'error': str(e)
        }


def set_volume_qos(action: str, qos_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage volume QoS policies.
    
    Args:
        action: Action to perform (list, create, delete, show)
        qos_name: Name of QoS policy (for specific operations)
        **kwargs: Additional parameters
    
    Returns:
        Result of the QoS operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            qos_policies = []
            try:
                for qos in conn.volume.qos_specs():
                    qos_policies.append({
                        'id': qos.id,
                        'name': getattr(qos, 'name', 'unnamed'),
                        'consumer': getattr(qos, 'consumer', 'unknown'),
                        'specs': getattr(qos, 'specs', {}),
                        'created_at': str(getattr(qos, 'created_at', 'unknown'))
                    })
            except Exception as e:
                logger.warning(f"QoS specs may not be supported: {e}")
                return {
                    'success': False,
                    'message': 'QoS specs not supported or available',
                    'qos_policies': []
                }
            
            return {
                'success': True,
                'qos_policies': qos_policies,
                'count': len(qos_policies)
            }
            
        else:
            return {
                'success': False,
                'message': f'Action "{action}" not implemented for QoS policies'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage QoS policy: {e}")
        return {
            'success': False,
            'message': f'Failed to manage QoS policy: {str(e)}',
            'error': str(e)
        }


def get_server_volumes(instance_name: str) -> List[Dict[str, Any]]:
    """
    Get volumes attached to a specific server/instance.
    
    Args:
        instance_name: Server ID / instance UUID. Cinder DB stores instance_uuid, not server name.
        
    Returns:
        List of attached volumes
    """
    try:
        conn = _get_cinder_mariadb_connection()
        try:
            with conn.cursor() as cur:
                attachment_columns = _table_columns(cur, "volume_attachment")
                volume_columns = _table_columns(cur, "volumes")
                if not attachment_columns:
                    raise RuntimeError("MariaDB table 'volume_attachment' is not available")
                if not volume_columns:
                    raise RuntimeError("MariaDB table 'volumes' is not available")
                if "instance_uuid" not in attachment_columns:
                    raise RuntimeError("MariaDB table 'volume_attachment' has no instance_uuid column")

                attachment_deleted_expr = _column_expr("va", attachment_columns, "deleted", default="0")
                volume_deleted_expr = _column_expr("v", volume_columns, "deleted", default="0")
                name_expr = _column_expr("v", volume_columns, "name", "display_name", default="NULL")
                type_expr = _column_expr("v", volume_columns, "volume_type_id", "volume_type", default="NULL")
                bootable_expr = _column_expr("v", volume_columns, "bootable", default="0")
                encrypted_expr = _column_expr("v", volume_columns, "encryption_key_id", default="NULL")
                status_expr = _column_expr("v", volume_columns, "status", default="'unknown'")
                mountpoint_expr = _column_expr("va", attachment_columns, "mountpoint", default="NULL")
                attach_time_expr = _column_expr("va", attachment_columns, "attach_time", "created_at", default="NULL")
                attached_host_expr = _column_expr("va", attachment_columns, "attached_host", default="NULL")

                sql = (
                    "SELECT va.id AS attachment_id, va.volume_id, va.instance_uuid, "
                    f"{mountpoint_expr} AS device, {attach_time_expr} AS attached_at, "
                    f"{attached_host_expr} AS attached_host, "
                    f"{name_expr} AS volume_name, v.size, {status_expr} AS status, "
                    f"{type_expr} AS volume_type, {bootable_expr} AS bootable, "
                    f"{encrypted_expr} AS encryption_key_id "
                    "FROM volume_attachment va "
                    "LEFT JOIN volumes v ON v.id = va.volume_id "
                    "WHERE va.instance_uuid = %s "
                )
                params: List[Any] = [instance_name]
                if attachment_deleted_expr != "0":
                    sql += f"AND ({attachment_deleted_expr} = 0 OR {attachment_deleted_expr} = '0') "
                if volume_deleted_expr != "0":
                    sql += f"AND ({volume_deleted_expr} = 0 OR {volume_deleted_expr} = '0' OR v.id IS NULL) "
                sql += "ORDER BY attached_at DESC"

                cur.execute(sql, params)
                return [
                    {
                        "volume_id": row.get("volume_id"),
                        "volume_name": row.get("volume_name") or "unnamed",
                        "device": row.get("device") or "unknown",
                        "size": row.get("size") or 0,
                        "status": row.get("status") or "unknown",
                        "volume_type": row.get("volume_type") or "unknown",
                        "bootable": _bool_value(row.get("bootable")),
                        "encrypted": bool(row.get("encryption_key_id")),
                        "attachment_id": row.get("attachment_id") or "unknown",
                        "attached_at": _str_time(row.get("attached_at")),
                        "attached_host": row.get("attached_host"),
                        "server_id": row.get("instance_uuid"),
                        "data_source": "mariadb",
                    }
                    for row in cur.fetchall()
                ]
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Failed to get server volumes: {e}")
        return [{'error': str(e), 'instance_name': instance_name}]


def set_server_volume(instance_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage server volume attachments (attach, detach, list).
    
    Args:
        instance_name: Name or ID of the server
        action: Action to perform (attach, detach, list)
        **kwargs: Additional parameters (volume_name, device, etc.)
        
    Returns:
        Result of the volume attachment operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the server first
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
        
        if action.lower() == 'list':
            attached_volumes = get_server_volumes(instance_name)
            return {
                'success': True,
                'server_name': getattr(server, 'name', 'unnamed'),
                'server_id': server.id,
                'attached_volumes': attached_volumes,
                'count': len(attached_volumes)
            }
            
        elif action.lower() == 'attach':
            volume_name = kwargs.get('volume_name', kwargs.get('volume_id'))
            device = kwargs.get('device')
            
            if not volume_name:
                return {
                    'success': False,
                    'message': 'volume_name or volume_id is required for attach action'
                }
            
            # Find the volume
            volume = None
            for vol in conn.volume.volumes():
                if getattr(vol, 'name', '') == volume_name or vol.id == volume_name:
                    volume = vol
                    break
            
            if not volume:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" not found'
                }
            
            # Check if volume is available
            volume_status = getattr(volume, 'status', 'unknown')
            if volume_status not in ['available', 'in-use'] and not getattr(volume, 'multiattach', False):
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" is not available (status: {volume_status})'
                }
            
            # Attach the volume
            attach_params = {
                'volume_id': volume.id,
                'instance_uuid': server.id
            }
            
            if device:
                attach_params['device'] = device
            
            try:
                attachment = conn.compute.create_volume_attachment(server.id, **attach_params)
                return {
                    'success': True,
                    'message': f'Volume "{volume_name}" attached to server "{instance_name}"',
                    'attachment': {
                        'volume_id': volume.id,
                        'volume_name': getattr(volume, 'name', 'unnamed'),
                        'server_id': server.id,
                        'server_name': getattr(server, 'name', 'unnamed'),
                        'device': getattr(attachment, 'device', device or 'auto'),
                        'attachment_id': getattr(attachment, 'id', 'unknown')
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to attach volume: {str(e)}'
                }
                
        elif action.lower() == 'detach':
            volume_name = kwargs.get('volume_name', kwargs.get('volume_id'))
            
            if not volume_name:
                return {
                    'success': False,
                    'message': 'volume_name or volume_id is required for detach action'
                }
            
            # Find the volume
            volume = None
            for vol in conn.volume.volumes():
                if getattr(vol, 'name', '') == volume_name or vol.id == volume_name:
                    volume = vol
                    break
            
            if not volume:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" not found'
                }
            
            # Check if volume is attached to this server
            volume_attachments = getattr(volume, 'attachments', [])
            attached_to_server = False
            
            for attachment in volume_attachments:
                if attachment.get('server_id') == server.id:
                    attached_to_server = True
                    break
            
            if not attached_to_server:
                return {
                    'success': False,
                    'message': f'Volume "{volume_name}" is not attached to server "{instance_name}"'
                }
            
            try:
                conn.compute.delete_volume_attachment(volume.id, server.id)
                return {
                    'success': True,
                    'message': f'Volume "{volume_name}" detached from server "{instance_name}"'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to detach volume: {str(e)}'
                }
                
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: attach, detach, list'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage server volume: {e}")
        return {
            'success': False,
            'message': f'Failed to manage server volume: {str(e)}',
            'error': str(e)
        }
