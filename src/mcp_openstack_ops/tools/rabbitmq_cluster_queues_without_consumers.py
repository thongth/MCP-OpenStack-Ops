"""Tool implementation for rabbitmq_cluster_queues_without_consumers."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_queues_without_consumers as _rabbitmq_cluster_queues_without_consumers
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_queues_without_consumers(
    vhost: str = "",
    min_messages: int = 0,
    limit: int = 100,
    fields: str = "",
) -> str:
    """
    List RabbitMQ queues with zero consumers.

    Args:
        vhost: Optional vhost. Empty means all vhosts. Use "/" for the default vhost.
        min_messages: Only include queues with at least this many messages.
        limit: Maximum queues returned.
        fields: Comma-separated fields to return, or "all" for full payload.
    """
    try:
        result = _rabbitmq_cluster_queues_without_consumers(
            vhost=vhost,
            min_messages=min_messages,
            limit=limit,
            fields=fields,
        )
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ queues without consumers - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
