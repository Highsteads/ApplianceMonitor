#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_source_freshness.py
# Description: A meter can stop reporting without ever saying it is offline, and
#              the appliance then looks idle for ever. Plus the online-state key,
#              which was hardcoded to ShellyDirect's name.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     1.0

from datetime import datetime, timedelta

import pytest


def silent_for(meter, minutes, attr="lastSuccessfulComm"):
    setattr(meter, attr, datetime.now() - timedelta(minutes=minutes))


# ------------------------------------------------------ silence detection

def test_a_silent_meter_raises_a_fault(plugin, appliance, meter):
    appliance.pluginProps["sourceStaleMinutes"] = "30"
    silent_for(meter, 90)
    plugin._tick_device(appliance)
    assert appliance.errorState == "meter silent"


def test_a_recently_heard_meter_does_not(plugin, appliance, meter):
    appliance.pluginProps["sourceStaleMinutes"] = "30"
    silent_for(meter, 5)
    plugin._tick_device(appliance)
    assert not appliance.errorState


def test_zero_disables_the_check(plugin, appliance, meter):
    appliance.pluginProps["sourceStaleMinutes"] = "0"
    silent_for(meter, 5000)
    plugin._tick_device(appliance)
    assert not appliance.errorState


def test_absent_setting_disables_the_check(plugin, appliance, meter):
    """Every device created before v1.9.0 has no such field."""
    appliance.pluginProps.pop("sourceStaleMinutes", None)
    silent_for(meter, 5000)
    plugin._tick_device(appliance)
    assert not appliance.errorState


def test_a_meter_with_no_timestamps_is_never_called_stale(plugin, appliance, meter):
    """An unknown age must not be mistaken for a fault."""
    appliance.pluginProps["sourceStaleMinutes"] = "1"
    for attr in ("lastSuccessfulComm", "lastChanged"):
        if hasattr(meter, attr):
            delattr(meter, attr)
    plugin._tick_device(appliance)
    assert not appliance.errorState


def test_lastChanged_is_the_fallback_when_there_is_no_comm_stamp(plugin, appliance, meter):
    appliance.pluginProps["sourceStaleMinutes"] = "30"
    if hasattr(meter, "lastSuccessfulComm"):
        delattr(meter, "lastSuccessfulComm")
    silent_for(meter, 90, attr="lastChanged")
    plugin._tick_device(appliance)
    assert appliance.errorState == "meter silent"


def test_lastSuccessfulComm_wins_over_lastChanged(plugin, appliance, meter):
    """A meter that writes only on CHANGE looks silent whenever the appliance is
    idle, so the comm stamp has to win or the check fires on healthy kit."""
    appliance.pluginProps["sourceStaleMinutes"] = "30"
    silent_for(meter, 2, attr="lastSuccessfulComm")
    silent_for(meter, 500, attr="lastChanged")
    plugin._tick_device(appliance)
    assert not appliance.errorState


def test_the_fault_clears_when_the_meter_reports_again(plugin, appliance, meter):
    appliance.pluginProps["sourceStaleMinutes"] = "30"
    silent_for(meter, 90)
    plugin._tick_device(appliance)
    assert appliance.errorState == "meter silent"

    silent_for(meter, 0)
    plugin._tick_device(appliance)
    assert not appliance.errorState


def test_a_silent_meter_freezes_the_cycle_rather_than_guessing(plugin, appliance, meter):
    """Its readings cannot be trusted, so the FSM is left exactly as it was."""
    meter.states["powerWatts"] = 1000.0
    plugin._tick_device(appliance)
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "running"

    appliance.pluginProps["sourceStaleMinutes"] = "30"
    silent_for(meter, 90)
    meter.states["powerWatts"] = 0.0
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "running"


def test_silence_seconds_is_never_negative(plugin_mod, meter):
    """A clock step would otherwise produce a negative age."""
    meter.lastSuccessfulComm = datetime.now() + timedelta(hours=1)
    assert plugin_mod._source_silence_seconds(meter) == 0.0


# ----------------------------------------------- configurable online key

def test_the_default_key_still_works(plugin, appliance, meter):
    meter.states["deviceOnline"] = False
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "off"


def test_a_custom_key_is_honoured(plugin, appliance, meter):
    """Hardcoding deviceOnline meant the offline path silently never fired for
    a meter that calls it anything else."""
    appliance.pluginProps["sourceOnlineStateKey"] = "reachable"
    meter.states["reachable"] = False
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "off"


def test_the_old_key_is_ignored_once_a_custom_one_is_set(plugin, appliance, meter):
    appliance.pluginProps["sourceOnlineStateKey"] = "reachable"
    meter.states["reachable"]    = True
    meter.states["deviceOnline"] = False
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] != "off"


def test_a_key_the_meter_does_not_have_means_no_opinion(plugin, appliance, meter):
    """Not an error — most meters have no such state, and treating absence as
    offline would park every one of them permanently."""
    appliance.pluginProps["sourceOnlineStateKey"] = "nothingLikeThis"
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] != "off"
    assert not appliance.errorState


def test_a_blank_key_switches_the_check_off(plugin, appliance, meter):
    appliance.pluginProps["sourceOnlineStateKey"] = ""
    meter.states["deviceOnline"] = False
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] != "off"


@pytest.mark.parametrize("value,ok", [
    ("0", True), ("60", True), ("", True), ("-5", False),
])
def test_the_stale_setting_is_validated(plugin, appliance, value, ok):
    values = dict(appliance.pluginProps)
    values["sourceStaleMinutes"] = value
    assert plugin.validateDeviceConfigUi(values, "applianceMonitor", appliance.id)[0] is ok


def test_an_online_key_the_meter_lacks_is_refused_at_save_time(plugin, appliance):
    """It would never fire — exactly the trap this release closes — so say so
    while the dialog is open rather than letting it fail silently for months."""
    values = dict(appliance.pluginProps)
    values["sourceOnlineStateKey"] = "notAState"
    ok, _, errors = plugin.validateDeviceConfigUi(values, "applianceMonitor", appliance.id)
    assert ok is False and "sourceOnlineStateKey" in errors


def test_a_blank_online_key_saves_cleanly(plugin, appliance):
    values = dict(appliance.pluginProps)
    values["sourceOnlineStateKey"] = ""
    assert plugin.validateDeviceConfigUi(values, "applianceMonitor", appliance.id)[0] is True
