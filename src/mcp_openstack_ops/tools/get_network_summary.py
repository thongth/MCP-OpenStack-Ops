"""Tool implementation for get_network_summary."""

import json
from datetime import datetime
from ..functions import get_network_summary as _get_network_summary
from ..mcp_main import logger, mcp

@mcp.tool()
async def get_network_summary(
    project_id: str = "",
) -> str:
    """Get network counts grouped by status, project, admin state, shared, and external."""
    try:
        summary = _get_network_summary(
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
        logger.error(f"Error: Failed to fetch network summary - {e}")
        return f"Error: Failed to fetch network summary - {str(e)}"
