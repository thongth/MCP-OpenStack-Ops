"""Tool implementation for get_image_by_project."""

import json
from datetime import datetime
from ..functions import get_image_list_filtered as _get_image_list_filtered
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_image_by_project(
    project_id: str,
    include_all_projects: bool = True,
    status: str = "",
    visibility: str = "",
) -> str:
    """Get images filtered by project owner."""
    try:
        result = _get_image_list_filtered(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
            visibility=visibility,
            owner=project_id,
            name_filter="",
            limit=200,
            offset=0,
        )
        response = {
            "timestamp": datetime.now().isoformat(),
            "filter": {
                "project_id": project_id,
                "include_all_projects": include_all_projects,
                "status": status,
                "visibility": visibility,
            },
            **result,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to fetch images by project - {str(e)}"
        logger.error(error_msg)
        return error_msg
