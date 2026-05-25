"""Tool implementation for rabbitmq_cluster_queues."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_queues as _rabbitmq_cluster_queues
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_queues(vhost: str = "", name: str = "", limit: int = 100) -> str:
    """List RabbitMQ queues, optionally scoped by vhost and queue name."""
    try:
        result = _rabbitmq_cluster_queues(vhost=vhost, name=name, limit=limit)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ queues - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
