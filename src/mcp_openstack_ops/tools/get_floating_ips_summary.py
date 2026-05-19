"""Tool implementation for get_floating_ips_summary."""

import json
from datetime import datetime
from ..functions import get_floating_ips_summary as _get_floating_ips_summary
from ..mcp_main import logger, mcp

@mcp.tool()
async def get_floating_ips_summary(
    include_all_projects: bool = False,
    project_id: str = "",
) -> str:
    """Get floating IP counts grouped by status, project, network, port binding, and router binding."""
    try:
        summary = _get_floating_ips_summary(
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
        logger.error(f"Error: Failed to fetch floating IPs summary - {e}")
        return f"Error: Failed to fetch floating IPs summary - {str(e)}"
