# Scripts Overview

Tai lieu nay tom tat cac script ho tro local dev va inspection.

## Danh sach scripts

- `mcp-server-docker-cmd.sh`
- Load `.env`, in bien moi truong (mask secret), va chay:
- `python -m mcp_openstack_ops --type ${FASTMCP_TYPE} --host ${FASTMCP_HOST} --port ${FASTMCP_PORT}`

- `run-mcp-inspector-local.sh`
- Chay MCP Inspector voi source local (`PYTHONPATH=./src`) de debug nhanh truoc khi publish package.

- `run-mcp-inspector-pypi.sh`
- Chay MCP Inspector voi package da publish tren PyPI qua `uvx mcp-openstack-ops`.

## Cach dung nhanh

- Tu project root:
- `bash scripts/run-mcp-inspector-local.sh`
- `bash scripts/run-mcp-inspector-pypi.sh`
- `bash scripts/mcp-server-docker-cmd.sh`

## Luu y

- Can co `.env` hop le cho OpenStack credentials khi chay local.
- Script inspector yeu cau `npx` va `@modelcontextprotocol/inspector`.
