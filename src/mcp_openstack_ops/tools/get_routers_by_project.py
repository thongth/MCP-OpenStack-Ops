"""Tool implementation for get_routers_by_project."""

import json
from datetime import datetime
from ..functions import get_routers as _get_routers
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_routers_by_project(
    project_id: str,
    include_all_projects: bool = True,
    status: str = "",
) -> str:
    """Get routers for a specific project ID."""
    try:
        routers = _get_routers(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "project_id": project_id,
                    "include_all_projects": include_all_projects,
                    "status": status,
                },
                "total_routers": len(routers),
                "routers": routers,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch routers by project - {e}")
        return f"Error: Failed to fetch routers by project - {str(e)}"
