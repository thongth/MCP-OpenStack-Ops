"""Tool implementation for get_snapshot."""

import json
from datetime import datetime
from ..functions import get_volume_snapshots as _get_volume_snapshots
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_snapshot(
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> str:
    """Get list of volume snapshots."""
    try:
        logger.info(
            f"Fetching snapshots (include_all_projects={include_all_projects}, project_id={project_id}, status={status})"
        )
        snapshots = _get_volume_snapshots(
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
                "total_snapshots": len(snapshots),
                "limit": limit,
                "offset": offset,
                "snapshots": snapshots,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        error_msg = f"Error: Failed to fetch snapshots - {str(e)}"
        logger.error(error_msg)
        return error_msg
