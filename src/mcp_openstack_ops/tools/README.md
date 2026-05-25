# Tools Overview

Each file in this directory registers one MCP tool. Tool discovery is automatic through `tools/__init__.py`.

## Registration Rules

- Read-only `get_*` and `search_*` tools are registered.
- `set_*` modules are skipped.
- Deprecated alias modules are skipped to avoid duplicate tools.
- Removed tools are not available: Heat tools and `get_service_status`.

## Compute

- `get_instance.py`
- `get_compute_resource.py`
- `get_instance_by_id_or_name.py`
- `get_instance_by_project.py`
- `get_instance_details.py`
- `get_instance_related_info.py`
- `get_instance_summary.py`
- `get_instances_by_status.py`
- `search_instances.py`
- `get_server_events.py`
- `get_server_groups.py`
- `get_server_volumes.py`
- `get_hypervisor_details.py`
- `get_availability_zones.py`

## Network

- `get_network.py`
- `get_network_resource.py`
- `get_network_by_id_or_name.py`
- `get_network_by_project.py`
- `get_network_details.py`
- `get_port.py`
- `get_network_ports.py`
- `get_network_summary.py`
- `get_network_agents.py`
- `get_floating_ip_pools.py`
- `get_floating_ips.py`
- `get_floating_ips_by_project.py`
- `get_floating_ips_summary.py`
- `get_security_groups.py`
- `get_security_groups_by_project.py`
- `get_security_groups_summary.py`
- `get_routers_by_id_or_name.py`
- `get_routers_by_project.py`
- `get_routers_by_state.py`
- `get_routers_by_status.py`
- `get_routers_details.py`
- `get_routers_summary.py`

## Storage / Cinder

### Volume

- `get_storage_resource.py`
- `get_volume_list.py`
- `get_volume_by_id_or_name.py`
- `get_volume_by_project.py`
- `get_volume_by_status.py`
- `get_volume_summary.py`
- `get_volume_types.py`
- `get_server_volumes.py`

### Volume Snapshot

- `get_volume_snapshot_list.py`
- `get_volume_snapshot_by_id_or_name.py`
- `get_volume_snapshot_by_project.py`
- `get_volume_snapshot_by_status.py`
- `get_volume_snapshot_summary.py`

### Volume Backup

- `get_volume_backup_list.py`
- `get_volume_backup_by_id_or_name.py`
- `get_volume_backup_by_project.py`
- `get_volume_backup_by_status.py`
- `get_volume_backup_summary.py`

## Image

- `get_image_list.py`
- `get_image_detail_list.py`
- `get_image_by_id_or_name.py`
- `get_image_by_project.py`
- `get_image_by_status.py`
- `search_images.py`

## Identity / Project

- `get_project_details.py`
- `get_project_list.py`
- `get_user_list.py`
- `get_role_assignments.py`
- `get_keypair_list.py`

## Monitoring / Quota

- `get_system_information.py`
- `get_resource_monitoring.py`
- `get_usage_statistics.py`
- `get_quota.py`

## MariaDB Cluster

- `mariadb_cluster_health.py`
- `mariadb_cluster_replication_overview.py`
- `mariadb_cluster_connection_stats.py`
- `mariadb_cluster_query_performance.py`
- `mariadb_cluster_storage_utilization.py`
- `mariadb_cluster_capacity_summary.py`
- `mariadb_cluster_top_slow_queries.py`
- `mariadb_cluster_top_tables.py`
- `mariadb_cluster_alerts.py`
- `mariadb_cluster_wsrep_status.py`

## RabbitMQ Cluster

- `rabbitmq_cluster_overview.py`
- `rabbitmq_cluster_health.py`
- `rabbitmq_cluster_nodes.py`
- `rabbitmq_cluster_queues.py`
- `rabbitmq_cluster_queues_without_consumers.py`
- `rabbitmq_cluster_top_queues.py`
- `rabbitmq_cluster_connections.py`
- `rabbitmq_cluster_channels.py`
- `rabbitmq_cluster_consumers.py`
- `rabbitmq_cluster_exchanges.py`
- `rabbitmq_cluster_vhosts.py`
- `rabbitmq_cluster_alerts.py`

## Load Balancer / Octavia

- `get_loadbalancer_list.py`
- `get_loadbalancer_resource.py`
- `get_loadbalancer_details.py`
- `get_loadbalancer_by_vip.py`
- `get_loadbalancer_by_floatingip.py`
- `get_loadbalancer_listeners.py`
- `get_loadbalancer_pools.py`
- `get_loadbalancer_pool_members.py`
- `get_loadbalancer_health_monitors.py`
- `get_loadbalancer_l7_policies.py`
- `get_loadbalancer_l7_rules.py`
- `get_loadbalancer_providers.py`
- `get_loadbalancer_flavors.py`
- `get_loadbalancer_availability_zones.py`
- `get_loadbalancer_quotas.py`
- `get_loadbalancer_amphorae.py`

## Notes

- Use summary tools before list/detail tools on large sites.
- Use filters such as `project_id`, `status`, `id/name`, `limit`, `offset`, and `fields` where supported.
- Do not reintroduce duplicate storage aliases unless tool registration is also updated.
