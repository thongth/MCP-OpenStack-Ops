"""Tool implementation for mariadb_cluster_storage_utilization."""

import json
from datetime import datetime
from ..functions import mariadb_cluster_storage_utilization as _mariadb_cluster_storage_utilization
from ..mcp_main import logger, mcp


@mcp.tool()
async def mariadb_cluster_storage_utilization() -> str:
    """Get MariaDB storage utilization grouped by schema."""
    try:
        result = _mariadb_cluster_storage_utilization()
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Error: Failed to get MariaDB storage utilization - {e}")
        return json.dumps({"timestamp": datetime.now().isoformat(), "success": False, "error": str(e)}, indent=2)
