# Load Balancer Services Overview

Tai lieu nay tom tat nhom service `src/mcp_openstack_ops/services/load_balancer/` (Octavia).

## Modules

- `core.py`
- Chuc nang: lay danh sach va chi tiet load balancers
- Ham chinh: `get_load_balancer_list`, `get_load_balancer_details`

- `listeners.py`
- Chuc nang: lay danh sach listeners
- Ham chinh: `get_load_balancer_listeners`

- `pools.py`
- Chuc nang: lay danh sach pools va members
- Ham chinh: `get_load_balancer_pools`, `get_load_balancer_pool_members`

- `health_monitors.py`
- Chuc nang: lay health monitors cho pools
- Ham chinh: `get_load_balancer_health_monitors`

- `l7_policies.py`
- Chuc nang: lay L7 policies va rules
- Ham chinh: `get_load_balancer_l7_policies`, `get_load_balancer_l7_rules`

- `management.py`
- Chuc nang: provider-level management
- Ham chinh: `get_load_balancer_availability_zones`, `get_load_balancer_flavors`, `get_load_balancer_providers`, `get_load_balancer_quotas`

- `amphorae.py`
- Chuc nang: amphora listing
- Ham chinh: `get_load_balancer_amphorae`

## Ghi chu

- Nhom `get_*` la read-oriented.
