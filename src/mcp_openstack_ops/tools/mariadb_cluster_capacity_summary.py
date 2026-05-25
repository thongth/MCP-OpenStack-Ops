"""Tool implementation for mariadb_cluster_capacity_summary."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_capacity_summary as _mariadb_cluster_capacity_summary
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_capacity_summary() -> str:
    """Get MariaDB capacity summary across connections, storage, and largest tables."""
    try:
        result = _mariadb_cluster_capacity_summary()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB capacity summary - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
