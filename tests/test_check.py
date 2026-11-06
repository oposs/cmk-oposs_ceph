"""The seven Ceph check plugins, fed with agent output.

tests/data/ holds `ceph status -f json`, `ceph osd perf -f json` and
`ceph df detail -f json` output in the shape Ceph 18 (Reef) prints it: a
12-OSD cluster, once healthy and once with one OSD down. The agent prints
each one under a `sep(0)` header, so every line of it arrives as a
one-element row of the string table.
"""

import copy
import importlib.util
import json
import pathlib
import re
import sys

import pytest
from cmk.agent_based.v2 import Metric, Result, Service, State

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHECK = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_ceph/agent_based/oposs_ceph.py"
DATA = pathlib.Path(__file__).resolve().parent / "data"


@pytest.fixture(scope="module")
def check():
    name = "test_oposs_ceph_check"
    spec = importlib.util.spec_from_file_location(name, CHECK)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(name, None)


def _raw(name):
    return (DATA / name).read_text()


def _table(text):
    """The string table Checkmk builds for a sep(0) section."""
    return [[line] for line in text.splitlines()]


def _load(name):
    return json.loads(_raw(name))


@pytest.fixture
def ok(check):
    return (
        check._parse_json_section(_table(_raw("status_ok.json"))),
        check._parse_json_section(_table(_raw("osd_perf.json"))),
        check._parse_json_section(_table(_raw("df_detail.json"))),
    )


@pytest.fixture
def warn(check):
    return (
        check._parse_json_section(_table(_raw("status_warn.json"))),
        check._parse_json_section(_table(_raw("osd_perf.json"))),
        check._parse_json_section(_table(_raw("df_detail.json"))),
    )


def _results(out):
    return [r for r in out if isinstance(r, Result)]


def _metrics(out):
    return {m.name: m.value for m in out if isinstance(m, Metric)}


def _worst(out):
    return State.worst(*(r.state for r in _results(out)))


SERVICES = ("health", "osd_status", "osd_latency", "scrub", "pool_usage", "pg_status", "io")


def _defaults(check, service):
    return getattr(check, f"check_plugin_oposs_ceph_{service}").check_default_parameters


def _run(check, service, sections, params=None):
    fn = getattr(check, f"check_oposs_ceph_{service}")
    if _defaults(check, service) is None:
        return list(fn(*sections))
    return list(fn(params if params is not None else _defaults(check, service), *sections))


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def test_parse_single_line_json(check):
    parsed = check._parse_json_section(_table(_raw("status_ok.json")))
    assert parsed == _load("status_ok.json")


def test_parse_pretty_printed_json(check):
    # `ceph ... -f json-pretty` spreads the object over many lines
    pretty = json.dumps(_load("df_detail.json"), indent=4)
    assert len(_table(pretty)) > 50
    assert check._parse_json_section(_table(pretty)) == _load("df_detail.json")


@pytest.mark.parametrize("table", [
    [],
    [[""]],
    [["   "]],
    [["Error initializing cluster client: ObjectNotFound('RADOS object not found (error calling conf_read_file)')"]],
    [['{"health": {"status": "HEALTH_OK"']],  # cut off mid-object
])
def test_parse_garbage_gives_empty_section(check, table):
    assert check._parse_json_section(table) == {}


def test_each_section_has_its_parser(check):
    for name in ("status", "osd_perf", "df"):
        section = getattr(check, f"agent_section_oposs_ceph_{name}")
        assert section.name == f"oposs_ceph_{name}"
        assert section.parse_function is check._parse_json_section


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------


@pytest.mark.parametrize("service", SERVICES)
def test_discovery_finds_one_service_each(check, ok, service):
    fn = getattr(check, f"discover_oposs_ceph_{service}")
    assert list(fn(*ok)) == [Service()]


