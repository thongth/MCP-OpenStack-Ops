# Services Overview

Service modules contain the implementation behind MCP tool wrappers.

## Database Query Model

- `compute.py` queries the `nova` database.
- `network.py` queries the `neutron` database.
- `storage.py` queries the `cinder` database.
- MariaDB connection settings are shared through `MARIADB_HOST`, `MARIADB_PORT`, `MARIADB_USER`, `MARIADB_PASSWORD`, `MARIADB_CHARSET`, and `MARIADB_CONNECT_TIMEOUT`.
- Service database names are hardcoded; do not set `MARIADB_DATABASE` or service-specific DB names for normal operation.

## Modules

### `compute.py`

Nova read helpers:

- Instances: `get_instance_details`, `get_instance_by_name`, `get_instance_by_id`, `search_instances`, `get_instances_by_status`
- Summary: `get_instance_summary`
- Flavor metadata: `get_flavor_list`
- Events and grouping: `get_server_events`, `get_server_groups`
- Attachments: `get_server_volumes`

### `network.py`

Neutron read helpers:

- Networks: `get_network_details`, `get_network_summary`
- Ports: `get_network_ports` read-only port listing
- Agents: `get_network_agents`
- Security groups: `get_security_groups`, `get_security_groups_summary`
- Floating IPs: `get_floating_ips`, `get_floating_ips_summary`, `get_floating_ip_pools`
- Routers: `get_routers`, `get_routers_summary`

### `storage.py`

Cinder read helpers:

- Unified query: `get_storage_resource`
- Volumes: `get_volume_list`, `get_volume_summary`
- Volume types: `get_volume_types`
- Snapshots: service `get_volume_snapshots`, exposed through canonical tools such as `get_volume_snapshot_list` and `get_volume_snapshot_summary`
- Backups: service `get_volume_backups`, exposed through canonical tools such as `get_volume_backup_list` and `get_volume_backup_summary`
- Server attachments: `get_server_volumes`

### `image.py`

Glance read helpers:

- `get_image_list`
- `get_image_list_filtered`
- `get_image_by_id_or_name`
- `search_images`
- `get_image_detail_list`

### `identity.py`

Keystone/project helpers:

- `get_project_info`
- `get_project_list`
- `get_project_details`
- `get_user_list`
- `get_role_assignments`
- `get_keypair_list`

### `monitoring.py`

Monitoring and quota helpers:

- `get_system_information`
- `get_resource_monitoring`
- `get_usage_statistics`
- `get_quota`
- `get_compute_quota_usage`
- `get_hypervisor_details`
- `get_availability_zones`

### `load_balancer/`

Octavia helpers:

- `core.py`: load balancer list/detail
- `listeners.py`: listeners
- `pools.py`: pools and members
- `health_monitors.py`: health monitors
- `l7_policies.py`: L7 policies and rules
- `management.py`: availability zones, flavors, providers, quotas
- `amphorae.py`: amphora list/detail

## Removed

- `core.py` service-status module was removed.
- Heat/orchestration service support was removed.
- Mutating service exports were removed from package-level `services.__init__`.
