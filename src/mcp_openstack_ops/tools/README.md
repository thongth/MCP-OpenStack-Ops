# Tools Overview

Tai lieu nay tom tat nhanh cac tool wrappers trong `src/mcp_openstack_ops/tools/`.

## Vai tro cua tools layer

- Moi file trong thu muc nay dinh nghia MCP tool interface (input/output cho LLM usage).
- Tool se goi xuong service layer trong `src/mcp_openstack_ops/services/` de xu ly nghiep vu.
- Quy uoc:
- `get_*` va `search_*`: read-only retrieval.

## Nhom Read Tools

### Compute

- `get_instance.py`
- `get_instance_by_id_or_name.py`
- `get_instance_by_project.py`
- `get_instance_related_info.py`
- `get_instance_details.py`
- `get_instances_by_status.py`
- `get_server_events.py`
- `get_server_groups.py`
- `search_instances.py`

### Network

- `get_network.py`
- `get_network_by_id_or_name.py`
- `get_network_by_project.py`
- `get_network_details.py`
- `get_network_ports.py`
- `get_network_agents.py`
- `get_floating_ips.py`
- `get_floating_ips_by_project.py`
- `get_floating_ip_pools.py`
- `get_security_groups.py`
- `get_security_groups_by_project.py`
- `get_routers_by_status.py`
- `get_routers_by_state.py`
- `get_routers_by_project.py`
- `get_routers_by_id_or_name.py`
- `get_routers_details.py`

### Storage

- `get_volume.py`
- `get_volume_by_id_or_name.py`
- `get_volume_by_project.py`
- `get_volume_by_status.py`
- `get_volume_types.py`
- `get_snapshot.py`
- `get_volume_snapshots.py`
- `get_snapshot_by_id_or_name.py`
- `get_snapshot_by_project.py`
- `get_snapshot_by_status.py`
- `get_volume_backup.py`
- `get_volume_backups.py`
- `get_volume_backup_by_id_or_name.py`
- `get_volume_backup_by_project.py`
- `get_volume_backup_by_status.py`
- `get_server_volumes.py`

### Image

- `get_image_list.py`
- `get_image_by_id_or_name.py`
- `get_image_by_project.py`
- `get_image_by_status.py`
- `search_images.py`
- `get_image_detail_list.py`

### Identity / Project

- `get_user_list.py`
- `get_role_assignments.py`
- `get_keypair_list.py`
- `get_project_list.py`
- `get_project_details.py`

### Monitoring / Core

- `get_service_status.py`
- `get_system_information.py`
- `get_resource_monitoring.py`
- `get_usage_statistics.py`
- `get_quota.py`
- `get_hypervisor_details.py`
- `get_availability_zones.py`

### Orchestration

- `get_heat_stacks.py`

### Load Balancer (Octavia)

- `get_load_balancer_list.py`
- `get_load_balancer_details.py`
- `get_load_balancer_listeners.py`
- `get_load_balancer_pools.py`
- `get_load_balancer_pool_members.py`
- `get_load_balancer_health_monitors.py`
- `get_load_balancer_l7_policies.py`
- `get_load_balancer_l7_rules.py`
- `get_load_balancer_providers.py`
- `get_load_balancer_flavors.py`
- `get_load_balancer_availability_zones.py`
- `get_load_balancer_quotas.py`
- `get_load_balancer_amphorae.py`

## Ghi chu

- Day la catalog chuc nang o muc module/file.
- De xem chi tiet schema tham so tung tool, mo truc tiep file tuong ung trong thu muc nay.
