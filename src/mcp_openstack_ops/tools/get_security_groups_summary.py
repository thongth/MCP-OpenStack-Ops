"""Tool implementation for get_security_groups_summary."""

import json
from datetime import datetime
from ..functions import get_security_groups_summary as _get_security_groups_summary
from ..mcp_main import logger, mcp

@mcp.tool()
async def get_security_groups_summary(
    project_id: str = "",
) -> str:
    """Get security group and security group rule counts grouped by project and rule fields."""
    try:
        summary = _get_security_groups_summary(
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
        logger.error(f"Error: Failed to fetch security groups summary - {e}")
        return f"Error: Failed to fetch security groups summary - {str(e)}"
