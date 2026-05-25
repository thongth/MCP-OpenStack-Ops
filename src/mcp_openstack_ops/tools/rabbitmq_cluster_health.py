"""Tool implementation for rabbitmq_cluster_health."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_health as _rabbitmq_cluster_health
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_health() -> str:
    """Get RabbitMQ cluster health and derived alerts."""
    try:
        result = _rabbitmq_cluster_health()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ health - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
