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
- Flavor: `get_flavor_list`
- Event va grouping: `get_server_events`, `get_server_groups`

### `network.py`

Quan ly Neutron networking:
- Truy van mang: `get_network_details`
- Network agents: `get_network_agents`
- Security va IP: `get_security_groups`, `get_floating_ips`, `get_floating_ip_pools`
- Router va ports: `get_routers`

### `storage.py`

Quan ly Cinder storage:
- Volumes: `get_volume_list`, `get_server_volumes`
- Volume metadata: `get_volume_types`
- Snapshots: `get_volume_snapshots`
- Backups: `get_volume_backups`

### `image.py`

Quan ly Glance images:
- Listing: `get_image_list`, `get_image_detail_list`

### `identity.py`

Quan ly Keystone identity/project scope:
- Project va user thong tin: `get_project_info`, `get_project_details`, `get_user_list`
- Role assignments: `get_role_assignments`
- Keypairs: `get_keypair_list`

### `monitoring.py`

Tong hop monitoring va quota/usage:
- System monitoring: `get_system_information` (compute services, block storage services, network agents)
- Health/tai nguyen tong quan: `get_resource_monitoring`
- Usage va quota: `get_usage_statistics`, `get_quota`, `get_compute_quota_usage`
- Ha tang compute: `get_hypervisor_details`, `get_availability_zones`

### `orchestration.py`

Quan ly Heat orchestration:
- Listing stacks: `get_heat_stacks`

### `core.py`

Service-level status:
- Lay trang thai dich vu OpenStack: `get_service_status`

## Nhom load balancer (`load_balancer/`)

Tap hop cac service cho Octavia:

- `core.py`: `get_load_balancer_list`, `get_load_balancer_details`
- `listeners.py`: `get_load_balancer_listeners`
- `pools.py`: `get_load_balancer_pools`, `get_load_balancer_pool_members`
- `health_monitors.py`: `get_load_balancer_health_monitors`
- `l7_policies.py`: `get_load_balancer_l7_policies`, `get_load_balancer_l7_rules`
- `management.py`: availability zone, flavor, provider, quota APIs
- `amphorae.py`: amphora listing va actions

## Ghi chu van hanh

- Cac ham bat dau bang `get_` la read-oriented.
- Project isolation/ownership filter duoc thuc thi o tang connection + service logic.
