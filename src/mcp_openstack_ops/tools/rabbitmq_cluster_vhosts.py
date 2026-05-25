"""Tool implementation for rabbitmq_cluster_vhosts."""

import json
from datetime import datetime
from ..functions import rabbitmq_cluster_vhosts as _rabbitmq_cluster_vhosts
from ..mcp_main import logger, mcp


@mcp.tool()
async def rabbitmq_cluster_vhosts() -> str:
    """List RabbitMQ virtual hosts."""
    try:
        result = _rabbitmq_cluster_vhosts()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get RabbitMQ vhosts - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
