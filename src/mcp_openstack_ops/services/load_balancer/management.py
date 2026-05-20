"""
Load Balancer Management Module for Advanced Operations

This module provides comprehensive management operations for load balancer
including availability zones, flavors, quotas, providers, and advanced operations.
"""

import logging
from typing import Dict, Any
from ...connection import get_openstack_connection
from ..db import bool_value, str_time, table_columns
from .db import get_octavia_connection

logger = logging.getLogger(__name__)


def get_load_balancer_availability_zones() -> Dict[str, Any]:
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


def set_load_balancer_availability_zone(action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage availability zone operations.
    
    Args:
        action: Action (create, delete, set, unset, show)
        **kwargs: Parameters based on action
    
    Returns:
        Dictionary with operation results
    """
    try:
        conn = get_openstack_connection()
        
        if action == "create":
            name = kwargs.get('name')
            availability_zone_profile_id = kwargs.get('availability_zone_profile_id')
            
            if not name or not availability_zone_profile_id:
                return {
                    'success': False,
                    'message': 'name and availability_zone_profile_id are required for create'
                }
            
            az_params = {
                'name': name,
                'availability_zone_profile_id': availability_zone_profile_id,
                'description': kwargs.get('description', ''),
                'enabled': kwargs.get('enabled', True)
            }
            
            az = conn.load_balancer.create_availability_zone(**az_params)
            
            return {
                'success': True,
                'message': f'Availability zone created: {az.name}',
                'availability_zone': {
                    'name': az.name,
                    'description': getattr(az, 'description', ''),
                    'enabled': getattr(az, 'enabled', True)
                }
            }
        
        elif action == "delete":
            az_name = kwargs.get('az_name')
            if not az_name:
                return {
                    'success': False,
                    'message': 'az_name is required for delete'
                }
            
            az = conn.load_balancer.find_availability_zone(az_name)
            if not az:
                return {
                    'success': False,
                    'message': f'Availability zone not found: {az_name}'
                }
            
            conn.load_balancer.delete_availability_zone(az.name)
            return {
                'success': True,
                'message': f'Availability zone deleted: {az.name}'
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage availability zone: {e}")
        return {
            'success': False,
            'message': f'Failed to manage availability zone: {str(e)}',
            'error': str(e)
        }


def get_load_balancer_flavors() -> Dict[str, Any]:
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


def set_load_balancer_flavor(action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage flavor operations.
    
    Args:
        action: Action (create, delete, set, unset, show)
        **kwargs: Parameters based on action
    
    Returns:
        Dictionary with operation results
    """
    try:
        conn = get_openstack_connection()
        
        if action == "create":
            name = kwargs.get('name')
            flavor_profile_id = kwargs.get('flavor_profile_id')
            
            if not name or not flavor_profile_id:
                return {
                    'success': False,
                    'message': 'name and flavor_profile_id are required for create'
                }
            
            flavor_params = {
                'name': name,
                'flavor_profile_id': flavor_profile_id,
                'description': kwargs.get('description', ''),
                'enabled': kwargs.get('enabled', True)
            }
            
            flavor = conn.load_balancer.create_flavor(**flavor_params)
            
            return {
                'success': True,
                'message': f'Flavor created: {flavor.name}',
                'flavor': {
                    'id': flavor.id,
                    'name': flavor.name,
                    'description': getattr(flavor, 'description', ''),
                    'enabled': getattr(flavor, 'enabled', True)
                }
            }
        
        elif action == "delete":
            flavor_name_or_id = kwargs.get('flavor_name_or_id')
            if not flavor_name_or_id:
                return {
                    'success': False,
                    'message': 'flavor_name_or_id is required for delete'
                }
            
            flavor = conn.load_balancer.find_flavor(flavor_name_or_id)
            if not flavor:
                return {
                    'success': False,
                    'message': f'Flavor not found: {flavor_name_or_id}'
                }
            
            conn.load_balancer.delete_flavor(flavor.id)
            return {
                'success': True,
                'message': f'Flavor deleted: {flavor.name}'
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage flavor: {e}")
        return {
            'success': False,
            'message': f'Failed to manage flavor: {str(e)}',
            'error': str(e)
        }


def get_load_balancer_providers() -> Dict[str, Any]:
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


def get_load_balancer_quotas(project_id: str = "") -> Dict[str, Any]:
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


def set_load_balancer_quota(action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage quota operations.
    
    Args:
        action: Action (set, reset, unset)
        **kwargs: Parameters based on action
    
    Returns:
        Dictionary with operation results
    """
    try:
        conn = get_openstack_connection()
        
        if action == "set":
            project_id = kwargs.get('project_id')
            if not project_id:
                return {
                    'success': False,
                    'message': 'project_id is required for set'
                }
            
            quota_params = {}
            for key in ['load_balancer', 'listener', 'pool', 'health_monitor', 'member']:
                if key in kwargs:
                    quota_params[key] = kwargs[key]
            
            if not quota_params:
                return {
                    'success': False,
                    'message': 'At least one quota parameter is required'
                }
            
            updated_quota = conn.load_balancer.update_quota(project_id, **quota_params)
            
            return {
                'success': True,
                'message': f'Quota updated for project: {project_id}',
                'quota': {
                    'project_id': project_id,
                    'load_balancer': getattr(updated_quota, 'load_balancer', -1),
                    'listener': getattr(updated_quota, 'listener', -1),
                    'pool': getattr(updated_quota, 'pool', -1),
                    'health_monitor': getattr(updated_quota, 'health_monitor', -1),
                    'member': getattr(updated_quota, 'member', -1)
                }
            }
        
        elif action == "reset":
            project_id = kwargs.get('project_id')
            if not project_id:
                return {
                    'success': False,
                    'message': 'project_id is required for reset'
                }
            
            conn.load_balancer.delete_quota(project_id)
            return {
                'success': True,
                'message': f'Quota reset to defaults for project: {project_id}'
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: set, reset'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage quota: {e}")
        return {
            'success': False,
            'message': f'Failed to manage quota: {str(e)}',
            'error': str(e)
        }
