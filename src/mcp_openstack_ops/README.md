# MCP OpenStack Ops Package

Tai lieu nay mo ta cau truc va vai tro cua package `src/mcp_openstack_ops/`.

## Thanh phan chinh

- `__main__.py`: entrypoint de chay bang `python -m mcp_openstack_ops`.
- `mcp_main.py`: khoi tao FastMCP server, auth, safety gate, va register tool modules.
- `connection.py`: quan ly OpenStack connection cache, env loading, project isolation, ownership validation.
- `functions.py`: bridge/helper functions de reuse trong nhieu luong xu ly.
- `prompt_template.md`: prompt nen cho MCP server behavior.
- `services/`: business logic theo tung OpenStack domain.
- `tools/`: MCP tool wrappers (schema va callable entry points cho model).

## Luong xu ly tong quan

1. MCP server duoc khoi tao trong `mcp_main.py`.
2. `tools.register_all_tools()` import tat ca tool modules.
3. Moi tool goi ham service tuong ung.
4. Service su dung `connection.py` de truy cap OpenStack SDK va enforce security rules.

## Co che an toan

- `ALLOW_MODIFY_OPERATIONS=false` (mac dinh): chan cac thao tac modify.
- `ALLOW_ALL_PROJECTS_READONLY=true`: cho phep read-only cross-project listing (modify bi ep disable).

## Tai lieu lien quan

- Service catalog: `src/mcp_openstack_ops/services/README.md`
- Tool catalog: `src/mcp_openstack_ops/tools/README.md`

