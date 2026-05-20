# Scripts Overview

Helper scripts for local development and inspection.

## Scripts

- `mcp-server-docker-cmd.sh`
  - Loads `.env`, masks secrets in startup output, and runs `python -m mcp_openstack_ops`.
- `run-mcp-inspector-local.sh`
  - Runs MCP Inspector against local source with `PYTHONPATH=./src`.
- `run-mcp-inspector-pypi.sh`
  - Runs MCP Inspector through `uvx mcp-openstack-ops`.

## Usage

Run from the repository root:

```bash
bash scripts/run-mcp-inspector-local.sh
bash scripts/run-mcp-inspector-pypi.sh
bash scripts/mcp-server-docker-cmd.sh
```

## Requirements

- A valid `.env`.
- OpenStack credentials for SDK-backed helpers.
- MariaDB readonly credentials for Nova/Neutron/Cinder DB-backed helpers.
- `npx` and `@modelcontextprotocol/inspector` for inspector scripts.
