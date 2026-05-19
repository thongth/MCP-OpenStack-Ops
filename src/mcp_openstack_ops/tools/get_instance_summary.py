"""Tool implementation for get_instance_summary."""

import json
from datetime import datetime
from ..functions import get_instance_summary as _get_instance_summary
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_instance_summary(
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """Get instance counts grouped by status, project, availability zone, host, and power state."""
    try:
        summary = _get_instance_summary(
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
        logger.error(f"Error: Failed to fetch instance summary - {e}")
        return f"Error: Failed to fetch instance summary - {str(e)}"
