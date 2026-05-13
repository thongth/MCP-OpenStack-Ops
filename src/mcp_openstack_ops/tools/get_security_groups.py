"""Tool implementation for get_security_groups."""

import json
from datetime import datetime
from ..functions import get_security_groups as _get_security_groups
from ..mcp_main import (
    logger,
    mcp,
)

@mcp.tool()
async def get_security_groups(
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """
    Get list of security groups with their rules.
    
    Functions:
    - Query security groups and their rule configurations
    - Display ingress and egress rules with protocols and ports
    - Show remote IP prefixes and security group references
    - Provide comprehensive network security information
    
    Use when user requests security group information, firewall rules, or network security queries.
    
    Returns:
        List of security groups with detailed rules in JSON format.
    """
    try:
        logger.info(
            f"Fetching security groups (include_all_projects={include_all_projects}, project_id={project_id})"
        )
        security_groups = _get_security_groups(
            include_all_projects=include_all_projects,
            project_id=project_id,
        )
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "total_security_groups": len(security_groups),
            "security_groups": security_groups
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"Error: Failed to fetch security groups - {str(e)}"
        logger.error(error_msg)
        return error_msg
