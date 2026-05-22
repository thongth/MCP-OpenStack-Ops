"""Tool implementation for get_instance_by_port."""

import json
from datetime import datetime
from typing import Any, Dict, List

from ..functions import get_instance_by_name as _get_instance_by_name
from ..mcp_main import logger, mcp
from ..services.network import _get_network_ports_from_mariadb, get_floating_ips


def _matches_port(port: Dict[str, Any], target: str) -> bool:
    normalized = target.strip().lower()
    if not normalized:
        return False

    for field in ("id", "name", "device_id", "mac_address"):
        if str(port.get(field, "")).strip().lower() == normalized:
            return True

    for fixed_ip in port.get("fixed_ips", []) or []:
        if str(fixed_ip.get("ip_address", "")).strip().lower() == normalized:
            return True

    return False


def _find_ports(query: str, project_id: str = "") -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ports = _get_network_ports_from_mariadb(project_id=project_id)
    matches = [port for port in ports if _matches_port(port, query)]
    floating_ip_matches: List[Dict[str, Any]] = []

    if not matches:
        target = query.strip().lower()
        for fip in get_floating_ips(project_id=project_id):
            if str(fip.get("floating_ip_address", "")).strip().lower() != target:
                continue
            floating_ip_matches.append(fip)
            port_id = str(fip.get("port_id") or "").strip()
            if port_id:
                matches.extend([port for port in ports if str(port.get("id") or "") == port_id])

    seen = set()
    unique_matches = []
    for port in matches:
        port_id = port.get("id")
        if port_id in seen:
            continue
        seen.add(port_id)
        unique_matches.append(port)

    return unique_matches, floating_ip_matches


@mcp.tool()
async def get_instance_by_port(query: str, project_id: str = "", include_all_instance_ports: bool = True) -> str:
    """
    Resolve an OpenStack instance from a Neutron port identifier.

    Args:
        query: Port ID, port name, fixed IP, MAC address, device_id, or floating IP address.
        project_id: Optional project ID filter.
        include_all_instance_ports: Include all Neutron ports attached to the resolved instance.

    Returns:
        JSON string containing matched ports and resolved instance details.
    """
    try:
        query = str(query or "").strip()
        if not query:
            return "Error: query is required"

        matched_ports, matched_floating_ips = _find_ports(query, project_id=project_id)

        resolved_instances = []
        unresolved_ports = []
        all_ports = None

        for port in matched_ports:
            device_id = str(port.get("device_id") or "").strip()
            device_owner = str(port.get("device_owner") or "").strip()
            if not device_id:
                unresolved_ports.append(
                    {
                        "port_id": port.get("id"),
                        "reason": "Port has no device_id",
                        "device_owner": device_owner,
                    }
                )
                continue

            instance = _get_instance_by_name(device_id)
            if not instance:
                unresolved_ports.append(
                    {
                        "port_id": port.get("id"),
                        "device_id": device_id,
                        "reason": "device_id did not resolve to a Nova instance",
                        "device_owner": device_owner,
                    }
                )
                continue

            instance_id = str(instance.get("id") or "").strip()
            attached_ports = []
            if include_all_instance_ports and instance_id:
                if all_ports is None:
                    all_ports = _get_network_ports_from_mariadb(project_id=project_id)
                attached_ports = [
                    candidate
                    for candidate in all_ports
                    if str(candidate.get("device_id") or "").strip() == instance_id
                ]

            resolved_instances.append(
                {
                    "instance": instance,
                    "matched_port": port,
                    "attached_ports": attached_ports,
                    "attached_port_count": len(attached_ports),
                }
            )

        response = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "project_id": project_id,
            "matched_port_count": len(matched_ports),
            "matched_ports": matched_ports,
            "matched_floating_ips": matched_floating_ips,
            "resolved_instance_count": len(resolved_instances),
            "resolved_instances": resolved_instances,
            "unresolved_ports": unresolved_ports,
            "notes": [
                "device_id resolves to a VM only for compute-owned ports such as compute:nova.",
                "Router, DHCP, load balancer, and other service ports are returned as unresolved.",
            ],
        }

        return json.dumps(response, indent=2, ensure_ascii=False, default=str)

    except Exception as e:
        error_msg = f"Error: Failed to resolve instance by port - {str(e)}"
        logger.error(error_msg)
        return error_msg
