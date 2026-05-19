"""Tool implementation for get_volume_backup_by_status."""

import json
from datetime import datetime
from ..functions import get_volume_backups as _get_volume_backups
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_backup_by_status(
    status: str,
    include_all_projects: bool = False,
    project_id: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> str:
    """Get volume backups filtered by status."""
    try:
        backups = _get_volume_backups(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset,
            fields=fields,
        )
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "status": status,
                    "include_all_projects": include_all_projects,
                    "project_id": project_id,
                    "limit": limit,
                    "offset": offset,
                    "fields": fields,
                },
                "total_backups": len(backups),
                "backups": backups,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch volume backups by status - {e}")
        return f"Error: Failed to fetch volume backups by status - {str(e)}"
