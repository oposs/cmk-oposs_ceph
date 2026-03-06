#!/usr/bin/env python3
"""Rulesets for Ceph monitoring: check parameter thresholds and bakery config."""

from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    Float,
    Integer,
    SimpleLevels,
    LevelDirection,
    TimeSpan,
    TimeMagnitude,
)
from cmk.rulesets.v1.rule_specs import (
    AgentConfig,
    CheckParameters,
    HostCondition,
    Topic,
)


# ---------------------------------------------------------------------------
# Check parameter rulesets
# ---------------------------------------------------------------------------

def _form_oposs_ceph_osd_latency():
    return Dictionary(
        title=Title("Ceph OSD Latency Thresholds"),
        elements={
            "commit_latency_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("Commit latency"),
                    help_text=Help("Worst OSD commit latency thresholds"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(unit_symbol="s"),
                    prefill_fixed_levels=DefaultValue((0.050, 0.100)),
                ),
            ),
            "apply_latency_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("Apply latency"),
                    help_text=Help("Worst OSD apply latency thresholds"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(unit_symbol="s"),
                    prefill_fixed_levels=DefaultValue((0.050, 0.100)),
                ),
            ),
        },
    )


rule_spec_oposs_ceph_osd_latency = CheckParameters(
    title=Title("Ceph OSD Latency"),
    topic=Topic.STORAGE,
    name="oposs_ceph_osd_latency",
    parameter_form=_form_oposs_ceph_osd_latency,
    condition=HostCondition(),
)


def _form_oposs_ceph_scrub():
    return Dictionary(
        title=Title("Ceph Scrub Thresholds"),
        elements={
            "not_scrubbed_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("PGs not scrubbed in time"),
                    help_text=Help("Number of PGs overdue for regular scrub"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(unit_symbol="PGs"),
                    prefill_fixed_levels=DefaultValue((10, 50)),
                ),
            ),
            "not_deep_scrubbed_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("PGs not deep-scrubbed in time"),
                    help_text=Help("Number of PGs overdue for deep scrub"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Integer(unit_symbol="PGs"),
                    prefill_fixed_levels=DefaultValue((10, 50)),
                ),
            ),
        },
    )


rule_spec_oposs_ceph_scrub = CheckParameters(
    title=Title("Ceph Scrub"),
    topic=Topic.STORAGE,
    name="oposs_ceph_scrub",
    parameter_form=_form_oposs_ceph_scrub,
    condition=HostCondition(),
)


def _form_oposs_ceph_pool_usage():
    return Dictionary(
        title=Title("Ceph Pool Usage Thresholds"),
        elements={
            "usage_levels": DictElement(
                parameter_form=SimpleLevels(
                    title=Title("Cluster usage"),
                    help_text=Help("Overall cluster capacity usage thresholds"),
                    level_direction=LevelDirection.UPPER,
                    form_spec_template=Float(unit_symbol="%"),
                    prefill_fixed_levels=DefaultValue((80.0, 90.0)),
                ),
            ),
        },
    )


rule_spec_oposs_ceph_pool_usage = CheckParameters(
    title=Title("Ceph Pool Usage"),
    topic=Topic.STORAGE,
    name="oposs_ceph_pool_usage",
    parameter_form=_form_oposs_ceph_pool_usage,
    condition=HostCondition(),
)


# ---------------------------------------------------------------------------
# Bakery ruleset
# ---------------------------------------------------------------------------

def _form_oposs_ceph_bakery():
    return Dictionary(
        title=Title("Ceph Monitoring Agent Plugin"),
        help_text=Help("Deploy the Ceph monitoring agent plugin to hosts with ceph CLI access"),
        elements={
            "interval": DictElement(
                parameter_form=TimeSpan(
                    title=Title("Collection interval"),
                    help_text=Help("How often to collect Ceph data (0 = every agent run)"),
                    displayed_magnitudes=[
                        TimeMagnitude.MINUTE,
                        TimeMagnitude.SECOND,
                    ],
                    prefill=DefaultValue(60.0),
                ),
            ),
        },
    )


rule_spec_oposs_ceph_bakery = AgentConfig(
    name="oposs_ceph",
    title=Title("Ceph Monitoring (Linux)"),
    topic=Topic.STORAGE,
    parameter_form=_form_oposs_ceph_bakery,
)
