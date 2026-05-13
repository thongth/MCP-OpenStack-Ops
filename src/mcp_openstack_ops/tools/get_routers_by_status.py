"""Tool implementation for get_routers_by_status."""

import json
from datetime import datetime
from ..functions import get_routers as _get_routers
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_routers_by_status(
    status: str,
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """Get routers filtered by router status (e.g. ACTIVE, DOWN, ERROR)."""
    try:
        routers = _get_routers(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {"status": status, "include_all_projects": include_all_projects, "project_id": project_id},
                "total_routers": len(routers),
                "routers": routers,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch routers by status - {e}")
        return f"Error: Failed to fetch routers by status - {str(e)}"