@pytest.mark.parametrize("service", SERVICES)
def test_no_service_without_data(check, service):
    # The ceph command failed: headers are there, the sections are empty
    fn = getattr(check, f"discover_oposs_ceph_{service}")
    assert list(fn({}, {}, {})) == []
    assert list(fn(None, None, None)) == []


def test_discovery_follows_the_section_each_service_reads(check, ok):
    status, perf, df = ok
    only_status = {s for s in SERVICES if list(getattr(check, f"discover_oposs_ceph_{s}")(status, None, None))}
    assert only_status == {"health", "osd_status", "scrub", "pg_status", "io"}
    assert list(check.discover_oposs_ceph_osd_latency(None, perf, None)) == [Service()]
    assert list(check.discover_oposs_ceph_pool_usage(None, None, df)) == [Service()]


def test_service_names(check):
    names = {getattr(check, f"check_plugin_oposs_ceph_{s}").service_name for s in SERVICES}
    assert names == {
        "Ceph Health", "Ceph OSD Status", "Ceph OSD Latency", "Ceph Scrub",
        "Ceph Pool Usage", "Ceph PG Status", "Ceph I/O",
    }


# --------------------------------------------------------------------------
# Missing data at check time
# --------------------------------------------------------------------------


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.parametrize("empty", [None, {}])
def test_missing_section_is_unknown(check, service, empty):
    out = _run(check, service, (empty, empty, empty))
    assert out == [Result(state=State.UNKNOWN, summary="No data from agent")]


def test_latency_without_osds_is_unknown(check):
    out = _run(check, "osd_latency", ({}, {"osdstats": {"osd_perf_infos": []}}, {}))
    assert out == [Result(state=State.UNKNOWN, summary="No OSD perf data")]


# --------------------------------------------------------------------------
# Ceph Health
# --------------------------------------------------------------------------


def test_health_ok(check, ok):
    assert _run(check, "health", ok) == [Result(state=State.OK, summary="HEALTH_OK")]


def test_health_warn_lists_every_check(check, warn):
    (result,) = _run(check, "health", warn)
    assert result.state is State.WARN
    assert result.summary.startswith("HEALTH_WARN: 1 osds down; Degraded data redundancy")
    assert "62 pgs not deep-scrubbed in time" in result.summary


def test_health_err_is_crit(check, ok):
    status = copy.deepcopy(ok[0])
    status["health"] = {
        "status": "HEALTH_ERR",
        "checks": {
            "OSD_SCRUB_ERRORS": {"severity": "HEALTH_ERR", "summary": {"message": "2 scrub errors", "count": 2}},
            "PG_DAMAGED": {"severity": "HEALTH_ERR",
                           "summary": {"message": "Possible data damage: 1 pg inconsistent", "count": 1}},
        },
        "mutes": [],
    }
    (result,) = _run(check, "health", (status, None, None))
    assert result.state is State.CRIT
    assert result.summary == "HEALTH_ERR: 2 scrub errors; Possible data damage: 1 pg inconsistent"


def test_health_detail_lines_get_their_own_severity(check, ok):
    # `ceph health detail -f json` adds a detail list to each check
    status = copy.deepcopy(ok[0])
    status["health"] = {
        "status": "HEALTH_WARN",
        "checks": {"OSD_DOWN": {
            "severity": "HEALTH_WARN",
            "summary": {"message": "1 osds down", "count": 1},
            "detail": [{"message": "osd.5 (root=default,host=ceph-osd2) is down"}],
        }},
    }
    out = _run(check, "health", (status, None, None))
    assert out[1] == Result(state=State.WARN, notice="osd.5 (root=default,host=ceph-osd2) is down")


def test_health_unknown_status_string(check):
    assert _run(check, "health", ({"health": {}}, None, None)) == [
        Result(state=State.OK, summary="HEALTH_UNKNOWN")]


# --------------------------------------------------------------------------
# Ceph OSD Status
# --------------------------------------------------------------------------


