"""
Load Balancer Pool and Member Query Module

This module provides read-only load balancer pool and member queries.
"""

import logging
from typing import Dict, Any
from .db import find_load_balancer, list_listeners, list_members, list_pools

logger = logging.getLogger(__name__)


def get_loadbalancer_pools(listener_name_or_id: str = None) -> Dict[str, Any]:
    """
    Get load balancer pools, optionally filtered by listener.
    
    Args:
        listener_name_or_id: Optional listener or load balancer name/ID to filter pools
    
    Returns:
        Dictionary containing pools information
    """
    try:
        if listener_name_or_id:
            listeners = [l for l in list_listeners() if l.get("id") == listener_name_or_id or l.get("name") == listener_name_or_id]
            if listeners:
                listener = listeners[0]
                pools = list_pools(listener_id=listener.get("id"))
                default_pool_id = str(listener.get("default_pool_id") or "")
                if default_pool_id:
                    pools.extend([p for p in list_pools() if str(p.get("id")) == default_pool_id])
                filter_label = f'listener: {listener_name_or_id}'
            else:
                lb = find_load_balancer(listener_name_or_id)
                if not lb:
                    return {
                        'success': False,
                        'message': f'Listener or load balancer not found: {listener_name_or_id}'
                    }
                pools = list_pools(loadbalancer_id=lb.get("id"))
                filter_label = f'load_balancer: {listener_name_or_id}'
            if not pools:
                pools = []
        else:
            pools = list_pools()
            filter_label = 'all pools'

        if listener_name_or_id:
            seen_pool_ids = set()
            unique_pools = []
            for pool in pools:
                pool_id = pool.get("id")
                if pool_id in seen_pool_ids:
                    continue
                seen_pool_ids.add(pool_id)
                unique_pools.append(pool)
            pools = unique_pools
        
        pool_details = []
        for pool in pools:
            member_summary = list_members(pool.get("id"))
            pool_info = {**pool, 'members': member_summary, 'member_count': len(member_summary)}
            pool_details.append(pool_info)
        
        return {
            'success': True,
            'pools': pool_details,
            'pool_count': len(pool_details),
            'filter': filter_label
        }
        
    except Exception as e:
        logger.error(f"Failed to get pools: {e}")
        return {
            'success': False,
            'message': f'Failed to get pools: {str(e)}',
            'error': str(e)
        }


def get_loadbalancer_pool_members(pool_name_or_id: str) -> Dict[str, Any]:
    """
    Get members for a specific load balancer pool.
    
    Args:
        pool_name_or_id: Pool name or ID
        
    Returns:
        Dictionary with pool members information
    """
    try:
        pool = next((p for p in list_pools() if p.get("name") == pool_name_or_id or p.get("id") == pool_name_or_id), None)
        
        if not pool:
            return {
                'success': False,
                'message': f'Pool not found: {pool_name_or_id}'
            }
        
        member_details = list_members(pool.get("id"))
        
        return {
            'success': True,
            'pool': {
                'id': pool.get("id"),
                'name': pool.get("name"),
                'protocol': pool.get("protocol")
            },
            'members': member_details,
            'member_count': len(member_details)
        }
        
    except Exception as e:
        logger.error(f"Failed to get pool members: {e}")
        return {
            'success': False,
            'message': f'Failed to get pool members: {str(e)}',
            'error': str(e)
        }
