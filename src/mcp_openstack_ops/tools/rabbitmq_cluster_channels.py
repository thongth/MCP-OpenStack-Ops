"""Tool implementation for rabbitmq_cluster_channels."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_channels as _rabbitmq_cluster_channels
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_channels(limit: int = 100) -> str:
    """List RabbitMQ channels."""
    try:
        result = _rabbitmq_cluster_channels(limit=limit)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ channels - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
