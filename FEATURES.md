# MCP-OpenStack-Ops Features

## Overview
MCP-OpenStack-Ops is a Model Context Protocol server designed for safe, project-scoped OpenStack operations and monitoring. It provides a wide range of read and write tools while enforcing tenant boundaries and configurable safety gates.

## Core Features

- **Project-Scoped Operations**: All tools are scoped to the configured `OS_PROJECT_NAME`, preventing cross-tenant access.
- **Safety-Gated Writes**: Mutating tools (`set_*`) are only registered when `ALLOW_MODIFY_OPERATIONS=true`, making default deployments read-only.
- **Wide OpenStack Coverage**: Supports compute, networking, storage, image, identity, orchestration, monitoring, and load balancer operations.
- **Bulk & Filtered Actions**: Accepts comma-separated lists and filter conditions for bulk resource targeting.
- **Monitoring & Usage Insights**: Includes tools for service status, resource consumption, usage statistics, and quota monitoring.
- **Unified Instance Queries**: Consolidated instance lookup with pagination, summary/detail modes, and flexible targeting.
- **Audit-Friendly Diagnostics**: Access to server events, hypervisor details, availability zones, project details, and role assignments.
- **Load Balancer Support**: Octavia integration for listeners, pools, members, health monitors, providers, flavors, and quotas.
- **Connection Flexibility**: Supports proxy routing and service-specific endpoint configuration for bastion or multi-project deployments.

## Safety & Deployment

- `ALLOW_MODIFY_OPERATIONS=false` by default to keep the server read-only.
- Connection caching reduces repeated authentication overhead while automatically resetting invalid sessions.
- Works with both `stdio` and `streamable-http` transport modes.

## Target OpenStack Releases

- Primary target: **OpenStack Epoxy (2025.1)**
- Compatible with modern OpenStack releases such as Dalmatian, Caracal, and Bobcat.

## Recommended Usage

- Use the new `set_*` tools for bulk lifecycle and configuration updates.
- Use `get_*` tools for unified and filtered resource discovery.
- Combine status and monitoring tools to quickly diagnose project-level health and capacity.

## Notes

- This repository is designed for production-safe OpenStack management within a single tenant/project.
- Feature expansion can be added by extending `src/mcp_openstack_ops/functions.py`, `src/mcp_openstack_ops/mcp_main.py`, and the tooling modules in `src/mcp_openstack_ops/tools/`.
