"""Tool implementation for get_load_balancer_by_vip."""

import json
from datetime import datetime
from ..functions import get_load_balancer_by_vip as _get_load_balancer_by_vip
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_load_balancer_by_vip(vip_address: str) -> str:
    """
    Get OpenStack load balancer details by exact VIP address.

    Use when user requests:
    - "Find load balancer by VIP [address]"
    - "Which load balancer owns VIP [address]?"
    - "Show LB for internal IP [address]"

    Args:
        vip_address: Exact load balancer VIP address to query

    Returns:
        JSON string containing matching load balancer details
    """
    try:
        logger.info(f"Getting load balancer by VIP address: {vip_address}")
        result = _get_load_balancer_by_vip(vip_address=vip_address)
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
        error_msg = f"Error: Failed to get load balancer by VIP - {str(e)}"
        logger.error(error_msg)
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "success": False,
            },
            indent=2,
        )
