#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_cost_and_logging.py
# Description: Cost-per-cycle arithmetic and the log-level mapping. The rate is
#              pence/kWh, so a pounds/pence mix-up under-reports by 100x in
#              silence. And Indigo silently ignores a STRING log level, which
#              hid every warning this plugin raised until v1.7.0.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import logging

import pytest

from conftest import FakeVariable

T0 = 1784600000


def _finish_cycle(plugin, dev, src, kwh=2.0, peak_w=2000.0, minutes=60):
    dev.states["cycleStartedAt"] = T0
    plugin.runtime[dev.id] = {"peak": peak_w, "kwh_start": 0.0, "above": 0}
    src.states["energyKwhToday"] = kwh
    plugin._enter_door_wait(dev, finished_at=T0 + minutes * 60,
                            src=src, energy_key="energyKwhToday")
    return dev.states


def _with_rate(indigo_mod, dev, value):
    indigo_mod.variables["rate_var"] = FakeVariable("rate_var", value)
    dev.pluginProps["rateVariableName"] = "rate_var"


# --------------------------------------------------------------------------
# Cost arithmetic — the rate is PENCE per kWh
# --------------------------------------------------------------------------

def test_cost_is_pence_per_kwh_not_pounds(plugin, appliance, meter, indigo_mod):
    _with_rate(indigo_mod, appliance, "26.46")
    states = _finish_cycle(plugin, appliance, meter, kwh=2.0)
    # 2.0 kWh x 26.46p = 52.92p = £0.5292
    assert states["lastCycleCostGbp"] == pytest.approx(0.529, abs=0.001)
    assert states["lastCycleRateP"] == pytest.approx(26.46)


def test_no_rate_variable_means_no_cost(plugin, appliance, meter):
    states = _finish_cycle(plugin, appliance, meter, kwh=2.0)
    assert states["lastCycleCostGbp"] == 0.0
    assert states["lastCycleCostGbp.ui"] == "—"


def test_unreadable_rate_variable_warns_and_skips_costing(
        plugin, appliance, meter, indigo_mod):
    appliance.pluginProps["rateVariableName"] = "does_not_exist"
    states = _finish_cycle(plugin, appliance, meter, kwh=2.0)
    assert states["lastCycleCostGbp"] == 0.0
    warnings = [m for m, lvl in indigo_mod.server.lines if lvl == logging.WARNING]
    assert any("unreadable" in m for m in warnings)


def test_non_numeric_rate_variable_does_not_raise(plugin, appliance, meter, indigo_mod):
    _with_rate(indigo_mod, appliance, "not a number")
    states = _finish_cycle(plugin, appliance, meter, kwh=2.0)
    assert states["lastCycleCostGbp"] == 0.0


# --------------------------------------------------------------------------
# Rate sanity band — catches a pounds/pence mix-up and a stale sentinel
# --------------------------------------------------------------------------

@pytest.mark.parametrize("rate", ["0.2646", "0.0", "-5", "5000", "99999"])
def test_rate_outside_the_sane_band_is_refused(plugin, appliance, meter, indigo_mod, rate):
    _with_rate(indigo_mod, appliance, rate)
    states = _finish_cycle(plugin, appliance, meter, kwh=2.0)
    assert states["lastCycleCostGbp"] == 0.0


@pytest.mark.parametrize("rate", ["1.0", "26.46", "75.5", "199.9"])
def test_rate_inside_the_sane_band_is_used(plugin, appliance, meter, indigo_mod, rate):
    _with_rate(indigo_mod, appliance, rate)
    states = _finish_cycle(plugin, appliance, meter, kwh=2.0)
    assert states["lastCycleCostGbp"] > 0.0


def test_a_pounds_per_kwh_mixup_is_caught_and_warned(plugin, appliance, meter, indigo_mod):
    """0.2646 £/kWh is the same tariff expressed wrongly — must not silently
    under-report the cost by two orders of magnitude."""
    _with_rate(indigo_mod, appliance, "0.2646")
    _finish_cycle(plugin, appliance, meter, kwh=2.0)
    warnings = [m for m, lvl in indigo_mod.server.lines if lvl == logging.WARNING]
    assert any("outside the sane band" in m for m in warnings)


# --------------------------------------------------------------------------
# Log-level mapping — Indigo drops a STRING level silently
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name, expected", [
    ("INFO",    logging.INFO),
    ("WARNING", logging.WARNING),
    ("ERROR",   logging.ERROR),
    ("DEBUG",   logging.DEBUG),
    ("warning", logging.WARNING),      # case-insensitive
])
def test_level_names_map_to_real_logging_ints(plugin_mod, indigo_mod, name, expected):
    plugin_mod.log("hello", level=name)
    assert indigo_mod.server.lines[-1][1] == expected


def test_unknown_level_falls_back_to_info(plugin_mod, indigo_mod):
    plugin_mod.log("hello", level="SHOUTING")
    assert indigo_mod.server.lines[-1][1] == logging.INFO


def test_an_int_level_passes_straight_through(plugin_mod, indigo_mod):
    plugin_mod.log("hello", level=logging.ERROR)
    assert indigo_mod.server.lines[-1][1] == logging.ERROR


def test_log_carries_a_millisecond_timestamp(plugin_mod, indigo_mod):
    import re
    plugin_mod.log("hello")
    assert re.match(r"^\[\d{2}:\d{2}:\d{2}\.\d{3}\] hello$", indigo_mod.server.lines[-1][0])


def test_a_string_level_is_never_passed_to_indigo(plugin_mod, indigo_mod):
    """The actual defect. Indigo ignores a string and logs it as Info."""
    for name in ("WARNING", "ERROR", "DEBUG", "INFO"):
        plugin_mod.log("x", level=name)
    assert all(isinstance(lvl, int) for _, lvl in indigo_mod.server.lines)
