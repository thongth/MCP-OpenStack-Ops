"""Tool implementation for get_barbican_order_details."""

import json
from datetime import datetime

from ..functions import get_barbican_order_details as _get_barbican_order_details
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_barbican_order_details(order_id_or_ref: str) -> str:
    """Get Barbican order details by ID/ref."""
    try:
        result = _get_barbican_order_details(order_id_or_ref=order_id_or_ref)
        return json.dumps({"timestamp": datetime.now().isoformat(), "result": result}, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("Error: Failed to get Barbican order details - %s", e)
        return f"Error: Failed to get Barbican order details - {str(e)}"
