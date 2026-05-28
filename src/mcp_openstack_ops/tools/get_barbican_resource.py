"""Unified Barbican resource query tool."""

import json
from datetime import datetime

from ..functions import (
    get_barbican_container_details as _get_barbican_container_details,
    get_barbican_containers as _get_barbican_containers,
    get_barbican_order_details as _get_barbican_order_details,
    get_barbican_orders as _get_barbican_orders,
    get_barbican_secret_details as _get_barbican_secret_details,
    get_barbican_secrets as _get_barbican_secrets,
)
from ..mcp_main import logger, mcp


def _project(items, fields: str):
    requested = [field.strip() for field in fields.split(",") if field.strip()]
    if not requested:
        return items
    return [{field: item.get(field) for field in requested if field in item} for item in items]


def _filter_query(items, query: str):
    if not query:
        return items
    target = query.strip()
    return [
        item for item in items
        if str(item.get("id", "")) == target
        or str(item.get("name", "")) == target
        or str(item.get("secret_ref", "")) == target
        or str(item.get("container_ref", "")) == target
        or str(item.get("order_ref", "")) == target
    ]


@mcp.tool()
async def get_barbican_resource(
    resource_type: str = "secret",
    query: str = "",
    status: str = "",
    project_id: str = "",
    type_filter: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> str:
    """
    Unified Barbican query for secrets, containers, and orders.

    Args:
        resource_type: secret, container, or order.
        query: Optional exact id/name/ref filter. Detail is returned when query is set.
        status: Optional status filter for list paths.
        project_id: Optional project ID filter when exposed by Barbican response metadata.
        type_filter: Optional secret_type, container type, or order type filter.
        limit: Max rows returned, 0 for full result.
        offset: Rows to skip.
        fields: Comma-separated response fields.
    """
    try:
        normalized_type = resource_type.strip().lower()
        if normalized_type in {"secret", "secrets"}:
            if query:
                result = _get_barbican_secret_details(secret_id_or_ref=query)
                items = [result.get("secret")] if result.get("secret") else []
            else:
                result = _get_barbican_secrets(secret_type=type_filter, status=status, project_id=project_id, limit=limit, offset=offset)
                items = _filter_query(result.get("secrets", []), query)
            result_key = "secrets"
        elif normalized_type in {"container", "containers"}:
            if query:
                result = _get_barbican_container_details(container_id_or_ref=query)
                items = [result.get("container")] if result.get("container") else []
            else:
                result = _get_barbican_containers(container_type=type_filter, status=status, project_id=project_id, limit=limit, offset=offset)
                items = _filter_query(result.get("containers", []), query)
            result_key = "containers"
        elif normalized_type in {"order", "orders"}:
            if query:
                result = _get_barbican_order_details(order_id_or_ref=query)
                items = [result.get("order")] if result.get("order") else []
            else:
                result = _get_barbican_orders(order_type=type_filter, status=status, project_id=project_id, limit=limit, offset=offset)
                items = _filter_query(result.get("orders", []), query)
            result_key = "orders"
        else:
            return "Error: resource_type must be secret, container, or order"

        items = _project([item for item in items if item], fields)
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "resource_type": normalized_type,
                "filter": {
                    "query": query,
                    "status": status,
                    "project_id": project_id,
                    "type_filter": type_filter,
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
        logger.error("Error: Failed to query Barbican resource - %s", e)
        return f"Error: Failed to query Barbican resource - {str(e)}"
