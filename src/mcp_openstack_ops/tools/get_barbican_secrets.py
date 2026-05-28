"""Tool implementation for get_barbican_secrets."""

import json
from datetime import datetime

from ..functions import get_barbican_secrets as _get_barbican_secrets
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_barbican_secrets(
    name: str = "",
    secret_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List Barbican secrets metadata without returning secret payloads."""
    try:
        result = _get_barbican_secrets(
            name=name,
            secret_type=secret_type,
            status=status,
            project_id=project_id,
            limit=limit,
            offset=offset,
        )
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("Error: Failed to list Barbican secrets - %s", e)
        return f"Error: Failed to list Barbican secrets - {str(e)}"