def test_osd_status_all_up(check, ok):
    out = _run(check, "osd_status", ok)
    assert _results(out) == [Result(state=State.OK, summary="12/12 OSDs up and in")]
    assert _metrics(out) == {"oposs_ceph_osd_total": 12, "oposs_ceph_osd_up": 12, "oposs_ceph_osd_in": 12}


def test_osd_down_is_crit(check, warn):
    out = _run(check, "osd_status", warn)
    assert _results(out) == [Result(state=State.CRIT, summary="1/12 OSDs down")]
    assert _metrics(out)["oposs_ceph_osd_up"] == 11


def test_osd_out_is_warn(check, ok):
    status = copy.deepcopy(ok[0])
    status["osdmap"]["num_in_osds"] = 10
    assert _results(_run(check, "osd_status", (status, None, None))) == [
        Result(state=State.WARN, summary="2/12 OSDs out")]


def test_osd_down_wins_over_out(check, warn):
    status = copy.deepcopy(warn[0])
    status["osdmap"]["num_in_osds"] = 11
    assert _worst(_run(check, "osd_status", (status, None, None))) is State.CRIT


# --------------------------------------------------------------------------
# Ceph OSD Latency
# --------------------------------------------------------------------------


def test_latency_ok_names_the_worst_osd(check, ok):
    out = _run(check, "osd_latency", ok)
    summaries = [r.summary for r in _results(out) if r.summary]
    assert summaries == ["Worst commit latency (OSD 5): 12.0 ms", "Worst apply latency (OSD 5): 12.0 ms"]
    assert _worst(out) is State.OK


def test_latency_metrics_are_seconds(check, ok):
    metrics = _metrics(_run(check, "osd_latency", ok))
    assert metrics["oposs_ceph_osd_worst_commit_latency"] == pytest.approx(0.012)
    assert metrics["oposs_ceph_osd_worst_apply_latency"] == pytest.approx(0.012)
    assert metrics["oposs_ceph_osd_9_commit_latency"] == pytest.approx(0.007)
    assert metrics["oposs_ceph_osd_6_apply_latency"] == 0.0
    assert len([n for n in metrics if n.endswith("_commit_latency") and "worst" not in n]) == 12


def test_latency_details_are_sorted_by_osd(check, ok):
    notices = [r.details for r in _results(_run(check, "osd_latency", ok)) if not r.summary]
    osd_lines = [n for n in notices if n.startswith("OSD ")]
    assert osd_lines[0] == "OSD 0: commit 4 ms, apply 4 ms"
    assert osd_lines[-1] == "OSD 11: commit 4 ms, apply 4 ms"
    assert len(osd_lines) == 12


@pytest.mark.parametrize("ms, state", [(49, State.OK), (50, State.WARN), (99, State.WARN), (100, State.CRIT), (850, State.CRIT)])
def test_latency_default_levels(check, ok, ms, state):
    perf = copy.deepcopy(ok[1])
    perf["osdstats"]["osd_perf_infos"][3]["perf_stats"].update(commit_latency_ms=ms, apply_latency_ms=1)
    out = _run(check, "osd_latency", (None, perf, None))
    commit = [r for r in _results(out) if r.summary.startswith("Worst commit")]
    assert commit[0].state is state
    assert "OSD 8" in commit[0].summary


def test_apply_latency_has_its_own_levels(check, ok):
    perf = copy.deepcopy(ok[1])
    perf["osdstats"]["osd_perf_infos"][0]["perf_stats"]["apply_latency_ms"] = 30
    params = {"commit_latency_levels": ("no_levels", None), "apply_latency_levels": ("fixed", (0.010, 0.020))}
    out = _run(check, "osd_latency", (None, perf, None), params)
    apply = [r for r in _results(out) if r.summary.startswith("Worst apply")]
    assert apply[0].state is State.CRIT
    assert apply[0].summary.startswith("Worst apply latency (OSD 11): 30.0 ms")


