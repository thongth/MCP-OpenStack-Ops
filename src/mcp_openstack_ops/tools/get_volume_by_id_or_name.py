"""Tool implementation for get_volume_by_id_or_name."""

import json
from datetime import datetime
from ..functions import get_volume_list as _get_volume_list
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_by_id_or_name(
    volume_id_or_name: str,
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
) -> str:
    """Get volume details by exact volume ID or name."""
    try:
        volumes = _get_volume_list(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )
        query = volume_id_or_name.strip()
        filtered_volumes = [
            v for v in volumes
            if str(v.get("id", "")) == query or str(v.get("name", "")) == query
        ]

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "query": volume_id_or_name,
                "found": len(filtered_volumes) > 0,
                "total_volumes": len(filtered_volumes),
                "volumes": filtered_volumes,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch volume by id or name - {e}")
        return f"Error: Failed to fetch volume by id or name - {str(e)}"
