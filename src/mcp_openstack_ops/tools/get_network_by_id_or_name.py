"""Tool implementation for get_network_by_id_or_name."""

import json
from datetime import datetime
from ..functions import get_network_details as _get_network_details
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_network_by_id_or_name(
    network_id_or_name: str,
    project_id: str = "",
    status: str = "",
) -> str:
    """Get network details by exact network ID or name."""
    try:
        networks = _get_network_details(
            network_name=network_id_or_name,
            project_id=project_id,
            status=status,
        )
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "query": network_id_or_name,
                "found": len(networks) > 0,
                "total_networks": len(networks),
                "networks": networks,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch network by id or name - {e}")
        return f"Error: Failed to fetch network by id or name - {str(e)}"
