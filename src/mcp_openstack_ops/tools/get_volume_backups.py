"""Tool implementation for get_volume_backups."""

import json
from datetime import datetime
from ..functions import get_volume_backups as _get_volume_backups
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_backups(
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
) -> str:
    """Get list of volume backups."""
    try:
        logger.info(
            f"Fetching volume backups (include_all_projects={include_all_projects}, project_id={project_id}, status={status})"
        )
        backups = _get_volume_backups(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "total_backups": len(backups),
                "backups": backups,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        error_msg = f"Error: Failed to fetch volume backups - {str(e)}"
        logger.error(error_msg)
        return error_msg
