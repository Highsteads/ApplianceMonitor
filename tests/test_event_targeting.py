#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_event_targeting.py
# Description: Which triggers an event reaches, and what happens when one of
#              them is broken. A trigger with no appliance chosen used to fire
#              for every appliance in the house.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import logging

from conftest import FakeTrigger


def test_a_trigger_only_fires_for_its_own_appliance(plugin, appliance, indigo_mod):
    mine   = FakeTrigger(1, "doorReady", "100")
    theirs = FakeTrigger(2, "doorReady", "101")
    plugin.triggerStartProcessing(mine)
    plugin.triggerStartProcessing(theirs)
    plugin._fire_event(appliance, "doorReady")
    assert indigo_mod.trigger.executed == [mine]


def test_the_event_type_is_honoured(plugin, appliance, indigo_mod):
    door  = FakeTrigger(1, "doorReady", "100")
    start = FakeTrigger(2, "cycleStarted", "100")
    plugin.triggerStartProcessing(door)
    plugin.triggerStartProcessing(start)
    plugin._fire_event(appliance, "cycleStarted")
    assert indigo_mod.trigger.executed == [start]


def test_a_blank_appliance_fires_for_nothing_and_warns_once(plugin, appliance,
                                                            indigo_mod, caplog):
    """v1.8.0: this used to be a silent fire-for-every-appliance wildcard."""
    blank = FakeTrigger(1, "doorReady", "")
    plugin.triggerStartProcessing(blank)
    with caplog.at_level(logging.WARNING, logger="appliancemonitor.test"):
        for _ in range(4):
            plugin._fire_event(appliance, "doorReady")
    assert indigo_mod.trigger.executed == []
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "no appliance chosen" in warnings[0].getMessage()


def test_a_non_numeric_appliance_also_fires_for_nothing(plugin, appliance, indigo_mod):
    plugin.triggerStartProcessing(FakeTrigger(1, "doorReady", "not-an-id"))
    plugin._fire_event(appliance, "doorReady")
    assert indigo_mod.trigger.executed == []


def test_one_broken_trigger_does_not_stop_the_others(plugin, appliance, indigo_mod, caplog):
    broken = FakeTrigger(1, "doorReady", "100", raises=True)
    good   = FakeTrigger(2, "doorReady", "100")
    plugin.triggerStartProcessing(broken)
    plugin.triggerStartProcessing(good)
    with caplog.at_level(logging.ERROR, logger="appliancemonitor.test"):
        plugin._fire_event(appliance, "doorReady")
    assert indigo_mod.trigger.executed == [good]
    assert any("could not execute trigger" in r.getMessage() for r in caplog.records)


def test_a_broken_trigger_still_lets_the_pushover_go_out(plugin, appliance, indigo_mod):
    from conftest import FakePushoverPlugin
    push = FakePushoverPlugin()
    indigo_mod.server.plugins["io.thechad.indigoplugin.pushover"] = push
    plugin.triggerStartProcessing(FakeTrigger(1, "doorReady", "100", raises=True))
    plugin._notify(appliance, "doorReady")
    assert len(push.sent) == 1


def test_stopping_a_trigger_forgets_it_was_warned_about(plugin, appliance, caplog):
    blank = FakeTrigger(1, "doorReady", "")
    plugin.triggerStartProcessing(blank)
    plugin._fire_event(appliance, "doorReady")
    plugin.triggerStopProcessing(blank)
    assert blank.id not in plugin.bad_triggers


# --------------------------------------------------------------------------
# The config dialog rejects it in the first place
# --------------------------------------------------------------------------

def test_validate_event_config_requires_an_appliance(plugin):
    ok, _, errors = plugin.validateEventConfigUi({"applianceDevice": ""},
                                                 "doorReady", 1)
    assert not ok
    assert "applianceDevice" in errors


def test_validate_event_config_accepts_a_chosen_appliance(plugin):
    ok, *_ = plugin.validateEventConfigUi({"applianceDevice": "100"}, "doorReady", 1)
    assert ok
