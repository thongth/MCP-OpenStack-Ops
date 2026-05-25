import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Import connection management from separate module
from .connection import get_openstack_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Compute (Nova) Functions - Enhanced
# =============================================================================
# Compute (Nova) Functions - Enhanced
# =============================================================================

# Compute functions are now imported from services.compute module
# All compute-related functionality has been modularized


# =============================================================================
# Image Service (Glance) Functions - Enhanced
# =============================================================================

def set_identity_groups(action: str, group_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack identity groups (list, show, create, delete, update)
    
    Args:
        action: Action to perform (list, show, create, delete, update)
        group_name: Name or ID of the group
        **kwargs: Additional parameters
    
    Returns:
        Result of the identity group management operation
    """
    try:
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            groups = []
            try:
                for group in conn.identity.groups():
                    groups.append({
                        'id': group.id,
                        'name': group.name,
                        'description': getattr(group, 'description', 'N/A'),
                        'domain_id': getattr(group, 'domain_id', 'N/A'),
                        'created_at': str(getattr(group, 'created_at', 'N/A')),
                        'updated_at': str(getattr(group, 'updated_at', 'N/A'))
                    })
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Identity groups not accessible: {str(e)}',
                    'groups': []
                }
            return {
                'success': True,
                'groups': groups,
                'count': len(groups)
            }
            
        elif action.lower() == 'create':
            if not group_name:
                return {
                    'success': False,
                    'message': 'group_name is required for create action'
                }
                
            description = kwargs.get('description', f'Group created via MCP: {group_name}')
            domain_id = kwargs.get('domain_id', 'default')
            
            try:
                group = conn.identity.create_group(
                    name=group_name,
                    description=description,
                    domain_id=domain_id
                )
                return {
                    'success': True,
                    'message': f'Group "{group_name}" created successfully',
                    'group_id': group.id,
                    'domain_id': domain_id
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create group: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, create'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage identity group: {e}")
        return {
            'success': False,
            'message': f'Failed to manage identity group: {str(e)}',
            'error': str(e)
        }


def set_roles(action: str, role_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack roles (list, show, create, delete, assign, unassign)
    
    Args:
        action: Action to perform (list, show, create, delete, assign, unassign)
        role_name: Name or ID of the role
        **kwargs: Additional parameters
    
    Returns:
        Result of the role management operation
    """
    try:
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            roles = []
            try:
                for role in conn.identity.roles():
                    roles.append({
                        'id': role.id,
                        'name': role.name,
                        'description': getattr(role, 'description', 'N/A'),
                        'domain_id': getattr(role, 'domain_id', None),
                        'created_at': str(getattr(role, 'created_at', 'N/A')),
                        'updated_at': str(getattr(role, 'updated_at', 'N/A'))
                    })
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Roles not accessible: {str(e)}',
                    'roles': []
                }
            return {
                'success': True,
                'roles': roles,
                'count': len(roles)
            }
            
        elif action.lower() == 'create':
            if not role_name:
                return {
                    'success': False,
                    'message': 'role_name is required for create action'
                }
                
            description = kwargs.get('description', f'Role created via MCP: {role_name}')
            domain_id = kwargs.get('domain_id', None)
            
            try:
                role = conn.identity.create_role(
                    name=role_name,
                    description=description,
                    domain_id=domain_id
                )
                return {
                    'success': True,
                    'message': f'Role "{role_name}" created successfully',
                    'role_id': role.id,
                    'domain_id': domain_id
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create role: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, create'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage role: {e}")
        return {
            'success': False,
            'message': f'Failed to manage role: {str(e)}',
            'error': str(e)
        }


def set_services(action: str, service_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack services (list, show, create, delete)
    
    Args:
        action: Action to perform (list, show, create, delete)
        service_name: Name or ID of the service
        **kwargs: Additional parameters
    
    Returns:
        Result of the service management operation
    """
    try:
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            services = []
            try:
                for service in conn.identity.services():
                    services.append({
                        'id': service.id,
                        'name': service.name,
                        'type': service.type,
                        'description': getattr(service, 'description', 'N/A'),
                        'enabled': getattr(service, 'enabled', True),
                        'created_at': str(getattr(service, 'created_at', 'N/A')),
                        'updated_at': str(getattr(service, 'updated_at', 'N/A'))
                    })
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Services not accessible: {str(e)}',
                    'services': []
                }
            return {
                'success': True,
                'services': services,
                'count': len(services)
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage service: {e}")
        return {
            'success': False,
            'message': f'Failed to manage service: {str(e)}',
            'error': str(e)
        }


def set_service_logs(
    action: str,
    service_name: str = None,
    log_level: str = "INFO"
) -> Dict[str, Any]:
    """
    Manage OpenStack service logs and logging configuration.
    
    Args:
        action: Action to perform - list, show
        service_name: Name of the service to get logs for
        log_level: Log level filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Service logs information
    """
    try:
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            # List available services for logging
            services = []
            try:
                # Get compute services
                for service in conn.compute.services():
                    services.append({
                        'name': service.binary,
                        'type': 'compute',
                        'host': service.host,
                        'status': service.status,
                        'state': service.state
                    })
                    
                # Get network agents (similar to services)
                for agent in conn.network.agents():
                    services.append({
                        'name': agent.agent_type,
                        'type': 'network',
                        'host': agent.host,
                        'status': 'enabled' if agent.is_enabled else 'disabled',
                        'state': 'up' if agent.is_alive else 'down'
                    })
                    
            except Exception as e:
                logger.warning(f"Could not get all services: {e}")
                
            return {
                'success': True,
                'services': services,
                'message': f'Found {len(services)} services available for logging',
                'log_level_filter': log_level
            }
            
        elif action.lower() == 'show':
            if not service_name:
                return {
                    'success': False,
                    'message': 'Service name required for show action'
                }
                
            # This would normally query actual log files or log aggregation service
            # For now, return service status and configuration info
            service_info = {
                'service_name': service_name,
                'log_level': log_level,
                'message': f'Log information for {service_name} (log level: {log_level})',
                'note': 'Log aggregation would require additional configuration with centralized logging system'
            }
            
            return {
                'success': True,
                'service_logs': service_info
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, show'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage service logs: {e}")
        return {
            'success': False,
            'message': f'Failed to manage service logs: {str(e)}',
            'error': str(e)
        }


def set_metrics(
    action: str,
    resource_type: str = "compute",
    resource_id: str = None
) -> Dict[str, Any]:
    """
    Manage OpenStack metrics collection and monitoring.
    
    Args:
        action: Action to perform - list, show, summary
        resource_type: Type of resource (compute, network, storage, identity)
        resource_id: Specific resource ID to get metrics for
        
    Returns:
        Metrics information
    """
    try:
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            metrics = []
            
            if resource_type.lower() == 'compute':
                # Get compute metrics
                try:
                    for server in conn.compute.servers():
                        metrics.append({
                            'resource_type': 'compute',
                            'resource_id': server.id,
                            'resource_name': server.name,
                            'status': server.status,
                            'power_state': getattr(server, 'power_state', 'unknown'),
                            'created_at': server.created_at,
                            'updated_at': server.updated_at
                        })
                except Exception as e:
                    logger.warning(f"Could not get compute metrics: {e}")
                    
            elif resource_type.lower() == 'network':
                # Get network metrics
                try:
                    for network in conn.network.networks():
                        metrics.append({
                            'resource_type': 'network',
                            'resource_id': network.id,
                            'resource_name': network.name,
                            'status': network.status,
                            'is_admin_state_up': network.is_admin_state_up,
                            'created_at': getattr(network, 'created_at', None),
                            'updated_at': getattr(network, 'updated_at', None)
                        })
                except Exception as e:
                    logger.warning(f"Could not get network metrics: {e}")
                    
            elif resource_type.lower() == 'storage':
                # Get storage metrics
                try:
                    for volume in conn.block_storage.volumes():
                        metrics.append({
                            'resource_type': 'storage',
                            'resource_id': volume.id,
                            'resource_name': volume.name,
                            'status': volume.status,
                            'size': volume.size,
                            'created_at': volume.created_at,
                            'updated_at': volume.updated_at
                        })
                except Exception as e:
                    logger.warning(f"Could not get storage metrics: {e}")
                    
            return {
                'success': True,
                'metrics': metrics,
                'resource_type': resource_type,
                'count': len(metrics)
            }
            
        elif action.lower() == 'show':
            if not resource_id:
                return {
                    'success': False,
                    'message': 'Resource ID required for show action'
                }
                
            # Get specific resource metrics
            resource_metrics = {
                'resource_type': resource_type,
                'resource_id': resource_id,
                'timestamp': datetime.utcnow().isoformat(),
                'note': 'Detailed metrics would require integration with monitoring system like Prometheus or Ceilometer'
            }
            
            return {
                'success': True,
                'resource_metrics': resource_metrics
            }
            
        elif action.lower() == 'summary':
            # Get summary metrics across all resource types
            summary = {
                'compute': {'total': 0, 'active': 0, 'error': 0, 'states': {}},
                'network': {'total': 0, 'active': 0, 'down': 0},
                'storage': {'total': 0, 'available': 0, 'in_use': 0},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            try:
                # Compute summary from Nova DB includes all instance states, not only ACTIVE.
                compute_summary = get_instance_summary()
                summary['compute']['total'] = compute_summary.get('total', 0)
                summary['compute']['active'] = compute_summary.get('active', 0)
                summary['compute']['error'] = compute_summary.get('error', 0)
                summary['compute']['states'] = {
                    row.get('status'): row.get('count', 0)
                    for row in compute_summary.get('by_status', [])
                }
                summary['compute']['data_source'] = compute_summary.get('data_source')
                
                # Network summary
                networks = list(conn.network.networks())
                summary['network']['total'] = len(networks)
                summary['network']['active'] = len([n for n in networks if n.status == 'ACTIVE'])
                summary['network']['down'] = len([n for n in networks if n.status == 'DOWN'])
                
                # Storage summary
                volumes = list(conn.block_storage.volumes())
                summary['storage']['total'] = len(volumes)
                summary['storage']['available'] = len([v for v in volumes if v.status == 'available'])
                summary['storage']['in_use'] = len([v for v in volumes if v.status == 'in-use'])
                
            except Exception as e:
                summary['error'] = f"Could not get complete summary: {str(e)}"
                
            return {
                'success': True,
                'summary': summary
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, show, summary'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage metrics: {e}")
        return {
            'success': False,
            'message': f'Failed to manage metrics: {str(e)}',
            'error': str(e)
        }


def set_alarms(
    action: str,
    alarm_name: str = None,
    resource_id: str = None,
    threshold: float = None,
    comparison: str = "gt"
) -> Dict[str, Any]:
    """
    Manage OpenStack alarms and alerting (requires Aodh service).
    
    Args:
        action: Action to perform - list, create, show, delete
        alarm_name: Name of the alarm
        resource_id: Resource ID to monitor
        threshold: Threshold value for alarm
        comparison: Comparison operator (gt, lt, eq, ne, ge, le)
        
    Returns:
        Alarm management information
    """
    try:
        # Note: This would require Aodh (alarming service) to be installed
        # For now, we'll simulate alarm management
        
        if action.lower() == 'list':
            # List available alarms (simulated)
            alarms = [
                {
                    'name': 'cpu-high-alarm',
                    'type': 'threshold',
                    'state': 'ok',
                    'enabled': True,
                    'description': 'CPU usage alarm for compute instances'
                },
                {
                    'name': 'memory-high-alarm',
                    'type': 'threshold',
                    'state': 'alarm',
                    'enabled': True,
                    'description': 'Memory usage alarm for compute instances'
                }
            ]
            
            return {
                'success': True,
                'alarms': alarms,
                'count': len(alarms),
                'note': 'Alarm management requires Aodh service to be installed and configured'
            }
            
        elif action.lower() == 'create':
            if not alarm_name:
                return {
                    'success': False,
                    'message': 'Alarm name required for create action'
                }
                
            # Simulate alarm creation
            alarm = {
                'name': alarm_name,
                'resource_id': resource_id,
                'threshold': threshold,
                'comparison': comparison,
                'state': 'insufficient data',
                'enabled': True,
                'created_at': datetime.utcnow().isoformat()
            }
            
            return {
                'success': True,
                'alarm': alarm,
                'message': f'Alarm "{alarm_name}" created (simulation - requires Aodh service)'
            }
            
        elif action.lower() == 'show':
            if not alarm_name:
                return {
                    'success': False,
                    'message': 'Alarm name required for show action'
                }
                
            # Simulate alarm details
            alarm_details = {
                'name': alarm_name,
                'type': 'threshold',
                'state': 'ok',
                'enabled': True,
                'threshold': threshold or 80.0,
                'comparison': comparison,
                'resource_id': resource_id,
                'description': f'Alarm monitoring for {alarm_name}'
            }
            
            return {
                'success': True,
                'alarm_details': alarm_details
            }
            
        elif action.lower() == 'delete':
            if not alarm_name:
                return {
                    'success': False,
                    'message': 'Alarm name required for delete action'
                }
                
            return {
                'success': True,
                'message': f'Alarm "{alarm_name}" deleted (simulation - requires Aodh service)'
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, create, show, delete'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage alarms: {e}")
        return {
            'success': False,
            'message': f'Failed to manage alarms: {str(e)}',
            'error': str(e)
        }


def set_compute_agents(
    action: str,
    agent_id: str = None,
    host: str = None
) -> Dict[str, Any]:
    """
    Manage OpenStack compute agents and hypervisor monitoring.
    
    Args:
        action: Action to perform - list, show
        agent_id: ID of specific agent
        host: Host name to filter agents
        
    Returns:
        Compute agent information
    """
    try:
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            agents = []
            
            # Get compute services (agents)
            try:
                for service in conn.compute.services():
                    if not host or service.host == host:
                        agents.append({
                            'id': service.id,
                            'binary': service.binary,
                            'host': service.host,
                            'zone': service.zone,
                            'status': service.status,
                            'state': service.state,
                            'updated_at': service.updated_at,
                            'disabled_reason': getattr(service, 'disabled_reason', None)
                        })
            except Exception as e:
                logger.warning(f"Could not get compute services: {e}")
                
            # Get hypervisor information
            try:
                hypervisors = []
                for hypervisor in conn.compute.hypervisors():
                    if not host or hypervisor.name == host:
                        hypervisors.append({
                            'id': hypervisor.id,
                            'name': hypervisor.name,
                            'status': hypervisor.status,
                            'state': hypervisor.state,
                            'vcpus': hypervisor.vcpus,
                            'vcpus_used': hypervisor.vcpus_used,
                            'memory_mb': hypervisor.memory_mb,
                            'memory_mb_used': hypervisor.memory_mb_used,
                            'local_gb': hypervisor.local_gb,
                            'local_gb_used': hypervisor.local_gb_used,
                            'running_vms': hypervisor.running_vms
                        })
                        
                return {
                    'success': True,
                    'compute_services': agents,
                    'hypervisors': hypervisors,
                    'count': {
                        'services': len(agents),
                        'hypervisors': len(hypervisors)
                    }
                }
            except Exception as e:
                logger.warning(f"Could not get hypervisor information: {e}")
                return {
                    'success': True,
                    'compute_services': agents,
                    'count': {'services': len(agents)}
                }
                
        elif action.lower() == 'show':
            if not agent_id and not host:
                return {
                    'success': False,
                    'message': 'Agent ID or host name required for show action'
                }
                
            # Get specific agent details
            if agent_id:
                try:
                    service = conn.compute.get_service(agent_id)
                    agent_details = {
                        'id': service.id,
                        'binary': service.binary,
                        'host': service.host,
                        'zone': service.zone,
                        'status': service.status,
                        'state': service.state,
                        'updated_at': service.updated_at,
                        'disabled_reason': getattr(service, 'disabled_reason', None)
                    }
                    
                    return {
                        'success': True,
                        'agent_details': agent_details
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'message': f'Agent not found: {str(e)}'
                    }
            else:
                # Search by host
                agents = []
                for service in conn.compute.services():
                    if service.host == host:
                        agents.append({
                            'id': service.id,
                            'binary': service.binary,
                            'host': service.host,
                            'zone': service.zone,
                            'status': service.status,
                            'state': service.state
                        })
                        
                return {
                    'success': True,
                    'agents_on_host': agents,
                    'host': host,
                    'count': len(agents)
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, show'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage compute agents: {e}")
        return {
            'success': False,
            'message': f'Failed to manage compute agents: {str(e)}',
            'error': str(e)
        }


    except Exception as e:
        logger.error(f"Failed to manage compute agents: {e}")
        return {
            'success': False,
            'message': f'Failed to manage compute agents: {str(e)}',
            'error': str(e)
        }


# =============================================================================
# OCTAVIA (LOAD BALANCER) FUNCTIONS - IMPORTED FROM MODULAR SERVICES
# =============================================================================

# Load balancer functions are now modularized in services.load_balancer
# Import compute functions from services
from .services.compute import (
    get_instance_details,
    get_instance_summary,
    get_instance_by_name,
    get_instances_by_status,
    get_server_events,
    get_server_groups,
)

# Import network functions from services
from .services.network import (
    get_network_details,
    get_network_summary,
    get_network_agents,
    get_security_groups,
    get_security_groups_summary,
    get_floating_ips,
    get_floating_ips_summary,
    get_floating_ip_pools,
    get_routers,
    get_routers_summary,
    set_network_ports,
)

# Import storage functions from services
from .services.storage import (
    get_volume_list,
    get_volume_summary,
    get_volume_types,
    get_volume_snapshots,
    get_volume_snapshot_summary,
    get_volume_backups,
    get_volume_backup_summary,
    get_server_volumes,
)

# Import identity functions from services
from .services.identity import (
    get_project_list,
    get_user_list,
    get_role_assignments,
    get_keypair_list,
    get_project_details,
)

# Import image functions from services
from .services.image import (
    get_image_list_filtered,
    get_image_by_id_or_name,
    search_images,
    get_image_detail_list,
)

# Import monitoring functions from services  
from .services.monitoring import (
    get_system_information,
    get_resource_monitoring,
    get_usage_statistics,
    get_quota,
    get_hypervisor_details,
    get_availability_zones,
)

from .services.mariadb_cluster import (
    mariadb_cluster_alerts,
    mariadb_cluster_capacity_summary,
    mariadb_cluster_connection_stats,
    mariadb_cluster_health,
    mariadb_cluster_query_performance,
    mariadb_cluster_replication_overview,
    mariadb_cluster_storage_utilization,
    mariadb_cluster_top_slow_queries,
    mariadb_cluster_top_tables,
    mariadb_cluster_wsrep_status,
)

from .services.rabbitmq import (
    rabbitmq_cluster_alerts,
    rabbitmq_cluster_channels,
    rabbitmq_cluster_connections,
    rabbitmq_cluster_consumers,
    rabbitmq_cluster_exchanges,
    rabbitmq_cluster_health,
    rabbitmq_cluster_nodes,
    rabbitmq_cluster_overview,
    rabbitmq_cluster_queues,
    rabbitmq_cluster_vhosts,
)

from .services.load_balancer import (
    # Core operations
    get_loadbalancer_list,
    get_loadbalancer_details, 
    get_loadbalancer_by_vip,
    get_loadbalancer_by_floatingip,
    
    # Listener operations
    get_loadbalancer_listeners,
    
    # Pool operations
    get_loadbalancer_pools,
    get_loadbalancer_pool_members,
    
    # Health monitor operations
    get_loadbalancer_health_monitors,
    
    # L7 policy operations
    get_loadbalancer_l7_policies,
    get_loadbalancer_l7_rules,
    
    # Management operations
    get_loadbalancer_availability_zones,
    get_loadbalancer_flavors,
    get_loadbalancer_providers,
    get_loadbalancer_quotas,
    
    # Amphora operations
    get_loadbalancer_amphorae,
)


__all__ = [
    "get_availability_zones",
    "get_floating_ip_pools",
    "get_floating_ips",
    "get_floating_ips_summary",
    "get_hypervisor_details",
    "get_image_by_id_or_name",
    "get_image_detail_list",
    "get_image_list_filtered",
    "get_instance_by_name",
    "get_instance_details",
    "get_instance_summary",
    "get_instances_by_status",
    "get_keypair_list",
    "get_loadbalancer_amphorae",
    "get_loadbalancer_availability_zones",
    "get_loadbalancer_by_floatingip",
    "get_loadbalancer_by_vip",
    "get_loadbalancer_details",
    "get_loadbalancer_flavors",
    "get_loadbalancer_health_monitors",
    "get_loadbalancer_l7_policies",
    "get_loadbalancer_l7_rules",
    "get_loadbalancer_list",
    "get_loadbalancer_listeners",
    "get_loadbalancer_pool_members",
    "get_loadbalancer_pools",
    "get_loadbalancer_providers",
    "get_loadbalancer_quotas",
    "get_network_agents",
    "get_network_details",
    "get_network_summary",
    "get_project_details",
    "get_project_list",
    "get_quota",
    "get_resource_monitoring",
    "get_role_assignments",
    "get_routers",
    "get_routers_summary",
    "get_security_groups",
    "get_security_groups_summary",
    "get_server_events",
    "get_server_groups",
    "get_server_volumes",
    "get_system_information",
    "get_usage_statistics",
    "get_user_list",
    "get_volume_backup_summary",
    "get_volume_backups",
    "get_volume_list",
    "get_volume_snapshot_summary",
    "get_volume_snapshots",
    "get_volume_summary",
    "get_volume_types",
    "mariadb_cluster_alerts",
    "mariadb_cluster_capacity_summary",
    "mariadb_cluster_connection_stats",
    "mariadb_cluster_health",
    "mariadb_cluster_query_performance",
    "mariadb_cluster_replication_overview",
    "mariadb_cluster_storage_utilization",
    "mariadb_cluster_top_slow_queries",
    "mariadb_cluster_top_tables",
    "mariadb_cluster_wsrep_status",
    "rabbitmq_cluster_alerts",
    "rabbitmq_cluster_channels",
    "rabbitmq_cluster_connections",
    "rabbitmq_cluster_consumers",
    "rabbitmq_cluster_exchanges",
    "rabbitmq_cluster_health",
    "rabbitmq_cluster_nodes",
    "rabbitmq_cluster_overview",
    "rabbitmq_cluster_queues",
    "rabbitmq_cluster_vhosts",
    "search_images",
    "set_network_ports",
]
