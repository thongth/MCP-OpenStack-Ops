"""
Load Balancer Management Data Query Module

This module provides read-only load balancer management data queries,
including availability zones, flavors, quotas, and providers.
"""

import logging
from typing import Dict, Any
from ..db import bool_value, table_columns
from .db import get_octavia_connection

logger = logging.getLogger(__name__)


def get_loadbalancer_availability_zones() -> Dict[str, Any]:
    """
    Get load balancer availability zones.
    
    Returns:
        Dictionary containing availability zones information
    """
    try:
        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                if not table_columns(cur, "availability_zone"):
                    return {'success': True, 'availability_zones': [], 'zone_count': 0}
                cur.execute("SELECT * FROM availability_zone ORDER BY name ASC")
                zone_details = [{
                    'name': zone.get("name"),
                    'description': zone.get("description") or "",
                    'availability_zone_profile_id': zone.get("availability_zone_profile_id"),
                    'enabled': bool_value(zone.get("enabled")),
                    'data_source': 'mariadb',
                } for zone in cur.fetchall()]
        finally:
            conn.close()
        
        return {
            'success': True,
            'availability_zones': zone_details,
            'zone_count': len(zone_details)
        }
        
    except Exception as e:
        logger.error(f"Failed to get availability zones: {e}")
        return {
            'success': False,
            'message': f'Failed to get availability zones: {str(e)}',
            'error': str(e)
        }


def get_loadbalancer_flavors() -> Dict[str, Any]:
    """
    Get load balancer flavors.
    
    Returns:
        Dictionary containing flavors information
    """
    try:
        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                if not table_columns(cur, "flavor"):
                    return {'success': True, 'flavors': [], 'flavor_count': 0}
                cur.execute("SELECT * FROM flavor ORDER BY name ASC")
                flavor_details = [{
                    'id': flavor.get("id"),
                    'name': flavor.get("name"),
                    'description': flavor.get("description") or "",
                    'flavor_profile_id': flavor.get("flavor_profile_id"),
                    'enabled': bool_value(flavor.get("enabled")),
                    'data_source': 'mariadb',
                } for flavor in cur.fetchall()]
        finally:
            conn.close()
        
        return {
            'success': True,
            'flavors': flavor_details,
            'flavor_count': len(flavor_details)
        }
        
    except Exception as e:
        logger.error(f"Failed to get flavors: {e}")
        return {
            'success': False,
            'message': f'Failed to get flavors: {str(e)}',
            'error': str(e)
        }


def get_loadbalancer_providers() -> Dict[str, Any]:
    """
    Get load balancer providers.
    
    Returns:
        Dictionary containing providers information
    """
    try:
        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                columns = table_columns(cur, "provider")
                if not columns:
                    return {'success': True, 'providers': [], 'provider_count': 0}
                cur.execute("SELECT * FROM provider ORDER BY name ASC")
                provider_details = [{
                    'name': provider.get("name"),
                    'description': provider.get("description") or "",
                    'data_source': 'mariadb',
                } for provider in cur.fetchall()]
        finally:
            conn.close()
        
        return {
            'success': True,
            'providers': provider_details,
            'provider_count': len(provider_details)
        }
        
    except Exception as e:
        logger.error(f"Failed to get providers: {e}")
        return {
            'success': False,
            'message': f'Failed to get providers: {str(e)}',
            'error': str(e)
        }


def get_loadbalancer_quotas(project_id: str = "") -> Dict[str, Any]:
    """
    Get load balancer quotas.
    
    Args:
        project_id: Optional project ID for specific quota
    
    Returns:
        Dictionary containing quota information
    """
    try:
        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                if not table_columns(cur, "quotas"):
                    return {'success': True, 'quotas': [], 'quota_count': 0}
                sql = "SELECT * FROM quotas"
                params = []
                if project_id:
                    sql += " WHERE project_id = %s"
                    params.append(project_id)
                sql += " ORDER BY project_id ASC"
                cur.execute(sql, params)
                quota_details = [{
                    'project_id': quota.get("project_id"),
                    'load_balancer': quota.get("load_balancer", quota.get("loadbalancer", -1)),
                    'listener': quota.get("listener", -1),
                    'pool': quota.get("pool", -1),
                    'health_monitor': quota.get("health_monitor", -1),
                    'member': quota.get("member", -1),
                    'data_source': 'mariadb',
                } for quota in cur.fetchall()]
        finally:
            conn.close()
        if project_id:
            return {'success': True, 'quota': quota_details[0] if quota_details else {'project_id': project_id}}
        return {'success': True, 'quotas': quota_details, 'quota_count': len(quota_details)}
        
    except Exception as e:
        logger.error(f"Failed to get quotas: {e}")
        return {
            'success': False,
            'message': f'Failed to get quotas: {str(e)}',
            'error': str(e)
        }
