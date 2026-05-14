"""
OpenStack Load Balancer Core Functions

This module contains core load balancer management functions including
creation, deletion, and basic load balancer operations.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from ...connection import get_openstack_connection, is_all_projects_readonly_mode

# Configure logging
logger = logging.getLogger(__name__)


def get_load_balancer_list(
    limit: int = 50,
    offset: int = 0,
    include_all: bool = False,
    include_all_projects: bool = False,
    project_id: str = "",
) -> Dict[str, Any]:
    """
    Get list of load balancers with comprehensive details.
    
    Args:
        limit: Maximum number of load balancers to return (1-200, default: 50)
        offset: Number of load balancers to skip (default: 0)
        include_all: If True, return all load balancers (ignores limit/offset)
        include_all_projects: If True, list load balancers across all projects
        project_id: Optional project ID to filter
    
    Returns:
        Dictionary containing load balancers list with details
    """
    try:
        conn = get_openstack_connection()
        current_project_id = conn.current_project_id
        all_projects_mode = is_all_projects_readonly_mode()
        start_time = datetime.now()

        scope_project_id: Optional[str] = None
        scope: str = "project"
        # Security guard: cross-project listing is only allowed in read-only all-projects mode.
        if all_projects_mode and project_id:
            scope_project_id = project_id
            scope = "project-filter"
        elif all_projects_mode and include_all_projects:
            scope_project_id = None
            scope = "all-projects"
        elif all_projects_mode:
            scope_project_id = None
            scope = "all-projects-readonly"
        else:
            scope_project_id = current_project_id
            scope = "project"

        logger.info(
            "Fetching load balancers (scope=%s, scope_project_id=%s, limit=%s, offset=%s, include_all=%s)",
            scope,
            scope_project_id,
            limit,
            offset,
            include_all,
        )
        
        # Validate limit
        if not include_all:
            limit = max(1, min(limit, 200))
        
        # Get all load balancers and filter by requested scope
        all_lbs = []
        for lb in conn.load_balancer.load_balancers():
            if scope_project_id is None or getattr(lb, 'project_id', None) == scope_project_id:
                all_lbs.append(lb)
        
        # Apply pagination
        if include_all:
            load_balancers = all_lbs
        else:
            load_balancers = all_lbs[offset:offset + limit]
        
        # Build detailed load balancer information
        lb_details = []
        for lb in load_balancers:
            try:
                # Get listeners for this load balancer
                listeners = list(conn.load_balancer.listeners(loadbalancer_id=lb.id))
                listener_summary = []
                
                for listener in listeners:
                    listener_info = {
                        'id': listener.id,
                        'name': listener.name,
                        'protocol': listener.protocol,
                        'protocol_port': listener.protocol_port,
                        'admin_state_up': getattr(listener, 'admin_state_up', None)
                    }
                    listener_summary.append(listener_info)
                
                lb_info = {
                    'id': lb.id,
                    'name': lb.name,
                    'description': lb.description,
                    'vip_address': lb.vip_address,
                    'vip_port_id': lb.vip_port_id,
                    'vip_subnet_id': lb.vip_subnet_id,
                    'vip_network_id': lb.vip_network_id,
                    'provisioning_status': lb.provisioning_status,
                    'operating_status': lb.operating_status,
                    'admin_state_up': getattr(lb, 'admin_state_up', None),
                    'project_id': lb.project_id,
                    'provider': getattr(lb, 'provider', 'Unknown'),
                    'created_at': str(lb.created_at) if hasattr(lb, 'created_at') else 'N/A',
                    'updated_at': str(lb.updated_at) if hasattr(lb, 'updated_at') else 'N/A',
                    'listeners': listener_summary,
                    'listener_count': len(listener_summary)
                }
                lb_details.append(lb_info)
                
            except Exception as e:
                logger.warning(f"Failed to get details for load balancer {lb.id}: {e}")
                # Add basic info even if detailed fetch fails
                lb_details.append({
                    'id': lb.id,
                    'name': lb.name,
                    'vip_address': getattr(lb, 'vip_address', 'N/A'),
                    'provisioning_status': getattr(lb, 'provisioning_status', 'Unknown'),
                    'operating_status': getattr(lb, 'operating_status', 'Unknown'),
                    'project_id': getattr(lb, 'project_id', current_project_id),
                    'error': f'Failed to fetch details: {str(e)}'
                })
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        result = {
            'success': True,
            'load_balancers': lb_details,
            'summary': {
                'total_returned': len(lb_details),
                'limit': limit if not include_all else 'all',
                'offset': offset if not include_all else 0,
                'processing_time_seconds': round(processing_time, 2),
                'project_id': scope_project_id,
                'scope': scope,
            }
        }
        
        if not include_all:
            result['summary']['total_available'] = len(all_lbs)
            result['summary']['has_more'] = (offset + limit) < len(all_lbs)
        
        logger.info(
            "Successfully retrieved %s load balancers (scope=%s, project_id=%s) in %.2fs",
            len(lb_details),
            scope,
            scope_project_id,
            processing_time,
        )
        return result
        
    except Exception as e:
        logger.error(f"Failed to get load balancers: {e}")
        return {
            'success': False,
            'message': f'Failed to get load balancers: {str(e)}',
            'error': str(e)
        }


def get_load_balancer_details(lb_name_or_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific load balancer.
    
    Args:
        lb_name_or_id: Load balancer name or ID
    
    Returns:
        Dictionary containing detailed load balancer information
    """
    try:
        # Import here to avoid circular imports
        conn = get_openstack_connection()
        
        logger.info(f"Fetching load balancer details for: {lb_name_or_id}")
        
        # Try to find load balancer by ID or name
        lb = conn.load_balancer.find_load_balancer(lb_name_or_id)
        if not lb:
            return {
                'success': False,
                'message': f'Load balancer not found: {lb_name_or_id}'
            }
        
        # Get comprehensive load balancer details
        lb_details = {
            'id': lb.id,
            'name': lb.name,
            'description': lb.description,
            'vip_address': lb.vip_address,
            'vip_port_id': lb.vip_port_id,
            'vip_subnet_id': lb.vip_subnet_id,
            'vip_network_id': lb.vip_network_id,
            'provisioning_status': lb.provisioning_status,
            'operating_status': lb.operating_status,
            'admin_state_up': getattr(lb, 'admin_state_up', None),
            'project_id': lb.project_id,
            'provider': getattr(lb, 'provider', 'Unknown'),
            'created_at': str(lb.created_at) if hasattr(lb, 'created_at') else 'N/A',
            'updated_at': str(lb.updated_at) if hasattr(lb, 'updated_at') else 'N/A'
        }
        
        listener_details = []
        warnings = []
        
        # Get listeners/pools/members with resilient partial-failure handling.
        try:
            raw_listeners = list(conn.load_balancer.listeners(loadbalancer_id=lb.id))
            listeners = []
            for listener in raw_listeners:
                listener_lb_id = str(getattr(listener, 'loadbalancer_id', '') or '')
                listener_lbs = getattr(listener, 'load_balancers', []) or []
                in_lb_refs = any(str((ref or {}).get('id', '')) == str(lb.id) for ref in listener_lbs if isinstance(ref, dict))
                if listener_lb_id == str(lb.id) or in_lb_refs:
                    listeners.append(listener)
        except Exception as e:
            warnings.append(f"Failed to list listeners: {e}")
            listeners = []
        
        for listener in listeners:
            pool_summary = []
            try:
                pools = list(conn.load_balancer.pools(listener_id=listener.id))
            except Exception as e:
                warnings.append(
                    f"Failed to list pools for listener {listener.id} via listener_id filter: {e}. "
                    "Falling back to global pool listing."
                )
                try:
                    all_pools = list(conn.load_balancer.pools())
                    listener_default_pool_id = str(getattr(listener, 'default_pool_id', '') or '')
                    pools = [
                        p for p in all_pools
                        if str(getattr(p, 'listener_id', '')) == str(listener.id)
                        or str(getattr(p, 'loadbalancer_id', '')) == str(lb.id)
                        or str(getattr(p, 'id', '')) == listener_default_pool_id
                        or any(
                            str((ref or {}).get('id', '')) == str(listener.id)
                            for ref in (getattr(p, 'listeners', []) or [])
                            if isinstance(ref, dict)
                        )
                        or any(
                            str((ref or {}).get('id', '')) == str(lb.id)
                            for ref in (getattr(p, 'load_balancers', []) or [])
                            if isinstance(ref, dict)
                        )
                    ]
                except Exception as fallback_e:
                    warnings.append(f"Fallback pool listing failed for listener {listener.id}: {fallback_e}")
                    pools = []
            
            for pool in pools:
                try:
                    members = list(conn.load_balancer.members(pool))
                    member_summary = [{'id': m.id, 'address': m.address, 'protocol_port': m.protocol_port} for m in members]
                except Exception as e:
                    warnings.append(f"Failed to list members for pool {pool.id}: {e}")
                    member_summary = []
                
                pool_info = {
                    'id': pool.id,
                    'name': pool.name,
                    'protocol': pool.protocol,
                    'lb_algorithm': pool.lb_algorithm,
                    'admin_state_up': getattr(pool, 'admin_state_up', None),
                    'members': member_summary,
                    'member_count': len(member_summary)
                }
                pool_summary.append(pool_info)
            
            listener_info = {
                'id': listener.id,
                'name': listener.name,
                'protocol': listener.protocol,
                'protocol_port': listener.protocol_port,
                'admin_state_up': getattr(listener, 'admin_state_up', None),
                'pools': pool_summary,
                'pool_count': len(pool_summary)
            }
            listener_details.append(listener_info)
        
        lb_details['listeners'] = listener_details
        lb_details['listener_count'] = len(listener_details)
        lb_details['warnings'] = warnings
        
        return {
            'success': True,
            'load_balancer': lb_details
        }
        
    except Exception as e:
        logger.error(f"Failed to get load balancer details: {e}")
        return {
            'success': False,
            'message': f'Failed to get load balancer details: {str(e)}',
            'error': str(e)
        }


