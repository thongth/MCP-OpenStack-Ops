"""Tool implementation for get_network."""

import json
from datetime import datetime
from ..functions import get_network_details as _get_network_details
from ..mcp_main import (
    logger,
    mcp,
)


@mcp.tool()
async def get_network(
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
) -> str:
    """
    Get list of OpenStack networks.

    Args:
        include_all_projects: Include resources from all projects when all-project read-only mode is enabled.
        project_id: Optional project ID filter (effective only in all-project read-only mode).
        status: Optional network status filter (case-insensitive exact match, e.g. ACTIVE, DOWN).

    Returns:
        JSON string containing network list and summary.
    """
    try:
        logger.info(
            "Fetching network list (include_all_projects=%s, project_id=%s, status=%s)",
            include_all_projects,
            project_id,
            status,
        )
        networks = _get_network_details(
            network_name="all",
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )

        result = {
            "timestamp": datetime.now().isoformat(),
            "total_networks": len(networks),
            "networks": networks,
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        error_msg = f"Error: Failed to fetch network list - {str(e)}"
        logger.error(error_msg)
        return error_msg
