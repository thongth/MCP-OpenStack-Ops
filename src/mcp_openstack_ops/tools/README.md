# Tools Overview

Tai lieu nay tom tat nhanh cac tool wrappers trong `src/mcp_openstack_ops/tools/`.

## Vai tro cua tools layer

- Moi file trong thu muc nay dinh nghia MCP tool interface (input/output cho LLM usage).
- Tool se goi xuong service layer trong `src/mcp_openstack_ops/services/` de xu ly nghiep vu.
- Quy uoc:
- `get_*` va `search_*`: read-only retrieval.
- `set_*`: modify operations (co the bi chan boi safety gate khi `ALLOW_MODIFY_OPERATIONS=false`).

## Nhom Read Tools

### Compute

- `get_instance.py`
- `get_instance_by_name.py`
- `get_instance_details.py`
- `get_instances_by_status.py`
- `get_server_events.py`
- `get_server_groups.py`
- `search_instances.py`

### Network

- `get_network_details.py`
- `get_network_agents.py`
- `get_floating_ips.py`
- `get_floating_ip_pools.py`
- `get_security_groups.py`
- `get_routers.py`

### Storage

- `get_volume_list.py`
- `get_volume_types.py`
- `get_volume_snapshots.py`
- `get_server_volumes.py`

### Image

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

## Nhom Modify Tools

### Compute

- `set_instance.py`
- `set_flavor.py`
- `set_server_group.py`
- `set_server_network.py`
- `set_server_floating_ip.py`
- `set_server_fixed_ip.py`
- `set_server_security_group.py`
- `set_server_migration.py`
- `set_server_properties.py`
- `set_server_backup.py`
- `set_server_dump.py`

### Network

- `set_networks.py`
- `set_subnets.py`
- `set_floating_ip.py`
- `set_floating_ip_port_forwarding.py`
- `set_network_ports.py`
- `set_network_agents.py`
- `set_network_qos_policies.py`

### Storage

- `set_volume.py`
- `set_snapshot.py`
- `set_server_volume.py`
- `set_volume_backups.py`
- `set_volume_groups.py`
- `set_volume_qos.py`

### Image

- `set_image.py`
- `set_image_members.py`
- `set_image_metadata.py`
- `set_image_visibility.py`

### Identity / Project

- `set_domains.py`
- `set_keypair.py`
- `set_project.py`
- `set_roles.py`
- `set_identity_groups.py`

### Monitoring / Ops

- `set_quota.py`
- `set_alarms.py`
- `set_metrics.py`
- `set_compute_agents.py`
- `set_services.py`
- `set_service_logs.py`

### Orchestration

- `set_heat_stack.py`

### Load Balancer (Octavia)

- `set_load_balancer.py`
- `set_load_balancer_listener.py`
- `set_load_balancer_pool.py`
- `set_load_balancer_pool_member.py`
- `set_load_balancer_health_monitor.py`
- `set_load_balancer_l7_policy.py`
- `set_load_balancer_l7_rule.py`
- `set_load_balancer_flavor.py`
- `set_load_balancer_availability_zone.py`
- `set_load_balancer_quota.py`
- `set_load_balancer_amphora.py`

## Ghi chu

- Day la catalog chuc nang o muc module/file.
- De xem chi tiet schema tham so tung tool, mo truc tiep file tuong ung trong thu muc nay.