def set_load_balancer(action: str, **kwargs) -> Dict[str, Any]:
    """
    Comprehensive load balancer management operations.
    
    Args:
        action: Action to perform (create, delete, set, unset, failover, stats, status)
        **kwargs: Additional parameters based on action
    
    Returns:
        Dictionary containing operation results
    """
    try:
        conn = get_openstack_connection()
        
        logger.info(f"Managing load balancer with action: {action}")
        
        if action == "create":
            # Create load balancer
            name = kwargs.get('name')
            vip_subnet_id = kwargs.get('vip_subnet_id')
            
            if not name or not vip_subnet_id:
                return {
                    'success': False,
                    'message': 'name and vip_subnet_id are required for load balancer creation'
                }
            
            lb_params = {
                'name': name,
                'vip_subnet_id': vip_subnet_id,
                'description': kwargs.get('description', ''),
                'admin_state_up': kwargs.get('admin_state_up', True),
                'provider': kwargs.get('provider'),
                'flavor_id': kwargs.get('flavor_id'),
                'availability_zone': kwargs.get('availability_zone')
            }
            
            # Remove None values
            lb_params = {k: v for k, v in lb_params.items() if v is not None}
            
            lb = conn.load_balancer.create_load_balancer(**lb_params)
            
            return {
                'success': True,
                'message': f'Load balancer created successfully: {lb.name}',
                'load_balancer': {
                    'id': lb.id,
                    'name': lb.name,
                    'vip_address': lb.vip_address,
                    'provisioning_status': lb.provisioning_status,
                    'operating_status': lb.operating_status
                }
            }
        
        elif action == "delete":
            lb_name_or_id = kwargs.get('lb_name_or_id')
            if not lb_name_or_id:
                return {
                    'success': False,
                    'message': 'lb_name_or_id is required for deletion'
                }
            
            lb = conn.load_balancer.find_load_balancer(lb_name_or_id)
            if not lb:
                return {
                    'success': False,
                    'message': f'Load balancer not found: {lb_name_or_id}'
                }
            
            conn.load_balancer.delete_load_balancer(lb.id, cascade=kwargs.get('cascade', False))
            return {
                'success': True,
                'message': f'Load balancer deleted successfully: {lb.name}'
            }
        
        elif action in ["set", "update"]:
            lb_name_or_id = kwargs.get('lb_name_or_id')
            if not lb_name_or_id:
                return {
                    'success': False,
                    'message': 'lb_name_or_id is required for update'
                }
            
            lb = conn.load_balancer.find_load_balancer(lb_name_or_id)
            if not lb:
                return {
                    'success': False,
                    'message': f'Load balancer not found: {lb_name_or_id}'
                }
            
            update_params = {}
            for key in ['name', 'description', 'admin_state_up']:
                if key in kwargs:
                    update_params[key] = kwargs[key]
            
            if not update_params:
                return {
                    'success': False,
                    'message': 'No update parameters provided'
                }
            
            updated_lb = conn.load_balancer.update_load_balancer(lb.id, **update_params)
            return {
                'success': True,
                'message': f'Load balancer updated successfully: {updated_lb.name}',
                'load_balancer': {
                    'id': updated_lb.id,
                    'name': updated_lb.name,
                    'description': updated_lb.description,
                    'admin_state_up': updated_lb.admin_state_up
                }
            }
        
        elif action == "unset":
            lb_name_or_id = kwargs.get('lb_name_or_id')
            if not lb_name_or_id:
                return {
                    'success': False,
                    'message': 'lb_name_or_id is required for unset'
                }
            
            lb = conn.load_balancer.find_load_balancer(lb_name_or_id)
            if not lb:
                return {
                    'success': False,
                    'message': f'Load balancer not found: {lb_name_or_id}'
                }
            
            unset_params = {}
            # Unset operations: clear description
            if kwargs.get('description'):
                unset_params['description'] = ''
            
            if unset_params:
                updated_lb = conn.load_balancer.update_load_balancer(lb.id, **unset_params)
                return {
                    'success': True,
                    'message': f'Load balancer settings cleared: {updated_lb.name}'
                }
            else:
                return {
                    'success': False,
                    'message': 'No unset parameters specified'
                }
        
        elif action == "failover":
            lb_name_or_id = kwargs.get('lb_name_or_id')
            if not lb_name_or_id:
                return {
                    'success': False,
                    'message': 'lb_name_or_id is required for failover'
                }
            
            lb = conn.load_balancer.find_load_balancer(lb_name_or_id)
            if not lb:
                return {
                    'success': False,
                    'message': f'Load balancer not found: {lb_name_or_id}'
                }
            
            # Trigger load balancer failover
            try:
                conn.load_balancer.failover_load_balancer(lb.id)
                return {
                    'success': True,
                    'message': f'Load balancer failover initiated: {lb.name}'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to trigger failover: {str(e)}'
                }
        
        elif action == "stats":
            lb_name_or_id = kwargs.get('lb_name_or_id')
            if not lb_name_or_id:
                return {
                    'success': False,
                    'message': 'lb_name_or_id is required for stats'
                }
            
            lb = conn.load_balancer.find_load_balancer(lb_name_or_id)
            if not lb:
                return {
                    'success': False,
                    'message': f'Load balancer not found: {lb_name_or_id}'
                }
            
            # Get load balancer statistics
            try:
                stats = conn.load_balancer.get_load_balancer_statistics(lb.id)
                return {
                    'success': True,
                    'load_balancer_stats': {
                        'bytes_in': getattr(stats, 'bytes_in', 0),
                        'bytes_out': getattr(stats, 'bytes_out', 0),
                        'active_connections': getattr(stats, 'active_connections', 0),
                        'total_connections': getattr(stats, 'total_connections', 0)
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to get load balancer statistics: {str(e)}'
                }
        
        elif action == "status":
            lb_name_or_id = kwargs.get('lb_name_or_id')
            if not lb_name_or_id:
                return {
                    'success': False,
                    'message': 'lb_name_or_id is required for status'
                }
            
            lb = conn.load_balancer.find_load_balancer(lb_name_or_id)
            if not lb:
                return {
                    'success': False,
                    'message': f'Load balancer not found: {lb_name_or_id}'
                }
            
            # Get load balancer status tree
            try:
                # Since status endpoint may not be available, get basic status
                return {
                    'success': True,
                    'load_balancer_status': {
                        'id': lb.id,
                        'name': lb.name,
                        'provisioning_status': lb.provisioning_status,
                        'operating_status': lb.operating_status,
                        'admin_state_up': lb.admin_state_up,
                        'vip_address': lb.vip_address
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to get load balancer status: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete, set, unset, failover, stats, status'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage load balancer: {e}")
        return {
            'success': False,
            'message': f'Failed to manage load balancer: {str(e)}',
            'error': str(e)
        }
