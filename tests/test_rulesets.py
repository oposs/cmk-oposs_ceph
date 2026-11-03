"""The rule forms build, and every check default has a matching form field."""

import importlib.util
import pathlib
import sys

import pytest
from cmk.rulesets.v1 import form_specs, rule_specs

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "local/lib/python3/cmk_addons/plugins/oposs_ceph"

WITH_PARAMS = ("osd_latency", "scrub", "pool_usage")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rulesets():
    return _load(PLUGIN / "rulesets/oposs_ceph.py", "test_oposs_ceph_rulesets")


@pytest.fixture(scope="module")
def check():
    return _load(PLUGIN / "agent_based/oposs_ceph.py", "test_oposs_ceph_check_rs")


@pytest.mark.parametrize("service", WITH_PARAMS)
def test_check_names_its_ruleset(rulesets, check, service):
    rule = getattr(rulesets, f"rule_spec_oposs_ceph_{service}")
    plugin = getattr(check, f"check_plugin_oposs_ceph_{service}")
    assert isinstance(rule, rule_specs.CheckParameters)
    assert plugin.check_ruleset_name == rule.name


@pytest.mark.parametrize("service", WITH_PARAMS)
def test_services_without_item_use_host_condition(rulesets, service):
    rule = getattr(rulesets, f"rule_spec_oposs_ceph_{service}")
    assert isinstance(rule.condition, rule_specs.HostCondition)


@pytest.mark.parametrize("service", WITH_PARAMS)
def test_defaults_match_form(rulesets, check, service):
    form = getattr(rulesets, f"rule_spec_oposs_ceph_{service}").parameter_form()
    defaults = getattr(check, f"check_plugin_oposs_ceph_{service}").check_default_parameters
    assert set(defaults) == set(form.elements)
    for key, default in defaults.items():
        spec = form.elements[key].parameter_form
        assert isinstance(spec, form_specs.SimpleLevels), key
        assert default[0] == "fixed", key
        assert spec.prefill_fixed_levels.value == default[1], key


def test_services_without_params_have_no_ruleset(check):
    for service in ("health", "osd_status", "pg_status", "io"):
        plugin = getattr(check, f"check_plugin_oposs_ceph_{service}")
        assert plugin.check_ruleset_name is None
        assert plugin.check_default_parameters is None


def test_bakery_form(rulesets):
    rule = rulesets.rule_spec_oposs_ceph_bakery
    assert isinstance(rule, rule_specs.AgentConfig)
    assert rule.name == "oposs_ceph"
    form = rule.parameter_form()
    assert set(form.elements) == {"interval"}
    assert form.elements["interval"].parameter_form.prefill.value == 60.0
