"""The bakery deploys the agent plugin with the interval from the rule."""

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BAKERY = ROOT / "local/lib/python3/cmk/base/cee/plugins/bakery/oposs_ceph.py"
AGENT = ROOT / "local/share/check_mk/agents/plugins/oposs_ceph"


@pytest.fixture(scope="module")
def bakery():
    name = "test_oposs_ceph_bakery"
    spec = importlib.util.spec_from_file_location(name, BAKERY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(name, None)


def test_default_interval(bakery):
    (plugin,) = bakery.get_oposs_ceph_files({})
    assert plugin.kwargs["source"].name == AGENT.name
    assert plugin.kwargs["target"].name == AGENT.name
    assert plugin.kwargs["interval"] == 60
    assert plugin.kwargs["base_os"] == bakery.OS.LINUX


def test_interval_from_the_rule(bakery):
    # TimeSpan hands the bakery a float in seconds
    (plugin,) = bakery.get_oposs_ceph_files({"interval": 300.0})
    assert plugin.kwargs["interval"] == 300


def test_no_rule_no_files(bakery):
    assert list(bakery.get_oposs_ceph_files(None)) == []
