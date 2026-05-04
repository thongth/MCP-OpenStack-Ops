# Services Overview

Tai lieu nay tom tat nhanh cac module trong `src/mcp_openstack_ops/services/` va chuc nang chinh cua tung module.

## Kien truc tong quan

- `mcp_main.py` dang ky tool MCP.
- Tool wrappers trong `src/mcp_openstack_ops/tools/` goi vao service functions tai day.
- Services xu ly logic nghiep vu OpenStack theo tung domain.
- `connection.py` phu trach ket noi, project isolation, va resource ownership validation.

## Danh sach service modules

### `compute.py`

Quan ly Nova compute resources:
- Lay thong tin instances: `get_instance_details`, `get_instance_by_name`, `get_instance_by_id`, `search_instances`, `get_instances_by_status`
- Quan ly instance lifecycle: `set_instance`
- Flavor va server metadata: `get_flavor_list`, `set_flavor`, `set_server_properties`
- Server networking va security: `set_server_network`, `set_server_floating_ip`, `set_server_fixed_ip`, `set_server_security_group`
- Van hanh server nang cao: `set_server_migration`, `create_server_backup`, `create_server_dump`
- Event va grouping: `get_server_events`, `get_server_groups`, `set_server_group`

### `network.py`

Quan ly Neutron networking:
- Truy van mang: `get_network_details`
- Quan ly network va subnet: `set_networks`, `set_subnets`
- Security va IP: `get_security_groups`, `get_floating_ips`, `set_floating_ip`, `get_floating_ip_pools`, `set_floating_ip_port_forwarding`
- Router va ports: `get_routers`, `set_network_ports`

### `storage.py`

Quan ly Cinder storage:
- Volumes: `get_volume_list`, `set_volume`, `get_server_volumes`, `set_server_volume`
- Volume metadata: `get_volume_types`
- Snapshots: `get_volume_snapshots`, `set_snapshot`
- Backups, groups, QoS: `set_volume_backups`, `set_volume_groups`, `set_volume_qos`

### `image.py`

Quan ly Glance images:
- Listing: `get_image_list`, `get_image_detail_list`
- Quan ly image: `set_image`
- Chia se va metadata: `set_image_members`, `set_image_metadata`, `set_image_visibility`

### `identity.py`

Quan ly Keystone identity/project scope:
- Domains: `set_domains`
- Project va user thong tin: `get_project_info`, `get_project_details`, `get_user_list`
- Role assignments: `get_role_assignments`
- Keypairs: `get_keypair_list`, `set_keypair`
- Project operations: `set_project`

### `monitoring.py`

Tong hop monitoring va quota/usage:
- System monitoring: `get_system_information` (compute services, block storage services, network agents)
- Health/tai nguyen tong quan: `get_resource_monitoring`
- Usage va quota: `get_usage_statistics`, `get_quota`, `set_quota`, `get_compute_quota_usage`
- Ha tang compute: `get_hypervisor_details`, `get_availability_zones`

### `orchestration.py`

Quan ly Heat orchestration:
- Listing stacks: `get_heat_stacks`
- Vong doi stack: `set_heat_stack`

### `core.py`

Service-level status:
- Lay trang thai dich vu OpenStack: `get_service_status`

## Nhom load balancer (`load_balancer/`)

Tap hop cac service cho Octavia:

- `core.py`: `get_load_balancer_list`, `get_load_balancer_details`, `set_load_balancer`
- `listeners.py`: `get_load_balancer_listeners`, `set_load_balancer_listener`
- `pools.py`: `get_load_balancer_pools`, `set_load_balancer_pool`, `get_load_balancer_pool_members`, `set_load_balancer_pool_member`
- `health_monitors.py`: `get_load_balancer_health_monitors`, `set_load_balancer_health_monitor`
- `l7_policies.py`: `get_load_balancer_l7_policies`, `set_load_balancer_l7_policy`, `get_load_balancer_l7_rules`, `set_load_balancer_l7_rule`
- `management.py`: availability zone, flavor, provider, quota APIs
- `amphorae.py`: amphora listing va actions

## Ghi chu van hanh

- Cac ham bat dau bang `get_` la read-oriented.
- Cac ham bat dau bang `set_` la modify-oriented va phu thuoc co che an toan (`ALLOW_MODIFY_OPERATIONS`).
- Project isolation/ownership filter duoc thuc thi o tang connection + service logic.
