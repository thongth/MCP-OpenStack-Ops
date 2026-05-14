"""Tool implementation for search_images."""

import json
from datetime import datetime
from ..functions import search_images as _search_images
from ..mcp_main import logger, mcp


@mcp.tool()
async def search_images(
    search_term: str,
    search_in: str = "all",
    limit: int = 50,
    offset: int = 0,
    case_sensitive: bool = False,
) -> str:
    """Search images by partial match across selected fields."""
    try:
        result = _search_images(
            search_term=search_term,
            search_in=search_in,
            limit=limit,
            offset=offset,
            case_sensitive=case_sensitive,
        )
        response = {
            "timestamp": datetime.now().isoformat(),
            "query": {
                "search_term": search_term,
                "search_in": search_in,
                "limit": limit,
                "offset": offset,
                "case_sensitive": case_sensitive,
            },
            **result,
        }
        return json.dumps(response, indent=2, ensure_ascii=False)
    except Exception as e:
        error_msg = f"Error: Failed to search images - {str(e)}"
        logger.error(error_msg)
        return error_msg
