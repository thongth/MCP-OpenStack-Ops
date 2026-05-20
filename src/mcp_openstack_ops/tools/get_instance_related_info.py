"""Tool implementation for get_instance_related_info."""

import json
from datetime import datetime
from ..functions import get_instance_by_name as _get_instance_by_name
from ..functions import get_server_events as _get_server_events
from ..functions import get_server_volumes as _get_server_volumes
from ..mcp_main import logger, mcp
from ..services.identity import get_project_list
from ..services.image import get_image_by_id_or_name
from ..services.network import _get_network_ports_from_mariadb, get_floating_ips
from ..services.compute import get_server_groups


@mcp.tool()
async def get_instance_related_info(
    instance_name_or_id: str,
    include_volumes: bool = True,
    include_fips: bool = True,
    include_events: bool = True,
    include_ports: bool = True,
    include_image: bool = True,
    include_server_groups: bool = True,
    events_limit: int = 20,
) -> str:
    """Get consolidated instance-related info in a single response object."""
    try:
        instance = _get_instance_by_name(instance_name_or_id)
        if not instance:
            return f"Instance '{instance_name_or_id}' not found"

        instance_id = str(instance.get("id", "")).strip()
        project_id = str(instance.get("tenant_id") or instance.get("project_id") or "").strip()
        fixed_ip_set = set()
        warnings = []

        # Normalize fixed IPs from instance.networks
        for net in instance.get("networks", []) or []:
            for addr in net.get("addresses", []) or []:
                ip_addr = addr.get("addr")
                if ip_addr:
                    fixed_ip_set.add(str(ip_addr))

        ports = []
        if include_ports:
            try:
                for port in _get_network_ports_from_mariadb():
                    if str(port.get("device_id") or "") != instance_id:
                        continue
                    for fixed_ip in port.get("fixed_ips", []) or []:
                        if fixed_ip.get("ip_address"):
                            fixed_ip_set.add(str(fixed_ip.get("ip_address")))
                    ports.append(port)
            except Exception as e:
                warnings.append(f"Failed to collect ports: {e}")

        floating_ips = []
        if include_fips:
            try:
                for fip in get_floating_ips():
                    fip_port_id = fip.get("port_id")
                    fip_fixed_ip = fip.get("fixed_ip_address")

                    match_by_port = any(str(p.get("id", "")) == str(fip_port_id) for p in ports)
                    match_by_fixed_ip = bool(fip_fixed_ip and str(fip_fixed_ip) in fixed_ip_set)

                    if not match_by_port and not match_by_fixed_ip:
                        continue

                    floating_ips.append(
                        {
                            "id": fip.get("id", ""),
                            "floating_ip_address": fip.get("floating_ip_address"),
                            "fixed_ip_address": fip_fixed_ip,
                            "port_id": fip_port_id,
                            "status": fip.get("status"),
                            "floating_network_id": fip.get("floating_network_id"),
                            "project_id": fip.get("project_id") or fip.get("tenant_id"),
                        }
                    )
            except Exception as e:
                warnings.append(f"Failed to collect floating IPs: {e}")

        volumes = []
        attached_volume_ids = [str(v) for v in (instance.get("attached_volumes", []) or []) if v]
        if include_volumes:
            try:
                volumes = _get_server_volumes(instance_id or instance_name_or_id)
                if any(isinstance(v, dict) and v.get("error") for v in (volumes or [])):
                    warnings.append("Volume API returned partial/error entries; applying fallback from instance attachments")
                    volumes = [v for v in volumes if not (isinstance(v, dict) and v.get("error"))]

                if attached_volume_ids and not volumes:
                    warnings.append("Instance has attached_volumes metadata but no volume detail could be retrieved")
            except Exception as e:
                warnings.append(f"Failed to collect volumes: {e}")

        events = []
        if include_events:
            try:
                events_result = _get_server_events(instance_name_or_id, limit=events_limit)
                if isinstance(events_result, dict):
                    events = events_result.get("events", []) or []
                    if not events_result.get("success", True):
                        event_message = events_result.get("message", "Failed to retrieve server events")
                        if "not found" in str(event_message).lower():
                            warnings.append(
                                "Recent events unavailable for this instance in event API scope "
                                "(instance detail still resolved successfully)"
                            )
                        else:
                            warnings.append(event_message)
                    elif not events:
                        warnings.append("No recent events returned for this instance")
                else:
                    events = []
                    warnings.append("Unexpected events response format")
            except Exception as e:
                warnings.append(f"Failed to collect events: {e}")

        project_info = None
        try:
            if project_id:
                projects = get_project_list().get("projects", [])
                project_info = next((p for p in projects if p.get("id") == project_id), {"id": project_id})
        except Exception as e:
            warnings.append(f"Failed to collect project info: {e}")

        image_info = instance.get("image")
        if include_image:
            try:
                image_ref = instance.get("image") if isinstance(instance.get("image"), dict) else {}
                image_id = str(image_ref.get("id", "")).strip()
                if not image_info and image_id and image_id != "unknown":
                    image_result = get_image_by_id_or_name(image_id)
                    image_info = image_result.get("image") or image_info
            except Exception as e:
                warnings.append(f"Failed to collect image detail: {e}")

        server_groups = []
        if include_server_groups:
            try:
                for group in get_server_groups():
                    members = group.get("members", []) or []
                    if instance_id not in [str(m) for m in members]:
                        continue
                    server_groups.append(
                        {
                            "id": group.get("id", ""),
                            "name": group.get("name", ""),
                            "project_id": group.get("project_id"),
                            "policies": group.get("policies", []),
                            "members": members,
                            "member_count": len(members),
                        }
                    )
            except Exception as e:
                warnings.append(f"Failed to collect server groups: {e}")

        hypervisor_az_info = {
            "host": instance.get("host"),
            "hypervisor_hostname": instance.get("hypervisor_hostname"),
            "availability_zone": instance.get("availability_zone"),
        }

        result = {
            "timestamp": datetime.now().isoformat(),
            "query": instance_name_or_id,
            "instance": instance,
            "ports": ports if include_ports else [],
            "floating_ips": floating_ips if include_fips else [],
            "volumes": volumes if include_volumes else [],
            "security_groups": instance.get("security_groups", []) or [],
            "recent_events": events if include_events else [],
            "image": image_info if include_image else None,
            "project": project_info,
            "hypervisor_and_az": hypervisor_az_info,
            "server_groups": server_groups if include_server_groups else [],
            "counts": {
                "ports": len(ports) if include_ports else 0,
                "floating_ips": len(floating_ips) if include_fips else 0,
                "volumes": len(volumes) if include_volumes else 0,
                "security_groups": len(instance.get("security_groups", []) or []),
                "events": len(events) if include_events else 0,
                "server_groups": len(server_groups) if include_server_groups else 0,
            },
            "warnings": warnings,
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        error_msg = f"Error: Failed to get instance related info - {str(e)}"
        logger.error(error_msg)
        return error_msg
