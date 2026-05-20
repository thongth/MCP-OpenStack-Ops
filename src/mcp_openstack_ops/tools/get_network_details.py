"""Tool implementation for get_network_details."""

import json
from datetime import datetime
from ..functions import get_network_details as _get_network_details
from ..mcp_main import (
    logger,
    mcp,
)

@mcp.tool()
async def get_network_details(
    network_name: str = "all",
    project_id: str = "",
    status: str = "",
    name_contains: str = "",
    limit: int = 0,
    offset: int = 0,
    include_subnets: bool = True,
) -> str:
    """
    Provides detailed information for OpenStack networks, subnets, routers, and security groups.
    
    Functions:
    - Query configuration information for specified network or all networks
    - Check subnet configuration and IP allocation status per network
    - Collect router connection status and gateway configuration
    - Analyze security group rules and port information
    
    Use when user requests network information, subnet details, router configuration, or network troubleshooting.
    
    Args:
        network_name: Name of network to query or "all" for all networks (default: "all")
        
    Returns:
        Network detailed information in JSON format with networks, subnets, routers, and security groups.
    """
    try:
        logger.info(
            f"Fetching network details: {network_name} ("
            f"project_id={project_id}, status={status})"
        )
        details = _get_network_details(
            network_name=network_name,
            project_id=project_id,
            status=status,
            name_contains=name_contains,
            limit=limit,
            offset=offset,
            include_subnets=include_subnets,
        )
        
        result = {
            "timestamp": datetime.now().isoformat(), 
            "requested_network": network_name,
            "returned_networks": len(details),
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": bool(limit and len(details) == limit),
            },
            "filters": {
                "project_id": project_id,
                "status": status,
                "name_contains": name_contains,
                "include_subnets": include_subnets,
            },
            "network_details": details
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"Error: Failed to fetch network information - {str(e)}"
        logger.error(error_msg)
        return error_msg
