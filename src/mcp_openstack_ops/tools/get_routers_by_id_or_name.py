"""Tool implementation for get_routers_by_id_or_name."""

import json
from datetime import datetime
from ..functions import get_routers as _get_routers
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_routers_by_id_or_name(
    router_id_or_name: str,
    project_id: str = "",
    exact_match: bool = True,
) -> str:
    """Get routers filtered by exact ID or name."""
    try:
        routers = _get_routers(
            project_id=project_id,
        )
        query_raw = router_id_or_name.strip()
        query = query_raw.lower()
        if exact_match:
            filtered = [
                r for r in routers
                if str(r.get("id", "")) == query_raw or str(r.get("name", "")).lower() == query
            ]
        else:
            filtered = [r for r in routers if query in str(r.get("name", "")).lower()]
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "router_id_or_name": router_id_or_name,
                    "exact_match": exact_match,
                    "project_id": project_id,
                },
                "total_routers": len(filtered),
                "routers": filtered,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch routers by id or name - {e}")
        return f"Error: Failed to fetch routers by id or name - {str(e)}"
