"""Tool implementation for get_subnet_by_network."""

import json
from datetime import datetime
from ..functions import get_network_details as _get_network_details
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_subnet_by_network(
    network_name_or_id: str,
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """Get subnets belonging to a specific network (by name or ID)."""
    try:
        networks = _get_network_details(
            network_name=network_name_or_id,
            include_all_projects=include_all_projects,
            project_id=project_id,
            status="",
        )

        subnets = []
        for network in networks:
            for subnet in network.get("subnets", []):
                subnets.append(
                    {
                        "network_id": network.get("id"),
                        "network_name": network.get("name"),
                        **subnet,
                    }
                )

        result = {
            "timestamp": datetime.now().isoformat(),
            "query": network_name_or_id,
            "found_networks": len(networks),
            "total_subnets": len(subnets),
            "subnets": subnets,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to fetch subnets by network - {str(e)}"
        logger.error(error_msg)
        return error_msg
