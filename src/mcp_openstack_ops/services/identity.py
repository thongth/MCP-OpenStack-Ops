"""
OpenStack Identity (Keystone) Service Functions

This module contains functions for managing projects, users, roles, domains, and keypairs.
"""

import logging
from typing import Dict, List, Any, Optional
from ..connection import get_openstack_connection
from .db import bool_value, column_expr, get_mariadb_connection, json_value, str_time, table_columns, table_exists

# Configure logging
logger = logging.getLogger(__name__)
KEYSTONE_DATABASE = "keystone"


def _get_keystone_mariadb_connection():
    return get_mariadb_connection(KEYSTONE_DATABASE)


def _get_project_by_id(project_id: str) -> Optional[Dict[str, Any]]:
    result = get_project_list()
    if not result.get("success"):
        return None
    for project in result.get("projects", []):
        if project.get("id") == project_id:
            return project
    return None


def set_domains(action: str, domain_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack domains (list, show,             # Calculate compute resources
            resources['compute']['instances'] = len(project_instances)
            for instance in project_instances:
                try:
                    # Get vCPU and RAM directly from flavor object
                    if hasattr(instance, 'flavor'):
                        flavor = instance.flavor
                        # Flavor object has vcpus and ram attributes directly
                        if hasattr(flavor, 'vcpus') and hasattr(flavor, 'ram'):
                            vcpus = getattr(flavor, 'vcpus', 0)
                            ram_mb = getattr(flavor, 'ram', 0)
                            resources['compute']['vcpus_used'] += vcpus
                            resources['compute']['ram_mb_used'] += ram_mb
                            logger.debug(f"Instance {instance.name}: vCPUs={vcpus}, RAM={ram_mb}MB")
                        else:
                            # Fallback: try to get from dict representation
                            flavor_dict = dict(flavor)
                            vcpus = flavor_dict.get('vcpus', 0)
                            ram_mb = flavor_dict.get('ram', 0)
                            resources['compute']['vcpus_used'] += vcpus
                            resources['compute']['ram_mb_used'] += ram_mb
                            logger.debug(f"Instance {instance.name} (dict): vCPUs={vcpus}, RAM={ram_mb}MB")
                except Exception as inst_error:
                    logger.warning(f"Could not get flavor info for instance {instance.id}: {inst_error}")
                    continueate)
    
    Args:
        action: Action to perform (list, show, create, delete, update)
        domain_name: Name or ID of the domain
        **kwargs: Additional parameters
    
    Returns:
        Result of the domain management operation
    """
    try:
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            domains = []
            try:
                for domain in conn.identity.domains():
                    domains.append({
                        'id': domain.id,
                        'name': domain.name,
                        'description': getattr(domain, 'description', 'N/A'),
                        'enabled': domain.is_enabled,
                        'created_at': str(getattr(domain, 'created_at', 'N/A')),
                        'updated_at': str(getattr(domain, 'updated_at', 'N/A'))
                    })
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Domains not accessible: {str(e)}',
                    'domains': []
                }
            return {
                'success': True,
                'domains': domains,
                'count': len(domains)
            }
            
        elif action.lower() == 'create':
            if not domain_name:
                return {
                    'success': False,
                    'message': 'domain_name is required for create action'
                }
                
            description = kwargs.get('description', f'Domain created via MCP: {domain_name}')
            enabled = kwargs.get('enabled', True)
            
            try:
                domain = conn.identity.create_domain(
                    name=domain_name,
                    description=description,
                    enabled=enabled
                )
                return {
                    'success': True,
                    'message': f'Domain "{domain_name}" created successfully',
                    'domain_id': domain.id,
                    'enabled': enabled
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create domain: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, create'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage domain: {e}")
        return {
            'success': False,
            'message': f'Failed to manage domain: {str(e)}',
            'error': str(e)
        }


def get_project_info() -> Dict[str, Any]:
    """
    Get information about the current OpenStack project/tenant.
    
    Returns:
        Dict containing project information
    """
    try:
        project_id = (
            __import__("os").getenv("MARIADB_PROJECT_ID")
            or __import__("os").getenv("OS_PROJECT_ID")
            or __import__("os").getenv("OS_TENANT_ID")
        )
        if not project_id:
            return {'error': 'OS_PROJECT_ID/MARIADB_PROJECT_ID is not set', 'name': 'unknown-project', 'id': 'unknown'}
        project = _get_project_by_id(project_id)
        return project or {'error': f'Project {project_id} not found', 'id': project_id, 'name': 'unknown-project'}
    except Exception as e:
        logger.error(f"Failed to get project info: {e}")
        return {'error': str(e), 'name': 'unknown-project', 'id': 'unknown'}


def get_user_list() -> List[Dict[str, Any]]:
    """
    Get list of users in the current project scope.
    
    Returns:
        List of user dictionaries for current project
    """
    try:
        conn = _get_keystone_mariadb_connection()
        try:
            with conn.cursor() as cur:
                user_columns = table_columns(cur, "user")
                if not user_columns:
                    raise RuntimeError("MariaDB table 'user' is not available")
                local_columns = table_columns(cur, "local_user")
                name_expr = "lu.name" if {"user_id", "name"}.issubset(local_columns) else column_expr("u", user_columns, "name", default="u.id")
                domain_expr = "COALESCE(lu.domain_id, u.domain_id)" if "domain_id" in user_columns and "domain_id" in local_columns else column_expr("u", user_columns, "domain_id", default="NULL")
                enabled_expr = column_expr("u", user_columns, "enabled", default="1")
                extra_expr = column_expr("u", user_columns, "extra", default="NULL")
                created_expr = column_expr("u", user_columns, "created_at", default="NULL")
                updated_expr = column_expr("u", user_columns, "updated_at", default="NULL")
                sql = (
                    "SELECT u.id, "
                    f"{name_expr} AS name, {domain_expr} AS domain_id, {enabled_expr} AS enabled, "
                    f"{extra_expr} AS extra, {created_expr} AS created_at, {updated_expr} AS updated_at "
                    "FROM user u "
                )
                if {"user_id", "name"}.issubset(local_columns):
                    sql += "LEFT JOIN local_user lu ON lu.user_id = u.id "
                sql += "ORDER BY name ASC"
                cur.execute(sql)
                users = []
                for row in cur.fetchall():
                    extra = json_value(row.get("extra"), {}) or {}
                    users.append({
                        'id': row.get("id"),
                        'name': row.get("name") or row.get("id"),
                        'email': extra.get("email", "N/A"),
                        'enabled': bool_value(row.get("enabled")),
                        'domain_id': row.get("domain_id") or "N/A",
                        'created_at': str_time(row.get("created_at")),
                        'updated_at': str_time(row.get("updated_at")),
                        'data_source': 'mariadb',
                    })
                return users
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get user list: {e}")
        return [{'error': str(e)}]


def get_role_assignments() -> List[Dict[str, Any]]:
    """
    Get role assignments for the current project only.
    
    Returns:
        List of role assignment dictionaries for current project
    """
    try:
        conn = _get_keystone_mariadb_connection()
        try:
            with conn.cursor() as cur:
                columns = table_columns(cur, "assignment")
                if not columns:
                    raise RuntimeError("MariaDB table 'assignment' is not available")
                role_columns = table_columns(cur, "role")
                type_expr = column_expr("a", columns, "type", default="NULL")
                actor_expr = column_expr("a", columns, "actor_id", default="NULL")
                target_expr = column_expr("a", columns, "target_id", default="NULL")
                role_expr = column_expr("a", columns, "role_id", default="NULL")
                inherited_expr = column_expr("a", columns, "inherited", default="0")
                role_name_expr = column_expr("r", role_columns, "name", default="NULL")
                sql = (
                    "SELECT "
                    f"{type_expr} AS assignment_type, {actor_expr} AS actor_id, {target_expr} AS target_id, "
                    f"{role_expr} AS role_id, {inherited_expr} AS inherited, {role_name_expr} AS role_name "
                    "FROM assignment a "
                )
                if role_columns:
                    sql += "LEFT JOIN role r ON r.id = a.role_id "
                sql += "ORDER BY target_id ASC, actor_id ASC"
                cur.execute(sql)
                assignments = []
                for row in cur.fetchall():
                    assignments.append({
                        'user_id': row.get("actor_id") or "N/A",
                        'project_id': row.get("target_id") or "N/A",
                        'role_id': row.get("role_id") or "N/A",
                        'role_name': row.get("role_name") or "N/A",
                        'scope_type': [row.get("assignment_type") or "project"],
                        'inherited': bool_value(row.get("inherited")),
                        'data_source': 'mariadb',
                    })
                return assignments
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get role assignments: {e}")
        return [
            {'user_id': 'user-1', 'project_id': 'project-1', 'role_id': 'role-1', 
             'role_name': 'member', 'error': str(e)}
        ]


def get_keypair_list() -> List[Dict[str, Any]]:
    """
    Get list of SSH keypairs for the current project.
    
    Returns:
        List of keypair dictionaries
    """
    try:
        from .compute import _column_expr, _get_nova_mariadb_connection, _table_columns

        conn = _get_nova_mariadb_connection()
        try:
            with conn.cursor() as cur:
                columns = _table_columns(cur, "key_pairs")
                if not columns:
                    raise RuntimeError("MariaDB table 'key_pairs' is not available")

                deleted_expr = _column_expr("kp", columns, "deleted", default="0")
                type_expr = _column_expr("kp", columns, "type", default="'ssh'")
                public_key_expr = _column_expr("kp", columns, "public_key", default="NULL")
                fingerprint_expr = _column_expr("kp", columns, "fingerprint", default="NULL")
                user_expr = _column_expr("kp", columns, "user_id", default="NULL")
                cur.execute(
                    "SELECT kp.name, "
                    f"{fingerprint_expr} AS fingerprint, {public_key_expr} AS public_key, "
                    f"{type_expr} AS type, {user_expr} AS user_id "
                    "FROM key_pairs kp "
                    f"WHERE ({deleted_expr} = 0 OR {deleted_expr} = '0') "
                    "ORDER BY kp.name ASC"
                )
                keypairs = []
                for row in cur.fetchall():
                    public_key = row.get("public_key")
                    keypairs.append({
                        "name": row.get("name") or "unnamed",
                        "fingerprint": row.get("fingerprint") or "N/A",
                        "public_key": public_key[:100] + "..." if public_key else "N/A",
                        "type": row.get("type") or "ssh",
                        "user_id": row.get("user_id") or "N/A",
                        "data_source": "mariadb",
                    })
                return keypairs
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get keypair list: {e}")
        return [
            {'name': 'demo-key', 'fingerprint': 'xx:xx:xx:...', 'type': 'ssh', 'error': str(e)}
        ]


def set_keypair(keypair_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage SSH keypairs (create, delete, list).
    
    Args:
        keypair_name: Name of the keypair
        action: Action to perform (create, delete, list, show)
        **kwargs: Additional parameters (public_key for create, type)
    
    Returns:
        Result of the keypair operation
    """
    try:
        if action.lower() == 'list':
            keypairs = get_keypair_list()
            return {
                'success': True,
                'keypairs': keypairs,
                'count': len(keypairs)
            }
        
        elif action.lower() == 'create':
            from ..connection import get_openstack_connection
            conn = get_openstack_connection()
            public_key = kwargs.get('public_key')
            keypair_type = kwargs.get('type', 'ssh')
            
            create_params = {
                'name': keypair_name,
                'type': keypair_type
            }
            
            if public_key:
                create_params['public_key'] = public_key
            
            keypair = conn.compute.create_keypair(**create_params)
            
            return {
                'success': True,
                'message': f'Keypair "{keypair_name}" created successfully',
                'keypair': {
                    'name': keypair.name,
                    'fingerprint': getattr(keypair, 'fingerprint', 'N/A'),
                    'private_key': getattr(keypair, 'private_key', None),  # Only available on creation
                    'type': getattr(keypair, 'type', 'ssh')
                }
            }
            
        elif action.lower() == 'delete':
            try:
                from ..connection import get_openstack_connection
                conn = get_openstack_connection()
                conn.compute.delete_keypair(keypair_name)
                return {
                    'success': True,
                    'message': f'Keypair "{keypair_name}" deleted successfully'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to delete keypair "{keypair_name}": {str(e)}'
                }
        
        elif action.lower() == 'show':
            try:
                keypairs = [kp for kp in get_keypair_list() if kp.get("name") == keypair_name]
                if not keypairs:
                    raise RuntimeError(f'Keypair "{keypair_name}" not found')
                return {
                    'success': True,
                    'keypair': keypairs[0]
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Keypair "{keypair_name}" not found: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete, list, show'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage keypair: {e}")
        return {
            'success': False,
            'message': f'Failed to manage keypair: {str(e)}',
            'error': str(e)
        }


def get_project_details(project_name: str = "") -> Dict[str, Any]:
    """
    Get detailed information about the current project scope.
    
    Args:
        project_name: Name of specific project (if provided, must match current project)
    
    Returns:
        Dict containing current project details only
    """
    try:
        projects = get_project_list(name_filter=project_name)
        if not projects.get("success"):
            return projects
        return {
            'success': True,
            'total_projects': projects.get("count", 0),
            'projects': projects.get("projects", []),
            'message': 'Retrieved project details from Keystone MariaDB',
            'scope': 'mariadb',
        }
    except Exception as e:
        logger.error(f"Failed to get project details: {e}")
        return {
            'success': False,
            'message': f'Failed to get project details: {str(e)}',
            'error': str(e)
        }


def get_project_list(name_filter: str = "", enabled_only: bool = False) -> Dict[str, Any]:
    """
    Get list of OpenStack projects visible to the current credentials.

    Args:
        name_filter: Optional project name substring filter (case-insensitive)
        enabled_only: If True, include enabled projects only

    Returns:
        Dict containing project list summary
    """
    try:
        conn = _get_keystone_mariadb_connection()
        try:
            with conn.cursor() as cur:
                columns = table_columns(cur, "project")
                if not columns:
                    raise RuntimeError("MariaDB table 'project' is not available")
                enabled_expr = column_expr("p", columns, "enabled", default="1")
                desc_expr = column_expr("p", columns, "description", default="''")
                domain_expr = column_expr("p", columns, "domain_id", default="NULL")
                parent_expr = column_expr("p", columns, "parent_id", default="NULL")
                is_domain_expr = column_expr("p", columns, "is_domain", default="0")
                extra_expr = column_expr("p", columns, "extra", default="NULL")
                created_expr = column_expr("p", columns, "created_at", default="NULL")
                updated_expr = column_expr("p", columns, "updated_at", default="NULL")
                sql = (
                    "SELECT p.id, p.name, "
                    f"{desc_expr} AS description, {domain_expr} AS domain_id, {enabled_expr} AS enabled, "
                    f"{parent_expr} AS parent_id, {is_domain_expr} AS is_domain, {extra_expr} AS extra, "
                    f"{created_expr} AS created_at, {updated_expr} AS updated_at "
                    "FROM project p WHERE 1=1 "
                )
                params: List[Any] = []
                if name_filter.strip():
                    sql += "AND LOWER(p.name) LIKE %s "
                    params.append(f"%{name_filter.strip().lower()}%")
                if enabled_only:
                    sql += f"AND {enabled_expr} = 1 "
                sql += "ORDER BY p.name ASC"
                cur.execute(sql, params)
                projects = []
                for row in cur.fetchall():
                    extra = json_value(row.get("extra"), {}) or {}
                    projects.append({
                        "id": row.get("id"),
                        "name": row.get("name") or "unnamed",
                        "description": row.get("description") or extra.get("description", ""),
                        "domain_id": row.get("domain_id"),
                        "enabled": bool_value(row.get("enabled")),
                        "parent_id": row.get("parent_id"),
                        "is_domain": bool_value(row.get("is_domain")),
                        "tags": extra.get("tags", []),
                        "created_at": str_time(row.get("created_at")),
                        "updated_at": str_time(row.get("updated_at")),
                        "data_source": "mariadb",
                    })
                return {
                    "success": True,
                    "count": len(projects),
                    "filter": {"name_filter": name_filter, "enabled_only": enabled_only},
                    "projects": projects,
                }
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get project list: {e}")
        return {
            "success": False,
            "message": f"Failed to get project list: {str(e)}",
            "error": str(e),
            "projects": [],
            "count": 0,
        }


def _get_single_project_details(conn, project) -> Dict[str, Any]:
    """
    Helper function to get detailed information for a single project.
    
    Args:
        conn: OpenStack connection
        project: Project object
    
    Returns:
        Dict containing single project details
    """
    try:
        # Get project users and roles
        users = []
        try:
            for assignment in conn.identity.role_assignments():
                scope = getattr(assignment, 'scope', {})
                if 'project' in scope and scope['project'].get('id') == project.id:
                    user_info = getattr(assignment, 'user', {})
                    role_info = getattr(assignment, 'role', {})
                    users.append({
                        'user_id': user_info.get('id', 'N/A'),
                        'user_name': user_info.get('name', 'N/A'),
                        'role_id': role_info.get('id', 'N/A'),
                        'role_name': role_info.get('name', 'N/A')
                    })
        except Exception as user_e:
            logger.warning(f"Could not retrieve project users: {user_e}")
            users = []
        
        # Get project resource usage (NEW - ENHANCED)
        resources = {
            'compute': {'instances': 0, 'vcpus_used': 0, 'ram_mb_used': 0},
            'volume': {'volumes': 0, 'total_size_gb': 0, 'snapshots': 0, 'backups': 0},
            'network': {'networks': 0, 'floating_ips': 0, 'ports': 0, 'routers': 0},
            'image': {'images': 0}
        }
        
        try:
            # Get all resources and filter by project
            all_instances = list(conn.compute.servers())
            all_volumes = list(conn.volume.volumes())
            all_floating_ips = list(conn.network.ips())
            all_networks = list(conn.network.networks()) 
            all_ports = list(conn.network.ports())
            all_routers = list(conn.network.routers())
            
            # Filter by project ID
            project_instances = [inst for inst in all_instances if getattr(inst, 'project_id', None) == project.id]
            project_volumes = [vol for vol in all_volumes if getattr(vol, 'project_id', None) == project.id]
            project_floating_ips = [fip for fip in all_floating_ips if getattr(fip, 'project_id', None) == project.id]
            project_networks = [net for net in all_networks if getattr(net, 'project_id', None) == project.id]
            project_ports = [port for port in all_ports if getattr(port, 'project_id', None) == project.id]
            project_routers = [router for router in all_routers if getattr(router, 'project_id', None) == project.id]
            
            # Calculate compute resources
            resources['compute']['instances'] = len(project_instances)
            for instance in project_instances:
                try:
                    # Get flavor info directly from instance (already included in server detail)
                    if hasattr(instance, 'flavor'):
                        if isinstance(instance.flavor, dict):
                            resources['compute']['vcpus_used'] += instance.flavor.get('vcpus', 0)
                            resources['compute']['ram_mb_used'] += instance.flavor.get('ram', 0)
                        else:
                            # If flavor is an object, try to get attributes
                            resources['compute']['vcpus_used'] += getattr(instance.flavor, 'vcpus', 0)
                            resources['compute']['ram_mb_used'] += getattr(instance.flavor, 'ram', 0)
                except Exception as flavor_e:
                    logger.warning(f"Could not get flavor info for instance {getattr(instance, 'id', 'unknown')}: {flavor_e}")
                    continue
            
            # Calculate volume resources
            resources['volume']['volumes'] = len(project_volumes)
            resources['volume']['total_size_gb'] = sum(getattr(vol, 'size', 0) for vol in project_volumes)
            
            # Try to get snapshots (may need special handling)
            try:
                all_snapshots = list(conn.volume.snapshots())
                project_snapshots = [snap for snap in all_snapshots if getattr(snap, 'project_id', None) == project.id]
                resources['volume']['snapshots'] = len(project_snapshots)
            except Exception:
                resources['volume']['snapshots'] = 0
            
            # Network resources
            resources['network']['networks'] = len(project_networks)
            resources['network']['floating_ips'] = len(project_floating_ips)
            resources['network']['ports'] = len(project_ports)
            resources['network']['routers'] = len(project_routers)
            
        except Exception as e:
            logger.warning(f"Could not retrieve project resources: {e}")
        
        return {
            'id': project.id,
            'name': project.name,
            'description': getattr(project, 'description', 'N/A'),
            'domain_id': getattr(project, 'domain_id', 'N/A'),
            'enabled': project.is_enabled,
            'is_domain': getattr(project, 'is_domain', False),
            'parent_id': getattr(project, 'parent_id', None),
            'created_at': str(getattr(project, 'created_at', 'N/A')),
            'updated_at': str(getattr(project, 'updated_at', 'N/A')),
            'users': users,
            'user_count': len(users),
            'resources': resources
        }
        
    except Exception as e:
        logger.error(f"Failed to get single project details: {e}")
        return {
            'id': getattr(project, 'id', 'unknown'),
            'name': getattr(project, 'name', 'unknown'),
            'error': str(e)
        }


def set_project(project_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack projects (create, delete, update, show).
    
    Args:
        project_name: Name of the project
        action: Action to perform (create, delete, update, show, list)
        **kwargs: Additional parameters
    
    Returns:
        Result of the project operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            projects = []
            try:
                for project in conn.identity.projects():
                    projects.append({
                        'id': project.id,
                        'name': project.name,
                        'description': getattr(project, 'description', 'N/A'),
                        'domain_id': getattr(project, 'domain_id', 'N/A'),
                        'enabled': project.is_enabled,
                        'is_domain': getattr(project, 'is_domain', False),
                        'parent_id': getattr(project, 'parent_id', None)
                    })
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to list projects: {str(e)}',
                    'projects': []
                }
            return {
                'success': True,
                'projects': projects,
                'count': len(projects)
            }
            
        elif action.lower() == 'create':
            description = kwargs.get('description', f'Project {project_name}')
            domain_id = kwargs.get('domain_id', 'default')
            enabled = kwargs.get('enabled', True)
            
            try:
                project = conn.identity.create_project(
                    name=project_name,
                    description=description,
                    domain_id=domain_id,
                    is_enabled=enabled
                )
                return {
                    'success': True,
                    'message': f'Project "{project_name}" created successfully',
                    'project': {
                        'id': project.id,
                        'name': project.name,
                        'description': getattr(project, 'description', 'N/A'),
                        'enabled': project.is_enabled
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to create project "{project_name}": {str(e)}'
                }
                
        elif action.lower() == 'delete':
            # Find the project
            project = None
            for proj in conn.identity.projects():
                if proj.name == project_name or proj.id == project_name:
                    project = proj
                    break
                    
            if not project:
                return {
                    'success': False,
                    'message': f'Project "{project_name}" not found'
                }
                
            try:
                conn.identity.delete_project(project)
                return {
                    'success': True,
                    'message': f'Project "{project_name}" deleted successfully'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to delete project "{project_name}": {str(e)}'
                }
                
        elif action.lower() == 'update':
            # Find the project
            project = None
            for proj in conn.identity.projects():
                if proj.name == project_name or proj.id == project_name:
                    project = proj
                    break
                    
            if not project:
                return {
                    'success': False,
                    'message': f'Project "{project_name}" not found'
                }
                
            update_params = {}
            if 'description' in kwargs:
                update_params['description'] = kwargs['description']
            if 'enabled' in kwargs:
                update_params['is_enabled'] = kwargs['enabled']
                
            try:
                updated_project = conn.identity.update_project(project, **update_params)
                return {
                    'success': True,
                    'message': f'Project "{project_name}" updated successfully',
                    'project': {
                        'id': updated_project.id,
                        'name': updated_project.name,
                        'description': getattr(updated_project, 'description', 'N/A'),
                        'enabled': updated_project.is_enabled
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to update project "{project_name}": {str(e)}'
                }
                
        elif action.lower() == 'show':
            # Find the project
            project = None
            for proj in conn.identity.projects():
                if proj.name == project_name or proj.id == project_name:
                    project = proj
                    break
                    
            if not project:
                return {
                    'success': False,
                    'message': f'Project "{project_name}" not found'
                }
                
            return {
                'success': True,
                'project': {
                    'id': project.id,
                    'name': project.name,
                    'description': getattr(project, 'description', 'N/A'),
                    'domain_id': getattr(project, 'domain_id', 'N/A'),
                    'enabled': project.is_enabled,
                    'is_domain': getattr(project, 'is_domain', False),
                    'parent_id': getattr(project, 'parent_id', None),
                    'created_at': str(getattr(project, 'created_at', 'N/A')),
                    'updated_at': str(getattr(project, 'updated_at', 'N/A'))
                }
            }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete, update, show, list'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage project: {e}")
        return {
            'success': False,
            'message': f'Failed to manage project: {str(e)}',
            'error': str(e)
        }
