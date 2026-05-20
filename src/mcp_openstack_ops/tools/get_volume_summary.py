"""Tool implementation for get_volume_summary."""

import json
from datetime import datetime
from ..functions import get_volume_summary as _get_volume_summary
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_summary(
    project_id: str = "",
) -> str:
    """Get volume counts grouped by status, project, and availability zone."""
    try:
        summary = _get_volume_summary(
            project_id=project_id,
        )
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "summary": summary,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch volume summary - {e}")
        return f"Error: Failed to fetch volume summary - {str(e)}"
