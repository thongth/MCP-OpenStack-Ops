"""Tool implementation for get_volume_backup_summary."""

import json
from datetime import datetime
from ..functions import get_volume_backup_summary as _get_volume_backup_summary
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_backup_summary(
    project_id: str = "",
) -> str:
    """Get backup counts grouped by status, project, availability zone, and fail reason."""
    try:
        summary = _get_volume_backup_summary(
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
        logger.error(f"Error: Failed to fetch volume backup summary - {e}")
        return f"Error: Failed to fetch volume backup summary - {str(e)}"
