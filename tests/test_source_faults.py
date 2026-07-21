#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_source_faults.py
# Description: A missing power meter, or a mistyped power state name, must be
#              reported once and shown on the device — not logged every 20
#              seconds forever, and not swallowed as a reading of 0 W.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import logging


def test_missing_source_device_logs_once_not_every_tick(plugin, appliance, caplog):
    appliance.pluginProps["sourceDeviceId"] = "999999"
    with caplog.at_level(logging.ERROR, logger="appliancemonitor.test"):
        for _ in range(10):
            plugin._tick_device(appliance)
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "no longer exists" in errors[0].getMessage()


def test_missing_source_device_marks_the_device_in_error(plugin, appliance):
    appliance.pluginProps["sourceDeviceId"] = "999999"
    plugin._tick_device(appliance)
    assert appliance.errorState == "no source device"
    # And only written once, not on every tick.
    plugin._tick_device(appliance)
    assert appliance.error_writes == ["no source device"]


def test_the_fault_repeats_once_an_hour(plugin, appliance, caplog, monkeypatch):
    appliance.pluginProps["sourceDeviceId"] = "999999"
    import plugin as plugin_mod

    clock = [1_000_000.0]
    monkeypatch.setattr(plugin_mod.time, "time", lambda: clock[0])
    with caplog.at_level(logging.ERROR, logger="appliancemonitor.test"):
        plugin._tick_device(appliance)
        clock[0] += plugin_mod.FAULT_REPEAT_SECONDS - 1
        plugin._tick_device(appliance)
        assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 1
        clock[0] += 2
        plugin._tick_device(appliance)
        assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 2


def test_the_fault_clears_when_the_meter_comes_back(plugin, appliance, meter, caplog):
    appliance.pluginProps["sourceDeviceId"] = "999999"
    plugin._tick_device(appliance)
    assert appliance.errorState == "no source device"
    appliance.pluginProps["sourceDeviceId"] = "200"
    with caplog.at_level(logging.INFO, logger="appliancemonitor.test"):
        plugin._tick_device(appliance)
    assert appliance.errorState is None
    assert any("readable again" in r.getMessage() for r in caplog.records)
    assert plugin.source_faults == {}


def test_a_mistyped_power_state_is_a_fault_not_a_reading_of_zero(plugin, appliance,
                                                                 meter, caplog):
    """This is the whole point: a typo used to look exactly like 0 W."""
    appliance.pluginProps["sourceStateKey"] = "powerWattz"
    with caplog.at_level(logging.ERROR, logger="appliancemonitor.test"):
        for _ in range(5):
            plugin._tick_device(appliance)
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "powerWattz" in errors[0].getMessage()
    assert "powerWatts" in errors[0].getMessage()   # lists what IS available
    assert appliance.errorState == "no power state"
    # And the state machine never ran, so no reading was invented.
    assert "currentWatts" not in appliance.states


def test_a_good_config_never_touches_the_error_state(plugin, appliance, meter):
    plugin._tick_device(appliance)
    assert appliance.error_writes == []
    assert appliance.errorState is None
