"""Tool implementation for get_security_groups_by_project."""

import json
from datetime import datetime
from ..functions import get_security_groups as _get_security_groups
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_security_groups_by_project(
    project_id: str,
    include_all_projects: bool = True,
) -> str:
    """Get security groups owned by a specific project."""
    try:
        security_groups = _get_security_groups(
            include_all_projects=include_all_projects,
            project_id=project_id,
        )
        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "project_id": project_id,
                    "include_all_projects": include_all_projects,
                },
                "total_security_groups": len(security_groups),
                "security_groups": security_groups,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch security groups by project - {e}")
        return f"Error: Failed to fetch security groups by project - {str(e)}"