def test_latency_levels_off(check, ok):
    perf = copy.deepcopy(ok[1])
    perf["osdstats"]["osd_perf_infos"][0]["perf_stats"]["commit_latency_ms"] = 5000
    params = {"commit_latency_levels": ("no_levels", None), "apply_latency_levels": ("no_levels", None)}
    assert _worst(_run(check, "osd_latency", (None, perf, None), params)) is State.OK


def test_latency_all_zero_names_a_real_osd(check, ok):
    perf = copy.deepcopy(ok[1])
    for osd in perf["osdstats"]["osd_perf_infos"]:
        osd["perf_stats"].update(commit_latency_ms=0, apply_latency_ms=0)
    out = _run(check, "osd_latency", (None, perf, None))
    summaries = [r.summary for r in _results(out) if r.summary]
    # Ceph lists the OSDs from the highest id down; the first one is named
    assert summaries == ["Worst commit latency (OSD 11): 0.0 ms", "Worst apply latency (OSD 11): 0.0 ms"]
    assert _metrics(out)["oposs_ceph_osd_worst_commit_latency"] == 0.0


# --------------------------------------------------------------------------
# Ceph Scrub
# --------------------------------------------------------------------------


def test_scrub_ok(check, ok):
    out = _run(check, "scrub", ok)
    assert _worst(out) is State.OK
    metrics = _metrics(out)
    assert metrics == {
        "oposs_ceph_pgs_not_scrubbed": 0,
        "oposs_ceph_pgs_not_deep_scrubbed": 0,
        "oposs_ceph_pgs_scrubbing": 1,
        "oposs_ceph_pgs_deep_scrubbing": 3,
    }
    assert Result(state=State.OK, notice="Currently scrubbing: 1, deep-scrubbing: 3") in out


def test_scrub_backlog_from_health_checks(check, warn):
    out = _run(check, "scrub", warn)
    by_label = {r.summary.split(":")[0]: r.state for r in _results(out) if r.summary}
    # 14 not scrubbed is between 10 and 50, 62 not deep-scrubbed is above 50
    assert by_label == {"PGs not scrubbed in time": State.WARN, "PGs not deep-scrubbed in time": State.CRIT}
    assert _metrics(out)["oposs_ceph_pgs_not_deep_scrubbed"] == 62


@pytest.mark.parametrize("count, state", [(9, State.OK), (10, State.WARN), (49, State.WARN), (50, State.CRIT)])
def test_scrub_default_levels(check, ok, count, state):
    status = copy.deepcopy(ok[0])
    status["health"]["checks"]["PG_NOT_SCRUBBED"] = {
        "severity": "HEALTH_WARN", "summary": {"message": f"{count} pgs not scrubbed in time", "count": count}}
    out = _run(check, "scrub", (status, None, None))
    (result,) = [r for r in _results(out) if r.summary.startswith("PGs not scrubbed")]
    assert result.state is state


def test_scrub_levels_off(check, warn):
    params = {"not_scrubbed_levels": ("no_levels", None), "not_deep_scrubbed_levels": ("no_levels", None)}
    assert _worst(_run(check, "scrub", warn, params)) is State.OK


# --------------------------------------------------------------------------
# Ceph Pool Usage
# --------------------------------------------------------------------------


def test_pool_usage_ok(check, ok):
    out = _run(check, "pool_usage", ok)
    assert _worst(out) is State.OK
    metrics = _metrics(out)
    assert metrics["oposs_ceph_cluster_usage_pct"] == pytest.approx(33.432, abs=0.001)
    assert metrics["oposs_ceph_cluster_total_bytes"] == 52776558133248
    assert metrics["oposs_ceph_cluster_used_bytes"] == 17644316499968
    assert metrics["oposs_ceph_cluster_avail_bytes"] == 35132241633280
    assert metrics["oposs_ceph_pool_2_usage_pct"] == pytest.approx(32.7048, abs=0.001)
    assert metrics["oposs_ceph_pool_2_stored"] == 5512334680064
    assert metrics["oposs_ceph_pool_3_objects"] == 217565
    assert metrics["oposs_ceph_pool_1_bytes_used"] == 136458240


