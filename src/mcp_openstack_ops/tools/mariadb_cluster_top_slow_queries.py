"""Tool implementation for mariadb_cluster_top_slow_queries."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_top_slow_queries as _mariadb_cluster_top_slow_queries
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_top_slow_queries(limit: int = 10) -> str:
    """Get top statement digests by total execution time from performance_schema."""
    try:
        result = _mariadb_cluster_top_slow_queries(limit=limit)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB top slow queries - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
