"""Tool implementation for get_barbican_container_details."""

import json
from datetime import datetime

from ..functions import get_barbican_container_details as _get_barbican_container_details
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_barbican_container_details(container_id_or_ref: str) -> str:
    """Get Barbican container metadata by ID/ref without returning secret payloads."""
    try:
        result = _get_barbican_container_details(container_id_or_ref=container_id_or_ref)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("Error: Failed to get Barbican container details - %s", e)
        return f"Error: Failed to get Barbican container details - {str(e)}"
