"""Tool implementation for get_routers_by_state."""

import json
from datetime import datetime
from ..functions import get_routers as _get_routers
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_routers_by_state(
    state: str,
    project_id: str = "",
) -> str:
    """
    Get routers filtered by administrative state.
    `state` accepts: up, down, true, false, enabled, disabled.
    """
    try:
        routers = _get_routers(
            project_id=project_id,
        )
        normalized = state.strip().lower()
        wanted = normalized in {"up", "true", "enabled", "1", "yes", "on"}
        filtered = [r for r in routers if bool(r.get("admin_state_up", False)) == wanted]
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {"state": state, "project_id": project_id},
                "total_routers": len(filtered),
                "routers": filtered,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch routers by state - {e}")
        return f"Error: Failed to fetch routers by state - {str(e)}"
