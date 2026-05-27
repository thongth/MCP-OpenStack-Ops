"""
OpenStack Load Balancer Core Functions

This module contains read-only load balancer query functions.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from ..db import column_expr, get_mariadb_connection, str_time, table_columns
from .db import (
    find_load_balancer,
    find_load_balancers_by_vip,
    find_load_balancers_by_vip_port,
    list_listeners,
    list_load_balancers,
    list_members,
    list_pools,
)

# Configure logging
logger = logging.getLogger(__name__)

NEUTRON_DATABASE = "neutron"


def get_loadbalancer_list(
    limit: int = 50,
    offset: int = 0,
    include_all: bool = False,
    project_id: str = "",
) -> Dict[str, Any]:
    """
    Get list of load balancers with comprehensive details.
    
    Args:
        limit: Maximum number of load balancers to return (1-200, default: 50)
        offset: Number of load balancers to skip (default: 0)
        include_all: If True, return all load balancers (ignores limit/offset)
        project_id: Optional project ID to filter
    
    Returns:
        Dictionary containing load balancers list with details
    """
    try:
        start_time = datetime.now()
        scope = "project-filtered" if project_id else "all-projects"

        logger.info(
            "Fetching load balancers (scope=%s, scope_project_id=%s, limit=%s, offset=%s, include_all=%s)",
            scope,
            project_id,
            limit,
            offset,
            include_all,
        )
        
        # Validate limit
        if not include_all:
            limit = max(1, min(limit, 200))
        
        all_lbs = list_load_balancers(project_id=project_id)
        
        # Apply pagination
        if include_all:
            load_balancers = all_lbs
        else:
            load_balancers = all_lbs[offset:offset + limit]
        
        # Build detailed load balancer information
        lb_details = []
        for lb in load_balancers:
            try:
                listener_summary = []
                for listener in list_listeners(loadbalancer_id=lb.get("id")):
                    listener_info = {
                        'id': listener.get("id"),
                        'name': listener.get("name"),
                        'protocol': listener.get("protocol"),
                        'protocol_port': listener.get("protocol_port"),
                        'admin_state_up': listener.get("admin_state_up"),
                    }
                    listener_summary.append(listener_info)
                
                lb_info = {
                    **lb,
                    'listeners': listener_summary,
                    'listener_count': len(listener_summary)
                }
                lb_details.append(lb_info)
                
            except Exception as e:
                logger.warning(f"Failed to get details for load balancer {lb.get('id')}: {e}")
                # Add basic info even if detailed fetch fails
                lb_details.append({
                    'id': lb.get("id"),
                    'name': lb.get("name"),
                    'vip_address': lb.get("vip_address", "N/A"),
                    'provisioning_status': lb.get("provisioning_status", "Unknown"),
                    'operating_status': lb.get("operating_status", "Unknown"),
                    'project_id': lb.get("project_id"),
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
                'project_id': project_id,
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
            project_id,
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


def get_loadbalancer_details(
    lb_name_or_id: str,
    include_amphorae: bool = True,
    include_amphora_instance_details: bool = True,
) -> Dict[str, Any]:
    """
    Get detailed information about a specific load balancer.
    
    Args:
        lb_name_or_id: Load balancer name or ID
    
    Returns:
        Dictionary containing detailed load balancer information
    """
    try:
        logger.info(f"Fetching load balancer details for: {lb_name_or_id}")
        lb = find_load_balancer(lb_name_or_id)
        if not lb:
            return {'success': False, 'message': f'Load balancer not found: {lb_name_or_id}'}

        lb_details = dict(lb)
        lb_details['data_source'] = 'mariadb'
        listeners = list_listeners(loadbalancer_id=lb.get("id"))
        listener_details = []
        nested_pool_ids = set()
        for listener in listeners:
            pools = list_pools(listener_id=listener.get("id"))
            default_pool_id = str(listener.get("default_pool_id") or "")
            if default_pool_id:
                pools.extend([p for p in list_pools() if str(p.get("id")) == default_pool_id])
            seen_pool_ids = set()
            pool_summary = []
            for pool in pools:
                pool_id = pool.get("id")
                if pool_id in seen_pool_ids:
                    continue
                seen_pool_ids.add(pool_id)
                nested_pool_ids.add(pool_id)
                members = list_members(pool_id)
                pool_summary.append({
                    **pool,
                    'members': members,
                    'member_count': len(members),
                })
            listener_details.append({
                **listener,
                'pools': pool_summary,
                'pool_count': len(pool_summary),
            })

        pool_details = []
        unattached_pool_details = []
        for pool in list_pools(loadbalancer_id=lb.get("id")):
            pool_id = pool.get("id")
            members = list_members(pool_id)
            pool_info = {
                **pool,
                'members': members,
                'member_count': len(members),
            }
            pool_details.append(pool_info)
            if pool_id not in nested_pool_ids:
                unattached_pool_details.append(pool_info)

        lb_details['listeners'] = listener_details
        lb_details['listener_count'] = len(listener_details)
        lb_details['pools'] = pool_details
        lb_details['pool_count'] = len(pool_details)
        lb_details['unattached_pools'] = unattached_pool_details
        lb_details['unattached_pool_count'] = len(unattached_pool_details)
        if include_amphorae:
            from .amphorae import get_loadbalancer_amphorae
            amphora_result = get_loadbalancer_amphorae(lb_name_or_id=lb.get("id"))
            lb_details['amphorae'] = amphora_result.get('amphorae', []) if amphora_result.get('success') else []
            lb_details['amphora_count'] = len(lb_details['amphorae'])
        return {'success': True, 'load_balancer': lb_details}
    except Exception as e:
        logger.error(f"Failed to get load balancer details: {e}")
        return {
            'success': False,
            'message': f'Failed to get load balancer details: {str(e)}',
            'error': str(e)
        }

def get_loadbalancer_by_vip(vip_address: str) -> Dict[str, Any]:
    """Get load balancer details by exact VIP address."""
    try:
        vip_address = (vip_address or "").strip()
        if not vip_address:
            return {"success": False, "message": "vip_address is required"}

        logger.info("Fetching load balancer by VIP address: %s", vip_address)
        load_balancers = find_load_balancers_by_vip(vip_address)
        return _load_balancer_lookup_response(
            query_type="vip_address",
            query=vip_address,
            load_balancers=load_balancers,
            not_found_message=f"Load balancer not found for VIP address: {vip_address}",
        )
    except Exception as e:
        logger.error(f"Failed to get load balancer by VIP: {e}")
        return {
            "success": False,
            "message": f"Failed to get load balancer by VIP: {str(e)}",
            "error": str(e),
        }

def get_loadbalancer_by_floatingip(floating_ip: str) -> Dict[str, Any]:
    """Get load balancer details by floating IP address or floating IP ID."""
    try:
        floating_ip = (floating_ip or "").strip()
        if not floating_ip:
            return {"success": False, "message": "floating_ip is required"}

        logger.info("Fetching load balancer by floating IP: %s", floating_ip)
        fip = _find_floating_ip(floating_ip)
        if not fip:
            return {
                "success": False,
                "message": f"Floating IP not found: {floating_ip}",
                "floating_ip_query": floating_ip,
            }

        load_balancers = []
        match_method = ""
        fixed_port_id = fip.get("fixed_port_id")
        fixed_ip_address = fip.get("fixed_ip_address")
        if fixed_port_id:
            load_balancers = find_load_balancers_by_vip_port(fixed_port_id)
            match_method = "fixed_port_id_to_vip_port_id"
        if not load_balancers and fixed_ip_address:
            load_balancers = find_load_balancers_by_vip(fixed_ip_address)
            match_method = "fixed_ip_address_to_vip_address"

        result = _load_balancer_lookup_response(
            query_type="floating_ip",
            query=floating_ip,
            load_balancers=load_balancers,
            not_found_message=f"Load balancer not found for floating IP: {floating_ip}",
        )
        result["floating_ip"] = fip
        result["match_method"] = match_method or "none"
        return result
    except Exception as e:
        logger.error(f"Failed to get load balancer by floating IP: {e}")
        return {
            "success": False,
            "message": f"Failed to get load balancer by floating IP: {str(e)}",
            "error": str(e),
        }

def _load_balancer_lookup_response(
    query_type: str,
    query: str,
    load_balancers: List[Dict[str, Any]],
    not_found_message: str,
) -> Dict[str, Any]:
    if not load_balancers:
        return {
            "success": False,
            "message": not_found_message,
            "query_type": query_type,
            "query": query,
            "load_balancers": [],
            "total_load_balancers": 0,
        }

    detailed_lbs = []
    for lb in load_balancers:
        detail_result = get_loadbalancer_details(lb.get("id"), include_amphorae=True)
        detailed_lbs.append(detail_result.get("load_balancer", lb) if detail_result.get("success") else lb)

    result = {
        "success": True,
        "query_type": query_type,
        "query": query,
        "load_balancers": detailed_lbs,
        "total_load_balancers": len(detailed_lbs),
    }
    if len(detailed_lbs) == 1:
        result["load_balancer"] = detailed_lbs[0]
    return result

def _find_floating_ip(identifier: str) -> Optional[Dict[str, Any]]:
    conn = get_mariadb_connection(NEUTRON_DATABASE)
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, "floatingips")
            if not columns:
                raise RuntimeError("MariaDB table 'floatingips' is not available")

            fixed_port_expr = column_expr("f", columns, "fixed_port_id", "port_id")
            floating_port_expr = column_expr("f", columns, "floating_port_id")
            router_expr = column_expr("f", columns, "router_id")
            status_expr = column_expr("f", columns, "status", default="'unknown'")
            project_expr = column_expr("f", columns, "project_id", "tenant_id")
            tenant_expr = column_expr("f", columns, "tenant_id", "project_id")
            floating_network_expr = column_expr("f", columns, "floating_network_id")
            fixed_ip_expr = column_expr("f", columns, "fixed_ip_address")
            description_expr = column_expr("f", columns, "description", default="''")
            created_expr = column_expr("f", columns, "created_at")
            updated_expr = column_expr("f", columns, "updated_at")

            sql = (
                "SELECT f.id, f.floating_ip_address, "
                f"{fixed_ip_expr} AS fixed_ip_address, {fixed_port_expr} AS fixed_port_id, "
                f"{floating_port_expr} AS floating_port_id, {router_expr} AS router_id, "
                f"{status_expr} AS status, {tenant_expr} AS tenant_id, {project_expr} AS project_id, "
                f"{floating_network_expr} AS floating_network_id, {created_expr} AS created_at, "
                f"{updated_expr} AS updated_at, {description_expr} AS description "
                "FROM floatingips f WHERE f.id = %s OR f.floating_ip_address = %s LIMIT 1"
            )
            cur.execute(sql, [identifier, identifier])
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": row.get("id"),
                "floating_ip_address": row.get("floating_ip_address"),
                "fixed_ip_address": row.get("fixed_ip_address"),
                "fixed_port_id": row.get("fixed_port_id"),
                "floating_port_id": row.get("floating_port_id"),
                "router_id": row.get("router_id"),
                "status": row.get("status") or "unknown",
                "tenant_id": row.get("tenant_id"),
                "project_id": row.get("project_id"),
                "floating_network_id": row.get("floating_network_id"),
                "created_at": str_time(row.get("created_at")),
                "updated_at": str_time(row.get("updated_at")),
                "description": row.get("description") or "",
                "data_source": "mariadb",
            }
    finally:
        conn.close()
