"""Tool implementation for get_routers_by_name."""

import json
from datetime import datetime
from ..functions import get_routers as _get_routers
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_routers_by_name(
    router_name: str,
    include_all_projects: bool = False,
    project_id: str = "",
    exact_match: bool = True,
) -> str:
    """Get routers filtered by name."""
    try:
        routers = _get_routers(
            include_all_projects=include_all_projects,
            project_id=project_id,
        )
        query = router_name.strip().lower()
        if exact_match:
            filtered = [r for r in routers if str(r.get("name", "")).lower() == query]
        else:
            filtered = [r for r in routers if query in str(r.get("name", "")).lower()]
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "router_name": router_name,
                    "exact_match": exact_match,
                    "include_all_projects": include_all_projects,
                    "project_id": project_id,
                },
                "total_routers": len(filtered),
                "routers": filtered,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch routers by name - {e}")
        return f"Error: Failed to fetch routers by name - {str(e)}"
