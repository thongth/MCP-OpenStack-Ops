"""
Load Balancer Listener Query Module

This module provides read-only load balancer listener queries.
"""

import logging
from typing import Dict, Any
from .db import find_load_balancer, list_listeners

logger = logging.getLogger(__name__)


def get_loadbalancer_listeners(lb_name_or_id: str = "") -> Dict[str, Any]:
    """
    Get listeners for a specific load balancer.
    
    Args:
        lb_name_or_id: Load balancer name or ID
    
    Returns:
        Dictionary containing listeners information
    """
    try:
        if not lb_name_or_id:
            listener_details = list_listeners()
            return {
                'success': True,
                'scope': 'all_load_balancers',
                'listeners': listener_details,
                'listener_count': len(listener_details)
            }

        lb = find_load_balancer(lb_name_or_id)
        if not lb:
            return {
                'success': False,
                'message': f'Load balancer not found: {lb_name_or_id}'
            }
        
        listener_details = list_listeners(loadbalancer_id=lb.get("id"))
        
        return {
            'success': True,
            'load_balancer': {
                'id': lb.get("id"),
                'name': lb.get("name")
            },
            'listeners': listener_details,
            'listener_count': len(listener_details)
        }
        
    except Exception as e:
        logger.error(f"Failed to get load balancer listeners: {e}")
        return {
            'success': False,
            'message': f'Failed to get load balancer listeners: {str(e)}',
            'error': str(e)
        }
