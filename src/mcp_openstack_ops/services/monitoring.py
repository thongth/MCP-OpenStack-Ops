"""MariaDB-backed monitoring service functions."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def get_system_information() -> Dict[str, Any]:
    try:
        return {
            "success": True,
            "system": {
                "data_source": "mariadb",
            },
        }
    except Exception as e:
        logger.error(f"Failed to get system information from DB: {e}")
        return {"success": False, "error": str(e)}


def get_resource_monitoring() -> Dict[str, Any]:
    try:
        from .compute import get_instance_summary
        from .image import get_image_list_filtered
        from .network import (
            get_floating_ips_summary,
            get_network_summary,
            get_routers_summary,
            get_security_groups_summary,
        )
        from .storage import get_volume_backup_summary, get_volume_snapshot_summary, get_volume_summary

        images = get_image_list_filtered(limit=1)
        return {
            "success": True,
            "resources": {
                "compute": get_instance_summary(),
                "network": {
                    "networks": get_network_summary(),
                    "floating_ips": get_floating_ips_summary(),
                    "routers": get_routers_summary(),
                    "security_groups": get_security_groups_summary(),
                },
                "storage": {
                    "volumes": get_volume_summary(),
                    "snapshots": get_volume_snapshot_summary(),
                    "backups": get_volume_backup_summary(),
                },
                "image": {
                    "total": images.get("total_count", 0),
                    "data_source": "mariadb",
                },
            },
            "data_source": "mariadb",
        }
    except Exception as e:
        logger.error(f"Failed to get resource monitoring from DB: {e}")
        return {"success": False, "error": str(e)}


def get_compute_quota_usage(conn=None) -> Dict[str, Any]:
    return {
        "success": True,
        "message": "Compute quota usage is reported through MariaDB resource summaries.",
        "compute": get_resource_monitoring().get("resources", {}).get("compute", {}),
        "data_source": "mariadb",
    }


def get_usage_statistics(start_date: str = "", end_date: str = "") -> Dict[str, Any]:
    result = get_resource_monitoring()
    result["usage_window"] = {"start_date": start_date, "end_date": end_date}
    return result


def get_quota(project_name: str = "") -> Dict[str, Any]:
    try:
        from .identity import get_project_list

        return {
            "success": True,
            "message": "Quota values are not fetched through OpenStack SDK; project scope is returned from Keystone DB.",
            "project_filter": project_name,
            "projects": get_project_list(name_filter=project_name).get("projects", []),
            "data_source": "mariadb",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_hypervisor_details(hypervisor_name: str = "all") -> Dict[str, Any]:
    try:
        from .compute import _get_nova_mariadb_connection, _table_columns

        conn = _get_nova_mariadb_connection()
        try:
            with conn.cursor() as cur:
                columns = _table_columns(cur, "compute_nodes")
                if not columns:
                    raise RuntimeError("MariaDB table 'compute_nodes' is not available")
                sql = "SELECT * FROM compute_nodes"
                params = []
                if hypervisor_name and hypervisor_name != "all":
                    sql += " WHERE hypervisor_hostname = %s OR host = %s"
                    params.extend([hypervisor_name, hypervisor_name])
                sql += " ORDER BY hypervisor_hostname ASC"
                cur.execute(sql, params)
                hypervisors = [dict(row, data_source="mariadb") for row in cur.fetchall()]
                return {"success": True, "hypervisors": hypervisors, "count": len(hypervisors)}
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Failed to get hypervisor details from DB: {e}")
        return {"success": False, "error": str(e), "hypervisors": []}


def get_availability_zones() -> Dict[str, Any]:
    try:
        hypervisors = get_hypervisor_details().get("hypervisors", [])
        zones: Dict[str, int] = {}
        for hypervisor in hypervisors:
            zone = hypervisor.get("availability_zone") or "nova"
            zones[zone] = zones.get(zone, 0) + 1
        return {
            "success": True,
            "availability_zones": [{"name": name, "host_count": count} for name, count in sorted(zones.items())],
            "zone_count": len(zones),
            "data_source": "mariadb",
        }
    except Exception as e:
        return {"success": False, "error": str(e), "availability_zones": []}


def set_quota(project_name: str, service: str, **kwargs) -> Dict[str, Any]:
    return {
        "success": False,
        "message": "Quota modification is disabled in the MariaDB read-only tool set.",
        "project_name": project_name,
        "service": service,
    }
