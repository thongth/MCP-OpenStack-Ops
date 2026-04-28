"""Tool implementation for get_project_list."""

import json
from datetime import datetime
from ..functions import get_project_list as _get_project_list
from ..mcp_main import (
    logger,
    mcp,
)


@mcp.tool()
async def get_project_list(name_filter: str = "", enabled_only: bool = False) -> str:
    """
    Get list of OpenStack projects visible to current credentials.

    Args:
        name_filter: Optional project name substring filter
        enabled_only: If True, return enabled projects only

    Returns:
        JSON string with project list
    """
    try:
        logger.info(
            "Getting project list (name_filter=%s, enabled_only=%s)",
            name_filter,
            enabled_only,
        )
        result = _get_project_list(name_filter=name_filter, enabled_only=enabled_only)

        response = {
            "timestamp": datetime.now().isoformat(),
            "operation": "get_project_list",
            "parameters": {
                "name_filter": name_filter,
                "enabled_only": enabled_only,
            },
            "project_data": result,
        }

        return json.dumps(response, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to get project list - {str(e)}"
        logger.error(error_msg)
        return error_msg
