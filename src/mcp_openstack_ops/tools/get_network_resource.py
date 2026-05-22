"""Unified network resource query tool."""

import json
from datetime import datetime
from ..functions import (
    get_floating_ips as _get_floating_ips,
    get_network_agents as _get_network_agents,
    get_network_details as _get_network_details,
    get_routers as _get_routers,
    get_security_groups as _get_security_groups,
    set_network_ports as _set_network_ports,
)
from ..mcp_main import logger, mcp

def _project(items, fields: str):
    requested = [field.strip() for field in fields.split(",") if field.strip()]
    if not requested:
        return items
    return [{field: item.get(field) for field in requested if field in item} for item in items]

def _extract_items(result, key: str):
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        value = result.get(key)
        if isinstance(value, list):
            return value
        for fallback in ("ports", "network_agents", "agents", "security_groups", "routers", "floating_ips", "networks"):
            value = result.get(fallback)
            if isinstance(value, list):
                return value
    return []

def _matches_query(item, query: str) -> bool:
    if not query:
        return True
    target = query.strip().lower()
    for field in (
        "id",
        "name",
        "network_id",
        "port_id",
        "router_id",
        "device_id",
        "mac_address",
        "floating_ip_address",
        "fixed_ip_address",
        "host",
    ):
        if str(item.get(field, "")).lower() == target:
            return True
    for fixed_ip in item.get("fixed_ips", []) or []:
        if str(fixed_ip.get("ip_address", "")).lower() == target:
            return True
    return False

def _filter_page(items, query: str, project_id: str, status: str, limit: int, offset: int):
    filtered = []
    for item in items:
        if not _matches_query(item, query):
            continue
        if project_id and str(item.get("project_id") or item.get("tenant_id") or "") != project_id:
            continue
        if status and str(item.get("status") or item.get("admin_state_up") or "").lower() != status.strip().lower():
            continue
        filtered.append(item)
    safe_offset = max(int(offset or 0), 0)
    safe_limit = max(int(limit or 0), 0)
    return filtered[safe_offset:safe_offset + safe_limit] if safe_limit else filtered

@mcp.tool()
async def get_network_resource(
    resource_type: str = "network",
    query: str = "",
    project_id: str = "",
    status: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
    include_subnets: bool = True,
) -> str:
    """
    Unified network query for networks, ports, routers, security groups, floating IPs, and agents.

    Args:
        resource_type: network, port, router, security_group, floating_ip, or agent.
        query: Optional exact id/name/IP/host filter.
        project_id: Optional project ID filter.
        status: Optional status filter.
        limit: Max rows returned, 0 for full result.
        offset: Rows to skip.
        fields: Comma-separated response fields.
        include_subnets: Include subnet data when querying networks.
    """
    try:
        normalized_type = resource_type.strip().lower()

        if normalized_type in {"network", "networks"}:
            items = _get_network_details(
                network_name=query or "all",
                project_id=project_id,
                status=status,
                limit=limit,
                offset=offset,
                include_subnets=include_subnets,
            )
            result_key = "networks"
        elif normalized_type in {"port", "ports"}:
            result = _set_network_ports(action="list", project_id=project_id, status=status)
            items = _filter_page(_extract_items(result, "ports"), query, "", "", limit, offset)
            result_key = "ports"
        elif normalized_type in {"router", "routers"}:
            items = _filter_page(_get_routers(project_id=project_id, status=status), query, "", "", limit, offset)
            result_key = "routers"
        elif normalized_type in {"security_group", "security_groups", "sg"}:
            items = _filter_page(_get_security_groups(project_id=project_id), query, "", status, limit, offset)
            result_key = "security_groups"
        elif normalized_type in {"floating_ip", "floating_ips", "fip"}:
            items = _filter_page(_get_floating_ips(project_id=project_id, status=status), query, "", "", limit, offset)
            result_key = "floating_ips"
        elif normalized_type in {"agent", "agents", "network_agent", "network_agents"}:
            result = _get_network_agents()
            items = _filter_page(_extract_items(result, "network_agents"), query, project_id, status, limit, offset)
            result_key = "network_agents"
        else:
            return "Error: resource_type must be network, port, router, security_group, floating_ip, or agent"

        items = _project(items, fields)
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "resource_type": normalized_type,
                "filter": {
                    "query": query,
                    "project_id": project_id,
                    "status": status,
                    "limit": limit,
                    "offset": offset,
                    "fields": fields,
                    "include_subnets": include_subnets,
                },
                "count": len(items),
                result_key: items,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    except Exception as e:
        logger.error(f"Error: Failed to query network resource - {e}")
        return f"Error: Failed to query network resource - {str(e)}"
