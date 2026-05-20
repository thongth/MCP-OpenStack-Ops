"""Unified load balancer resource query tool."""

import json
from datetime import datetime
from ..functions import (
    get_load_balancer_amphorae as _get_load_balancer_amphorae,
    get_load_balancer_details as _get_load_balancer_details,
    get_load_balancer_health_monitors as _get_load_balancer_health_monitors,
    get_load_balancer_l7_policies as _get_load_balancer_l7_policies,
    get_load_balancer_l7_rules as _get_load_balancer_l7_rules,
    get_load_balancer_list as _get_load_balancer_list,
    get_load_balancer_listeners as _get_load_balancer_listeners,
    get_load_balancer_pool_members as _get_load_balancer_pool_members,
    get_load_balancer_pools as _get_load_balancer_pools,
)
from ..mcp_main import logger, mcp

def _project(items, fields: str):
    requested = [field.strip() for field in fields.split(",") if field.strip()]
    if not requested:
        return items
    return [{field: item.get(field) for field in requested if field in item} for item in items]

def _extract_items(result, *keys: str):
    if isinstance(result, list):
        return result
    if not isinstance(result, dict):
        return []
    for key in keys:
        value = result.get(key)
        if isinstance(value, list):
            return value
    for key in ("load_balancers", "listeners", "pools", "members", "health_monitors", "l7_policies", "l7_rules", "amphorae"):
        value = result.get(key)
        if isinstance(value, list):
            return value
    return []

def _matches_query(item, query: str) -> bool:
    if not query:
        return True
    target = query.strip().lower()
    for field in ("id", "name", "loadbalancer_id", "listener_id", "pool_id", "amphora_id", "compute_id", "lb_network_ip"):
        if str(item.get(field, "")).lower() == target:
            return True
    return False

def _filter_page(items, query: str, project_id: str, status: str, limit: int, offset: int):
    filtered = []
    for item in items:
        if not _matches_query(item, query):
            continue
        if project_id and str(item.get("project_id") or item.get("tenant_id") or "") != project_id:
            continue
        if status:
            candidate = item.get("provisioning_status") or item.get("operating_status") or item.get("status")
            if str(candidate or "").lower() != status.strip().lower():
                continue
        filtered.append(item)
    safe_offset = max(int(offset or 0), 0)
    safe_limit = max(int(limit or 0), 0)
    return filtered[safe_offset:safe_offset + safe_limit] if safe_limit else filtered

@mcp.tool()
async def get_loadbalancer_resource(
    resource_type: str = "load_balancer",
    query: str = "",
    parent_id: str = "",
    project_id: str = "",
    status: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
    include_amphora_instance_details: bool = True,
) -> str:
    """
    Unified Octavia query for load balancers and related resources.

    Args:
        resource_type: load_balancer, listener, pool, member, health_monitor, l7_policy, l7_rule, or amphora.
        query: Optional exact id/name filter. Used as target for load_balancer detail when resource_type is load_balancer and parent_id is empty.
        parent_id: Optional parent load balancer/listener/pool/policy ID or name. Listener queries can omit it to list all listeners.
        project_id: Optional project ID filter for load balancers and post-filtered child resources.
        status: Optional provisioning/operating status filter.
        limit: Max rows returned, 0 for full result.
        offset: Rows to skip.
        fields: Comma-separated response fields.
        include_amphora_instance_details: Include linked Nova instance details for load balancer detail/amphora paths.
    """
    try:
        normalized_type = resource_type.strip().lower()

        if normalized_type in {"load_balancer", "load_balancers", "lb", "lbs"}:
            if query:
                result = _get_load_balancer_details(
                    lb_name_or_id=query,
                    include_amphorae=True,
                    include_amphora_instance_details=include_amphora_instance_details,
                )
                items = [result] if isinstance(result, dict) else []
            else:
                result = _get_load_balancer_list(limit=max(int(limit or 50), 1), offset=offset, include_all=not bool(limit), project_id=project_id)
                items = _extract_items(result, "load_balancers")
            result_key = "load_balancers"

        elif normalized_type in {"listener", "listeners"}:
            result = _get_load_balancer_listeners(lb_name_or_id=parent_id)
            items = _filter_page(_extract_items(result, "listeners"), query, project_id, status, limit, offset)
            result_key = "listeners"

        elif normalized_type in {"pool", "pools"}:
            result = _get_load_balancer_pools(listener_name_or_id=parent_id or None)
            items = _filter_page(_extract_items(result, "pools"), query, project_id, status, limit, offset)
            result_key = "pools"

        elif normalized_type in {"member", "members", "pool_member", "pool_members"}:
            if not parent_id:
                return "Error: parent_id must be a pool name or ID for member resources"
            result = _get_load_balancer_pool_members(pool_name_or_id=parent_id)
            items = _filter_page(_extract_items(result, "members"), query, project_id, status, limit, offset)
            result_key = "members"

        elif normalized_type in {"health_monitor", "health_monitors", "hm"}:
            result = _get_load_balancer_health_monitors(pool_name_or_id=parent_id)
            items = _filter_page(_extract_items(result, "health_monitors"), query, project_id, status, limit, offset)
            result_key = "health_monitors"

        elif normalized_type in {"l7_policy", "l7_policies"}:
            result = _get_load_balancer_l7_policies(listener_name_or_id=parent_id)
            items = _filter_page(_extract_items(result, "l7_policies"), query, project_id, status, limit, offset)
            result_key = "l7_policies"

        elif normalized_type in {"l7_rule", "l7_rules"}:
            if not parent_id:
                return "Error: parent_id must be an L7 policy name or ID for l7_rule resources"
            result = _get_load_balancer_l7_rules(policy_name_or_id=parent_id)
            items = _filter_page(_extract_items(result, "l7_rules"), query, project_id, status, limit, offset)
            result_key = "l7_rules"

        elif normalized_type in {"amphora", "amphorae"}:
            result = _get_load_balancer_amphorae(lb_name_or_id=parent_id or query)
            items = _filter_page(_extract_items(result, "amphorae"), "" if parent_id else query, project_id, status, limit, offset)
            result_key = "amphorae"

        else:
            return "Error: resource_type must be load_balancer, listener, pool, member, health_monitor, l7_policy, l7_rule, or amphora"

        items = _project(items, fields)
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "resource_type": normalized_type,
                "filter": {
                    "query": query,
                    "parent_id": parent_id,
                    "project_id": project_id,
                    "status": status,
                    "limit": limit,
                    "offset": offset,
                    "fields": fields,
                    "include_amphora_instance_details": include_amphora_instance_details,
                },
                "count": len(items),
                result_key: items,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    except Exception as e:
        logger.error(f"Error: Failed to query load balancer resource - {e}")
        return f"Error: Failed to query load balancer resource - {str(e)}"
