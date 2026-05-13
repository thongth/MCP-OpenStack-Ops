"""Tool implementation for get_floating_ips_by_project."""

import json
from datetime import datetime
from ..functions import get_floating_ips as _get_floating_ips
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_floating_ips_by_project(
    project_id: str,
    include_all_projects: bool = True,
    status: str = "",
) -> str:
    """Get floating IPs owned by a specific project."""
    try:
        floating_ips = _get_floating_ips(
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
                "total_floating_ips": len(floating_ips),
                "floating_ips": floating_ips,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch floating IPs by project - {e}")
        return f"Error: Failed to fetch floating IPs by project - {str(e)}"
