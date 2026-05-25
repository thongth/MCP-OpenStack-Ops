"""Tool implementation for mariadb_cluster_health."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_health as _mariadb_cluster_health
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_health() -> str:
    """Get MariaDB node and Galera cluster health."""
    try:
        result = _mariadb_cluster_health()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB cluster health - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
