"""Tool implementation for get_volume_snapshots."""

import json
from datetime import datetime
from ..functions import get_volume_snapshots as _get_volume_snapshots
from ..mcp_main import (
    logger,
    mcp,
)

@mcp.tool()
async def get_volume_snapshots(
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """
    Get list of volume snapshots.
    
    Functions:
    - Query volume snapshots and their status
    - Display source volume information
    - Show snapshot creation and modification dates
    - Provide snapshot size and usage information
    
    Use when user requests snapshot information, backup queries, or volume restoration planning.
    
    Returns:
        List of volume snapshots with detailed information in JSON format.
    """
    try:
        logger.info(
            f"Fetching volume snapshots (include_all_projects={include_all_projects}, project_id={project_id})"
        )
        snapshots = _get_volume_snapshots(
            include_all_projects=include_all_projects,
            project_id=project_id,
        )
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "total_snapshots": len(snapshots),
            "snapshots": snapshots
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"Error: Failed to fetch volume snapshots - {str(e)}"
        logger.error(error_msg)
        return error_msg
