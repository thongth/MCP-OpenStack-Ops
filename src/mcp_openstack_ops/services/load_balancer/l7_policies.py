"""
Load Balancer L7 Policy and Rule Query Module

This module provides read-only L7 policy and rule queries for load balancers.
"""

import logging
from typing import Dict, Any
from ..db import bool_value, table_columns
from .db import get_octavia_connection, list_listeners

logger = logging.getLogger(__name__)


def get_loadbalancer_l7_policies(listener_name_or_id: str = "") -> Dict[str, Any]:
    """
    Get L7 policies for a listener or all policies.
    
    Args:
        listener_name_or_id: Optional listener name or ID to filter policies
    
    Returns:
        Dictionary containing L7 policies information
    """
    try:
        target_listener_id = ""
        if listener_name_or_id:
            listener = next((l for l in list_listeners() if l.get("name") == listener_name_or_id or l.get("id") == listener_name_or_id), None)
            if not listener:
                return {
                    'success': False,
                    'message': f'Listener not found: {listener_name_or_id}'
                }
            target_listener_id = listener.get("id")
        
        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                if not table_columns(cur, "l7policy"):
                    return {'success': True, 'l7_policies': [], 'policy_count': 0}
                sql = "SELECT * FROM l7policy WHERE 1=1 "
                params = []
                if target_listener_id:
                    sql += "AND listener_id = %s "
                    params.append(target_listener_id)
                sql += "ORDER BY position ASC"
                cur.execute(sql, params)
                policy_details = []
                for policy in cur.fetchall():
                    policy_details.append({
                        'id': policy.get("id"),
                        'name': policy.get("name") or 'N/A',
                        'description': policy.get("description") or '',
                        'listener_id': policy.get("listener_id"),
                        'action': policy.get("action"),
                        'position': policy.get("position"),
                        'redirect_pool_id': policy.get("redirect_pool_id"),
                        'redirect_url': policy.get("redirect_url"),
                        'admin_state_up': bool_value(policy.get("admin_state_up")),
                        'provisioning_status': policy.get("provisioning_status"),
                        'operating_status': policy.get("operating_status"),
                        'data_source': 'mariadb',
                    })
        finally:
            conn.close()
        
        return {
            'success': True,
            'l7_policies': policy_details,
            'policy_count': len(policy_details)
        }
        
    except Exception as e:
        logger.error(f"Failed to get L7 policies: {e}")
        return {
            'success': False,
            'message': f'Failed to get L7 policies: {str(e)}',
            'error': str(e)
        }


def get_loadbalancer_l7_rules(policy_name_or_id: str) -> Dict[str, Any]:
    """
    Get L7 rules for a specific L7 policy.
    
    Args:
        policy_name_or_id: L7 policy name or ID
    
    Returns:
        Dictionary containing L7 rules information
    """
    try:
        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                if not table_columns(cur, "l7policy"):
                    raise RuntimeError("MariaDB table 'l7policy' is not available")
                cur.execute("SELECT * FROM l7policy WHERE id = %s OR name = %s LIMIT 1", [policy_name_or_id, policy_name_or_id])
                policy = cur.fetchone()
        finally:
            conn.close()
        if not policy:
            return {
                'success': False,
                'message': f'L7 policy not found: {policy_name_or_id}'
            }
        
        conn = get_octavia_connection()
        try:
            with conn.cursor() as cur:
                if not table_columns(cur, "l7rule"):
                    rule_details = []
                else:
                    cur.execute("SELECT * FROM l7rule WHERE l7policy_id = %s ORDER BY created_at DESC", [policy.get("id")])
                    rule_details = [{
                        'id': rule.get("id"),
                        'l7policy_id': rule.get("l7policy_id"),
                        'type': rule.get("type"),
                        'compare_type': rule.get("compare_type"),
                        'key': rule.get("key"),
                        'value': rule.get("value"),
                        'invert': bool_value(rule.get("invert")),
                        'admin_state_up': bool_value(rule.get("admin_state_up")),
                        'provisioning_status': rule.get("provisioning_status"),
                        'operating_status': rule.get("operating_status"),
                        'data_source': 'mariadb',
                    } for rule in cur.fetchall()]
        finally:
            conn.close()
        
        return {
            'success': True,
            'l7_policy': {
                'id': policy.get("id"),
                'name': policy.get("name") or 'N/A'
            },
            'l7_rules': rule_details,
            'rule_count': len(rule_details)
        }
        
    except Exception as e:
        logger.error(f"Failed to get L7 rules: {e}")
        return {
            'success': False,
            'message': f'Failed to get L7 rules: {str(e)}',
            'error': str(e)
        }
