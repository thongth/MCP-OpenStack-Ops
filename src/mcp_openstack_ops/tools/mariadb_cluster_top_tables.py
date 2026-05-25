"""Tool implementation for mariadb_cluster_top_tables."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_top_tables as _mariadb_cluster_top_tables
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_top_tables(limit: int = 20) -> str:
    """Get largest MariaDB tables by data and index size."""
    try:
        result = _mariadb_cluster_top_tables(limit=limit)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB top tables - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
