"""Metric names: prefixed, declared, and used by the graphs."""

import importlib.util
import json
import pathlib
import re
import sys

import pytest
from cmk.agent_based.v2 import Metric
from cmk.graphing.v1 import graphs, metrics, perfometers

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_ceph"
DATA = pathlib.Path(__file__).resolve().parent / "data"

# Per-OSD, per-pool and per-PG-state metrics carry an id in the name and
# are graphed by Checkmk without a declaration.
DYNAMIC = re.compile(r"^oposs_ceph_(osd_\d+_|pool_\d+_|pg_state_)")


def _load(path):
    name = "test_graphing_" + path.stem + "_" + path.parent.name
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def check():
    return _load(PLUGIN / "agent_based/oposs_ceph.py")


@pytest.fixture(scope="module")
def graphing_objects():
    objects = []
    for path in sorted((PLUGIN / "graphing").glob("*.py")):
        objects.extend(vars(_load(path)).values())
    return objects


@pytest.fixture(scope="module")
def declared(graphing_objects):
    return {o.name for o in graphing_objects if isinstance(o, metrics.Metric)}


@pytest.fixture(scope="module")
def emitted(check):
    """Every metric the seven checks yield on the degraded cluster."""
    sections = tuple(
        check._parse_json_section([[(DATA / f).read_text()]])
        for f in ("status_warn.json", "osd_perf.json", "df_detail.json")
    )
    names = []
    for attr in sorted(vars(check)):
        if not attr.startswith("check_plugin_"):
            continue
        plugin = getattr(check, attr)
        if plugin.check_default_parameters is None:
            out = plugin.check_function(*sections)
        else:
            out = plugin.check_function(plugin.check_default_parameters, *sections)
        names.extend(m.name for m in out if isinstance(m, Metric))
    return names


def test_every_emitted_metric_is_prefixed(emitted):
    assert emitted
    assert [n for n in emitted if not n.startswith("oposs_ceph_")] == []


def test_every_fixed_metric_is_declared(emitted, declared):
    fixed = {n for n in emitted if not DYNAMIC.match(n)}
    assert sorted(fixed - declared) == []


def test_every_declared_metric_is_emitted(emitted, declared):
    assert sorted(declared - set(emitted)) == []


def test_each_metric_is_emitted_once(emitted):
    assert len(emitted) == len(set(emitted))


def test_every_declared_name_is_prefixed(graphing_objects):
    kinds = (metrics.Metric, graphs.Graph, graphs.Bidirectional, perfometers.Perfometer)
    names = [o.name for o in graphing_objects if isinstance(o, kinds)]
    for o in graphing_objects:
        if isinstance(o, graphs.Bidirectional):
            names += [o.lower.name, o.upper.name]
    assert names
    assert [n for n in names if not n.startswith("oposs_ceph_")] == []


def test_graphs_and_perfometers_use_declared_metrics(graphing_objects, declared):
    used = set()
    graph_list = []
    for o in graphing_objects:
        if isinstance(o, graphs.Graph):
            graph_list.append(o)
        elif isinstance(o, graphs.Bidirectional):
            graph_list += [o.lower, o.upper]
        elif isinstance(o, perfometers.Perfometer):
            used.update(o.segments)
    for g in graph_list:
        used.update(g.simple_lines)
        used.update(g.compound_lines)
    assert used
    assert sorted(used - declared) == []


def test_degraded_state_metric_name(emitted):
    assert "oposs_ceph_pg_state_active_undersized_degraded" in emitted
    json.dumps(emitted)  # plain strings only
