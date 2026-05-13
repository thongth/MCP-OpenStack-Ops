"""Tool implementation for get_volume_by_project."""

import json
from datetime import datetime
from ..functions import get_volume_list as _get_volume_list
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_by_project(
    project_id: str,
    include_all_projects: bool = True,
    status: str = "",
) -> str:
    """Get volumes owned by a specific project ID."""
    try:
        volumes = _get_volume_list(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )
        filtered_volumes = [
            v for v in volumes
            if str(v.get("project_id", "")) == project_id
        ]

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "project_id": project_id,
                    "include_all_projects": include_all_projects,
                    "status": status,
                },
                "total_volumes": len(filtered_volumes),
                "volumes": filtered_volumes,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch volumes by project - {e}")
        return f"Error: Failed to fetch volumes by project - {str(e)}"
