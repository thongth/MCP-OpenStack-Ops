"""Tool implementation for get_snapshot_by_id_or_name."""

import json
from datetime import datetime
from ..functions import get_volume_snapshots as _get_volume_snapshots
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_snapshot_by_id_or_name(
    snapshot_id_or_name: str,
    include_all_projects: bool = False,
    project_id: str = "",
    status: str = "",
) -> str:
    """Get snapshot details by exact snapshot ID or name."""
    try:
        snapshots = _get_volume_snapshots(
            include_all_projects=include_all_projects,
            project_id=project_id,
            status=status,
        )
        query = snapshot_id_or_name.strip()
        filtered_snapshots = [
            s for s in snapshots
            if str(s.get("id", "")) == query or str(s.get("name", "")) == query
        ]

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "query": snapshot_id_or_name,
                "found": len(filtered_snapshots) > 0,
                "total_snapshots": len(filtered_snapshots),
                "snapshots": filtered_snapshots,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch snapshot by id or name - {e}")
        return f"Error: Failed to fetch snapshot by id or name - {str(e)}"
