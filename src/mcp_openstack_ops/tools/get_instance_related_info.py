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
        attached_volume_ids = [str(v) for v in (instance.get("attached_volumes", []) or []) if v]
        if include_volumes:
            try:
                volumes = _get_server_volumes(instance_name_or_id)
                if any(isinstance(v, dict) and v.get("error") for v in (volumes or [])):
                    warnings.append("Volume API returned partial/error entries; applying fallback from instance attachments")
                    volumes = [v for v in volumes if not (isinstance(v, dict) and v.get("error"))]

                if attached_volume_ids and len(volumes) < len(attached_volume_ids):
                    conn = get_openstack_connection()
                    existing_ids = {str(v.get("volume_id") or v.get("id") or "") for v in volumes if isinstance(v, dict)}
                    for volume_id in attached_volume_ids:
                        if volume_id in existing_ids:
                            continue
                        try:
                            vol = conn.volume.get_volume(volume_id)
                            volumes.append(
                                {
                                    "volume_id": getattr(vol, "id", volume_id),
                                    "volume_name": getattr(vol, "name", ""),
                                    "size": getattr(vol, "size", 0),
                                    "status": getattr(vol, "status", "unknown"),
                                    "volume_type": getattr(vol, "volume_type", None),
                                    "bootable": getattr(vol, "is_bootable", False),
                                    "encrypted": getattr(vol, "is_encrypted", False),
                                    "attachment_id": None,
                                    "device": None,
                                    "source": "instance_attached_volumes_fallback",
                                }
                            )
                        except Exception as e:
                            warnings.append(f"Failed to resolve attached volume '{volume_id}': {e}")
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

        image_info = instance.get("image")
        if include_image:
            try:
                # Priority 1: image metadata from boot volume (volume_image_metadata).
                volume_image_metadata = {}
                for vol_item in volumes:
                    if not isinstance(vol_item, dict):
                        continue
                    vol_id = str(vol_item.get("volume_id") or vol_item.get("id") or "").strip()
                    if not vol_id:
                        continue
                    try:
                        conn = get_openstack_connection()
                        vol_obj = conn.volume.get_volume(vol_id)
                        meta = getattr(vol_obj, "volume_image_metadata", None) or {}
                        if meta:
                            volume_image_metadata = meta
                            break
                    except Exception:
                        continue

                if volume_image_metadata:
                    image_info = {
                        "id": volume_image_metadata.get("image_id"),
                        "name": volume_image_metadata.get("image_name"),
                        "checksum": volume_image_metadata.get("image_checksum"),
                        "container_format": volume_image_metadata.get("container_format"),
                        "disk_format": volume_image_metadata.get("disk_format"),
                        "min_disk": volume_image_metadata.get("min_disk"),
                        "min_ram": volume_image_metadata.get("min_ram"),
                        "size": volume_image_metadata.get("size"),
                        "visibility": volume_image_metadata.get("visibility"),
                        "owner": volume_image_metadata.get("owner_id"),
                        "source": "volume_image_metadata",
                        "volume_image_metadata": volume_image_metadata,
                    }

                # Priority 2: instance image reference/API lookup.
                image_ref = instance.get("image") if isinstance(instance.get("image"), dict) else {}
                image_id = str(image_ref.get("id", "")).strip()
                if not image_info and image_id and image_id != "unknown":
                    conn = get_openstack_connection()
                    image = conn.image.get_image(image_id)
                    image_info = {
                        "id": getattr(image, "id", image_id),
                        "name": getattr(image, "name", image_ref.get("name")),
                        "status": getattr(image, "status", None),
                        "visibility": getattr(image, "visibility", None),
                        "owner": getattr(image, "owner", None),
                        "size": getattr(image, "size", None),
                        "disk_format": getattr(image, "disk_format", None),
                        "container_format": getattr(image, "container_format", None),
                        "min_disk": getattr(image, "min_disk", None),
                        "min_ram": getattr(image, "min_ram", None),
                        "created_at": str(getattr(image, "created_at", "unknown")),
                        "updated_at": str(getattr(image, "updated_at", "unknown")),
                        "source": "image_api",
                    }
            except Exception as e:
                warnings.append(f"Failed to collect image detail: {e}")

        server_groups = []
        if include_server_groups:
            try:
                conn = get_openstack_connection()
                for group in conn.compute.server_groups():
                    members = getattr(group, "members", []) or []
                    if instance_id not in [str(m) for m in members]:
                        continue
                    policies = getattr(group, "policies", []) or []
                    policy = getattr(group, "policy", None)
                    if policy and not policies:
                        policies = [policy]
                    server_groups.append(
                        {
                            "id": getattr(group, "id", ""),
                            "name": getattr(group, "name", ""),
                            "project_id": getattr(group, "project_id", None),
                            "policies": policies,
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