def test_pool_details_biggest_first(check, ok):
    notices = [r.details for r in _results(_run(check, "pool_usage", ok)) if not r.summary]
    assert [n.split(" (")[0] for n in notices] == ["Pool rbd", "Pool cephfs.data", "Pool .mgr"]
    assert notices[0].startswith("Pool rbd (id=2): 32.70% used, ")
    assert notices[0].endswith(" stored, 2101245 objects")


@pytest.mark.parametrize("used_pct, state", [(79.9, State.OK), (80.0, State.WARN), (89.9, State.WARN), (90.0, State.CRIT)])
def test_pool_usage_default_levels(check, ok, used_pct, state):
    df = copy.deepcopy(ok[2])
    df["stats"]["total_bytes"] = 10**12
    df["stats"]["total_used_bytes"] = round(used_pct * 10**10)
    (result, *_) = _results(_run(check, "pool_usage", (None, None, df)))
    assert result.summary.startswith("Cluster usage: ")
    assert result.state is state


def test_pool_usage_empty_cluster(check):
    df = {"stats": {"total_bytes": 0, "total_used_bytes": 0, "total_avail_bytes": 0}, "pools": []}
    out = _run(check, "pool_usage", (None, None, df))
    assert _metrics(out)["oposs_ceph_cluster_usage_pct"] == 0.0
    assert _worst(out) is State.OK


# --------------------------------------------------------------------------
# Ceph PG Status
# --------------------------------------------------------------------------


def test_pg_status_scrubbing_counts_as_clean(check, ok):
    out = _run(check, "pg_status", ok)
    assert _results(out)[0] == Result(state=State.OK, summary="545/545 PGs clean")
    assert _metrics(out) == {"oposs_ceph_pg_total": 545, "oposs_ceph_pg_clean": 545}
    assert Result(state=State.OK, notice="3 PGs active+clean+scrubbing+deep") in out


def test_pg_status_degraded_is_warn(check, warn):
    out = _run(check, "pg_status", warn)
    assert _results(out)[0] == Result(
        state=State.WARN, summary="508/545 PGs clean, problematic: 37 active+undersized+degraded")
    assert _metrics(out)["oposs_ceph_pg_state_active_undersized_degraded"] == 37


def test_pg_status_inconsistent_is_not_clean(check, ok):
    status = copy.deepcopy(ok[0])
    status["pgmap"]["pgs_by_state"] = [
        {"state_name": "active+clean", "count": 544},
        {"state_name": "active+clean+inconsistent", "count": 1},
    ]
    out = _run(check, "pg_status", (status, None, None))
    assert _results(out)[0] == Result(
        state=State.WARN, summary="544/545 PGs clean, problematic: 1 active+clean+inconsistent")
    assert _metrics(out)["oposs_ceph_pg_state_active_clean_inconsistent"] == 1


@pytest.mark.parametrize("state_name", [
    "active+clean+scrubbing+deep+inconsistent+repair",
    "active+clean+inconsistent+failed_repair",
    "active+clean+snaptrim_error",
])
def test_pg_status_other_damage_flags_are_not_clean(check, ok, state_name):
    status = copy.deepcopy(ok[0])
    status["pgmap"]["pgs_by_state"] = [
        {"state_name": "active+clean", "count": 544},
        {"state_name": state_name, "count": 1},
    ]
    assert _worst(_run(check, "pg_status", (status, None, None))) is State.WARN


@pytest.mark.parametrize("state_name", [
    "active+clean+snaptrim", "active+clean+snaptrim_wait", "active+clean+scrubbing+deep",
])
def test_pg_status_maintenance_flags_stay_clean(check, ok, state_name):
    status = copy.deepcopy(ok[0])
    status["pgmap"]["pgs_by_state"] = [
        {"state_name": "active+clean", "count": 544},
        {"state_name": state_name, "count": 1},
    ]
    assert _results(_run(check, "pg_status", (status, None, None)))[0] == Result(
        state=State.OK, summary="545/545 PGs clean")


