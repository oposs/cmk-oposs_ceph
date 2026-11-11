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

    # 0 means every agent run (see the rule help). An interval puts the
    # plugin into plugins/<interval>/, and the agent runs only
    # plugins/[1-9]*/, so 0 must mean no interval at all.
    yield Plugin(
        base_os=OS.LINUX,
        source=Path("oposs_ceph"),
        target=Path("oposs_ceph"),
        interval=interval if interval > 0 else None,
    )


register.bakery_plugin(
    name="oposs_ceph",
    files_function=get_oposs_ceph_files,
)
