"""Read-only RabbitMQ monitoring helpers using the HTTP Management API."""

import base64
import json
import logging
import os
import ssl
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def _parse_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _api_base() -> str:
    return os.getenv("RABBITMQ_API_URL", "http://127.0.0.1:15672/api").rstrip("/")


def _timeout() -> int:
    return int(os.getenv("RABBITMQ_API_TIMEOUT", "10"))


def _request(path: str, query: Dict[str, Any] | None = None) -> Any:
    url = f"{_api_base()}/{path.lstrip('/')}"
    if query:
        filtered_query = {key: value for key, value in query.items() if value not in (None, "")}
        if filtered_query:
            url = f"{url}?{urlencode(filtered_query)}"

    user = os.getenv("RABBITMQ_API_USER", "guest")
    password = os.getenv("RABBITMQ_API_PASSWORD", "guest")
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    context = None
    if url.startswith("https://") and not _parse_bool(os.getenv("RABBITMQ_API_VERIFY_TLS", "true")):
        context = ssl._create_unverified_context()

    headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
    try:
        return _open_json(url, headers, context)
    except HTTPError as e:
        if e.code == 406:
            headers["Accept"] = "*/*"
            return _open_json(url, headers, context)
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"RabbitMQ API HTTP {e.code}: {detail}") from e
    except URLError as e:
        raise RuntimeError(f"RabbitMQ API connection failed: {e.reason}") from e


def _open_json(url: str, headers: Dict[str, str], context) -> Any:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=_timeout(), context=context) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else None


def _ok(data: Dict[str, Any] | List[Any] | Any, key: str = "data") -> Dict[str, Any]:
    return {"success": True, key: data, "data_source": "rabbitmq_http_api"}


def _fail(error: Exception, key: str = "data") -> Dict[str, Any]:
    logger.error("RabbitMQ API query failed: %s", error)
    return {"success": False, key: [] if key.endswith("s") else {}, "error": str(error), "data_source": "rabbitmq_http_api"}


def rabbitmq_cluster_overview() -> Dict[str, Any]:
    try:
        return _ok(_request("overview"), "overview")
    except Exception as e:
        return _fail(e, "overview")


DEFAULT_NODE_FIELDS = [
    "name",
    "type",
    "running",
    "mem_used",
    "mem_limit",
    "mem_alarm",
    "disk_free",
    "disk_free_limit",
    "disk_free_alarm",
    "fd_used",
    "fd_total",
    "sockets_used",
    "sockets_total",
    "proc_used",
    "proc_total",
    "partitions",
]


def _project_items(items: List[Dict[str, Any]], fields: str, default_fields: List[str]) -> List[Dict[str, Any]]:
    if fields.strip().lower() == "all":
        return items
    requested = [field.strip() for field in fields.split(",") if field.strip()] if fields else default_fields
    return [{field: item.get(field) for field in requested if field in item} for item in items]


def rabbitmq_cluster_nodes(fields: str = "", limit: int = 100) -> Dict[str, Any]:
    try:
        nodes = _request("nodes") or []
        safe_limit = max(1, min(int(limit or 100), 500))
        projected_nodes = _project_items(nodes[:safe_limit], fields, DEFAULT_NODE_FIELDS)
        return {
            "success": True,
            "nodes": projected_nodes,
            "count": len(projected_nodes),
            "total_available": len(nodes),
            "fields": fields or ",".join(DEFAULT_NODE_FIELDS),
            "data_source": "rabbitmq_http_api",
        }
    except Exception as e:
        return _fail(e, "nodes")


def rabbitmq_cluster_health() -> Dict[str, Any]:
    try:
        overview = _request("overview") or {}
        nodes = _request("nodes") or []
        alerts = _derive_alerts(overview, nodes)
        state = "healthy"
        if any(alert["severity"] == "critical" for alert in alerts):
            state = "critical"
        elif alerts:
            state = "warning"
        return {
            "success": True,
            "health_state": state,
            "cluster_name": overview.get("cluster_name"),
            "rabbitmq_version": overview.get("rabbitmq_version"),
            "erlang_version": overview.get("erlang_version"),
            "node_count": len(nodes),
            "running_nodes": len([node for node in nodes if node.get("running")]),
            "queue_totals": overview.get("queue_totals", {}),
            "object_totals": overview.get("object_totals", {}),
            "message_stats": overview.get("message_stats", {}),
            "listeners": overview.get("listeners", []),
            "alerts": alerts,
            "data_source": "rabbitmq_http_api",
        }
    except Exception as e:
        return _fail(e, "health")


