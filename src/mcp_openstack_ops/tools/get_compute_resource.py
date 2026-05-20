"""Unified compute resource query tool."""

import json
from datetime import datetime
from ..functions import (
    get_availability_zones as _get_availability_zones,
    get_hypervisor_details as _get_hypervisor_details,
    get_instance_details as _get_instance_details,
    get_instances_by_status as _get_instances_by_status,
    get_server_events as _get_server_events,
    get_server_groups as _get_server_groups,
)
from ..mcp_main import logger, mcp

def _project(items, fields: str):
    requested = [field.strip() for field in fields.split(",") if field.strip()]
    if not requested:
        return items
    return [{field: item.get(field) for field in requested if field in item} for item in items]

def _matches_query(item, query: str) -> bool:
    if not query:
        return True
    target = query.strip().lower()
    for field in ("id", "uuid", "name", "host", "hypervisor_hostname"):
        if str(item.get(field, "")).lower() == target:
            return True
    return False

def _filter_page(items, query: str, project_id: str, status: str, host: str, availability_zone: str, limit: int, offset: int):
    filtered = []
    for item in items:
        if not _matches_query(item, query):
            continue
        if project_id and str(item.get("project_id") or item.get("tenant_id") or "") != project_id:
            continue
        if status and str(item.get("status") or item.get("vm_state") or "").lower() != status.strip().lower():
            continue
        if host and str(item.get("host") or item.get("hypervisor_hostname") or "").lower() != host.strip().lower():
            continue
        if availability_zone and str(item.get("availability_zone") or "").lower() != availability_zone.strip().lower():
            continue
        filtered.append(item)
    safe_offset = max(int(offset or 0), 0)
    safe_limit = max(int(limit or 0), 0)
    return filtered[safe_offset:safe_offset + safe_limit] if safe_limit else filtered

@mcp.tool()
async def get_compute_resource(
    resource_type: str = "instance",
    query: str = "",
    project_id: str = "",
    status: str = "",
    host: str = "",
    availability_zone: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> str:
    """
    Unified compute query for instances, server events, server groups, hypervisors, and availability zones.

    Args:
        resource_type: instance, server, event, server_event, server_group, hypervisor, or availability_zone.
        query: Optional exact id/name/host filter. Required for server_event.
        project_id: Optional project ID filter where the resource has project scope.
        status: Optional status filter.
        host: Optional host/hypervisor filter.
        availability_zone: Optional availability zone filter.
        limit: Max rows returned, 0 for full result.
        offset: Rows to skip.
        fields: Comma-separated response fields.
    """
    try:
        normalized_type = resource_type.strip().lower()

        if normalized_type in {"instance", "instances", "server", "servers"}:
            if status and not any([query, project_id, host, availability_zone]):
                items = _get_instances_by_status(status)
            else:
                result = _get_instance_details(limit=max(limit, 1), offset=offset, include_all=bool(query or project_id or host or availability_zone))
                items = result.get("instances", []) if isinstance(result, dict) else []
            result_key = "instances"
            items = _filter_page(items, query, project_id, status, host, availability_zone, limit, offset)

        elif normalized_type in {"event", "events", "server_event", "server_events"}:
            if not query:
                return "Error: query must be an instance name or ID for server_event resources"
            result = _get_server_events(instance_name=query, limit=max(int(limit or 50), 1))
            items = result.get("events", []) if isinstance(result, dict) else []
            result_key = "events"

        elif normalized_type in {"server_group", "server_groups"}:
            items = _filter_page(_get_server_groups(), query, project_id, status, host, availability_zone, limit, offset)
            result_key = "server_groups"

        elif normalized_type in {"hypervisor", "hypervisors"}:
            result = _get_hypervisor_details(hypervisor_name=query or "all")
            items = result.get("hypervisors", []) if isinstance(result, dict) else []
            items = _filter_page(items, "", project_id, status, host, availability_zone, limit, offset)
            result_key = "hypervisors"

        elif normalized_type in {"availability_zone", "availability_zones", "az"}:
            result = _get_availability_zones()
            items = result.get("availability_zones", []) if isinstance(result, dict) else []
            items = _filter_page(items, query, project_id, status, host, availability_zone, limit, offset)
            result_key = "availability_zones"

        else:
            return "Error: resource_type must be instance, server_event, server_group, hypervisor, or availability_zone"

        items = _project(items, fields)
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "resource_type": normalized_type,
                "filter": {
                    "query": query,
                    "project_id": project_id,
                    "status": status,
                    "host": host,
                    "availability_zone": availability_zone,
                    "limit": limit,
                    "offset": offset,
                    "fields": fields,
                },
                "count": len(items),
                result_key: items,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    except Exception as e:
        logger.error(f"Error: Failed to query compute resource - {e}")
        return f"Error: Failed to query compute resource - {str(e)}"
