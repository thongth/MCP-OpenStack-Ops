"""Tool implementation for mariadb_cluster_alerts."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_alerts as _mariadb_cluster_alerts
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_alerts() -> str:
    """Get derived MariaDB cluster alerts from status counters."""
    try:
        result = _mariadb_cluster_alerts()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB cluster alerts - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
