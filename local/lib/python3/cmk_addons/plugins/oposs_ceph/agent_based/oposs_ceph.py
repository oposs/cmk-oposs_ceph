#!/usr/bin/env python3
"""Ceph cluster monitoring plugin for Checkmk.

Parses three agent sections (status, osd_perf, df) and creates
seven services covering health, OSD status, OSD latency, scrub,
pool usage, PG status, and cluster I/O.
"""

import json
from typing import Any, Dict, List, Mapping

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    check_levels,
    render,
)


# ---------------------------------------------------------------------------
# Parse functions
# ---------------------------------------------------------------------------

def _parse_json_section(string_table: List[List[str]]) -> Dict[str, Any]:
    """Join all lines and parse as a single JSON object."""
    raw = "".join(" ".join(line) for line in string_table)
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


agent_section_oposs_ceph_status = AgentSection(
    name="oposs_ceph_status",
    parse_function=_parse_json_section,
)

agent_section_oposs_ceph_osd_perf = AgentSection(
    name="oposs_ceph_osd_perf",
    parse_function=_parse_json_section,
)

agent_section_oposs_ceph_df = AgentSection(
    name="oposs_ceph_df",
    parse_function=_parse_json_section,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_from_ceph(severity: str) -> State:
    """Map Ceph health severity to Checkmk state."""
    if severity == "HEALTH_ERR":
        return State.CRIT
    if severity == "HEALTH_WARN":
        return State.WARN
    return State.OK


def _render_ms(v: float) -> str:
    """Render seconds as milliseconds."""
    return f"{v * 1000:.1f} ms"


def _render_iops(v: float) -> str:
    return f"{v:.0f}/s"


# ---------------------------------------------------------------------------
# 1. Ceph Health
# ---------------------------------------------------------------------------

def discover_oposs_ceph_health(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    if section_oposs_ceph_status:
        yield Service()


def check_oposs_ceph_health(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    section = section_oposs_ceph_status
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent")
        return

    health = section.get("health", {})
    status = health.get("status", "HEALTH_UNKNOWN")
    state = _state_from_ceph(status)

    checks = health.get("checks", {})
    if not checks:
        yield Result(state=state, summary=status)
        return

    summary_parts = []
    for name, info in checks.items():
        msg = info.get("summary", {}).get("message", name)
        summary_parts.append(msg)

    yield Result(state=state, summary=f"{status}: {'; '.join(summary_parts)}")

    # Details per health check
    for name, info in checks.items():
        sev = info.get("severity", "HEALTH_OK")
        for detail in info.get("detail", []):
            yield Result(
                state=_state_from_ceph(sev),
                notice=detail.get("message", ""),
            )


check_plugin_oposs_ceph_health = CheckPlugin(
    name="oposs_ceph_health",
    service_name="Ceph Health",
    sections=["oposs_ceph_status", "oposs_ceph_osd_perf", "oposs_ceph_df"],
    discovery_function=discover_oposs_ceph_health,
    check_function=check_oposs_ceph_health,
)


# ---------------------------------------------------------------------------
# 2. Ceph OSD Status
# ---------------------------------------------------------------------------

def discover_oposs_ceph_osd_status(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    if section_oposs_ceph_status:
        yield Service()


def check_oposs_ceph_osd_status(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    section = section_oposs_ceph_status
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent")
        return

    osdmap = section.get("osdmap", {})
    num_osds = osdmap.get("num_osds", 0)
    num_up = osdmap.get("num_up_osds", 0)
    num_in = osdmap.get("num_in_osds", 0)
    num_down = num_osds - num_up
    num_out = num_osds - num_in

    if num_down > 0:
        state = State.CRIT
        summary = f"{num_down}/{num_osds} OSDs down"
    elif num_out > 0:
        state = State.WARN
        summary = f"{num_out}/{num_osds} OSDs out"
    else:
        state = State.OK
        summary = f"{num_osds}/{num_osds} OSDs up and in"

    yield Result(state=state, summary=summary)

    yield Metric("oposs_ceph_osd_total", num_osds)
    yield Metric("oposs_ceph_osd_up", num_up)
    yield Metric("oposs_ceph_osd_in", num_in)


check_plugin_oposs_ceph_osd_status = CheckPlugin(
    name="oposs_ceph_osd_status",
    service_name="Ceph OSD Status",
    sections=["oposs_ceph_status", "oposs_ceph_osd_perf", "oposs_ceph_df"],
    discovery_function=discover_oposs_ceph_osd_status,
    check_function=check_oposs_ceph_osd_status,
)


# ---------------------------------------------------------------------------
# 3. Ceph OSD Latency
# ---------------------------------------------------------------------------

def discover_oposs_ceph_osd_latency(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    if section_oposs_ceph_osd_perf:
        yield Service()


def check_oposs_ceph_osd_latency(params, section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    section = section_oposs_ceph_osd_perf
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent")
        return

    infos = section.get("osdstats", {}).get("osd_perf_infos", [])
    if not infos:
        yield Result(state=State.UNKNOWN, summary="No OSD perf data")
        return

    worst_commit = 0.0
    worst_apply = 0.0
    worst_osd_commit = -1
    worst_osd_apply = -1

    for osd in infos:
        osd_id = osd["id"]
        stats = osd.get("perf_stats", {})
        commit_s = stats.get("commit_latency_ms", 0) / 1000.0
        apply_s = stats.get("apply_latency_ms", 0) / 1000.0

        yield Metric(f"oposs_ceph_osd_{osd_id}_commit_latency", commit_s)
        yield Metric(f"oposs_ceph_osd_{osd_id}_apply_latency", apply_s)

        if commit_s > worst_commit:
            worst_commit = commit_s
            worst_osd_commit = osd_id
        if apply_s > worst_apply:
            worst_apply = apply_s
            worst_osd_apply = osd_id

    yield from check_levels(
        worst_commit,
        levels_upper=params.get("commit_latency_levels"),
        metric_name="oposs_ceph_osd_worst_commit_latency",
        label=f"Worst commit latency (OSD {worst_osd_commit})",
        render_func=_render_ms,
    )

    yield from check_levels(
        worst_apply,
        levels_upper=params.get("apply_latency_levels"),
        metric_name="oposs_ceph_osd_worst_apply_latency",
        label=f"Worst apply latency (OSD {worst_osd_apply})",
        render_func=_render_ms,
    )

    # Per-OSD details in long output
    for osd in sorted(infos, key=lambda o: o["id"]):
        osd_id = osd["id"]
        stats = osd.get("perf_stats", {})
        commit = stats.get("commit_latency_ms", 0)
        apply = stats.get("apply_latency_ms", 0)
        yield Result(
            state=State.OK,
            notice=f"OSD {osd_id}: commit {commit} ms, apply {apply} ms",
        )


check_plugin_oposs_ceph_osd_latency = CheckPlugin(
    name="oposs_ceph_osd_latency",
    service_name="Ceph OSD Latency",
    sections=["oposs_ceph_status", "oposs_ceph_osd_perf", "oposs_ceph_df"],
    discovery_function=discover_oposs_ceph_osd_latency,
    check_function=check_oposs_ceph_osd_latency,
    check_ruleset_name="oposs_ceph_osd_latency",
    check_default_parameters={
        "commit_latency_levels": ("fixed", (0.050, 0.100)),
        "apply_latency_levels": ("fixed", (0.050, 0.100)),
    },
)


# ---------------------------------------------------------------------------
# 4. Ceph Scrub
# ---------------------------------------------------------------------------

def discover_oposs_ceph_scrub(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    if section_oposs_ceph_status:
        yield Service()


def check_oposs_ceph_scrub(params, section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    section = section_oposs_ceph_status
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent")
        return

    checks = section.get("health", {}).get("checks", {})

    not_scrubbed = checks.get("PG_NOT_SCRUBBED", {})
    not_deep = checks.get("PG_NOT_DEEP_SCRUBBED", {})

    scrub_count = not_scrubbed.get("summary", {}).get("count", 0)
    deep_count = not_deep.get("summary", {}).get("count", 0)

    yield from check_levels(
        scrub_count,
        levels_upper=params.get("not_scrubbed_levels"),
        metric_name="oposs_ceph_pgs_not_scrubbed",
        label="PGs not scrubbed in time",
        render_func=lambda v: f"{int(v)}",
    )

    yield from check_levels(
        deep_count,
        levels_upper=params.get("not_deep_scrubbed_levels"),
        metric_name="oposs_ceph_pgs_not_deep_scrubbed",
        label="PGs not deep-scrubbed in time",
        render_func=lambda v: f"{int(v)}",
    )

    # Scrubbing activity from PG states
    pgmap = section.get("pgmap", {})
    scrubbing = 0
    deep_scrubbing = 0
    for pg_state in pgmap.get("pgs_by_state", []):
        state_name = pg_state.get("state_name", "")
        count = pg_state.get("count", 0)
        if "scrubbing+deep" in state_name:
            deep_scrubbing += count
        elif "scrubbing" in state_name:
            scrubbing += count

    yield Metric("oposs_ceph_pgs_scrubbing", scrubbing)
    yield Metric("oposs_ceph_pgs_deep_scrubbing", deep_scrubbing)
    yield Result(
        state=State.OK,
        notice=f"Currently scrubbing: {scrubbing}, deep-scrubbing: {deep_scrubbing}",
    )

    # Detail lines for overdue PGs
    for detail in not_scrubbed.get("detail", []):
        yield Result(state=State.OK, notice=detail.get("message", ""))
    for detail in not_deep.get("detail", []):
        yield Result(state=State.OK, notice=detail.get("message", ""))


check_plugin_oposs_ceph_scrub = CheckPlugin(
    name="oposs_ceph_scrub",
    service_name="Ceph Scrub",
    sections=["oposs_ceph_status", "oposs_ceph_osd_perf", "oposs_ceph_df"],
    discovery_function=discover_oposs_ceph_scrub,
    check_function=check_oposs_ceph_scrub,
    check_ruleset_name="oposs_ceph_scrub",
    check_default_parameters={
        "not_scrubbed_levels": ("fixed", (10, 50)),
        "not_deep_scrubbed_levels": ("fixed", (10, 50)),
    },
)


# ---------------------------------------------------------------------------
# 5. Ceph Pool Usage
# ---------------------------------------------------------------------------

def discover_oposs_ceph_pool_usage(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    if section_oposs_ceph_df:
        yield Service()


def check_oposs_ceph_pool_usage(params, section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    section = section_oposs_ceph_df
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent")
        return

    stats = section.get("stats", {})
    total = stats.get("total_bytes", 0)
    used = stats.get("total_used_bytes", 0)
    avail = stats.get("total_avail_bytes", 0)

    if total > 0:
        usage_pct = used / total * 100.0
    else:
        usage_pct = 0.0

    yield from check_levels(
        usage_pct,
        levels_upper=params.get("usage_levels"),
        metric_name="oposs_ceph_cluster_usage_pct",
        label="Cluster usage",
        render_func=render.percent,
        boundaries=(0, 100),
    )

    yield Metric("oposs_ceph_cluster_total_bytes", total)
    yield Metric("oposs_ceph_cluster_used_bytes", used)
    yield Metric("oposs_ceph_cluster_avail_bytes", avail)

    # Per-pool details and metrics
    pools = section.get("pools", [])
    for pool in sorted(pools, key=lambda p: p.get("stats", {}).get("bytes_used", 0), reverse=True):
        pool_name = pool.get("name", "unknown")
        pool_id = pool.get("id", 0)
        pstats = pool.get("stats", {})
        p_used = pstats.get("bytes_used", 0)
        p_stored = pstats.get("stored", 0)
        p_avail = pstats.get("max_avail", 0)
        p_objects = pstats.get("objects", 0)
        p_pct = pstats.get("percent_used", 0) * 100.0

        yield Metric(f"oposs_ceph_pool_{pool_id}_usage_pct", p_pct)
        yield Metric(f"oposs_ceph_pool_{pool_id}_bytes_used", p_used)
        yield Metric(f"oposs_ceph_pool_{pool_id}_stored", p_stored)
        yield Metric(f"oposs_ceph_pool_{pool_id}_objects", p_objects)

        yield Result(
            state=State.OK,
            notice=f"Pool {pool_name} (id={pool_id}): {render.percent(p_pct)} used, "
                   f"{render.bytes(p_stored)} stored, {p_objects} objects",
        )


check_plugin_oposs_ceph_pool_usage = CheckPlugin(
    name="oposs_ceph_pool_usage",
    service_name="Ceph Pool Usage",
    sections=["oposs_ceph_status", "oposs_ceph_osd_perf", "oposs_ceph_df"],
    discovery_function=discover_oposs_ceph_pool_usage,
    check_function=check_oposs_ceph_pool_usage,
    check_ruleset_name="oposs_ceph_pool_usage",
    check_default_parameters={
        "usage_levels": ("fixed", (80.0, 90.0)),
    },
)


# ---------------------------------------------------------------------------
# 6. Ceph PG Status
# ---------------------------------------------------------------------------

def discover_oposs_ceph_pg_status(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    if section_oposs_ceph_status:
        yield Service()


def check_oposs_ceph_pg_status(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    section = section_oposs_ceph_status
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent")
        return

    pgmap = section.get("pgmap", {})
    num_pgs = pgmap.get("num_pgs", 0)
    pgs_by_state = pgmap.get("pgs_by_state", [])

    clean_count = 0
    problematic = []

    for entry in pgs_by_state:
        state_name = entry.get("state_name", "")
        count = entry.get("count", 0)
        # Count PGs that have "active+clean" as their base state (may include scrubbing)
        if state_name.startswith("active+clean"):
            clean_count += count
        else:
            problematic.append((state_name, count))

    yield Metric("oposs_ceph_pg_total", num_pgs)
    yield Metric("oposs_ceph_pg_clean", clean_count)

    if problematic:
        prob_parts = [f"{count} {name}" for name, count in problematic]
        yield Result(
            state=State.WARN,
            summary=f"{clean_count}/{num_pgs} PGs clean, problematic: {', '.join(prob_parts)}",
        )
        for name, count in problematic:
            yield Metric(f"oposs_ceph_pg_state_{name.replace('+', '_')}", count)
    else:
        yield Result(
            state=State.OK,
            summary=f"{clean_count}/{num_pgs} PGs clean",
        )

    # Detail per state
    for entry in pgs_by_state:
        yield Result(
            state=State.OK,
            notice=f"{entry.get('count', 0)} PGs {entry.get('state_name', 'unknown')}",
        )


check_plugin_oposs_ceph_pg_status = CheckPlugin(
    name="oposs_ceph_pg_status",
    service_name="Ceph PG Status",
    sections=["oposs_ceph_status", "oposs_ceph_osd_perf", "oposs_ceph_df"],
    discovery_function=discover_oposs_ceph_pg_status,
    check_function=check_oposs_ceph_pg_status,
)


# ---------------------------------------------------------------------------
# 7. Ceph I/O
# ---------------------------------------------------------------------------

def discover_oposs_ceph_io(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    if section_oposs_ceph_status:
        yield Service()


def check_oposs_ceph_io(section_oposs_ceph_status, section_oposs_ceph_osd_perf, section_oposs_ceph_df):
    section = section_oposs_ceph_status
    if not section:
        yield Result(state=State.UNKNOWN, summary="No data from agent")
        return

    pgmap = section.get("pgmap", {})
    read_bps = pgmap.get("read_bytes_sec", 0)
    write_bps = pgmap.get("write_bytes_sec", 0)
    read_iops = pgmap.get("read_op_per_sec", 0)
    write_iops = pgmap.get("write_op_per_sec", 0)

    yield Metric("oposs_ceph_read_bytes_per_sec", read_bps)
    yield Metric("oposs_ceph_write_bytes_per_sec", write_bps)
    yield Metric("oposs_ceph_read_iops", read_iops)
    yield Metric("oposs_ceph_write_iops", write_iops)

    yield Result(
        state=State.OK,
        summary=f"Read: {render.bytes(read_bps)}/s ({_render_iops(read_iops)}), "
                f"Write: {render.bytes(write_bps)}/s ({_render_iops(write_iops)})",
    )


check_plugin_oposs_ceph_io = CheckPlugin(
    name="oposs_ceph_io",
    service_name="Ceph I/O",
    sections=["oposs_ceph_status", "oposs_ceph_osd_perf", "oposs_ceph_df"],
    discovery_function=discover_oposs_ceph_io,
    check_function=check_oposs_ceph_io,
)
