"""Tool implementation for mariadb_cluster_query_performance."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_query_performance as _mariadb_cluster_query_performance
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_query_performance() -> str:
    """Get MariaDB query counters, QPS, slow query, and temp table metrics."""
    try:
        result = _mariadb_cluster_query_performance()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB query performance - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
