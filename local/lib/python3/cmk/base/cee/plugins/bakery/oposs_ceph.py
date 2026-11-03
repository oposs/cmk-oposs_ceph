"""Bakery plugin for deploying the Ceph monitoring agent plugin."""

from pathlib import Path
from typing import Any

from cmk.base.plugins.bakery.bakery_api.v1 import (
    OS,
    Plugin,
    register,
)


def get_oposs_ceph_files(conf: dict[str, Any]):
    """Deploy the oposs_ceph agent plugin."""
    if conf is None:
        return

    interval = int(conf.get("interval", 60))

    yield Plugin(
        base_os=OS.LINUX,
        source=Path("oposs_ceph"),
        target=Path("oposs_ceph"),
        interval=interval,
    )


register.bakery_plugin(
    name="oposs_ceph",
    files_function=get_oposs_ceph_files,
)
