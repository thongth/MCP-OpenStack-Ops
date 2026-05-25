# MCP-OpenStack-Ops

MCP server for read-only OpenStack operations. The current implementation is tuned for ops/reporting workflows and uses MariaDB read queries for Nova, Neutron, and Cinder data where possible.

## Current Scope

- Read-only MCP tools only. Mutating `set_*` tool modules are not registered.
- Compute, network, and storage tools query MariaDB directly using a shared read-only DB account.
- Database names are hardcoded in code:
  - Nova: `nova`
  - Neutron: `neutron`
  - Cinder: `cinder`
- Image, identity, monitoring, and selected Octavia paths still use OpenStack SDK where DB-backed logic is not available or practical.
- Heat/orchestration tools have been removed.
- Synthetic `get_service_status` / Glance-only service status output has been removed.
- `include_all_projects` has been removed from DB query tools. Use explicit filters such as `project_id`, `status`, `id/name`, `limit`, and `offset`.

## Main Tool Groups

### Compute / Nova

- `get_instance`
- `get_compute_resource`
- `get_instance_by_id_or_name`
- `get_instance_by_port`
- `get_instance_by_project`
- `get_instance_details`
- `get_instance_related_info`
- `get_instance_summary`
- `get_instances_by_status`
- `search_instances`
- `get_server_events`
- `get_server_groups`
- `get_server_volumes`
- `get_hypervisor_details`
- `get_availability_zones`

### Network / Neutron

- `get_network`
- `get_network_resource`
- `get_network_by_id_or_name`
- `get_network_by_project`
- `get_network_details`
- `get_port`
- `get_network_ports`
- `get_network_summary`
- `get_network_agents`
- `get_floating_ips`
- `get_floating_ips_by_project`
- `get_floating_ips_summary`
- `get_floating_ip_pools`
- `get_security_groups`
- `get_security_groups_by_project`
- `get_security_groups_summary`
- `get_routers_by_id_or_name`
- `get_routers_by_project`
- `get_routers_by_state`
- `get_routers_by_status`
- `get_routers_details`
- `get_routers_summary`

### Storage / Cinder

- `get_storage_resource`
- `get_volume_list`
- `get_volume_by_id_or_name`
- `get_volume_by_project`
- `get_volume_by_status`
- `get_volume_summary`
- `get_volume_types`
- `get_volume_snapshot_list`
- `get_volume_snapshot_by_id_or_name`
- `get_volume_snapshot_by_project`
- `get_volume_snapshot_by_status`
- `get_volume_snapshot_summary`
- `get_volume_backup_list`
- `get_volume_backup_by_id_or_name`
- `get_volume_backup_by_project`
- `get_volume_backup_by_status`
- `get_volume_backup_summary`

### Image / Glance

- `get_image_list`
- `get_image_detail_list`
- `get_image_by_id_or_name`
- `get_image_by_project`
- `get_image_by_status`
- `search_images`

### Identity / Project

- `get_project_list`
- `get_project_details`
- `get_user_list`
- `get_role_assignments`
- `get_keypair_list`

### Monitoring / Quota

- `get_system_information`
- `get_resource_monitoring`
- `get_usage_statistics`
- `get_quota`

### MariaDB Cluster

- `mariadb_cluster_health`
- `mariadb_cluster_replication_overview`
- `mariadb_cluster_connection_stats`
- `mariadb_cluster_query_performance`
- `mariadb_cluster_storage_utilization`
- `mariadb_cluster_capacity_summary`
- `mariadb_cluster_top_slow_queries`
- `mariadb_cluster_top_tables`
- `mariadb_cluster_alerts`
- `mariadb_cluster_wsrep_status`

### RabbitMQ Cluster

- `rabbitmq_cluster_overview`
- `rabbitmq_cluster_health`
- `rabbitmq_cluster_nodes`
- `rabbitmq_cluster_queues`
- `rabbitmq_cluster_queues_without_consumers`
- `rabbitmq_cluster_top_queues`
- `rabbitmq_cluster_connections`
- `rabbitmq_cluster_channels`
- `rabbitmq_cluster_consumers`
- `rabbitmq_cluster_exchanges`
- `rabbitmq_cluster_vhosts`
- `rabbitmq_cluster_alerts`

### Load Balancer / Octavia

- `get_loadbalancer_list`
- `get_loadbalancer_resource`
- `get_loadbalancer_details`
- `get_loadbalancer_by_vip`
- `get_loadbalancer_by_floatingip`
- `get_loadbalancer_listeners`
- `get_loadbalancer_pools`
- `get_loadbalancer_pool_members`
- `get_loadbalancer_health_monitors`
- `get_loadbalancer_l7_policies`
- `get_loadbalancer_l7_rules`
- `get_loadbalancer_providers`
- `get_loadbalancer_flavors`
- `get_loadbalancer_availability_zones`
- `get_loadbalancer_quotas`
- `get_loadbalancer_amphorae`

