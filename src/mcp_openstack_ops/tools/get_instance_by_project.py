"""Tool implementation for get_instance_by_project."""

import json
from datetime import datetime
from ..functions import get_instance_details as _get_instance_details
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_instance_by_project(
    project_id: str,
    status: str = "",
) -> str:
    """Get instances owned by a specific project ID."""
    try:
        details_result = _get_instance_details(
            instance_names=None,
            include_all=True,
        )

        instances = details_result.get("instances", []) if isinstance(details_result, dict) else details_result
        status_filter = status.strip().lower() if status else ""

        filtered_instances = []
        for instance in instances:
            instance_project_id = str(
                instance.get("tenant_id")
                or instance.get("project_id")
                or ""
            )
            instance_status = str(instance.get("status", "")).lower()

            if instance_project_id != project_id:
                continue
            if status_filter and instance_status != status_filter:
                continue

            filtered_instances.append(instance)

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "filter": {
                    "project_id": project_id,
                    "status": status,
                },
                "total_instances": len(filtered_instances),
                "instances": filtered_instances,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch instances by project - {e}")
        return f"Error: Failed to fetch instances by project - {str(e)}"
