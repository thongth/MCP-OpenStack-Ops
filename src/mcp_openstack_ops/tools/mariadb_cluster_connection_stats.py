"""Tool implementation for mariadb_cluster_connection_stats."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_connection_stats as _mariadb_cluster_connection_stats
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_connection_stats() -> str:
    """Get MariaDB connection counters and connection usage."""
    try:
        result = _mariadb_cluster_connection_stats()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB connection stats - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
