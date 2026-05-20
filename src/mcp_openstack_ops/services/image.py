"""
OpenStack Image (Glance) Service Functions

This module contains functions for managing images, image metadata, and image sharing.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from .db import bool_value, column_expr, get_mariadb_connection, str_time, table_columns

# Configure logging
logger = logging.getLogger(__name__)
GLANCE_DATABASE = "glance"


def _get_glance_mariadb_connection():
    return get_mariadb_connection(GLANCE_DATABASE)


def get_image_list() -> List[Dict[str, Any]]:
    """
    Get list of images accessible by current project.
    
    Returns:
        List of image dictionaries for current project
    """
    result = get_image_list_filtered(limit=200, offset=0)
    return result.get("images", []) if result.get("success") else [{"error": result.get("message", "unknown error")}]


def get_image_detail_list() -> List[Dict[str, Any]]:
    """
    Get detailed list of images accessible by current project.
    
    Returns:
        List of detailed image information dictionaries for current project
    """
    result = get_image_list_filtered(limit=200, offset=0)
    return result.get("images", []) if result.get("success") else []


def _serialize_image_row(row: Dict[str, Any], properties: Dict[str, Any], tags: List[str]) -> Dict[str, Any]:
    return {
        'id': row.get('id', ''),
        'name': row.get('name') or '',
        'status': row.get('status') or 'unknown',
        'visibility': row.get('visibility') or 'private',
        'owner': row.get('owner'),
        'size': row.get('size') or 0,
        'disk_format': row.get('disk_format') or 'unknown',
        'container_format': row.get('container_format') or 'unknown',
        'min_disk': row.get('min_disk') or 0,
        'min_ram': row.get('min_ram') or 0,
        'created_at': str_time(row.get('created_at')),
        'updated_at': str_time(row.get('updated_at')),
        'protected': bool_value(row.get('protected')),
        'checksum': row.get('checksum'),
        'properties': properties,
        'tags': tags,
        'data_source': 'mariadb',
    }


def _base_filtered_images(
    project_id: str = "",
    status: str = "",
    visibility: str = "",
    owner: str = "",
    name_filter: str = "",
) -> List[Dict[str, Any]]:
    owner_filter = owner.strip() or project_id.strip()
    status_filter = status.strip().lower()
    visibility_filter = visibility.strip().lower()
    name_filter_norm = name_filter.strip().lower()

    conn = _get_glance_mariadb_connection()
    try:
        with conn.cursor() as cur:
            columns = table_columns(cur, "images")
            if not columns:
                raise RuntimeError("MariaDB table 'images' is not available")

            deleted_expr = column_expr("i", columns, "deleted", default="0")
            visibility_expr = column_expr("i", columns, "visibility", default="'private'")
            owner_expr = column_expr("i", columns, "owner", default="NULL")
            protected_expr = column_expr("i", columns, "protected", default="0")
            checksum_expr = column_expr("i", columns, "checksum", default="NULL")
            updated_expr = column_expr("i", columns, "updated_at", default="NULL")
            sql = (
                "SELECT i.id, i.name, i.status, "
                f"{visibility_expr} AS visibility, {owner_expr} AS owner, "
                "i.size, i.disk_format, i.container_format, i.min_disk, i.min_ram, "
                f"{protected_expr} AS protected, {checksum_expr} AS checksum, "
                f"i.created_at, {updated_expr} AS updated_at "
                "FROM images i WHERE 1=1 "
            )
            params: List[Any] = []
            if deleted_expr != "0":
                sql += f"AND ({deleted_expr} = 0 OR {deleted_expr} = '0') "
            if owner_filter:
                sql += f"AND {owner_expr} = %s "
                params.append(owner_filter)
            if status_filter:
                sql += "AND LOWER(i.status) = %s "
                params.append(status_filter)
            if visibility_filter:
                sql += f"AND LOWER({visibility_expr}) = %s "
                params.append(visibility_filter)
            if name_filter_norm:
                sql += "AND LOWER(i.name) LIKE %s "
                params.append(f"%{name_filter_norm}%")
            sql += "ORDER BY i.created_at DESC"
            cur.execute(sql, params)
            rows = cur.fetchall()

            image_ids = [row["id"] for row in rows if row.get("id")]
            properties_by_image: Dict[str, Dict[str, Any]] = {image_id: {} for image_id in image_ids}
            tags_by_image: Dict[str, List[str]] = {image_id: [] for image_id in image_ids}
            if image_ids:
                placeholders = ",".join(["%s"] * len(image_ids))
                prop_columns = table_columns(cur, "image_properties")
                if {"image_id", "name", "value"}.issubset(prop_columns):
                    prop_deleted_expr = column_expr("", prop_columns, "deleted", default="0")
                    cur.execute(
                        f"SELECT image_id, name, value FROM image_properties WHERE image_id IN ({placeholders}) "
                        f"AND ({prop_deleted_expr} = 0 OR {prop_deleted_expr} = '0')",
                        image_ids,
                    )
                    for prop in cur.fetchall():
                        properties_by_image.setdefault(prop["image_id"], {})[prop["name"]] = prop.get("value")
                tag_columns = table_columns(cur, "image_tags")
                if {"image_id", "value"}.issubset(tag_columns):
                    cur.execute(f"SELECT image_id, value FROM image_tags WHERE image_id IN ({placeholders})", image_ids)
                    for tag in cur.fetchall():
                        tags_by_image.setdefault(tag["image_id"], []).append(tag.get("value"))

            return [
                _serialize_image_row(row, properties_by_image.get(row.get("id"), {}), tags_by_image.get(row.get("id"), []))
                for row in rows
            ]
    finally:
        conn.close()


def get_image_list_filtered(
    project_id: str = "",
    status: str = "",
    visibility: str = "",
    owner: str = "",
    name_filter: str = "",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    try:
        images = _base_filtered_images(
            project_id=project_id,
            status=status,
            visibility=visibility,
            owner=owner,
            name_filter=name_filter,
        )
        total = len(images)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        return {
            'success': True,
            'images': images[offset:offset + limit],
            'count': len(images[offset:offset + limit]),
            'total_count': total,
            'limit': limit,
            'offset': offset,
        }
    except Exception as e:
        logger.error(f"Failed to get filtered image list: {e}")
        return {'success': False, 'message': str(e), 'images': [], 'count': 0, 'total_count': 0}


def get_image_by_id_or_name(
    image_id_or_name: str,
    project_id: str = "",
) -> Dict[str, Any]:
    try:
        query = image_id_or_name.strip()
        images = _base_filtered_images(
            project_id=project_id,
        )
        matched = [i for i in images if str(i.get('id', '')) == query or str(i.get('name', '')) == query]
        return {'success': True, 'image': matched[0] if matched else None, 'found': len(matched) > 0}
    except Exception as e:
        logger.error(f"Failed to get image by id or name: {e}")
        return {'success': False, 'message': str(e), 'image': None, 'found': False}


def search_images(
    search_term: str,
    search_in: str = "all",
    limit: int = 50,
    offset: int = 0,
    case_sensitive: bool = False,
) -> Dict[str, Any]:
    try:
        term = search_term if case_sensitive else search_term.lower()
        fields = [f.strip() for f in search_in.split(',') if f.strip()] if search_in else ['all']
        images = _base_filtered_images()
        matched: List[Dict[str, Any]] = []

        def _contains(value: Any) -> bool:
            text = str(value if value is not None else "")
            if not case_sensitive:
                text = text.lower()
            return term in text

        for image in images:
            scan_fields = fields if 'all' not in fields else [
                'name', 'id', 'owner', 'visibility', 'disk_format', 'container_format', 'properties'
            ]
            found = False
            for field in scan_fields:
                if field == 'properties':
                    if _contains(json.dumps(image.get('properties', {}), ensure_ascii=False)):
                        found = True
                        break
                elif _contains(image.get(field)):
                    found = True
                    break
            if found:
                matched.append(image)

        total = len(matched)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        paged = matched[offset:offset + limit]
        return {
            'success': True,
            'images': paged,
            'count': len(paged),
            'total_count': total,
            'limit': limit,
            'offset': offset,
            'search_term': search_term,
            'search_in': fields,
        }
    except Exception as e:
        logger.error(f"Failed to search images: {e}")
        return {'success': False, 'message': str(e), 'images': [], 'count': 0, 'total_count': 0}


def set_image(image_name: str, action: str, **kwargs) -> Dict[str, Any]:
    """
    Manage images (create, delete, update, list).
    
    Args:
        image_name: Name or ID of the image (not required for 'list' action)
        action: Action to perform (create, delete, update, list)
        **kwargs: Additional parameters
    
    Returns:
        Result of the image operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        if action.lower() == 'list':
            images = []
            for image in conn.image.images():
                images.append({
                    'id': image.id,
                    'name': image.name,
                    'status': image.status,
                    'visibility': image.visibility,
                    'size': getattr(image, 'size', 0),
                    'disk_format': getattr(image, 'disk_format', 'unknown'),
                    'container_format': getattr(image, 'container_format', 'unknown'),
                    'min_disk': getattr(image, 'min_disk', 0),
                    'min_ram': getattr(image, 'min_ram', 0),
                    'owner': getattr(image, 'owner', 'unknown'),
                    'created_at': str(getattr(image, 'created_at', 'unknown')),
                    'updated_at': str(getattr(image, 'updated_at', 'unknown')),
                    'protected': getattr(image, 'is_protected', False),
                    'checksum': getattr(image, 'checksum', None),
                    'properties': getattr(image, 'properties', {})
                })
            return {
                'success': True,
                'images': images,
                'count': len(images)
            }
        
        elif action.lower() == 'create':
            container_format = kwargs.get('container_format', 'bare')
            disk_format = kwargs.get('disk_format', 'qcow2')
            
            image = conn.image.create_image(
                name=image_name,
                container_format=container_format,
                disk_format=disk_format,
                visibility=kwargs.get('visibility', 'private'),
                min_disk=kwargs.get('min_disk', 0),
                min_ram=kwargs.get('min_ram', 0),
                properties=kwargs.get('properties', {})
            )
            return {
                'success': True,
                'message': f'Image "{image_name}" created successfully',
                'image': {
                    'id': image.id,
                    'name': image.name,
                    'status': image.status,
                    'visibility': image.visibility
                }
            }
            
        elif action.lower() == 'delete':
            # Find the image using secure project-scoped lookup
            from ..connection import find_resource_by_name_or_id, get_openstack_connection
            conn = get_openstack_connection()
            
            image = find_resource_by_name_or_id(
                conn.image.images(), 
                image_name, 
                "Image"
            )
                    
            if not image:
                return {
                    'success': False,
                    'message': f'Image "{image_name}" not found or not accessible in current project'
                }
                
            conn.image.delete_image(image)
            return {
                'success': True,
                'message': f'Image "{image_name}" deleted successfully',
                'image_id': image.id
            }
            
        elif action.lower() == 'update':
            # Find the image
            image = None
            for img in conn.image.images():
                if img.name == image_name or img.id == image_name:
                    image = img
                    break
                    
            if not image:
                return {
                    'success': False,
                    'message': f'Image "{image_name}" not found'
                }
                
            update_params = {}
            if 'visibility' in kwargs:
                update_params['visibility'] = kwargs['visibility']
            if 'properties' in kwargs:
                update_params.update(kwargs['properties'])
                
            updated_image = conn.image.update_image(image, **update_params)
            return {
                'success': True,
                'message': f'Image "{image_name}" updated successfully',
                'image': {
                    'id': updated_image.id,
                    'name': updated_image.name,
                    'visibility': updated_image.visibility
                }
            }
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: create, delete, update, list'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage image: {e}")
        return {
            'success': False,
            'message': f'Failed to manage image: {str(e)}',
            'error': str(e)
        }