def rabbitmq_cluster_queues(vhost: str = "", name: str = "", limit: int = 100) -> Dict[str, Any]:
    try:
        if vhost and name:
            queues = [_request(f"queues/{quote(vhost, safe='')}/{quote(name, safe='')}")]
        elif vhost:
            queues = _request(f"queues/{quote(vhost, safe='')}") or []
        else:
            queues = _request("queues") or []
        safe_limit = max(1, min(int(limit or 100), 500))
        return {"success": True, "queues": queues[:safe_limit], "count": min(len(queues), safe_limit), "total_available": len(queues), "data_source": "rabbitmq_http_api"}
    except Exception as e:
        return _fail(e, "queues")


def rabbitmq_cluster_connections(limit: int = 100) -> Dict[str, Any]:
    try:
        items = _request("connections") or []
        safe_limit = max(1, min(int(limit or 100), 500))
        return {"success": True, "connections": items[:safe_limit], "count": min(len(items), safe_limit), "total_available": len(items), "data_source": "rabbitmq_http_api"}
    except Exception as e:
        return _fail(e, "connections")


def rabbitmq_cluster_channels(limit: int = 100) -> Dict[str, Any]:
    try:
        items = _request("channels") or []
        safe_limit = max(1, min(int(limit or 100), 500))
        return {"success": True, "channels": items[:safe_limit], "count": min(len(items), safe_limit), "total_available": len(items), "data_source": "rabbitmq_http_api"}
    except Exception as e:
        return _fail(e, "channels")


def rabbitmq_cluster_consumers(limit: int = 100) -> Dict[str, Any]:
    try:
        items = _request("consumers") or []
        safe_limit = max(1, min(int(limit or 100), 500))
        return {"success": True, "consumers": items[:safe_limit], "count": min(len(items), safe_limit), "total_available": len(items), "data_source": "rabbitmq_http_api"}
    except Exception as e:
        return _fail(e, "consumers")


def rabbitmq_cluster_exchanges(vhost: str = "", limit: int = 100) -> Dict[str, Any]:
    try:
        path = f"exchanges/{quote(vhost, safe='')}" if vhost else "exchanges"
        items = _request(path) or []
        safe_limit = max(1, min(int(limit or 100), 500))
        return {"success": True, "exchanges": items[:safe_limit], "count": min(len(items), safe_limit), "total_available": len(items), "data_source": "rabbitmq_http_api"}
    except Exception as e:
        return _fail(e, "exchanges")


def rabbitmq_cluster_vhosts() -> Dict[str, Any]:
    try:
        return _ok(_request("vhosts") or [], "vhosts")
    except Exception as e:
        return _fail(e, "vhosts")


def rabbitmq_cluster_alerts() -> Dict[str, Any]:
    try:
        overview = _request("overview") or {}
        nodes = _request("nodes") or []
        alerts = _derive_alerts(overview, nodes)
        return {"success": True, "alerts": alerts, "alert_count": len(alerts), "data_source": "rabbitmq_http_api"}
    except Exception as e:
        return _fail(e, "alerts")


def _derive_alerts(overview: Dict[str, Any], nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    for node in nodes:
        name = node.get("name")
        if not node.get("running"):
            alerts.append({"severity": "critical", "code": "node_down", "message": "RabbitMQ node is not running", "node": name})
        mem_used = node.get("mem_used")
        mem_limit = node.get("mem_limit")
        if mem_used and mem_limit and mem_limit > 0 and (mem_used / mem_limit) >= 0.9:
            alerts.append({"severity": "critical", "code": "node_memory_high", "message": "Node memory usage is above 90%", "node": name})
        disk_free = node.get("disk_free")
        disk_limit = node.get("disk_free_limit")
        if disk_free is not None and disk_limit is not None and disk_free <= disk_limit:
            alerts.append({"severity": "critical", "code": "node_disk_free_low", "message": "Node disk free is below RabbitMQ alarm limit", "node": name})
        if node.get("partitions"):
            alerts.append({"severity": "critical", "code": "network_partition", "message": "RabbitMQ network partition detected", "node": name, "partitions": node.get("partitions")})

    queue_totals = overview.get("queue_totals") or {}
    messages_ready = int(queue_totals.get("messages_ready") or 0)
    messages_unack = int(queue_totals.get("messages_unacknowledged") or 0)
    ready_threshold = int(os.getenv("RABBITMQ_ALERT_MESSAGES_READY", "100000"))
    unack_threshold = int(os.getenv("RABBITMQ_ALERT_MESSAGES_UNACKED", "50000"))
    if messages_ready >= ready_threshold:
        alerts.append({"severity": "warning", "code": "messages_ready_high", "message": "Ready message backlog is high", "value": messages_ready, "threshold": ready_threshold})
    if messages_unack >= unack_threshold:
        alerts.append({"severity": "warning", "code": "messages_unacked_high", "message": "Unacknowledged message count is high", "value": messages_unack, "threshold": unack_threshold})
    return alerts
