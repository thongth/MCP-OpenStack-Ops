# MCP OpenStack Ops Package

Package `mcp_openstack_ops` contains the MCP server, tool wrappers, and OpenStack service query logic.

## Main Files

- `__main__.py`: entrypoint for `python -m mcp_openstack_ops`.
- `mcp_main.py`: initializes FastMCP, logging, remote auth, and automatic tool registration.
- `connection.py`: OpenStack SDK connection cache and project helper functions.
- `functions.py`: compatibility re-export module used by existing tool wrappers.
- `services/`: domain logic for compute, network, storage, image, identity, monitoring, and load balancer data.
- `tools/`: MCP tool modules. Each file registers one read-only tool.
- `prompt_template.md`: operational prompt guidance for MCP clients.

## Runtime Model

1. `mcp_main.py` starts the FastMCP server.
2. `tools.register_all_tools()` imports every allowed module in `tools/`.
3. Tool modules call functions from `functions.py` or directly from `services/`.
4. Service modules return formatted read-only data.

## Data Access

- Compute/Nova, network/Neutron, and storage/Cinder use MariaDB read queries.
- Database names are fixed in service code: `nova`, `neutron`, `cinder`.
- Image, identity, monitoring, and selected Octavia helpers may use OpenStack SDK.

## Tool Policy

- Registered MCP tools are read-only.
- `set_*` modules are skipped by tool discovery.
- Deprecated aliases are skipped to avoid duplicate tools.
- Heat and `get_service_status` are removed.

## Related Docs

- Service catalog: `src/mcp_openstack_ops/services/README.md`
- Tool catalog: `src/mcp_openstack_ops/tools/README.md`
- Load balancer services: `src/mcp_openstack_ops/services/load_balancer/README.md`