def set_image_members(action: str, image_name: str, member_project: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack image members (sharing images between projects)
    
    Args:
        action: Action to perform (list, add, remove, show)
        image_name: Name or ID of the image
        member_project: Project ID to add/remove as member
        **kwargs: Additional parameters
    
    Returns:
        Result of the image member management operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the image
        image = None
        for img in conn.image.images():
            if img.name == image_name or img.id == image_name:
                image = img
                break
                
        if not image:
            return {
                'success': False,
                'message': f'Image "{image_name}" not found'
            }
        
        if action.lower() == 'list':
            members = []
            try:
                for member in conn.image.members(image.id):
                    members.append({
                        'member_id': member.member_id,
                        'image_id': member.image_id,
                        'status': member.status,
                        'created_at': str(getattr(member, 'created_at', 'N/A')),
                        'updated_at': str(getattr(member, 'updated_at', 'N/A'))
                    })
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to list image members: {str(e)}',
                    'members': []
                }
            return {
                'success': True,
                'image_id': image.id,
                'image_name': image.name,
                'members': members,
                'count': len(members)
            }
            
        elif action.lower() == 'add':
            if not member_project:
                return {
                    'success': False,
                    'message': 'member_project is required for add action'
                }
                
            try:
                member = conn.image.add_member(image.id, member_project)
                return {
                    'success': True,
                    'message': f'Project "{member_project}" added as member to image "{image_name}"',
                    'image_id': image.id,
                    'member_id': member_project,
                    'status': member.status
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to add image member: {str(e)}'
                }
                
        elif action.lower() == 'remove':
            if not member_project:
                return {
                    'success': False,
                    'message': 'member_project is required for remove action'
                }
                
            try:
                conn.image.remove_member(image.id, member_project)
                return {
                    'success': True,
                    'message': f'Project "{member_project}" removed as member from image "{image_name}"',
                    'image_id': image.id,
                    'member_id': member_project
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to remove image member: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: list, add, remove'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage image members: {e}")
        return {
            'success': False,
            'message': f'Failed to manage image members: {str(e)}',
            'error': str(e)
        }


def set_image_metadata(action: str, image_name: str, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack image metadata and properties
    
    Args:
        action: Action to perform (show, set, unset)
        image_name: Name or ID of the image
        **kwargs: Additional parameters (properties dict for set, property_keys list for unset)
    
    Returns:
        Result of the image metadata management operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the image
        image = None
        for img in conn.image.images():
            if img.name == image_name or img.id == image_name:
                image = img
                break
                
        if not image:
            return {
                'success': False,
                'message': f'Image "{image_name}" not found'
            }
        
        if action.lower() == 'show':
            try:
                # Get detailed image information including metadata
                detailed_image = conn.image.get_image(image.id)
                return {
                    'success': True,
                    'image_id': image.id,
                    'image_name': image.name,
                    'metadata': {
                        'properties': getattr(detailed_image, 'properties', {}),
                        'tags': getattr(detailed_image, 'tags', []),
                        'visibility': detailed_image.visibility,
                        'protected': detailed_image.is_protected,
                        'disk_format': detailed_image.disk_format,
                        'container_format': detailed_image.container_format,
                        'min_disk': getattr(detailed_image, 'min_disk', 0),
                        'min_ram': getattr(detailed_image, 'min_ram', 0),
                        'size': getattr(detailed_image, 'size', None),
                        'checksum': getattr(detailed_image, 'checksum', None),
                        'created_at': str(getattr(detailed_image, 'created_at', 'N/A')),
                        'updated_at': str(getattr(detailed_image, 'updated_at', 'N/A')),
                        'owner': getattr(detailed_image, 'owner', None),
                        'status': detailed_image.status
                    }
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to show image metadata: {str(e)}'
                }
                
        elif action.lower() == 'set':
            properties = kwargs.get('properties', {})
            if not properties:
                return {
                    'success': False,
                    'message': 'properties parameter is required for set action'
                }
                
            try:
                # Update image properties
                updated_image = conn.image.update_image(image.id, **properties)
                return {
                    'success': True,
                    'message': f'Image "{image_name}" metadata updated',
                    'image_id': image.id,
                    'updated_properties': properties
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to set image metadata: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: show, set'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage image metadata: {e}")
        return {
            'success': False,
            'message': f'Failed to manage image metadata: {str(e)}',
            'error': str(e)
        }


def set_image_visibility(action: str, image_name: str, **kwargs) -> Dict[str, Any]:
    """
    Manage OpenStack image visibility settings
    
    Args:
        action: Action to perform (show, set)
        image_name: Name or ID of the image
        **kwargs: Additional parameters (visibility for set action)
    
    Returns:
        Result of the image visibility management operation
    """
    try:
        # Import here to avoid circular imports
        from ..connection import get_openstack_connection
        conn = get_openstack_connection()
        
        # Find the image
        image = None
        for img in conn.image.images():
            if img.name == image_name or img.id == image_name:
                image = img
                break
                
        if not image:
            return {
                'success': False,
                'message': f'Image "{image_name}" not found'
            }
        
        if action.lower() == 'show':
            return {
                'success': True,
                'image_id': image.id,
                'image_name': image.name,
                'visibility': image.visibility,
                'is_protected': image.is_protected,
                'owner': getattr(image, 'owner', None)
            }
            
        elif action.lower() == 'set':
            visibility = kwargs.get('visibility')
            if not visibility:
                return {
                    'success': False,
                    'message': 'visibility parameter is required for set action'
                }
                
            # Validate visibility value
            valid_visibilities = ['public', 'private', 'shared', 'community']
            if visibility not in valid_visibilities:
                return {
                    'success': False,
                    'message': f'Invalid visibility "{visibility}". Valid values: {valid_visibilities}'
                }
                
            try:
                conn.image.update_image(image.id, visibility=visibility)
                return {
                    'success': True,
                    'message': f'Image "{image_name}" visibility set to "{visibility}"',
                    'image_id': image.id,
                    'old_visibility': image.visibility,
                    'new_visibility': visibility
                }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Failed to set image visibility: {str(e)}'
                }
        
        else:
            return {
                'success': False,
                'message': f'Unknown action "{action}". Supported: show, set'
            }
            
    except Exception as e:
        logger.error(f"Failed to manage image visibility: {e}")
        return {
            'success': False,
            'message': f'Failed to manage image visibility: {str(e)}',
            'error': str(e)
        }
