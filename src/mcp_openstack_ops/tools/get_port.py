"""Tool implementation for get_port."""

import json
from datetime import datetime
from typing import Any, Dict, List

from ..mcp_main import logger, mcp
from ..services.network import _get_network_ports_from_mariadb, get_floating_ips


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _port_match_reasons(port: Dict[str, Any], target: str) -> List[str]:
    reasons = []
    for field in ("id", "name", "device_id", "mac_address", "network_id"):
        if _normalize(port.get(field)) == target:
            reasons.append(field)

    for fixed_ip in port.get("fixed_ips", []) or []:
        if _normalize(fixed_ip.get("ip_address")) == target:
            reasons.append("fixed_ip")

    return reasons


def _floating_ip_match_reasons(fip: Dict[str, Any], target: str) -> List[str]:
    reasons = []
    for field in ("id", "floating_ip_address", "fixed_ip_address", "port_id"):
        if _normalize(fip.get(field)) == target:
            reasons.append(field)
    return reasons


@mcp.tool()
async def get_port(
    query: str = "",
    project_id: str = "",
    status: str = "",
    include_floating_ips: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """
    Get Neutron ports by port ID/name, fixed IP, MAC address, device_id, network_id, or floating IP.

    Args:
        query: Optional exact value to match against port ID, name, fixed IP, MAC, device_id,
            network_id, floating IP address, floating fixed IP, or floating IP port_id.
        project_id: Optional project ID filter.
        status: Optional port status filter.
        include_floating_ips: Include floating IP associations for matched ports.
        limit: Max rows returned after filtering. Use 0 for no limit.
        offset: Rows to skip after filtering.

    Returns:
        JSON string containing matching ports and floating IP associations.
    """
    try:
        target = _normalize(query)
        ports = _get_network_ports_from_mariadb(project_id=project_id, status=status)
        fips = get_floating_ips(project_id=project_id) if include_floating_ips or target else []

        fip_matched_port_ids = set()
        matched_floating_ips = []
        if target:
            for fip in fips:
                reasons = _floating_ip_match_reasons(fip, target)
                if not reasons:
                    continue
                enriched_fip = dict(fip)
                enriched_fip["match_reasons"] = reasons
                matched_floating_ips.append(enriched_fip)
                port_id = str(fip.get("port_id") or "").strip()
                if port_id:
                    fip_matched_port_ids.add(port_id)

        matched_ports = []
        for port in ports:
            reasons = _port_match_reasons(port, target) if target else ["list"]
            if port.get("id") in fip_matched_port_ids:
                reasons.append("floating_ip_association")
            if target and not reasons:
                continue
            enriched_port = dict(port)
            enriched_port["match_reasons"] = sorted(set(reasons))
            matched_ports.append(enriched_port)

        fips_by_port: Dict[str, List[Dict[str, Any]]] = {}
        if include_floating_ips:
            matched_port_ids = {str(port.get("id") or "") for port in matched_ports}
            for fip in fips:
                port_id = str(fip.get("port_id") or "")
                if port_id in matched_port_ids:
                    fips_by_port.setdefault(port_id, []).append(fip)
            for port in matched_ports:
                port["floating_ips"] = fips_by_port.get(str(port.get("id") or ""), [])

        safe_offset = max(int(offset or 0), 0)
        safe_limit = max(int(limit or 0), 0)
        paged_ports = matched_ports[safe_offset:safe_offset + safe_limit] if safe_limit else matched_ports[safe_offset:]

        response = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "filter": {
                "project_id": project_id,
                "status": status,
                "include_floating_ips": include_floating_ips,
                "limit": limit,
                "offset": offset,
            },
            "total_matches": len(matched_ports),
            "count": len(paged_ports),
            "ports": paged_ports,
            "matched_floating_ips": matched_floating_ips,
        }

        return json.dumps(response, indent=2, ensure_ascii=False, default=str)

    except Exception as e:
        error_msg = f"Error: Failed to get port - {str(e)}"
        logger.error(error_msg)
        return error_msg
