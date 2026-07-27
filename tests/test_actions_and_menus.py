#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_actions_and_menus.py
# Description: The two Indigo actions added in v1.9.0, plus the menu handlers
#              and the Pushover recipient list — the areas the deep review left
#              uncovered.
# Author:      CliveS & Claude Opus 5
# Date:        27-07-2026
# Version:     1.0

import types

import pytest

from conftest import FakePushoverPlugin


def action_for(device_id):
    """Stands in for the indigo action object handed to a device action."""
    return types.SimpleNamespace(deviceId=device_id, props={})


def run_a_cycle_into_running(plugin, appliance, meter):
    meter.states["powerWatts"] = 1200.0
    plugin._tick_device(appliance)
    plugin._tick_device(appliance)
    assert appliance.states["cycleState"] == "running"


# ------------------------------------------------------- Reset to Idle

def test_reset_puts_a_stuck_cycle_back_to_idle(plugin, appliance, meter):
    run_a_cycle_into_running(plugin, appliance, meter)
    plugin.actionResetToIdle(action_for(appliance.id))
    assert appliance.states["cycleState"] == "idle"


def test_reset_records_NOTHING_for_the_abandoned_cycle(plugin, appliance, meter):
    """A cycle that never really ended has no honest duration or energy, and a
    fabricated figure in the history is worse than a gap."""
    run_a_cycle_into_running(plugin, appliance, meter)
    plugin.actionResetToIdle(action_for(appliance.id))
    assert appliance.states["lastCycleMinutes"] == 0
    assert appliance.states["cycleStartedAt"] == 0


def test_reset_clears_the_in_flight_metrics(plugin, appliance, meter):
    run_a_cycle_into_running(plugin, appliance, meter)
    plugin.actionResetToIdle(action_for(appliance.id))
    assert appliance.states["cyclePeakWatts"] == 0.0
    assert appliance.states["cycleKwhStart"] == -1.0
    assert plugin.runtime[appliance.id]["peak"] == 0.0


def test_reset_clears_every_latch(plugin, appliance, meter):
    run_a_cycle_into_running(plugin, appliance, meter)
    appliance.states["overrunNotified"] = True
    appliance.states["doorNotified"]    = True
    plugin.actionResetToIdle(action_for(appliance.id))
    assert appliance.states["overrunNotified"] is False
    assert appliance.states["doorNotified"] is False


def test_reset_fires_no_notification(plugin, appliance, meter, indigo_mod, pushover):
    run_a_cycle_into_running(plugin, appliance, meter)
    pushover.sent.clear()
    plugin.actionResetToIdle(action_for(appliance.id))
    assert pushover.sent == []


def test_reset_on_a_deleted_device_is_survivable(plugin, indigo_mod, caplog):
    """An action group saved against a device that has since gone still fires."""
    plugin.actionResetToIdle(action_for(999999))
    assert "no longer exists" in caplog.text


# ------------------------------------------------- Send Test Notification

def test_the_test_message_goes_out_by_pushover(plugin, appliance, pushover):
    plugin.actionSendTestNotification(action_for(appliance.id))
    assert len(pushover.sent) == 1
    _, props = pushover.sent[0]
    assert "test" in props["msgBody"].lower()
    assert appliance.name in props["msgBody"]


def test_the_test_message_does_not_touch_the_appliance_state(plugin, appliance, meter, pushover):
    run_a_cycle_into_running(plugin, appliance, meter)
    before = dict(appliance.states)
    plugin.actionSendTestNotification(action_for(appliance.id))
    assert dict(appliance.states) == before


def test_the_test_message_honours_the_email_switch(plugin, appliance, indigo_mod, pushover):
    appliance.pluginProps["emailRecipients"] = "someone@example.com"
    appliance.pluginProps["emailEnabled"]    = "false"
    plugin.actionSendTestNotification(action_for(appliance.id))
    assert indigo_mod.server.emails == []


def test_the_test_message_emails_when_enabled(plugin, appliance, indigo_mod, pushover):
    appliance.pluginProps["emailRecipients"] = "someone@example.com"
    appliance.pluginProps["emailEnabled"]    = True
    plugin.actionSendTestNotification(action_for(appliance.id))
    assert len(indigo_mod.server.emails) == 1


def test_the_test_message_reports_what_it_delivered(plugin, appliance, indigo_mod, pushover):
    plugin.actionSendTestNotification(action_for(appliance.id))
    logged = " ".join(m for m, _ in indigo_mod.server.lines)
    assert "Pushover delivered to 1 recipient(s)" in logged


