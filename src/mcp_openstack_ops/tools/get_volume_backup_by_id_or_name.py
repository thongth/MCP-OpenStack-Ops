"""Tool implementation for get_volume_backup_by_id_or_name."""

import json
from datetime import datetime
from ..functions import get_volume_backups as _get_volume_backups
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_volume_backup_by_id_or_name(
    backup_id_or_name: str,
    project_id: str = "",
    status: str = "",
    fields: str = "",
) -> str:
    """Get volume backup details by exact backup ID or name."""
    try:
        backups = _get_volume_backups(
            project_id=project_id,
            status=status,
            limit=0,
        )
        query = backup_id_or_name.strip()
        filtered_backups = [
            b for b in backups
            if str(b.get("id", "")) == query or str(b.get("name", "")) == query
        ]
        if fields:
            requested = [field.strip() for field in fields.split(",") if field.strip()]
            filtered_backups = [
                {field: b.get(field) for field in requested if field in b}
                for b in filtered_backups
            ]

        return json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "query": backup_id_or_name,
                "found": len(filtered_backups) > 0,
                "total_backups": len(filtered_backups),
                "backups": filtered_backups,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error(f"Error: Failed to fetch volume backup by id or name - {e}")
        return f"Error: Failed to fetch volume backup by id or name - {str(e)}"