# --------------------------------------------------------------------------
# Ceph I/O
# --------------------------------------------------------------------------


def test_io(check, ok):
    out = _run(check, "io", ok)
    assert _metrics(out) == {
        "oposs_ceph_read_bytes_per_sec": 48523264,
        "oposs_ceph_write_bytes_per_sec": 12582912,
        "oposs_ceph_read_iops": 1260,
        "oposs_ceph_write_iops": 418,
    }
    (result,) = _results(out)
    assert result.state is State.OK
    assert result.summary == "Read: 46.3 MiB/s (1260/s), Write: 12.0 MiB/s (418/s)"


def test_io_idle_cluster(check, ok):
    # Ceph leaves the rate keys out of pgmap when there is no client I/O
    status = copy.deepcopy(ok[0])
    for key in ("read_bytes_sec", "write_bytes_sec", "read_op_per_sec", "write_op_per_sec"):
        del status["pgmap"][key]
    out = _run(check, "io", (status, None, None))
    assert set(_metrics(out).values()) == {0}
    assert _results(out)[0].summary == "Read: 0 B/s (0/s), Write: 0 B/s (0/s)"


# --------------------------------------------------------------------------
# Cluster mode
# --------------------------------------------------------------------------


@pytest.mark.parametrize("service", SERVICES)
def test_cluster_uses_the_node_with_data(check, ok, service):
    status, perf, df = ok
    nodes = (
        {"ceph-mon1": None, "ceph-mon2": status},
        {"ceph-mon1": None, "ceph-mon2": perf},
        {"ceph-mon1": None, "ceph-mon2": df},
    )
    plugin = getattr(check, f"check_plugin_oposs_ceph_{service}")
    if plugin.check_default_parameters is None:
        clustered = list(plugin.cluster_check_function(*nodes))
    else:
        clustered = list(plugin.cluster_check_function(plugin.check_default_parameters, *nodes))
    assert clustered == _run(check, service, ok)


def test_cluster_without_any_data_is_unknown(check):
    nodes = ({"ceph-mon1": {}, "ceph-mon2": None}, {}, {})
    assert list(check.cluster_check_oposs_ceph_health(*nodes)) == [
        Result(state=State.UNKNOWN, summary="No data from agent")]


def test_pick_node_tolerates_missing_side_sections(check, ok):
    assert check._pick_node_sections({"n1": ok[0]}, None, None) == (ok[0], {}, {})


def test_check_carries_the_released_version():
    # The publish check fails on main when a version file disagrees with
    # the newest released CHANGES.md heading.
    released = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGES.md").read_text(),
                         flags=re.MULTILINE).group(1)
    assert re.search(rf'^__version__ = "{re.escape(released)}"$', CHECK.read_text(), flags=re.MULTILINE)


def test_release_writes_version_into_check(tmp_path):
    """Apply the version_files entry of .github/repo-infra.json to the check
    module, as Create release PR does (a multiline regex, first match)"""
    config = json.loads((ROOT / ".github/repo-infra.json").read_text())
    (spec,) = [f for f in config["version_files"] if (ROOT / f["path"]) == CHECK]
    stamped = re.sub(spec["pattern"], spec["replacement"].replace("$VERSION", "9.8.7"),
                     CHECK.read_text(), count=1, flags=re.MULTILINE)
    assert re.search(spec["verify"].replace("$VERSION", re.escape("9.8.7")), stamped, flags=re.MULTILINE)
    copy = tmp_path / "stamped_check.py"
    copy.write_text(stamped)
    module_spec = importlib.util.spec_from_file_location("stamped_check", copy)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    assert module.__version__ == "9.8.7"
