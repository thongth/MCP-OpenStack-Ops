"""Tool implementation for get_image_list."""

import json
from datetime import datetime
from ..functions import get_image_list_filtered as _get_image_list_filtered
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_image_list(
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
    visibility: str = "",
    owner: str = "",
    name_filter: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List images with summary output and optional filters."""
    try:
        result = _get_image_list_filtered(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
            visibility=visibility,
            owner=owner,
            name_filter=name_filter,
            limit=limit,
            offset=offset,
        )
        response = {
            "timestamp": datetime.now().isoformat(),
            "filter": {
                "include_all_projects": include_all_projects,
                "project_id": project_id,
                "status": status,
                "visibility": visibility,
                "owner": owner,
                "name_filter": name_filter,
                "limit": limit,
                "offset": offset,
            },
            **result,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to fetch image list - {str(e)}"
        logger.error(error_msg)
        return error_msg
