"""Tool implementation for get_snapshot_by_project."""

import json
from datetime import datetime
from ..connection import is_all_projects_readonly_mode
from ..functions import get_project_list as _get_project_list
from ..functions import get_volume_snapshots as _get_volume_snapshots
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_snapshot_by_project(
    project_id: str,
    include_all_projects: bool = True,
    status: str = "",
) -> str:
    """Get snapshots owned by a specific project ID or exact project name."""
    try:
        target_project_id = project_id.strip()
        all_projects_mode = is_all_projects_readonly_mode()

        if not target_project_id:
            return "Error: project_id is required"

        if "-" not in target_project_id:
            projects_result = _get_project_list(
                name_filter=target_project_id,
                enabled_only=False,
            )
            projects = projects_result.get("projects", []) if isinstance(projects_result, dict) else []
            exact_name_matches = [
                p for p in projects
                if str(p.get("name", "")).strip().lower() == target_project_id.lower()
            ]
            if len(exact_name_matches) == 1:
                target_project_id = str(exact_name_matches[0].get("id", target_project_id))

        snapshots = _get_volume_snapshots(
            include_all_projects=include_all_projects,
            project_id=target_project_id,
            status=status,
        )
        filtered_snapshots = [
            s for s in snapshots
            if str(s.get("project_id", "")) == target_project_id
        ]

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "project_id": target_project_id,
                    "input_project": project_id,
                    "include_all_projects": include_all_projects,
                    "status": status,
                },
                "mode": {
                    "all_projects_readonly": all_projects_mode,
                    "cross_project_effective": all_projects_mode and include_all_projects,
                },
                "total_snapshots": len(filtered_snapshots),
                "snapshots": filtered_snapshots,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch snapshots by project - {e}")
        return f"Error: Failed to fetch snapshots by project - {str(e)}"
