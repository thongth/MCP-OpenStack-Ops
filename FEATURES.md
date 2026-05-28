# MCP-OpenStack-Ops Features

## Overview

This repository exposes read-only MCP tools for OpenStack operations. It is optimized for reporting, troubleshooting, and health checks in production environments.

## Current Capabilities

- Compute/Nova instance lookup, summaries, events, server groups, hypervisor data, and availability zones.
- Network/Neutron networks, ports, routers, security groups, floating IPs, network agents, and summaries.
- Storage/Cinder volumes, volume types, snapshots, backups, server volume attachments, and summaries.
- Glance image lookup and search.
- Keystone project, user, role assignment, and keypair lookup.
- Barbican secret, container, and order metadata lookup. Secret payloads are intentionally omitted.
- Octavia load balancer, listener, pool, member, health monitor, L7 policy/rule, provider, flavor, quota, and amphora lookup.
- Monitoring and quota helpers for usage and resource reporting.

## Data Backend

- Nova, Neutron, and Cinder read tools use MariaDB queries through a shared read-only connection.
- Database names are fixed by service: `nova`, `neutron`, and `cinder`.
- Tools no longer expose `include_all_projects`; use explicit filters instead.
- Summary tools are preferred before detail/list tools in large environments.

## Removed / Disabled

- Heat/orchestration tools.
- `get_service_status`.
- Synthetic Glance-only service status output.
- Mutating `set_*` MCP tools.
- Deprecated storage aliases that caused duplicate tool names.

## Recommended Usage

- Use summaries first: `get_instance_summary`, `get_network_summary`, `get_volume_summary`, `get_volume_snapshot_summary`, `get_volume_backup_summary`.
- Use filtered detail tools for investigation: by `project_id`, `status`, `id/name`, `limit`, `offset`, and `fields`.
- Use unified resource tools when the user asks broadly by domain: `get_compute_resource`, `get_network_resource`, `get_storage_resource`, `get_loadbalancer_resource`, `get_barbican_resource`.
- Avoid full backup/snapshot lists on large sites unless exporting or auditing.
