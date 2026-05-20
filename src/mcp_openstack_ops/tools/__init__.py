"""Tool registration utilities for OpenStack MCP."""

import importlib
import pkgutil
from typing import Iterable

DISABLED_ALIAS_MODULES = {
    "get_snapshot",
    "get_snapshot_by_id_or_name",
    "get_snapshot_by_project",
    "get_snapshot_by_status",
    "get_volume",
    "get_volume_by_name",
    "get_volume_backup",
    "get_volume_backups",
    "get_volume_snapshots",
}

def _iter_tool_modules() -> Iterable[str]:
    """Yield importable tool module names within this package."""
    for module_info in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        name = module_info.name
        if name.startswith('_'):
            continue
        # Skip old aliases if a stale image still contains their modules.
        if name in DISABLED_ALIAS_MODULES:
            continue
        # Enforce read-only MCP mode: do not register any mutating tools.
        if name.startswith('set_'):
            continue
        yield name

def register_all_tools() -> None:
    """Import every tool module so decorators register with FastMCP."""
    for module_name in sorted(_iter_tool_modules()):
        importlib.import_module(f"{__name__}.{module_name}")
