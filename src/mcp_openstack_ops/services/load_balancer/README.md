# Load Balancer Services Overview

Tai lieu nay tom tat nhom service `src/mcp_openstack_ops/services/load_balancer/` (Octavia).

## Modules

- `core.py`
- Chuc nang: CRUD load balancers va lay detail/list
- Ham chinh: `get_load_balancer_list`, `get_load_balancer_details`, `set_load_balancer`

- `listeners.py`
- Chuc nang: quan ly listeners
- Ham chinh: `get_load_balancer_listeners`, `set_load_balancer_listener`

- `pools.py`
- Chuc nang: quan ly pools va members
- Ham chinh: `get_load_balancer_pools`, `set_load_balancer_pool`, `get_load_balancer_pool_members`, `set_load_balancer_pool_member`

- `health_monitors.py`
- Chuc nang: monitor health cho pools
- Ham chinh: `get_load_balancer_health_monitors`, `set_load_balancer_health_monitor`

- `l7_policies.py`
- Chuc nang: L7 policies va rules
- Ham chinh: `get_load_balancer_l7_policies`, `set_load_balancer_l7_policy`, `get_load_balancer_l7_rules`, `set_load_balancer_l7_rule`

- `management.py`
- Chuc nang: provider-level management
- Ham chinh: `get_load_balancer_availability_zones`, `set_load_balancer_availability_zone`, `get_load_balancer_flavors`, `set_load_balancer_flavor`, `get_load_balancer_providers`, `get_load_balancer_quotas`, `set_load_balancer_quota`

- `amphorae.py`
- Chuc nang: amphora listing va action operations
- Ham chinh: `get_load_balancer_amphorae`, `set_load_balancer_amphora`

## Ghi chu

- Nhom `get_*` la read-oriented.
- Nhom `set_*` la modify-oriented va phu thuoc safety gate cua MCP server.

