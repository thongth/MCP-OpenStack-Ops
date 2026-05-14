"""Tool implementation for get_instance_related_info."""

import json
from datetime import datetime
from ..connection import get_openstack_connection
from ..functions import get_instance_by_name as _get_instance_by_name
from ..functions import get_server_events as _get_server_events
from ..functions import get_server_volumes as _get_server_volumes
from ..mcp_main import logger, mcp


@mcp.tool()
async def get_instance_related_info(
    instance_name_or_id: str,
    include_volumes: bool = True,
    include_fips: bool = True,
    include_events: bool = True,
    include_ports: bool = True,
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
                conn = get_openstack_connection()
                try:
                    port_iter = conn.network.ports(device_id=instance_id)
                except TypeError:
                    port_iter = conn.network.ports()

                for port in port_iter:
                    if getattr(port, "device_id", "") != instance_id:
                        continue

                    port_fixed_ips = []
                    for fip in getattr(port, "fixed_ips", []) or []:
                        ip_addr = fip.get("ip_address") if isinstance(fip, dict) else None
                        subnet_id = fip.get("subnet_id") if isinstance(fip, dict) else None
                        if ip_addr:
                            fixed_ip_set.add(str(ip_addr))
                        port_fixed_ips.append(
                            {
                                "ip_address": ip_addr,
                                "subnet_id": subnet_id,
                            }
                        )

                    ports.append(
                        {
                            "id": getattr(port, "id", ""),
                            "name": getattr(port, "name", ""),
                            "network_id": getattr(port, "network_id", None),
                            "mac_address": getattr(port, "mac_address", None),
                            "status": getattr(port, "status", None),
                            "admin_state_up": getattr(port, "admin_state_up", None),
                            "device_owner": getattr(port, "device_owner", None),
                            "fixed_ips": port_fixed_ips,
                            "security_group_ids": getattr(port, "security_group_ids", []) or [],
                        }
                    )
            except Exception as e:
                warnings.append(f"Failed to collect ports: {e}")

        floating_ips = []
        if include_fips:
            try:
                conn = get_openstack_connection()
                try:
                    fip_iter = conn.network.ips()
                except Exception:
                    fip_iter = []

                for fip in fip_iter:
                    fip_port_id = getattr(fip, "port_id", None)
                    fip_fixed_ip = getattr(fip, "fixed_ip_address", None)

                    match_by_port = any(str(p.get("id", "")) == str(fip_port_id) for p in ports)
                    match_by_fixed_ip = bool(fip_fixed_ip and str(fip_fixed_ip) in fixed_ip_set)

                    if not match_by_port and not match_by_fixed_ip:
                        continue

                    floating_ips.append(
                        {
                            "id": getattr(fip, "id", ""),
                            "floating_ip_address": getattr(fip, "floating_ip_address", None),
                            "fixed_ip_address": fip_fixed_ip,
                            "port_id": fip_port_id,
                            "status": getattr(fip, "status", None),
                            "floating_network_id": getattr(fip, "floating_network_id", None),
                            "project_id": getattr(fip, "project_id", None) or getattr(fip, "tenant_id", None),
                        }
                    )
            except Exception as e:
                warnings.append(f"Failed to collect floating IPs: {e}")

        volumes = []
        if include_volumes:
            try:
                volumes = _get_server_volumes(instance_name_or_id)
            except Exception as e:
                warnings.append(f"Failed to collect volumes: {e}")

        events = []
        if include_events:
            try:
                events_result = _get_server_events(instance_name_or_id, limit=events_limit)
                events = events_result.get("events", []) if isinstance(events_result, dict) else []
            except Exception as e:
                warnings.append(f"Failed to collect events: {e}")

        project_info = None
        try:
            if project_id:
                conn = get_openstack_connection()
                project = conn.identity.find_project(project_id, ignore_missing=True)
                if project:
                    project_info = {
                        "id": getattr(project, "id", project_id),
                        "name": getattr(project, "name", None),
                        "description": getattr(project, "description", ""),
                        "domain_id": getattr(project, "domain_id", None),
                        "enabled": bool(getattr(project, "is_enabled", False)),
                    }
                else:
                    project_info = {"id": project_id}
        except Exception as e:
            warnings.append(f"Failed to collect project info: {e}")

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
            "project": project_info,
            "hypervisor_and_az": hypervisor_az_info,
            "counts": {
                "ports": len(ports) if include_ports else 0,
                "floating_ips": len(floating_ips) if include_fips else 0,
                "volumes": len(volumes) if include_volumes else 0,
                "security_groups": len(instance.get("security_groups", []) or []),
                "events": len(events) if include_events else 0,
            },
            "warnings": warnings,
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        error_msg = f"Error: Failed to get instance related info - {str(e)}"
        logger.error(error_msg)
        return error_msg
