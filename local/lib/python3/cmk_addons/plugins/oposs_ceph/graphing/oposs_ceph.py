#!/usr/bin/env python3
"""Graphing definitions for Ceph monitoring.

Only defines explicit Graph objects for aggregate metrics where combining
multiple lines into one chart adds value. Per-OSD and per-pool metrics
are yielded dynamically by the check plugin and auto-graphed by Checkmk.
"""

from cmk.graphing.v1 import Title
from cmk.graphing.v1.graphs import Bidirectional, Graph, MinimalRange
from cmk.graphing.v1.metrics import (
    Color,
    DecimalNotation,
    IECNotation,
    Metric,
    TimeNotation,
    Unit,
)
from cmk.graphing.v1.perfometers import Closed, FocusRange, Perfometer

# -- Units -----------------------------------------------------------------

_UNIT_COUNT = Unit(DecimalNotation(""))
_UNIT_PERCENT = Unit(DecimalNotation("%"))
_UNIT_BYTES = Unit(IECNotation("B"))
_UNIT_BYTES_PER_SEC = Unit(IECNotation("B/s"))
_UNIT_SECONDS = Unit(TimeNotation())
_UNIT_IOPS = Unit(DecimalNotation("/s"))

# -- Cluster usage ---------------------------------------------------------

metric_oposs_ceph_cluster_usage_pct = Metric(
    name="oposs_ceph_cluster_usage_pct",
    title=Title("Cluster Usage"),
    unit=_UNIT_PERCENT,
    color=Color.BLUE,
)

metric_oposs_ceph_cluster_total_bytes = Metric(
    name="oposs_ceph_cluster_total_bytes",
    title=Title("Cluster Total"),
    unit=_UNIT_BYTES,
    color=Color.LIGHT_GRAY,
)

metric_oposs_ceph_cluster_used_bytes = Metric(
    name="oposs_ceph_cluster_used_bytes",
    title=Title("Cluster Used"),
    unit=_UNIT_BYTES,
    color=Color.BLUE,
)

metric_oposs_ceph_cluster_avail_bytes = Metric(
    name="oposs_ceph_cluster_avail_bytes",
    title=Title("Cluster Available"),
    unit=_UNIT_BYTES,
    color=Color.GREEN,
)

graph_oposs_ceph_cluster_capacity = Graph(
    name="oposs_ceph_cluster_capacity",
    title=Title("Ceph Cluster Capacity"),
    simple_lines=[
        "oposs_ceph_cluster_used_bytes",
        "oposs_ceph_cluster_avail_bytes",
        "oposs_ceph_cluster_total_bytes",
    ],
    minimal_range=MinimalRange(lower=0, upper=0),
)

perfometer_oposs_ceph_cluster_usage = Perfometer(
    name="oposs_ceph_cluster_usage",
    focus_range=FocusRange(lower=Closed(0), upper=Closed(100)),
    segments=["oposs_ceph_cluster_usage_pct"],
)

# -- OSD metrics -----------------------------------------------------------

metric_oposs_ceph_osd_total = Metric(
    name="oposs_ceph_osd_total",
    title=Title("OSDs Total"),
    unit=_UNIT_COUNT,
    color=Color.LIGHT_GRAY,
)

metric_oposs_ceph_osd_up = Metric(
    name="oposs_ceph_osd_up",
    title=Title("OSDs Up"),
    unit=_UNIT_COUNT,
    color=Color.GREEN,
)

metric_oposs_ceph_osd_in = Metric(
    name="oposs_ceph_osd_in",
    title=Title("OSDs In"),
    unit=_UNIT_COUNT,
    color=Color.BLUE,
)

metric_oposs_ceph_osd_worst_commit_latency = Metric(
    name="oposs_ceph_osd_worst_commit_latency",
    title=Title("Worst OSD Commit Latency"),
    unit=_UNIT_SECONDS,
    color=Color.ORANGE,
)

metric_oposs_ceph_osd_worst_apply_latency = Metric(
    name="oposs_ceph_osd_worst_apply_latency",
    title=Title("Worst OSD Apply Latency"),
    unit=_UNIT_SECONDS,
    color=Color.RED,
)

graph_oposs_ceph_osd_latency = Graph(
    name="oposs_ceph_osd_latency",
    title=Title("Ceph OSD Worst Latency"),
    simple_lines=[
        "oposs_ceph_osd_worst_commit_latency",
        "oposs_ceph_osd_worst_apply_latency",
    ],
    minimal_range=MinimalRange(lower=0, upper=0),
)

# -- Scrub metrics ---------------------------------------------------------

