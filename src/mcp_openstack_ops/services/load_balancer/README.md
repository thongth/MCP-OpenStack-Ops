# Load Balancer Services Overview

This directory contains read-oriented Octavia helpers.

## Modules

- `core.py`: `get_load_balancer_list`, `get_load_balancer_details`, `get_load_balancer_by_vip`, `get_load_balancer_by_floatingip`
- `listeners.py`: `get_load_balancer_listeners`
- `pools.py`: `get_load_balancer_pools`, `get_load_balancer_pool_members`
- `health_monitors.py`: `get_load_balancer_health_monitors`
- `l7_policies.py`: `get_load_balancer_l7_policies`, `get_load_balancer_l7_rules`
- `management.py`: `get_load_balancer_availability_zones`, `get_load_balancer_flavors`, `get_load_balancer_providers`, `get_load_balancer_quotas`
- `amphorae.py`: `get_load_balancer_amphorae`

## Notes

- MCP-exposed load balancer tools are read-only.
- Some code paths tolerate Octavia schema differences between deployments.
- Detail output serializes datetime values before returning JSON.
- Amphora-related detail may include linked Nova instance information when available.
