#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_state_machine.py
# Description: The full cycle state machine — idle/running/finishing/doorWait/off,
#              the debounce=0 fast path, phantom-cycle suppression and the
#              source-offline path. A regression here looks like a hardware
#              fault, so it is the hardest class of bug to diagnose from a log.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import pytest

T0 = 1784600000


@pytest.fixture
def clock(plugin_mod, monkeypatch):
    """Controllable wall clock for the tick loop."""
    class Clock:
        def __init__(self):
            self.now = T0

        def advance(self, seconds):
            self.now += seconds

    c = Clock()
    monkeypatch.setattr(plugin_mod.time, "time", lambda: c.now)
    return c


def tick(plugin, dev, meter, watts, *, online=True):
    meter.states["powerWatts"]  = watts
    meter.states["deviceOnline"] = online
    plugin._tick_device(dev)
    return dev.states["cycleState"]


def start_running(plugin, dev, meter, watts=2000.0):
    """Drive the device into 'running', honouring the start confirmation."""
    for _ in range(plugin_start_ticks(plugin)):
        tick(plugin, dev, meter, watts)
    assert dev.states["cycleState"] == "running"


def plugin_start_ticks(plugin):
    import plugin as plugin_mod
    return plugin_mod.START_CONFIRM_TICKS


# --------------------------------------------------------------------------
# Phantom-cycle suppression
# --------------------------------------------------------------------------

def test_single_above_threshold_tick_does_not_start_a_cycle(plugin, appliance, meter, clock):
    """One stray reading must not invent a cycle and three notifications."""
    assert tick(plugin, appliance, meter, 2000.0) == "idle"


def test_two_consecutive_ticks_start_a_cycle(plugin, appliance, meter, clock):
    tick(plugin, appliance, meter, 2000.0)
    assert tick(plugin, appliance, meter, 2000.0) == "running"


def test_above_threshold_counter_resets_on_a_dip(plugin, appliance, meter, clock):
    """A blip, a quiet tick, then a blip must not accumulate into a start."""
    tick(plugin, appliance, meter, 2000.0)
    tick(plugin, appliance, meter, 0.0)
    assert tick(plugin, appliance, meter, 2000.0) == "idle"


def test_short_cycle_discarded_when_below_the_configured_minimum(
        plugin, appliance, meter, clock, indigo_mod):
    appliance.pluginProps["minCycleMinutes"] = "10"
    appliance.pluginProps["debounceMinutes"] = "0"
    start_running(plugin, appliance, meter)
    clock.advance(120)                       # a 2-minute "cycle"
    tick(plugin, appliance, meter, 0.0)      # -> finishing
    clock.advance(20)
    state = tick(plugin, appliance, meter, 0.0)
    assert state == "idle"                   # discarded, not doorWait
    assert "lastCycleMinutes" not in appliance.states
    assert indigo_mod.trigger.executed == []  # and nothing announced


def test_weak_cycle_discarded_when_below_the_peak_minimum(
        plugin, appliance, meter, clock, indigo_mod):
    """The live phantom: a 3-minute 'wash' peaking at 5.2 W."""
    appliance.pluginProps["minCyclePeakWatts"] = "500"
    appliance.pluginProps["debounceMinutes"]   = "0"
    start_running(plugin, appliance, meter, watts=5.2)
    clock.advance(180)
    tick(plugin, appliance, meter, 0.0)
    clock.advance(20)
    assert tick(plugin, appliance, meter, 0.0) == "idle"
    assert indigo_mod.trigger.executed == []


# --------------------------------------------------------------------------
# The core transition table
# --------------------------------------------------------------------------

def test_running_to_finishing_below_idle_threshold(plugin, appliance, meter, clock):
    start_running(plugin, appliance, meter)
    assert tick(plugin, appliance, meter, 1.0) == "finishing"
    assert appliance.states["lowSince"] == clock.now


def test_finishing_returns_to_running_when_power_comes_back(plugin, appliance, meter, clock):
    start_running(plugin, appliance, meter)
    tick(plugin, appliance, meter, 1.0)
    assert tick(plugin, appliance, meter, 2000.0) == "running"
    assert appliance.states["lowSince"] == 0


def test_finishing_to_doorwait_only_after_the_debounce(plugin, appliance, meter, clock):
    start_running(plugin, appliance, meter)
    tick(plugin, appliance, meter, 1.0)          # -> finishing, lowSince set
    clock.advance(60)
    assert tick(plugin, appliance, meter, 1.0) == "finishing"   # 1 min < 3 min
    clock.advance(121)
    assert tick(plugin, appliance, meter, 1.0) == "doorWait"


def test_debounce_zero_ends_the_cycle_on_the_next_tick(plugin, appliance, meter, clock):
    """The deliberate v1.2.3 fast path — must keep working."""
    appliance.pluginProps["debounceMinutes"] = "0"
    start_running(plugin, appliance, meter)
    tick(plugin, appliance, meter, 0.0)          # -> finishing
    clock.advance(20)
    assert tick(plugin, appliance, meter, 0.0) == "doorWait"


def test_new_cycle_during_doorwait_jumps_straight_to_running(plugin, appliance, meter, clock):
    appliance.pluginProps["debounceMinutes"] = "0"
    start_running(plugin, appliance, meter)
    tick(plugin, appliance, meter, 0.0)
    clock.advance(20)
    tick(plugin, appliance, meter, 0.0)
    assert appliance.states["cycleState"] == "doorWait"
    assert tick(plugin, appliance, meter, 2000.0) == "running"


def test_cycle_started_fires_once_across_a_running_finishing_bounce(
        plugin, appliance, meter, clock, indigo_mod):
    """Bouncing in and out of finishing must not re-announce the cycle."""
    class T:
        pluginTypeId = "cycleStarted"
        id = 1
        pluginProps = {"applianceDevice": "100"}
    plugin.event_triggers[1] = T()

    start_running(plugin, appliance, meter)
    tick(plugin, appliance, meter, 1.0)      # -> finishing
    tick(plugin, appliance, meter, 2000.0)   # -> running again
    tick(plugin, appliance, meter, 1.0)
    tick(plugin, appliance, meter, 2000.0)
    assert len(indigo_mod.trigger.executed) == 1


# --------------------------------------------------------------------------
# Source-offline path (v1.2.5) — deliberately ignored while running
# --------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["idle", "finishing", "doorWait"])
def test_offline_source_drops_to_off_in_non_running_states(
        plugin, appliance, meter, clock, state):
    appliance.states["cycleState"] = state
    assert tick(plugin, appliance, meter, 0.0, online=False) == "off"


def test_offline_source_is_ignored_while_running(plugin, appliance, meter, clock):
    """A mid-cycle network blip must never drop cycle tracking."""
    start_running(plugin, appliance, meter)
    assert tick(plugin, appliance, meter, 2000.0, online=False) == "running"


def test_source_back_online_resets_to_idle_and_can_start_same_tick(
        plugin, appliance, meter, clock):
    appliance.states["cycleState"] = "off"
    # First tick back online resets to idle and counts one above-threshold tick.
    assert tick(plugin, appliance, meter, 2000.0) == "idle"
    assert tick(plugin, appliance, meter, 2000.0) == "running"


def test_missing_source_device_does_not_raise(plugin, appliance, indigo_mod, clock):
    appliance.pluginProps["sourceDeviceId"] = "999999"
    plugin._tick_device(appliance)            # must log, not explode
    assert appliance.states["cycleState"] == "idle"
