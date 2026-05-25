"""Tool implementation for rabbitmq_cluster_nodes."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_nodes as _rabbitmq_cluster_nodes
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_nodes() -> str:
    """Get RabbitMQ node details from the Management API."""
    try:
        result = _rabbitmq_cluster_nodes()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ nodes - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
