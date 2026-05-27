"""
Load Balancer Amphora Query Module

This module provides read-only amphora information for load balancer instances.
"""

import logging
from typing import Dict, Any
from ..db import bool_value, str_time, table_columns
from .db import find_load_balancer, get_octavia_connection

logger = logging.getLogger(__name__)


def get_loadbalancer_amphorae(lb_name_or_id: str = "", **kwargs) -> Dict[str, Any]:
    """
    Get amphora instances for load balancer or all amphorae.
    Supports both legacy parameter style and **kwargs style for compatibility.
    
    Args:
        lb_name_or_id: Optional load balancer name or ID (legacy parameter)
        **kwargs: Optional arguments including:
            - loadbalancer_id: Load balancer ID to filter amphorae
    
    Returns:
        Dictionary containing amphora information
    """
    try:
        loadbalancer_id = kwargs.get('loadbalancer_id') or lb_name_or_id
        if loadbalancer_id:
            lb = find_load_balancer(loadbalancer_id)
            if lb:
                loadbalancer_id = lb.get("id")

        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                if not table_columns(cur, "amphora"):
                    return {'success': True, 'amphorae': [], 'amphora_count': 0}
                sql = "SELECT * FROM amphora WHERE 1=1 "
                params = []
                if loadbalancer_id:
                    sql += "AND load_balancer_id = %s "
                    params.append(loadbalancer_id)
                sql += "ORDER BY created_at DESC"
                cur.execute(sql, params)
                amphorae = cur.fetchall()
        finally:
            conn.close()

        if loadbalancer_id:
            if not amphorae:
                return {
                    'success': False,
                    'message': f'Load balancer not found: {lb_name_or_id}'
                }
        
        amphora_details = []
        for amphora in amphorae:
            amphora_info = {
                'id': amphora.get("id"),
                'loadbalancer_id': amphora.get("load_balancer_id") or amphora.get("loadbalancer_id"),
                'compute_id': amphora.get("compute_id"),
                'lb_network_ip': amphora.get("lb_network_ip"),
                'vrrp_ip': amphora.get("vrrp_ip"),
                'ha_ip': amphora.get("ha_ip"),
                'vrrp_port_id': amphora.get("vrrp_port_id"),
                'ha_port_id': amphora.get("ha_port_id"),
                'cert_expiration': str_time(amphora.get("cert_expiration")),
                'cert_busy': bool_value(amphora.get("cert_busy")),
                'role': amphora.get("role"),
                'status': amphora.get("status"),
                'cached_zone': amphora.get("cached_zone"),
                'image_id': amphora.get("image_id"),
                'compute_flavor': amphora.get("compute_flavor"),
                'created_at': str_time(amphora.get("created_at")),
                'updated_at': str_time(amphora.get("updated_at")),
                'data_source': 'mariadb',
            }
            amphora_details.append(amphora_info)
        
        return {
            'success': True,
            'amphorae': amphora_details,
            'amphora_count': len(amphora_details)
        }
        
    except Exception as e:
        logger.error(f"Failed to get amphorae: {e}")
        return {
            'success': False,
            'message': f'Failed to get amphorae: {str(e)}',
            'error': str(e)
        }
