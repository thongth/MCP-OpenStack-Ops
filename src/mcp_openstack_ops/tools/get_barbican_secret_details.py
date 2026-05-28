"""Tool implementation for get_barbican_secret_details."""

import json
from datetime import datetime

from ..functions import get_barbican_secret_details as _get_barbican_secret_details
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_barbican_secret_details(secret_id_or_ref: str) -> str:
    """Get Barbican secret metadata by ID/ref without returning secret payload."""
    try:
        result = _get_barbican_secret_details(secret_id_or_ref=secret_id_or_ref)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("Error: Failed to get Barbican secret details - %s", e)
        return f"Error: Failed to get Barbican secret details - {str(e)}"
