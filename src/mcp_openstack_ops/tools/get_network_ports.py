"""Tool implementation for get_network_ports."""

import json
from datetime import datetime
from ..functions import set_network_ports as _set_network_ports
from ..mcp_main import (
    logger,
    mcp,
)


@mcp.tool()
async def get_network_ports(
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
) -> str:
    """
    Get list of network ports with optional scope and status filters.

    Args:
        include_all_projects: Include resources from all projects when all-project read-only mode is enabled.
        project_id: Optional project ID filter (effective only in all-project read-only mode).
        status: Optional port status filter (case-insensitive exact match, e.g. ACTIVE, DOWN).

    Returns:
        JSON string containing network port list and summary.
    """
    try:
        logger.info(
            "Fetching network ports (include_all_projects=%s, project_id=%s, status=%s)",
            include_all_projects,
            project_id,
            status,
        )
        result = _set_network_ports(
            action="list",
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )

        response = {
            "timestamp": datetime.now().isoformat(),
            "result": result,
        }

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        error_msg = f"Error: Failed to fetch network ports - {str(e)}"
        logger.error(error_msg)
        return error_msg
