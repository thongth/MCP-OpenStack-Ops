# Load Balancer Services Overview

This directory contains read-oriented Octavia helpers.

## Modules

- `core.py`: `get_loadbalancer_list`, `get_loadbalancer_details`, `get_loadbalancer_by_vip`, `get_loadbalancer_by_floatingip`
- `listeners.py`: `get_loadbalancer_listeners`
- `pools.py`: `get_loadbalancer_pools`, `get_loadbalancer_pool_members`
- `health_monitors.py`: `get_loadbalancer_health_monitors`
- `l7_policies.py`: `get_loadbalancer_l7_policies`, `get_loadbalancer_l7_rules`
- `management.py`: `get_loadbalancer_availability_zones`, `get_loadbalancer_flavors`, `get_loadbalancer_providers`, `get_loadbalancer_quotas`
- `amphorae.py`: `get_loadbalancer_amphorae`

## Notes

- MCP-exposed load balancer tools are read-only.
- Some code paths tolerate Octavia schema differences between deployments.
- Detail output serializes datetime values before returning JSON.
- Amphora-related detail may include linked Nova instance information when available.
