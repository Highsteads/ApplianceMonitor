#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_offline_finalisation.py
# Description: The meter going offline part-way through the end of a cycle used
#              to throw the whole cycle away. Also covers the deviceOnline
#              string coercion and the clock-step-back clamp.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import logging

T0 = 1_700_000_000


def _mid_cycle(plugin, appliance, meter, state="finishing"):
    appliance.states.update({
        "cycleState":     state,
        "cycleStartedAt": T0,
        "lowSince":       T0 + 3600,
    })
    plugin.runtime[appliance.id] = {"peak": 2100.0, "kwh_start": 5.0, "above": 0}
    meter.states["energyKwhToday"] = 5.9


def test_offline_while_finishing_records_the_cycle_before_going_off(
        plugin, appliance, meter, monkeypatch, caplog):
    import plugin as plugin_mod
    monkeypatch.setattr(plugin_mod.time, "time", lambda: T0 + 3700)
    _mid_cycle(plugin, appliance, meter)
    meter.states["deviceOnline"] = False
    with caplog.at_level(logging.INFO, logger="appliancemonitor.test"):
        plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "off"
    # The cycle it was in the middle of is now on record.
    assert appliance.states["lastCycleMinutes"] == 60
    assert appliance.states["lastCyclePeakWatts"] == 2100.0
    assert round(appliance.states["lastCycleEnergyKwh"], 3) == 0.9
    assert any("recording the cycle now" in r.getMessage() for r in caplog.records)


def test_offline_while_running_is_still_ignored(plugin, appliance, meter, monkeypatch):
    """Deliberate v1.2.5 behaviour — a mid-cycle blip must not drop tracking."""
    import plugin as plugin_mod
    monkeypatch.setattr(plugin_mod.time, "time", lambda: T0 + 100)
    _mid_cycle(plugin, appliance, meter, state="running")
    meter.states["powerWatts"]   = 2000.0
    meter.states["deviceOnline"] = False
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "running"


def test_offline_in_doorwait_before_the_alert_says_so(plugin, appliance, meter,
                                                      monkeypatch, caplog):
    import plugin as plugin_mod
    monkeypatch.setattr(plugin_mod.time, "time", lambda: T0 + 3700)
    appliance.states.update({"cycleState": "doorWait", "doorNotified": False,
                             "cycleFinishedAt": T0 + 3600})
    meter.states["deviceOnline"] = False
    with caplog.at_level(logging.INFO, logger="appliancemonitor.test"):
        plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "off"
    assert any("without one" in r.getMessage() for r in caplog.records)


def test_offline_in_idle_just_goes_off(plugin, appliance, meter, monkeypatch):
    import plugin as plugin_mod
    monkeypatch.setattr(plugin_mod.time, "time", lambda: T0)
    meter.states["deviceOnline"] = False
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "off"
    assert "lastCycleMinutes" not in appliance.states


def test_the_string_false_counts_as_offline(plugin, appliance, meter, monkeypatch):
    """A third-party plugin can publish the state as a string."""
    import plugin as plugin_mod
    monkeypatch.setattr(plugin_mod.time, "time", lambda: T0)
    meter.states["deviceOnline"] = "false"
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "off"


def test_a_clock_step_back_does_not_strand_the_appliance(plugin, appliance, meter,
                                                         monkeypatch, caplog):
    import plugin as plugin_mod
    monkeypatch.setattr(plugin_mod.time, "time", lambda: T0)
    appliance.states.update({"cycleState": "doorWait", "cycleFinishedAt": T0 + 600,
                             "doorNotified": False, "socketNotified": False})
    appliance.pluginProps["doorDelayMinutes"] = "0"
    with caplog.at_level(logging.WARNING, logger="appliancemonitor.test"):
        plugin._tick_device(appliance)
    assert appliance.states["doorNotified"] is True
    assert any("system clock" in r.getMessage() for r in caplog.records)
