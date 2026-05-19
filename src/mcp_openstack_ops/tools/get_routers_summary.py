"""Tool implementation for get_routers_summary."""

import json
from datetime import datetime
from ..functions import get_routers_summary as _get_routers_summary
from ..mcp_main import logger, mcp

@mcp.tool()
async def get_routers_summary(
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """Get router counts grouped by status, project, admin state, HA, distributed, and gateway."""
    try:
        summary = _get_routers_summary(
            include_all_projects=include_all_projects,
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
        logger.error(f"Error: Failed to fetch routers summary - {e}")
        return f"Error: Failed to fetch routers summary - {str(e)}"
