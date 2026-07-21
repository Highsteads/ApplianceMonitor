#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    conftest.py
# Description: Test seam for Appliance Monitor. Installs a fake `indigo` module
#              into sys.modules BEFORE plugin.py is imported, so the plugin can
#              be exercised with no Indigo server and no hardware.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import logging
import os
import sys
import types

import pytest

REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PLUGIN = os.path.join(
    REPO_ROOT, "ApplianceMonitor.indigoPlugin", "Contents", "Server Plugin"
)


# ==========================================================================
# Fake Indigo object model
#
# Only the surface plugin.py actually touches. Kept deliberately small — a
# fake that drifts from the real API is worse than no fake at all.
# ==========================================================================

class FakeStates(dict):
    """Device states. Real Indigo exposes .get() and `in`, which dict gives us."""


class FakeDevice:
    def __init__(self, dev_id, name="Test Appliance", props=None, states=None):
        self.id           = dev_id
        self.name         = name
        self.pluginProps  = dict(props or {})
        self.ownerProps   = self.pluginProps
        self.states       = FakeStates(states or {})
        self.state_writes = []          # ordered audit of every write
        self.refresh_calls = 0
        self.errorState   = None
        self.error_writes = []          # ordered audit of setErrorStateOnServer

    def setErrorStateOnServer(self, message):
        self.errorState = message
        self.error_writes.append(message)

    def updateStateOnServer(self, key, value=None, uiValue=None):
        self.states[key] = value
        if uiValue is not None:
            self.states[f"{key}.ui"] = uiValue
        self.state_writes.append((key, value, uiValue))

    def stateListOrDisplayStateIdChanged(self):
        """Real Indigo materialises any newly declared states here.

        Crucially a new Number state appears as 0.0 and a new Integer as 0 —
        NOT None. Reproducing that is the whole point of this fake, because
        trusting a fresh 0.0 as a real reading was a live bug in v1.7.0.
        """
        self.refresh_calls += 1
        for key, default in (("cyclePeakWatts", 0.0),
                             ("cycleKwhStart", 0.0),
                             ("cycleStateVersion", 0)):
            self.states.setdefault(key, default)


class FakeTrigger:
    """Stands in for an indigo trigger held in self.event_triggers."""

    def __init__(self, trigger_id, plugin_type_id, appliance_device="",
                 name=None, raises=False):
        self.id            = trigger_id
        self.pluginTypeId  = plugin_type_id
        self.pluginProps   = {"applianceDevice": appliance_device}
        self.name          = name or f"Trigger {trigger_id}"
        self.raises        = raises


class FakeVariable:
    def __init__(self, name, value):
        self.name  = name
        self.value = value


class FakeCollection(dict):
    """Stands in for indigo.devices / indigo.variables (keyed by id or name)."""


class FakeServer:
    def __init__(self):
        self.lines   = []   # [(message, level)]
        self.emails  = []
        self.plugins = {}

    def log(self, message, type=None, level=None, isError=False):
        self.lines.append((message, level))

    def getPlugin(self, plugin_id):
        return self.plugins.get(plugin_id)

    def sendEmailTo(self, address, subject="", body=""):
        self.emails.append((address, subject, body))

    def getInstallFolderPath(self):
        return "/tmp/fake-indigo"


class FakeTriggerNamespace:
    def __init__(self):
        self.executed = []

    def execute(self, trigger):
        if getattr(trigger, "raises", False):
            raise RuntimeError("trigger no longer exists")
        self.executed.append(trigger)


class FakePushoverPlugin:
    def __init__(self, enabled=True, raises=False):
        self._enabled = enabled
        self.raises   = raises
        self.sent     = []

    def isEnabled(self):
        return self._enabled

    def executeAction(self, action_id, props=None):
        if self.raises:
            raise RuntimeError("pushover exploded")
        self.sent.append((action_id, dict(props or {})))


class FakePluginBase:
    """Minimal stand-in for indigo.PluginBase."""

    class StopThread(Exception):
        pass

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        self.pluginId          = pluginId
        self.pluginDisplayName = pluginDisplayName
        self.pluginVersion     = pluginVersion
        self.pluginPrefs       = pluginPrefs
        self.logger            = logging.getLogger("appliancemonitor.test")
        # install_timestamp_filter is not idempotent, and this logger is a
        # module-level singleton, so filters would otherwise pile up across
        # tests and prefix each line once per test that had run before it.
        self.logger.filters.clear()
        self.logger.addHandler(logging.NullHandler())
        self.saved_prefs       = 0
        self.slept             = []

    def savePluginPrefs(self):
        self.saved_prefs += 1

    def sleep(self, seconds):
        self.slept.append(seconds)


def _build_fake_indigo():
    ind = types.ModuleType("indigo")
    ind.PluginBase = FakePluginBase
    ind.Dict       = dict
    ind.List       = list
    ind.devices    = FakeCollection()
    ind.variables  = FakeCollection()
    ind.server     = FakeServer()
    ind.trigger    = FakeTriggerNamespace()
    ind.kStateImageSel = types.SimpleNamespace(
        PowerOn="PowerOn", PowerOff="PowerOff", NoImage="NoImage"
    )
    return ind


# ==========================================================================
# Fixtures
# ==========================================================================

@pytest.fixture
def indigo_mod(monkeypatch):
    """A fresh fake indigo per test, with plugin.py re-imported against it."""
    ind = _build_fake_indigo()
    monkeypatch.setitem(sys.modules, "indigo", ind)
    if SERVER_PLUGIN not in sys.path:
        sys.path.insert(0, SERVER_PLUGIN)
    # Drop cached modules so each test binds to this test's fake indigo.
    for mod in ("plugin", "plugin_utils"):
        sys.modules.pop(mod, None)
    return ind


@pytest.fixture
def plugin_mod(indigo_mod):
    import plugin
    return plugin


@pytest.fixture
def plugin(plugin_mod):
    """A started Plugin instance."""
    return plugin_mod.Plugin(
        "com.clives.indigoplugin.appliancemonitor",
        "Appliance Monitor",
        "1.7.0",
        {"debug": False},
    )


DEFAULT_PROPS = {
    "sourceDeviceId":        "200",
    "sourceStateKey":        "powerWatts",
    "sourceEnergyStateKey":  "energyKwhToday",
    "runThresholdWatts":     "5.0",
    "idleThresholdWatts":    "2.0",
    "debounceMinutes":       "3",
    "doorDelayMinutes":      "2",
    "socketReminderMinutes": "30",
    "notifyCycleStarted":    True,
    "notifyDoorReady":       True,
    "notifySocketReminder":  True,
}


@pytest.fixture
def appliance(indigo_mod):
    """An appliance device (id 100) watching a power meter (id 200)."""
    src = FakeDevice(200, "Test Meter",
                     states={"powerWatts": 0.0, "energyKwhToday": 0.0,
                             "deviceOnline": True})
    dev = FakeDevice(100, "Test Appliance", props=dict(DEFAULT_PROPS),
                     states={"cycleState": "idle"})
    indigo_mod.devices[100] = dev
    indigo_mod.devices[200] = src
    return dev


@pytest.fixture
def meter(indigo_mod, appliance):
    return indigo_mod.devices[200]
