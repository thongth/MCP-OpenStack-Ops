"""Tool implementation for get_instance_by_id_or_name."""

import json
from datetime import datetime
from ..functions import get_instance_by_name as _get_instance_by_name
from ..mcp_main import (
    logger,
    mcp,
)

@mcp.tool()
async def get_instance_by_id_or_name(instance_id_or_name: str) -> str:
    """
    Get detailed information for a specific instance by ID or name.
    
    Args:
        instance_id_or_name: ID or name of the instance to retrieve
        
    Returns:
        Instance detailed information or error message if not found
    """
    try:
        logger.info(f"Getting instance by ID or name: {instance_id_or_name}")
        
        instance = _get_instance_by_name(instance_id_or_name)
        
        if not instance:
            return f"Instance '{instance_id_or_name}' not found"
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "query": instance_id_or_name,
            "instance_details": instance
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"Error: Failed to get instance '{instance_id_or_name}' - {str(e)}"
        logger.error(error_msg)
        return error_msg
