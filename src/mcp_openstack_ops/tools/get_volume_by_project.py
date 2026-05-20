"""Tool implementation for get_volume_by_project."""

import json
from datetime import datetime
from ..connection import is_all_projects_readonly_mode
from ..functions import get_project_list as _get_project_list
from ..functions import get_volume_list as _get_volume_list
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_by_project(
    project_id: str,
        status: str = "",
    limit: int = 100,
    offset: int = 0,
    fields: str = "",
) -> str:
    """Get volumes owned by a specific project ID (or exact project name)."""
    try:
        target_project_id = project_id.strip()
        all_projects_mode = is_all_projects_readonly_mode()

        if not target_project_id:
            return "Error: project_id is required"

        # Allow exact project-name input by resolving to project ID when possible.
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

        volumes = _get_volume_list(
            project_id=target_project_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        filtered_volumes = [
            v for v in volumes
            if str(v.get("project_id", "")) == target_project_id
        ]
        if fields:
            requested = [field.strip() for field in fields.split(",") if field.strip()]
            filtered_volumes = [
                {field: v.get(field) for field in requested if field in v}
                for v in filtered_volumes
            ]

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "project_id": target_project_id,
                    "input_project": project_id,
                    "status": status,
                    "limit": limit,
                    "offset": offset,
                    "fields": fields,
                },
                "mode": {
                    "all_projects_readonly": all_projects_mode,
                    "cross_project_effective": all_projects_mode,
                },
                "total_volumes": len(filtered_volumes),
                "volumes": filtered_volumes,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch volumes by project - {e}")
        return f"Error: Failed to fetch volumes by project - {str(e)}"
