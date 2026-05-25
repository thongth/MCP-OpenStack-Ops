"""Tool implementation for rabbitmq_cluster_connections."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_connections as _rabbitmq_cluster_connections
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_connections(limit: int = 100) -> str:
    """List RabbitMQ connections."""
    try:
        result = _rabbitmq_cluster_connections(limit=limit)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ connections - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
