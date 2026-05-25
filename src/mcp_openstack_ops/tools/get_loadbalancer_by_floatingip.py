"""Tool implementation for get_loadbalancer_by_floatingip."""

import json
from datetime import datetime
from ..functions import get_loadbalancer_by_floatingip as _get_loadbalancer_by_floatingip
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_loadbalancer_by_floatingip(floating_ip: str) -> str:
    """
    Get OpenStack load balancer details by floating IP address or floating IP ID.

    Use when user requests:
    - "Find load balancer by floating IP [address]"
    - "Which load balancer uses public IP [address]?"
    - "Show LB behind floating IP [address]"

    Args:
        floating_ip: Floating IP address or floating IP ID to query

    Returns:
        JSON string containing floating IP metadata and matching load balancer details
    """
    try:
        logger.info(f"Getting load balancer by floating IP: {floating_ip}")
        result = _get_loadbalancer_by_floatingip(floating_ip=floating_ip)
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "result": result,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    except Exception as e:
        error_msg = f"Error: Failed to get load balancer by floating IP - {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "success": False,
            },
            indent=2,
        )
