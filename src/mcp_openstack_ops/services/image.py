"""
OpenStack Image (Glance) Service Functions

This module contains functions for managing images, image metadata, and image sharing.
"""

import json
import logging
from typing import Dict, List, Any
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

