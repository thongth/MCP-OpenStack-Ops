"""Unified storage resource query tool."""

import json
from datetime import datetime
from ..functions import (
    get_volume_backups as _get_volume_backups,
    get_volume_list as _get_volume_list,
    get_volume_snapshots as _get_volume_snapshots,
)
from ..mcp_main import logger, mcp


def _project(items, fields: str):
    requested = [field.strip() for field in fields.split(",") if field.strip()]
    if not requested:
        return items
    return [{field: item.get(field) for field in requested if field in item} for item in items]


@mcp.tool()
async def get_storage_resource(
    resource_type: str = "volume",
    query: str = "",
    project_id: str = "",
    status: str = "",
    availability_zone: str = "",
    volume_type: str = "",
    attached_instance: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> str:
    """
    Unified storage query for volumes, volume snapshots, and volume backups.

    Args:
        resource_type: volume, snapshot, volume_snapshot, backup, or volume_backup.
        query: Optional exact id/name filter.
        project_id: Optional project ID filter.
        status: Optional status filter.
        availability_zone: Optional availability zone filter.
        volume_type: Optional volume type filter for volumes.
        attached_instance: Optional instance UUID filter for attached volumes.
        limit: Max rows returned, 0 for full result, capped in service.
        offset: Rows to skip.
        fields: Comma-separated response fields.
    """
    try:
        normalized_type = resource_type.strip().lower()
        if normalized_type in {"volume", "volumes"}:
            items = _get_volume_list(
                project_id=project_id,
                status=status,
                limit=limit,
                offset=offset,
            )
            result_key = "volumes"
        elif normalized_type in {"snapshot", "snapshots", "volume_snapshot", "volume_snapshots"}:
            items = _get_volume_snapshots(
                project_id=project_id,
                status=status,
                limit=limit,
                offset=offset,
            )
            result_key = "snapshots"
        elif normalized_type in {"backup", "backups", "volume_backup", "volume_backups"}:
            items = _get_volume_backups(
                project_id=project_id,
                status=status,
                limit=limit,
                offset=offset,
            )
            result_key = "backups"
        else:
            return "Error: resource_type must be volume, volume_snapshot, or volume_backup"

        if query:
            query_value = query.strip()
            items = [
                item for item in items
                if str(item.get("id", "")) == query_value or str(item.get("name", "")) == query_value
            ]
        if availability_zone:
            items = [
                item for item in items
                if str(item.get("availability_zone", "")).lower() == availability_zone.strip().lower()
            ]
        if volume_type and result_key == "volumes":
            items = [
                item for item in items
                if str(item.get("volume_type", "")).lower() == volume_type.strip().lower()
            ]
        if attached_instance and result_key == "volumes":
            target_instance = attached_instance.strip()
            items = [
                item for item in items
                if any(str(att.get("server_id", "")) == target_instance for att in item.get("attachments", []) or [])
            ]

        items = _project(items, fields)
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "resource_type": normalized_type,
                "filter": {
                    "query": query,
                    "project_id": project_id,
                    "status": status,
                    "availability_zone": availability_zone,
                    "volume_type": volume_type,
                    "attached_instance": attached_instance,
                    "limit": limit,
                    "offset": offset,
                    "fields": fields,
                },
                "count": len(items),
                result_key: items,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to query storage resource - {e}")
        return f"Error: Failed to query storage resource - {str(e)}"
