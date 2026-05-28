"""Tool implementation for get_barbican_containers."""

import json
from datetime import datetime

from ..functions import get_barbican_containers as _get_barbican_containers
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_barbican_containers(
    name: str = "",
    container_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List Barbican container metadata without returning secret payloads."""
    try:
        result = _get_barbican_containers(
            name=name,
            container_type=container_type,
            status=status,
            project_id=project_id,
            limit=limit,
            offset=offset,
        )
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("Error: Failed to list Barbican containers - %s", e)
        return f"Error: Failed to list Barbican containers - {str(e)}"
