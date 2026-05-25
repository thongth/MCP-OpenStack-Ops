"""Tool implementation for rabbitmq_cluster_alerts."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_alerts as _rabbitmq_cluster_alerts
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_alerts() -> str:
    """Get derived RabbitMQ cluster alerts."""
    try:
        result = _rabbitmq_cluster_alerts()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ alerts - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
