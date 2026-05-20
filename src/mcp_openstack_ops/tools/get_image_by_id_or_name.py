"""Tool implementation for get_image_by_id_or_name."""

import json
from datetime import datetime
from ..functions import get_image_by_id_or_name as _get_image_by_id_or_name
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_image_by_id_or_name(
    image_id_or_name: str,
    project_id: str = "",
) -> str:
    """Get image details by exact image ID or name."""
    try:
        result = _get_image_by_id_or_name(
            image_id_or_name=image_id_or_name,
            project_id=project_id,
        )
        response = {
            "timestamp": datetime.now().isoformat(),
            "query": image_id_or_name,
            "filter": {
                "project_id": project_id,
            },
            **result,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to fetch image by id or name - {str(e)}"
        logger.error(error_msg)
        return error_msg
