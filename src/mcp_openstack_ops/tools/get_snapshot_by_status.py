"""Tool implementation for get_snapshot_by_status."""

import json
from datetime import datetime
from ..functions import get_volume_snapshots as _get_volume_snapshots
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_snapshot_by_status(
    status: str,
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """Get snapshots filtered by status."""
    try:
        snapshots = _get_volume_snapshots(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "status": status,
                    "include_all_projects": include_all_projects,
                    "project_id": project_id,
                },
                "total_snapshots": len(snapshots),
                "snapshots": snapshots,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch snapshots by status - {e}")
        return f"Error: Failed to fetch snapshots by status - {str(e)}"