def test_it_reports_zero_when_pushover_is_down(plugin, appliance, indigo_mod):
    """It must not claim a delivery it did not achieve."""
    indigo_mod.server.plugins[plugin_pushover_id(plugin)] = FakePushoverPlugin(enabled=False)
    plugin.actionSendTestNotification(action_for(appliance.id))
    logged = " ".join(m for m, _ in indigo_mod.server.lines)
    assert "Pushover delivered to 0 recipient(s)" in logged


def plugin_pushover_id(plugin):
    import plugin as plugin_mod
    return plugin_mod.PUSHOVER_PLUGIN


# ------------------------------------------- Pushover recipient handling

def test_extra_recipients_each_get_a_copy(plugin, appliance, pushover):
    appliance.pluginProps["pushoverAlsoNotify"] = "aaaa1111, bbbb2222"
    plugin._send_pushover(appliance, "t", "b")
    users = [props.get("msgUser") for _, props in pushover.sent]
    assert users == [None, "aaaa1111", "bbbb2222"]


def test_a_duplicated_recipient_is_only_sent_once(plugin, appliance, pushover):
    appliance.pluginProps["pushoverUserToken"]  = "aaaa1111"
    appliance.pluginProps["pushoverAlsoNotify"] = "aaaa1111, bbbb2222"
    plugin._send_pushover(appliance, "t", "b")
    users = [props.get("msgUser") for _, props in pushover.sent]
    assert users == ["aaaa1111", "bbbb2222"]


def test_the_default_user_survives_the_de_dupe(plugin, appliance, pushover):
    """None means 'the Pushover plugin's own default user' — a real, distinct
    recipient, not an empty slot to be collapsed away."""
    appliance.pluginProps["pushoverAlsoNotify"] = "bbbb2222"
    plugin._send_pushover(appliance, "t", "b")
    users = [props.get("msgUser") for _, props in pushover.sent]
    assert None in users and "bbbb2222" in users


def test_blank_extras_are_ignored(plugin, appliance, pushover):
    appliance.pluginProps["pushoverAlsoNotify"] = " , ,, "
    assert plugin._send_pushover(appliance, "t", "b") == 1


def test_one_failed_recipient_does_not_stop_the_others(plugin, appliance, indigo_mod):
    class Flaky(FakePushoverPlugin):
        def executeAction(self, action_id, props=None):
            if (props or {}).get("msgUser") == "bbbb2222":
                raise RuntimeError("nope")
            self.sent.append((action_id, dict(props or {})))

    flaky = Flaky()
    indigo_mod.server.plugins[plugin_pushover_id(plugin)] = flaky
    appliance.pluginProps["pushoverAlsoNotify"] = "bbbb2222, cccc3333"
    delivered = plugin._send_pushover(appliance, "t", "b")
    assert delivered == 2                       # default user + cccc3333
    assert "cccc3333" in [p.get("msgUser") for _, p in flaky.sent]


# ------------------------------------------------------- menu handlers

def test_dump_state_lists_every_appliance(plugin, started, meter, indigo_mod):
    plugin.menuDumpState()
    logged = " ".join(m for m, _ in indigo_mod.server.lines)
    assert started.name in logged and "state=" in logged


def test_dump_state_says_so_when_there_is_nothing(plugin, indigo_mod):
    plugin.devices.clear()
    plugin.menuDumpState()
    logged = " ".join(m for m, _ in indigo_mod.server.lines)
    assert "No Appliance Monitor devices configured" in logged


def test_show_plugin_info_reports_the_tick_and_device_count(plugin, appliance, indigo_mod):
    plugin.showPluginInfo()
    logged = " ".join(m for m, _ in indigo_mod.server.lines)
    assert "Tick interval" in logged or "20" in logged


def test_the_timestamp_toggle_flips_and_persists(plugin, indigo_mod):
    """pluginPrefs only reach disk on a clean shutdown, so the toggle has to
    save them itself or the setting is quietly lost."""
    before = plugin.timestamp_enabled
    saved  = plugin.saved_prefs
    plugin.menuToggleTimestamps()
    assert plugin.timestamp_enabled is not before
    assert plugin.pluginPrefs["timestampEnabled"] is not before
    assert plugin.saved_prefs > saved


def test_the_timestamp_toggle_reaches_the_filter(plugin):
    if not plugin._ts_filter:
        pytest.skip("no timestamp filter installed in this environment")
    plugin.menuToggleTimestamps()
    assert plugin._ts_filter.enabled == plugin.timestamp_enabled