## Recommended Query Pattern

Use summary tools first, then drill down with filters:

- Instances: `get_instance_summary` -> `get_instances_by_status` / `get_instance_by_project` / `get_instance_by_id_or_name`
- Compute unified drill-down: `get_compute_resource`
- Networks: `get_network_summary` -> `get_network_by_project` / `get_network_by_id_or_name`
- Network unified drill-down: `get_network_resource`
- Routers: `get_routers_summary` -> `get_routers_by_status` / `get_routers_by_project`
- Security groups: `get_security_groups_summary` -> `get_security_groups_by_project`
- Floating IPs: `get_floating_ips_summary` -> `get_floating_ips_by_project`
- Volumes: `get_volume_summary` -> `get_volume_by_status` / `get_volume_by_project`
- Snapshots: `get_volume_snapshot_summary` -> `get_volume_snapshot_by_status` / `get_volume_snapshot_by_project`
- Backups: `get_volume_backup_summary` -> `get_volume_backup_by_status` / `get_volume_backup_by_project`
- Load balancer unified drill-down: `get_loadbalancer_resource`
- Listeners can be listed directly with `get_loadbalancer_listeners()` or `get_loadbalancer_resource(resource_type="listener")`; `parent_id` is optional.

For large sites, avoid full list tools unless an export/full audit is really needed. Prefer `limit`, `offset`, `fields`, `project_id`, and `status` filters.

## Environment

Minimal `.env` values:

```bash
MCP_LOG_LEVEL=INFO
PYTHONPATH=/app/src

FASTMCP_TYPE=streamable-http
FASTMCP_HOST=0.0.0.0
FASTMCP_PORT=8000

REMOTE_AUTH_ENABLE=false
REMOTE_SECRET_KEY=your-secure-secret-key

OS_PROJECT_DOMAIN_NAME=Default
OS_USER_DOMAIN_NAME=Default
OS_PROJECT_NAME=admin
OS_TENANT_NAME=admin
OS_USERNAME=view
OS_PASSWORD=your-openstack-password
OS_AUTH_HOST=172.26.32.100
OS_AUTH_PROTOCOL=https
OS_AUTH_PORT=5000
OS_INTERFACE=internal
OS_ENDPOINT_TYPE=internalURL
OS_IDENTITY_API_VERSION=3
OS_REGION_NAME=RegionOne
OS_AUTH_PLUGIN=password

OS_COMPUTE_PORT=8774
OS_NETWORK_PORT=9696
OS_VOLUME_PORT=8776
OS_IMAGE_PORT=9292
OS_PLACEMENT_PORT=8780

MARIADB_HOST=172.26.32.100
MARIADB_PORT=3306
MARIADB_USER=readonly
MARIADB_PASSWORD=your-readonly-password
MARIADB_CHARSET=utf8mb4
MARIADB_CONNECT_TIMEOUT=10
MARIADB_PROJECT_ID=

RABBITMQ_API_URL=http://127.0.0.1:15672/api
RABBITMQ_API_USER=readonly
RABBITMQ_API_PASSWORD=your-readonly-password
RABBITMQ_API_TIMEOUT=10
RABBITMQ_API_VERIFY_TLS=true
```

Do not configure per-service DB names in `.env`; the service database names are fixed in code.

## MariaDB Read-Only User

Example grants for a read-only operational user:

```sql
CREATE USER IF NOT EXISTS 'readonly'@'%' IDENTIFIED BY 'strong_password';
GRANT SELECT, PROCESS, SHOW DATABASES, BINLOG MONITOR, SHOW VIEW ON *.* TO 'readonly'@'%';
GRANT SELECT ON performance_schema.* TO 'readonly'@'%';
FLUSH PRIVILEGES;
SHOW GRANTS FOR 'readonly'@'%';
```

Use a narrower host instead of `%` when possible.

## Run

```bash
docker compose up -d
docker compose logs -f mcp-server
```

The compose file uses registry images:

- `vcr.infiniband.vn/openstack.custom/mcpo-server-openstack-ops:latest`
- `vcr.infiniband.vn/openstack.custom/mcpo-proxy-openstack-ops:latest`

## Development Checks

```bash
python3 -m compileall -q src/mcp_openstack_ops
pyflakes src/mcp_openstack_ops
git diff --check
```

## Important Notes

- `testnet/` is local/untracked test data if present; do not commit it unless explicitly required.
- `get_network_agents` now reads Neutron DB data.
- Volume, snapshot, and backup tools are named consistently under `volume`, `volume_snapshot`, and `volume_backup`.
- Deprecated storage aliases such as `get_volume`, `get_volume_backup`, `get_volume_backups`, `get_volume_snapshots`, and old `get_snapshot*` tools are skipped.
