"""Tool implementation for get_image_by_status."""

import json
from datetime import datetime
from ..functions import get_image_list_filtered as _get_image_list_filtered
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_image_by_status(
    status: str,
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """Get images filtered by image status."""
    try:
        result = _get_image_list_filtered(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
            visibility="",
            owner="",
            name_filter="",
            limit=200,
            offset=0,
        )
        response = {
            "timestamp": datetime.now().isoformat(),
            "filter": {
                "status": status,
                "include_all_projects": include_all_projects,
                "project_id": project_id,
            },
            **result,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to fetch images by status - {str(e)}"
        logger.error(error_msg)
        return error_msg
