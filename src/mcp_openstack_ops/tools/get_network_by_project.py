"""Tool implementation for get_network_by_project."""

import json
from datetime import datetime
from ..functions import get_network_details as _get_network_details
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_network_by_project(
    project_id: str,
    include_all_projects: bool = True,
    status: str = "",
) -> str:
    """Get networks for a specific project ID."""
    try:
        networks = _get_network_details(
            network_name="all",
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
                "total_networks": len(networks),
                "networks": networks,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch networks by project - {e}")
        return f"Error: Failed to fetch networks by project - {str(e)}"
