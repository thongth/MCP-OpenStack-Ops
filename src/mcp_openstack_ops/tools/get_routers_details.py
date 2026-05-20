"""Tool implementation for get_routers_details."""

import json
from datetime import datetime
from ..functions import get_routers as _get_routers
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_routers_details(
    router_name_or_id: str,
    project_id: str = "",
) -> str:
    """Get detailed information for a single router by name or ID."""
    try:
        routers = _get_routers(
            project_id=project_id,
        )
        query = router_name_or_id.strip().lower()
        matched = None
        for router in routers:
            rid = str(router.get("id", "")).lower()
            name = str(router.get("name", "")).lower()
            if query in {rid, name}:
                matched = router
                break

        result = {
            "timestamp": datetime.now().isoformat(),
            "query": router_name_or_id,
            "found": matched is not None,
            "router": matched,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error: Failed to fetch router details - {e}")
        return f"Error: Failed to fetch router details - {str(e)}"
