"""Read-only Barbican key manager service queries."""

import logging
from typing import Any, Dict, Iterable, List

from ..connection import get_openstack_connection

logger = logging.getLogger(__name__)


def _resource_to_dict(resource: Any) -> Dict[str, Any]:
    if resource is None:
        return {}
    if isinstance(resource, dict):
        return dict(resource)
    if hasattr(resource, "to_dict"):
        try:
            return resource.to_dict(computed=False)
        except TypeError:
            return resource.to_dict()
    data: Dict[str, Any] = {}
    for key in dir(resource):
        if key.startswith("_"):
            continue
        try:
            value = getattr(resource, key)
        except Exception:
            continue
        if callable(value):
            continue
        if isinstance(value, (str, int, float, bool, list, tuple, dict, type(None))):
            data[key] = value
    return data


def _first_value(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_ref_id(data: Dict[str, Any], resource_type: str) -> str:
    ref_key = f"{resource_type}_ref"
    ref = data.get(ref_key) or data.get("ref") or data.get("href")
    if data.get("id"):
        return str(data.get("id"))
    if ref:
        return str(ref).rstrip("/").split("/")[-1]
    return ""


def _serialize_secret(secret: Any, detailed: bool = False) -> Dict[str, Any]:
    data = _resource_to_dict(secret)
    result = {
        "id": _normalize_ref_id(data, "secret"),
        "name": data.get("name") or "",
        "secret_ref": data.get("secret_ref") or data.get("ref"),
        "secret_type": data.get("secret_type"),
        "content_types": data.get("content_types") or {},
        "algorithm": data.get("algorithm"),
        "bit_length": data.get("bit_length"),
        "mode": data.get("mode"),
        "status": data.get("status"),
        "created_at": _first_value(data, "created", "created_at"),
        "updated_at": _first_value(data, "updated", "updated_at"),
        "expiration": data.get("expiration"),
        "creator_id": data.get("creator_id"),
        "project_id": _first_value(data, "project_id", "tenant_id"),
        "payload_omitted": True,
        "data_source": "openstacksdk",
    }
    if detailed:
        result["metadata"] = {
            key: value for key, value in data.items()
            if key not in result and key not in {"payload", "payload_content_type", "payload_content_encoding"}
        }
    return result


def _serialize_container(container: Any, detailed: bool = False) -> Dict[str, Any]:
    data = _resource_to_dict(container)
    result = {
        "id": _normalize_ref_id(data, "container"),
        "name": data.get("name") or "",
        "container_ref": data.get("container_ref") or data.get("ref"),
        "type": data.get("type"),
        "status": data.get("status"),
        "created_at": _first_value(data, "created", "created_at"),
        "updated_at": _first_value(data, "updated", "updated_at"),
        "creator_id": data.get("creator_id"),
        "project_id": _first_value(data, "project_id", "tenant_id"),
        "secret_refs": data.get("secret_refs") or [],
        "payload_omitted": True,
        "data_source": "openstacksdk",
    }
    if detailed:
        result["metadata"] = {key: value for key, value in data.items() if key not in result}
    return result


def _serialize_order(order: Any, detailed: bool = False) -> Dict[str, Any]:
    data = _resource_to_dict(order)
    result = {
        "id": _normalize_ref_id(data, "order"),
        "name": data.get("name") or "",
        "order_ref": data.get("order_ref") or data.get("ref"),
        "type": data.get("type"),
        "status": data.get("status"),
        "created_at": _first_value(data, "created", "created_at"),
        "updated_at": _first_value(data, "updated", "updated_at"),
        "secret_ref": data.get("secret_ref"),
        "container_ref": data.get("container_ref"),
        "creator_id": data.get("creator_id"),
        "project_id": _first_value(data, "project_id", "tenant_id"),
        "data_source": "openstacksdk",
    }
    if detailed:
        result["metadata"] = {key: value for key, value in data.items() if key not in result}
    return result


def _page(items: List[Dict[str, Any]], limit: int, offset: int) -> List[Dict[str, Any]]:
    safe_offset = max(int(offset or 0), 0)
    safe_limit = max(0, min(int(limit or 0), 200))
    return items[safe_offset:safe_offset + safe_limit] if safe_limit else items[safe_offset:]


def _matches(value: Any, target: str) -> bool:
    return str(value or "").strip().lower() == target.strip().lower()


def _collect(resources: Iterable[Any], serializer, detailed: bool = False) -> List[Dict[str, Any]]:
    return [serializer(resource, detailed=detailed) for resource in resources]


def _key_manager():
    conn = get_openstack_connection()
    manager = getattr(conn, "key_manager", None)
    if manager is None:
        raise RuntimeError("OpenStack key_manager/Barbican proxy is not available")
    return manager


def get_barbican_secrets(
    name: str = "",
    secret_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List Barbican secrets without returning secret payloads."""
    try:
        query = {key: value for key, value in {"name": name, "secret_type": secret_type}.items() if value}
        secrets = _collect(_key_manager().secrets(**query), _serialize_secret)
        if status:
            secrets = [secret for secret in secrets if _matches(secret.get("status"), status)]
        if project_id:
            secrets = [secret for secret in secrets if _matches(secret.get("project_id"), project_id)]
        total = len(secrets)
        page = _page(secrets, limit, offset)
        return {"success": True, "secrets": page, "count": len(page), "total_count": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error("Failed to list Barbican secrets: %s", e)
        return {"success": False, "message": str(e), "secrets": [], "count": 0, "total_count": 0}


def get_barbican_secret_details(secret_id_or_ref: str) -> Dict[str, Any]:
    """Get Barbican secret metadata without returning the payload."""
    try:
        query = (secret_id_or_ref or "").strip()
        if not query:
            return {"success": False, "message": "secret_id_or_ref is required", "secret": None, "found": False}
        secret = _key_manager().get_secret(query)
        return {"success": True, "secret": _serialize_secret(secret, detailed=True) if secret else None, "found": bool(secret)}
    except Exception as e:
        logger.error("Failed to get Barbican secret details: %s", e)
        return {"success": False, "message": str(e), "secret": None, "found": False}


def get_barbican_containers(
    name: str = "",
    container_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List Barbican secret containers without returning secret payloads."""
    try:
        query = {key: value for key, value in {"name": name, "type": container_type}.items() if value}
        containers = _collect(_key_manager().containers(**query), _serialize_container)
        if status:
            containers = [container for container in containers if _matches(container.get("status"), status)]
        if project_id:
            containers = [container for container in containers if _matches(container.get("project_id"), project_id)]
        total = len(containers)
        page = _page(containers, limit, offset)
        return {"success": True, "containers": page, "count": len(page), "total_count": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error("Failed to list Barbican containers: %s", e)
        return {"success": False, "message": str(e), "containers": [], "count": 0, "total_count": 0}


def get_barbican_container_details(container_id_or_ref: str) -> Dict[str, Any]:
    """Get Barbican container metadata without returning secret payloads."""
    try:
        query = (container_id_or_ref or "").strip()
        if not query:
            return {"success": False, "message": "container_id_or_ref is required", "container": None, "found": False}
        container = _key_manager().get_container(query)
        return {"success": True, "container": _serialize_container(container, detailed=True) if container else None, "found": bool(container)}
    except Exception as e:
        logger.error("Failed to get Barbican container details: %s", e)
        return {"success": False, "message": str(e), "container": None, "found": False}


def get_barbican_orders(
    order_type: str = "",
    status: str = "",
    project_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List Barbican orders."""
    try:
        query = {"type": order_type} if order_type else {}
        orders = _collect(_key_manager().orders(**query), _serialize_order)
        if status:
            orders = [order for order in orders if _matches(order.get("status"), status)]
        if project_id:
            orders = [order for order in orders if _matches(order.get("project_id"), project_id)]
        total = len(orders)
        page = _page(orders, limit, offset)
        return {"success": True, "orders": page, "count": len(page), "total_count": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error("Failed to list Barbican orders: %s", e)
        return {"success": False, "message": str(e), "orders": [], "count": 0, "total_count": 0}


def get_barbican_order_details(order_id_or_ref: str) -> Dict[str, Any]:
    """Get Barbican order details."""
    try:
        query = (order_id_or_ref or "").strip()
        if not query:
            return {"success": False, "message": "order_id_or_ref is required", "order": None, "found": False}
        order = _key_manager().get_order(query)
        return {"success": True, "order": _serialize_order(order, detailed=True) if order else None, "found": bool(order)}
    except Exception as e:
        logger.error("Failed to get Barbican order details: %s", e)
        return {"success": False, "message": str(e), "order": None, "found": False}
