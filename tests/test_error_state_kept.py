#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_error_state_kept.py
# Description: A power-meter fault must stay on the device until the meter reads
#              properly again. Indigo clears a device's error state on every
#              state write unless told not to, and the fault is only set once,
#              so any write in between used to wipe it for good.
# Author:      CliveS & Claude Opus 5.5
# Date:        27-09-2026
# Version:     1.0

import ast
import os
import types

import pytest

from conftest import SERVER_PLUGIN


def action_for(device_id):
    return types.SimpleNamespace(deviceId=device_id, props={})


def _break_the_meter(appliance, how):
    if how == "missing-device":
        appliance.pluginProps["sourceDeviceId"] = "999999"
        return "no source device"
    appliance.pluginProps["sourceStateKey"] = "powerWattz"
    return "no power state"


@pytest.mark.parametrize("how", ["missing-device", "missing-state"])
def test_a_meter_fault_survives_reset_to_idle(plugin, appliance, meter, how):
    """The live failure: Reset Appliance to Idle wiped the red error, and the
    latched fault never set it again, so Device Health Monitor lost it."""
    expected = _break_the_meter(appliance, how)
    plugin._tick_device(appliance)
    assert appliance.errorState == expected

    plugin.actionResetToIdle(action_for(appliance.id))
    assert appliance.errorState == expected

    # And the ticks that follow do not need to put it back: it never left.
    plugin._tick_device(appliance)
    assert appliance.errorState == expected
    assert appliance.error_writes == [expected]


def test_the_error_still_clears_when_the_meter_reads_again(plugin, appliance, meter):
    """Keeping the error must not make it stick once the fault is over."""
    _break_the_meter(appliance, "missing-device")
    plugin._tick_device(appliance)
    plugin.actionResetToIdle(action_for(appliance.id))
    appliance.pluginProps["sourceDeviceId"] = "200"
    plugin._tick_device(appliance)
    assert appliance.errorState is None
    assert plugin.source_faults == {}


def test_start_up_seeding_keeps_a_standing_error(plugin, appliance):
    """deviceStartComm seeds missing states; that must not clear an error
    Indigo still holds for the device from before the restart."""
    appliance.errorState = "no source device"
    plugin.deviceStartComm(appliance)
    assert appliance.errorState == "no source device"


def test_every_state_write_keeps_the_error_state():
    """Guard: a new direct state write would quietly start wiping the error
    again, so every updateStateOnServer call must pass clearErrorState=False."""
    path = os.path.join(SERVER_PLUGIN, "plugin.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ("updateStateOnServer", "updateStatesOnServer")]
    assert calls, "no state writes found - the guard is looking in the wrong place"
    for call in calls:
        kws = {k.arg: k.value for k in call.keywords}
        flag = kws.get("clearErrorState")
        assert isinstance(flag, ast.Constant) and flag.value is False, (
            f"plugin.py line {call.lineno} writes a state without clearErrorState=False")
