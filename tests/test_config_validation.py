#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_config_validation.py
# Description: validateDeviceConfigUi and the numeric coercion helpers. Indigo
#              re-serialises saved dialog values as STRINGS even for numeric
#              fields, and a blank field arrives as "" — so every coercion on
#              the hot path has to be guarded, and the fallback coerced too.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import pytest

VALID = {
    "sourceDeviceId":        "200",
    "sourceStateKey":        "powerWatts",
    "runThresholdWatts":     "5.0",
    "idleThresholdWatts":    "2.0",
    "debounceMinutes":       "3",
    "doorDelayMinutes":      "2",
    "socketReminderMinutes": "30",
}


def validate(plugin, **overrides):
    values = dict(VALID)
    values.update(overrides)
    return plugin.validateDeviceConfigUi(values, "applianceMonitor", 100)


def test_a_valid_config_passes(plugin, appliance):
    ok, *_ = validate(plugin)
    assert ok


# --------------------------------------------------------------------------
# The door/socket relationship — one of the two defects the 05-Jun sweep named
# --------------------------------------------------------------------------

def test_socket_reminder_must_be_later_than_the_door_delay(plugin, appliance):
    """Otherwise both notifications land on the same tick."""
    ok, _, errors = validate(plugin, doorDelayMinutes="30", socketReminderMinutes="30")
    assert not ok
    assert "socketReminderMinutes" in errors


def test_socket_reminder_below_the_door_delay_is_refused(plugin, appliance):
    ok, _, errors = validate(plugin, doorDelayMinutes="30", socketReminderMinutes="5")
    assert not ok
    assert "socketReminderMinutes" in errors


def test_socket_reminder_above_the_door_delay_is_fine(plugin, appliance):
    ok, *_ = validate(plugin, doorDelayMinutes="2", socketReminderMinutes="30")
    assert ok


# --------------------------------------------------------------------------
# Threshold relationships
# --------------------------------------------------------------------------

def test_idle_threshold_must_be_below_the_run_threshold(plugin, appliance):
    ok, _, errors = validate(plugin, runThresholdWatts="5", idleThresholdWatts="5")
    assert not ok
    assert "idleThresholdWatts" in errors


def test_run_threshold_must_be_positive(plugin, appliance):
    ok, _, errors = validate(plugin, runThresholdWatts="0")
    assert not ok
    assert "runThresholdWatts" in errors


def test_debounce_zero_is_allowed(plugin, appliance):
    """Deliberate v1.2.3 behaviour — must not be validated away."""
    ok, *_ = validate(plugin, debounceMinutes="0")
    assert ok


def test_missing_source_device_is_refused(plugin, appliance):
    ok, _, errors = validate(plugin, sourceDeviceId="999999")
    assert not ok
    assert "sourceDeviceId" in errors


# --------------------------------------------------------------------------
# The new v1.7.0 minimums
# --------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["minCycleMinutes", "minCyclePeakWatts"])
def test_negative_minimums_are_refused(plugin, appliance, field):
    ok, _, errors = validate(plugin, **{field: "-1"})
    assert not ok
    assert field in errors


@pytest.mark.parametrize("field", ["minCycleMinutes", "minCyclePeakWatts"])
def test_zero_minimums_are_allowed_and_mean_off(plugin, appliance, field):
    ok, *_ = validate(plugin, **{field: "0"})
    assert ok


# --------------------------------------------------------------------------
# Blank and garbage input — the commonest bug class estate-wide
# --------------------------------------------------------------------------

@pytest.mark.parametrize("field", [
    "runThresholdWatts", "idleThresholdWatts", "debounceMinutes",
    "doorDelayMinutes", "socketReminderMinutes",
])
def test_blank_numeric_fields_never_raise(plugin, appliance, field):
    """A blank textfield arrives as "" and must be refused, not crash."""
    result = validate(plugin, **{field: ""})
    assert isinstance(result[0], bool)


@pytest.mark.parametrize("junk", ["", "  ", "abc", "on", None, "1,5"])
def test_coercion_helpers_survive_garbage(plugin_mod, junk):
    assert plugin_mod._f(junk, 4.2) == 4.2
    assert plugin_mod._i(junk, 7) == 7


def test_coercion_helpers_accept_the_string_forms_indigo_actually_stores(plugin_mod):
    assert plugin_mod._f("5.0", 0.0) == 5.0
    assert plugin_mod._i("30", 0) == 30
    assert plugin_mod._i("2.0", 0) == 2      # int(float()) handles a stored float


