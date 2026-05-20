"""Tool implementation for get_volume_snapshot_by_status."""

import json
from datetime import datetime
from ..functions import get_volume_snapshots as _get_volume_snapshots
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_snapshot_by_status(
    status: str,
    project_id: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> str:
    """Get snapshots filtered by status."""
    try:
        snapshots = _get_volume_snapshots(
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
                    "project_id": project_id,
                    "limit": limit,
                    "offset": offset,
                    "fields": fields,
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
