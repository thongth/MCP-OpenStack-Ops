"""Tool implementation for mariadb_cluster_wsrep_status."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_wsrep_status as _mariadb_cluster_wsrep_status
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_wsrep_status() -> str:
    """Get raw MariaDB Galera wsrep status and variables."""
    try:
        result = _mariadb_cluster_wsrep_status()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB wsrep status - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