metric_oposs_ceph_pgs_not_scrubbed = Metric(
    name="oposs_ceph_pgs_not_scrubbed",
    title=Title("PGs Not Scrubbed"),
    unit=_UNIT_COUNT,
    color=Color.ORANGE,
)

metric_oposs_ceph_pgs_not_deep_scrubbed = Metric(
    name="oposs_ceph_pgs_not_deep_scrubbed",
    title=Title("PGs Not Deep-Scrubbed"),
    unit=_UNIT_COUNT,
    color=Color.RED,
)

metric_oposs_ceph_pgs_scrubbing = Metric(
    name="oposs_ceph_pgs_scrubbing",
    title=Title("PGs Scrubbing"),
    unit=_UNIT_COUNT,
    color=Color.GREEN,
)

metric_oposs_ceph_pgs_deep_scrubbing = Metric(
    name="oposs_ceph_pgs_deep_scrubbing",
    title=Title("PGs Deep-Scrubbing"),
    unit=_UNIT_COUNT,
    color=Color.BLUE,
)

graph_oposs_ceph_scrub_backlog = Graph(
    name="oposs_ceph_scrub_backlog",
    title=Title("Ceph Scrub Backlog"),
    simple_lines=[
        "oposs_ceph_pgs_not_scrubbed",
        "oposs_ceph_pgs_not_deep_scrubbed",
    ],
    minimal_range=MinimalRange(lower=0, upper=0),
)

graph_oposs_ceph_scrub_activity = Graph(
    name="oposs_ceph_scrub_activity",
    title=Title("Ceph Scrub Activity"),
    simple_lines=[
        "oposs_ceph_pgs_scrubbing",
        "oposs_ceph_pgs_deep_scrubbing",
    ],
    minimal_range=MinimalRange(lower=0, upper=0),
)

# -- PG metrics ------------------------------------------------------------

metric_oposs_ceph_pg_total = Metric(
    name="oposs_ceph_pg_total",
    title=Title("PGs Total"),
    unit=_UNIT_COUNT,
    color=Color.LIGHT_GRAY,
)

metric_oposs_ceph_pg_clean = Metric(
    name="oposs_ceph_pg_clean",
    title=Title("PGs Clean"),
    unit=_UNIT_COUNT,
    color=Color.GREEN,
)

graph_oposs_ceph_pg = Graph(
    name="oposs_ceph_pg",
    title=Title("Ceph Placement Groups"),
    simple_lines=[
        "oposs_ceph_pg_clean",
        "oposs_ceph_pg_total",
    ],
    minimal_range=MinimalRange(lower=0, upper=0),
)

# -- I/O metrics -----------------------------------------------------------

metric_oposs_ceph_read_bytes_per_sec = Metric(
    name="oposs_ceph_read_bytes_per_sec",
    title=Title("Client Read Throughput"),
    unit=_UNIT_BYTES_PER_SEC,
    color=Color.GREEN,
)

metric_oposs_ceph_write_bytes_per_sec = Metric(
    name="oposs_ceph_write_bytes_per_sec",
    title=Title("Client Write Throughput"),
    unit=_UNIT_BYTES_PER_SEC,
    color=Color.BLUE,
)

metric_oposs_ceph_read_iops = Metric(
    name="oposs_ceph_read_iops",
    title=Title("Client Read IOPS"),
    unit=_UNIT_IOPS,
    color=Color.GREEN,
)

metric_oposs_ceph_write_iops = Metric(
    name="oposs_ceph_write_iops",
    title=Title("Client Write IOPS"),
    unit=_UNIT_IOPS,
    color=Color.BLUE,
)

graph_oposs_ceph_throughput = Bidirectional(
    name="oposs_ceph_throughput",
    title=Title("Ceph Client Throughput"),
    lower=Graph(
        name="oposs_ceph_throughput_write",
        title=Title("Write"),
        compound_lines=["oposs_ceph_write_bytes_per_sec"],
    ),
    upper=Graph(
        name="oposs_ceph_throughput_read",
        title=Title("Read"),
        compound_lines=["oposs_ceph_read_bytes_per_sec"],
    ),
)

graph_oposs_ceph_iops = Bidirectional(
    name="oposs_ceph_iops",
    title=Title("Ceph Client IOPS"),
    lower=Graph(
        name="oposs_ceph_iops_write",
        title=Title("Write"),
        compound_lines=["oposs_ceph_write_iops"],
    ),
    upper=Graph(
        name="oposs_ceph_iops_read",
        title=Title("Read"),
        compound_lines=["oposs_ceph_read_iops"],
    ),
)
