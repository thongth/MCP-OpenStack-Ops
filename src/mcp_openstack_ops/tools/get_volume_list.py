"""Tool implementation for get_volume_list."""

import json
from datetime import datetime
from ..functions import get_volume_list as _get_volume_list
from ..mcp_main import (
    logger,
    mcp,
)

@mcp.tool()
async def get_volume_list(
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
) -> str:
    """
    Get list of all volumes with detailed information.
    
    Functions:
    - List all volumes in the project
    - Show volume status, size, and type information
    - Display attachment information for volumes
    - Provide detailed metadata for each volume
    
    Use when user requests volume listing, volume information, or storage overview.
    
    Returns:
        Detailed volume list in JSON format with volume information, attachments, and metadata.
    """
    try:
        logger.info(
            f"Fetching volume list (include_all_projects={include_all_projects}, project_id={project_id}, status={status})"
        )
        volumes = _get_volume_list(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )
        
        response = {
            "timestamp": datetime.now().isoformat(),
            "volumes": volumes,
            "count": len(volumes),
            "operation": "list_volumes"
        }
        
        return json.dumps(response, indent=2, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"Error: Failed to fetch volume list - {str(e)}"
        logger.error(error_msg)
        return error_msg
