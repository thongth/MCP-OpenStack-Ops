"""Tool implementation for get_network_agents."""

import json
from datetime import datetime
from ..functions import get_network_agents as _get_network_agents
from ..mcp_main import (
    logger,
    mcp,
)


@mcp.tool()
async def get_network_agents(
    agent_type: str = "",
    host: str = "",
    alive_only: bool = False
) -> str:
    """
    Get OpenStack Neutron network agents.

    Args:
        agent_type: Optional filter by agent type (substring)
        host: Optional filter by host (substring)
        alive_only: If True, return alive agents only

    Returns:
        JSON string with network agent list
    """
    try:
        logger.info(
            "Fetching network agents (agent_type=%s, host=%s, alive_only=%s)",
            agent_type,
            host,
            alive_only,
        )
        agents = _get_network_agents(
            agent_type=agent_type,
            host=host,
            alive_only=alive_only,
        )

        result = {
            "timestamp": datetime.now().isoformat(),
            "operation": "get_network_agents",
            "parameters": {
                "agent_type": agent_type,
                "host": host,
                "alive_only": alive_only,
            },
            "total_agents": len(agents),
            "network_agents": agents,
        }

        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to fetch network agents - {str(e)}"
        logger.error(error_msg)
        return error_msg
