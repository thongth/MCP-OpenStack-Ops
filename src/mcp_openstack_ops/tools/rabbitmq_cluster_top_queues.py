"""Tool implementation for rabbitmq_cluster_top_queues."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_top_queues as _rabbitmq_cluster_top_queues
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_top_queues(
    sort_by: str = "messages",
    vhost: str = "",
    limit: int = 20,
    fields: str = "",
) -> str:
    """
    List top RabbitMQ queues by backlog, consumers, memory, or message rates.

    Args:
        sort_by: messages, ready, unack, consumers, memory, publish_rate, or deliver_rate.
        vhost: Optional vhost. Empty means all vhosts. Use "/" for the default vhost.
        limit: Maximum queues returned.
        fields: Comma-separated fields to return, or "all" for full payload.
    """
    try:
        result = _rabbitmq_cluster_top_queues(sort_by=sort_by, vhost=vhost, limit=limit, fields=fields)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ top queues - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
