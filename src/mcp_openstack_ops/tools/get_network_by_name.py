"""Tool implementation for get_network_by_name."""

import json
from datetime import datetime
from ..functions import get_network_details as _get_network_details
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_network_by_name(
    network_name: str,
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
) -> str:
    """Get network details by exact network name (or ID)."""
    try:
        networks = _get_network_details(
            network_name=network_name,
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "query": network_name,
                "found": len(networks) > 0,
                "total_networks": len(networks),
                "networks": networks,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch network by name - {e}")
        return f"Error: Failed to fetch network by name - {str(e)}"
