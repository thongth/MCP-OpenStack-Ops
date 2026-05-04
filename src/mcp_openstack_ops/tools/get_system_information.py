"""Tool implementation for get_system_information."""

import json
from datetime import datetime
from ..functions import get_system_information as _get_system_information
from ..mcp_main import (
    logger,
    mcp,
)


@mcp.tool()
async def get_system_information() -> str:
    """
    Get system monitoring information for core infrastructure services.

    Includes:
    - Compute services
    - Block storage services
    - Network agents
    """
    try:
        logger.info("Fetching system monitoring information")
        system_info = _get_system_information()

        result = {
            "timestamp": datetime.now().isoformat(),
            "system_information": system_info,
        }

        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to fetch system information - {str(e)}"
        logger.error(error_msg)
        return error_msg
