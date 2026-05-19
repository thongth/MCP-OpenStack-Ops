"""Tool implementation for get_volume_by_status."""

import json
from datetime import datetime
from ..functions import get_volume_list as _get_volume_list
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_by_status(
    status: str,
    include_all_projects: bool = False,
    project_id: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> str:
    """Get volumes filtered by status (e.g. available, in-use, error)."""
    try:
        volumes = _get_volume_list(
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
                "total_volumes": len(volumes),
                "volumes": volumes,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch volumes by status - {e}")
        return f"Error: Failed to fetch volumes by status - {str(e)}"
