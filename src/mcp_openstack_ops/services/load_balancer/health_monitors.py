"""
Load Balancer Health Monitor Query Module

This module provides read-only load balancer health monitor queries.
"""

import logging
from typing import Dict, Any
from ..db import bool_value, column_expr, str_time, table_columns
from .db import get_octavia_connection, list_pools

logger = logging.getLogger(__name__)


def get_loadbalancer_health_monitors(pool_name_or_id: str = "") -> Dict[str, Any]:
    """
    Get health monitors, optionally filtered by pool.
    
    Args:
        pool_name_or_id: Optional pool name or ID to filter monitors
        
    Returns:
        Dictionary with health monitor information
    """
    try:
        target_pool_id = ""
        if pool_name_or_id:
            pool = next((p for p in list_pools() if p.get("name") == pool_name_or_id or p.get("id") == pool_name_or_id), None)
            if not pool:
                return {
                    'success': False,
                    'message': f'Pool not found: {pool_name_or_id}'
                }
            target_pool_id = pool.get("id")
        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                columns = table_columns(cur, "health_monitor")
                if not columns:
                    raise RuntimeError("MariaDB table 'health_monitor' is not available")
                pool_expr = column_expr("hm", columns, "pool_id", default="NULL")
                sql = "SELECT hm.* FROM health_monitor hm WHERE 1=1 "
                params = []
                if target_pool_id:
                    sql += f"AND {pool_expr} = %s "
                    params.append(target_pool_id)
                sql += "ORDER BY hm.created_at DESC"
                cur.execute(sql, params)
                monitor_details = []
                for monitor in cur.fetchall():
                    monitor_details.append({
                        'id': monitor.get("id"),
                        'name': monitor.get("name") or "",
                        'type': monitor.get("type"),
                        'delay': monitor.get("delay"),
                        'timeout': monitor.get("timeout"),
                        'max_retries': monitor.get("max_retries"),
                        'max_retries_down': monitor.get("max_retries_down"),
                        'admin_state_up': bool_value(monitor.get("admin_state_up")),
                        'provisioning_status': monitor.get("provisioning_status"),
                        'operating_status': monitor.get("operating_status"),
                        'pool_id': monitor.get("pool_id"),
                        'http_method': monitor.get("http_method"),
                        'url_path': monitor.get("url_path"),
                        'expected_codes': monitor.get("expected_codes"),
                        'created_at': str_time(monitor.get("created_at")),
                        'updated_at': str_time(monitor.get("updated_at")),
                        'data_source': 'mariadb',
                    })
        finally:
            conn.close()
        
        return {
            'success': True,
            'health_monitors': monitor_details,
            'monitor_count': len(monitor_details),
            'filter': f'pool: {pool_name_or_id}' if pool_name_or_id else 'all monitors'
        }
        
    except Exception as e:
        logger.error(f"Failed to get health monitors: {e}")
        return {
            'success': False,
            'message': f'Failed to get health monitors: {str(e)}',
            'error': str(e)
        }