def test_tick_survives_blank_config_on_every_numeric_field(plugin, appliance, meter):
    """A never-saved device must not kill runConcurrentThread."""
    for field in ("runThresholdWatts", "idleThresholdWatts", "debounceMinutes",
                  "doorDelayMinutes", "socketReminderMinutes",
                  "minCycleMinutes", "minCyclePeakWatts"):
        appliance.pluginProps[field] = ""
    plugin._tick_device(appliance)            # must not raise
    assert appliance.states["cycleState"] in ("idle", "running", "off")


# --------------------------------------------------------------------------
# v1.8.0 — the state names and the rate variable are checked against reality
# --------------------------------------------------------------------------

def test_a_mistyped_power_state_name_is_refused(plugin, appliance):
    ok, _, errors = validate(plugin, sourceStateKey="powerWattz")
    assert not ok
    assert "powerWatts" in errors["sourceStateKey"]


def test_a_blank_power_state_name_is_refused(plugin, appliance):
    ok, _, errors = validate(plugin, sourceStateKey="")
    assert not ok
    assert "sourceStateKey" in errors


def test_a_mistyped_energy_state_name_is_refused(plugin, appliance):
    ok, _, errors = validate(plugin, sourceEnergyStateKey="energyKwhTodya")
    assert not ok
    assert "sourceEnergyStateKey" in errors


def test_a_blank_energy_state_name_is_fine(plugin, appliance):
    """Blank means the meter has no kWh counter — a supported setup."""
    ok, *_ = validate(plugin, sourceEnergyStateKey="")
    assert ok


def test_an_appliance_cannot_watch_itself(plugin, appliance):
    ok, _, errors = validate(plugin, sourceDeviceId="100")
    assert not ok
    assert "sourceDeviceId" in errors


def test_an_unknown_rate_variable_is_refused(plugin, appliance):
    ok, _, errors = validate(plugin, rateVariableName="no_such_variable")
    assert not ok
    assert "rateVariableName" in errors


def test_a_real_rate_variable_is_accepted(plugin, appliance, indigo_mod):
    from conftest import FakeVariable
    indigo_mod.variables["tracker_rate_today"] = FakeVariable("tracker_rate_today", "24.5")
    ok, *_ = validate(plugin, rateVariableName="tracker_rate_today")
    assert ok


def test_a_blank_rate_variable_is_fine(plugin, appliance):
    ok, *_ = validate(plugin, rateVariableName="")
    assert ok


# --------------------------------------------------------------------------
# Value coercion — a string "false" must not read as True
# --------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    (True, True), (False, False),
    ("true", True), ("false", False),
    ("True", True), ("FALSE", False),
    ("1", True), ("0", False),
    ("yes", True), ("no", False),
    (1, True), (0, False),
])
def test_as_bool_coerces_indigo_values(plugin_mod, value, expected):
    assert plugin_mod._as_bool(value, default=None) is expected


def test_as_bool_falls_back_for_blank_and_missing(plugin_mod):
    assert plugin_mod._as_bool(None, True) is True
    assert plugin_mod._as_bool("", False) is False


def test_email_is_silenced_by_the_string_false(plugin, appliance, indigo_mod):
    appliance.pluginProps["emailEnabled"]    = "false"
    appliance.pluginProps["emailRecipients"] = "someone@example.com"
    plugin._send_email(appliance, "Cycle done", "body")
    assert indigo_mod.server.emails == []


def test_the_timestamp_toggle_writes_the_pref_to_disk(plugin):
    before = plugin.pluginPrefs.get("timestampEnabled")
    plugin.menuToggleTimestamps()
    assert plugin.pluginPrefs["timestampEnabled"] is not before
    assert plugin.saved_prefs == 1


# --------------------------------------------------------------------------
# v1.8.1 — a malformed email address is refused at save time
# --------------------------------------------------------------------------

@pytest.mark.parametrize("addr", ["notanaddress", "@example.com", "jane@"])
def test_a_malformed_email_address_is_refused(plugin, appliance, addr):
    ok, _, errors = validate(plugin, emailRecipients=addr)
    assert not ok
    assert "emailRecipients" in errors


def test_several_good_addresses_are_accepted(plugin, appliance):
    ok, *_ = validate(plugin, emailRecipients="jane@example.com, sam@example.com")
    assert ok


def test_one_bad_address_among_good_ones_is_named(plugin, appliance):
    ok, _, errors = validate(plugin, emailRecipients="jane@example.com, oops")
    assert not ok
    assert "oops" in errors["emailRecipients"]


def test_a_blank_recipient_list_is_fine(plugin, appliance):
    ok, *_ = validate(plugin, emailRecipients="")
    assert ok
