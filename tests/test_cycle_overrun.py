#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_cycle_overrun.py
# Description: The stuck-cycle watchdog. A meter pinned above the run threshold
#              leaves the appliance "running" for ever and no door-ready alert
#              ever follows — silently, because nothing looks wrong.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     1.0

import time

import pytest


def start_cycle(plugin, appliance, meter, watts=1000.0, minutes_ago=0):
    """Put the appliance in 'running' with a start time N minutes in the past."""
    meter.states["powerWatts"] = watts
    plugin._tick_device(appliance)
    plugin._tick_device(appliance)              # START_CONFIRM_TICKS
    assert appliance.states["cycleState"] == "running"
    if minutes_ago:
        appliance.states["cycleStartedAt"] = int(time.time()) - minutes_ago * 60
    return appliance


def test_a_cycle_inside_the_limit_does_not_warn(plugin, appliance, meter, indigo_mod):
    appliance.pluginProps["maxCycleMinutes"] = "120"
    start_cycle(plugin, appliance, meter, minutes_ago=30)
    plugin._tick_device(appliance)
    assert appliance.states["overrunNotified"] is False
    assert not [t for t in indigo_mod.trigger.executed]


def test_a_cycle_past_the_limit_warns_and_fires_the_event(plugin, appliance, meter,
                                                          indigo_mod, trigger_for):
    trigger_for("cycleOverrun", appliance.id)
    appliance.pluginProps["maxCycleMinutes"] = "120"
    start_cycle(plugin, appliance, meter, minutes_ago=180)
    plugin._tick_device(appliance)
    assert appliance.states["overrunNotified"] is True
    fired = [t.pluginTypeId for t in indigo_mod.trigger.executed]
    assert "cycleOverrun" in fired


def test_it_warns_ONCE_not_every_tick(plugin, appliance, meter, indigo_mod, trigger_for):
    trigger_for("cycleOverrun", appliance.id)
    appliance.pluginProps["maxCycleMinutes"] = "120"
    start_cycle(plugin, appliance, meter, minutes_ago=180)
    for _ in range(5):
        plugin._tick_device(appliance)
    fired = [t.pluginTypeId for t in indigo_mod.trigger.executed if t.pluginTypeId == "cycleOverrun"]
    assert len(fired) == 1


def test_it_does_NOT_end_the_cycle(plugin, appliance, meter, indigo_mod, trigger_for):
    """A cycle that never really finished has no honest duration or energy, so
    inventing one would put a fabricated figure into the history and the cost."""
    trigger_for("cycleOverrun", appliance.id)
    appliance.pluginProps["maxCycleMinutes"] = "120"
    start_cycle(plugin, appliance, meter, minutes_ago=180)
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "running"
    assert appliance.states.get("lastCycleMinutes", 0) == 0
    assert "doorReady" not in [t.pluginTypeId for t in indigo_mod.trigger.executed]


def test_zero_disables_the_check(plugin, appliance, meter, indigo_mod):
    appliance.pluginProps["maxCycleMinutes"] = "0"
    start_cycle(plugin, appliance, meter, minutes_ago=6000)
    plugin._tick_device(appliance)
    assert appliance.states["overrunNotified"] is False


def test_absent_setting_disables_the_check(plugin, appliance, meter, indigo_mod):
    """Every device created before v1.9.0 has no such field."""
    appliance.pluginProps.pop("maxCycleMinutes", None)
    start_cycle(plugin, appliance, meter, minutes_ago=6000)
    plugin._tick_device(appliance)
    assert appliance.states["overrunNotified"] is False


def test_an_unknown_start_time_cannot_trigger_it(plugin, appliance, meter):
    appliance.pluginProps["maxCycleMinutes"] = "1"
    start_cycle(plugin, appliance, meter)
    appliance.states["cycleStartedAt"] = 0
    plugin._tick_device(appliance)
    assert appliance.states["overrunNotified"] is False


def test_finishing_is_watched_too(plugin, appliance, meter, indigo_mod, trigger_for):
    """A meter oscillating around the idle threshold flips running/finishing for
    ever without either state ageing out — just as stuck."""
    trigger_for("cycleOverrun", appliance.id)
    appliance.pluginProps["maxCycleMinutes"] = "120"
    appliance.pluginProps["debounceMinutes"] = "60"
    start_cycle(plugin, appliance, meter, minutes_ago=180)
    meter.states["powerWatts"] = 0.5           # below idle -> finishing
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "finishing"
    plugin._tick_device(appliance)
    assert "cycleOverrun" in [t.pluginTypeId for t in indigo_mod.trigger.executed]


def test_a_new_cycle_re_arms_the_warning(plugin, appliance, meter, indigo_mod, trigger_for):
    """Without this a device warned once would never warn again."""
    trigger_for("cycleOverrun", appliance.id)
    appliance.pluginProps["maxCycleMinutes"] = "120"
    start_cycle(plugin, appliance, meter, minutes_ago=180)
    plugin._tick_device(appliance)
    assert appliance.states["overrunNotified"] is True

    plugin._reset_to_idle(appliance)
    assert appliance.states["overrunNotified"] is False
    start_cycle(plugin, appliance, meter, minutes_ago=180)
    assert appliance.states["overrunNotified"] is False
    plugin._tick_device(appliance)
    assert len([t for t in indigo_mod.trigger.executed
                if t.pluginTypeId == "cycleOverrun"]) == 2


@pytest.mark.parametrize("value,ok", [
    ("0", True), ("120", True), ("", True), (None, True),
    ("-1", False), ("2", False),        # 2 <= the 3 min default debounce
])
def test_the_setting_is_validated(plugin, appliance, indigo_mod, value, ok):
    values = dict(appliance.pluginProps)
    if value is None:
        values.pop("maxCycleMinutes", None)
    else:
        values["maxCycleMinutes"] = value
    result = plugin.validateDeviceConfigUi(values, "applianceMonitor", appliance.id)
    assert result[0] is ok
