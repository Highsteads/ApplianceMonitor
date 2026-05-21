#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Appliance Monitor - detect cycle start/end on appliances metered
#              by a power-monitoring device (e.g. Shelly). Sends Pushover
#              notifications directly and also fires three Indigo custom
#              events: cycleStarted, doorReady, socketReminder.
# Author:      CliveS & Claude Opus 4.7
# Date:        18-05-2026
# Version:     1.1.0

try:
    import indigo
except ImportError:
    pass

import os as _os
import sys as _sys
import time
from datetime import datetime

_sys.path.insert(0, _os.getcwd())
try:
    from plugin_utils import log_startup_banner
except ImportError:
    log_startup_banner = None


# ============================================================
# Constants
# ============================================================

PLUGIN_ID       = "com.clives.indigoplugin.appliancemonitor"
PLUGIN_VERSION  = "1.1.0"
PUSHOVER_PLUGIN = "io.thechad.indigoplugin.pushover"
TICK_SECONDS    = 20

VALID_STATES    = ("idle", "running", "finishing", "doorWait")


# ============================================================
# Helpers
# ============================================================

def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", level=level)


def _f(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _i(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# ============================================================
# Plugin class
# ============================================================

class Plugin(indigo.PluginBase):

    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        self.debug           = pluginPrefs.get("debug", False)
        self.event_triggers  = {}   # {trigger.id: indigo.trigger}
        self.devices         = {}   # {dev.id: indigo.Device} - tracked appliances

        if log_startup_banner:
            log_startup_banner(pluginId, pluginDisplayName, pluginVersion, extras=[
                ("Tick interval:", f"{TICK_SECONDS} s"),
            ])
        else:
            indigo.server.log(f"{pluginDisplayName} v{pluginVersion} starting")

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------

    def startup(self):
        self.logger.info("Appliance Monitor started")

    def shutdown(self):
        self.logger.info("Appliance Monitor stopped")

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.debug = valuesDict.get("debug", False)
            self.logger.info(f"Verbose debug = {self.debug}")

    # --------------------------------------------------------
    # Device lifecycle
    # --------------------------------------------------------

    def deviceStartComm(self, dev):
        self.logger.info(f"Watching appliance: {dev.name}")
        # Seed defaults so the device states are populated even before the
        # first tick (otherwise control pages show blanks).
        if dev.states.get("cycleState") not in VALID_STATES:
            dev.updateStateOnServer("cycleState", value="idle")
        for key in ("cycleStartedAt", "cycleFinishedAt", "lowSince", "lastCycleMinutes"):
            if not dev.states.get(key):
                dev.updateStateOnServer(key, value=0)
        for key in ("doorNotified", "socketNotified"):
            if dev.states.get(key) is None:
                dev.updateStateOnServer(key, value=False)
        self.devices[dev.id] = dev

    def deviceStopComm(self, dev):
        self.devices.pop(dev.id, None)
        self.logger.info(f"Stopped watching: {dev.name}")

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        errors = indigo.Dict()
        src_id = _i(valuesDict.get("sourceDeviceId"), 0)
        if src_id == 0 or src_id not in indigo.devices:
            errors["sourceDeviceId"] = "Pick a power-meter device."
        run_w  = _f(valuesDict.get("runThresholdWatts"), -1)
        idle_w = _f(valuesDict.get("idleThresholdWatts"), -1)
        if run_w <= 0:
            errors["runThresholdWatts"] = "Must be a positive number of watts."
        if idle_w < 0:
            errors["idleThresholdWatts"] = "Must be zero or a positive number of watts."
        if run_w > 0 and idle_w >= run_w:
            errors["idleThresholdWatts"] = "Idle threshold must be less than run threshold."
        if _i(valuesDict.get("debounceMinutes"), -1) < 1:
            errors["debounceMinutes"] = "Must be a positive integer (minutes)."
        if _i(valuesDict.get("doorDelayMinutes"), -1) < 0:
            errors["doorDelayMinutes"] = "Must be zero or a positive integer (minutes)."
        if _i(valuesDict.get("socketReminderMinutes"), -1) < 1:
            errors["socketReminderMinutes"] = "Must be a positive integer (minutes)."
        if errors:
            return (False, valuesDict, errors)
        return (True, valuesDict)

    # --------------------------------------------------------
    # Trigger lifecycle - per CLAUDE.md, the only way to fire events
    # --------------------------------------------------------

    def triggerStartProcessing(self, trigger):
        self.event_triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.event_triggers.pop(trigger.id, None)

    def _fire_event(self, dev, event_id):
        """Fire every trigger whose pluginTypeId matches event_id AND whose
        applianceDevice points at dev.id."""
        fired = 0
        for trigger in self.event_triggers.values():
            if trigger.pluginTypeId != event_id:
                continue
            target = str(trigger.pluginProps.get("applianceDevice", "")).strip()
            if target and target.isdigit() and int(target) != dev.id:
                continue
            indigo.trigger.execute(trigger)
            fired += 1
        if self.debug:
            self.logger.debug(f"[{dev.name}] event {event_id} -> {fired} trigger(s)")

    def _send_pushover(self, dev, title, body):
        """Send a Pushover notification using per-device settings."""
        pushover = indigo.server.getPlugin(PUSHOVER_PLUGIN)
        if not pushover or not pushover.isEnabled():
            self.logger.warning(
                f"[{dev.name}] Pushover plugin not enabled — message not sent: {body}"
            )
            return
        props = dev.pluginProps
        msg = {
            "msgTitle":    title,
            "msgBody":     body,
            "msgPriority": str(props.get("pushoverPriority", "0") or "0"),
            "msgSound":    props.get("pushoverSound", "vibrate") or "vibrate",
        }
        user = (props.get("pushoverUserToken") or "").strip()
        if user:
            msg["msgUser"] = user
        try:
            pushover.executeAction("send", props=msg)
            if self.debug:
                self.logger.debug(f"[{dev.name}] Pushover sent: {title} / {body}")
        except Exception:
            self.logger.exception(f"[{dev.name}] Pushover send failed")

    # Per-event notification config: which checkbox gates sending, and what
    # the default title/body look like. Body templates can reference
    # {name} and {minutes}.
    _NOTIFY_CONFIG = {
        "cycleStarted":   ("notifyCycleStarted",
                           "Wash started",
                           "{name}: cycle started."),
        "doorReady":      ("notifyDoorReady",
                           "Wash done",
                           "{name}: cycle complete after {minutes} min — door unlocking now."),
        "socketReminder": ("notifySocketReminder",
                           "Switch off socket",
                           "{name}: no new wash started — please switch the wall socket off."),
    }

    def _notify(self, dev, event_id):
        """Fire the matching Indigo event AND, if enabled, send a Pushover."""
        self._fire_event(dev, event_id)

        cfg = self._NOTIFY_CONFIG.get(event_id)
        if not cfg:
            return
        prop_key, title, body_template = cfg
        if not bool(dev.pluginProps.get(prop_key, False)):
            return
        body = body_template.format(
            name    = dev.name,
            minutes = _i(dev.states.get("lastCycleMinutes"), 0),
        )
        self._send_pushover(dev, title, body)

    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------

    def runConcurrentThread(self):
        try:
            while True:
                for dev_id in list(self.devices.keys()):
                    try:
                        dev = indigo.devices[dev_id]
                        self._tick_device(dev)
                    except Exception:
                        self.logger.exception(f"tick failed for device {dev_id}")
                self.sleep(TICK_SECONDS)
        except self.StopThread:
            pass

    # --------------------------------------------------------
    # State machine
    # --------------------------------------------------------

    def _tick_device(self, dev):
        props        = dev.pluginProps
        src_id       = _i(props.get("sourceDeviceId"), 0)
        state_key    = props.get("sourceStateKey", "powerWatts") or "powerWatts"
        run_w        = _f(props.get("runThresholdWatts"), 5.0)
        idle_w       = _f(props.get("idleThresholdWatts"), 2.0)
        debounce_s   = _i(props.get("debounceMinutes"), 3) * 60
        door_delay   = _i(props.get("doorDelayMinutes"), 2) * 60
        socket_delay = _i(props.get("socketReminderMinutes"), 30) * 60

        if src_id == 0 or src_id not in indigo.devices:
            self.logger.error(f"[{dev.name}] source device not configured or missing")
            return

        src   = indigo.devices[src_id]
        watts = _f(src.states.get(state_key), 0.0)
        now   = int(time.time())
        state = dev.states.get("cycleState", "idle")

        dev.updateStateOnServer("currentWatts", value=watts, uiValue=f"{watts:.1f} W")

        if self.debug:
            self.logger.debug(f"[{dev.name}] state={state} watts={watts:.1f}")

        if state == "idle":
            if watts >= run_w:
                self._enter_running(dev, now)

        elif state == "running":
            if watts < idle_w:
                dev.updateStateOnServer("lowSince", value=now)
                dev.updateStateOnServer("cycleState", value="finishing")
                if self.debug:
                    self.logger.debug(f"[{dev.name}] entered finishing at {now}")

        elif state == "finishing":
            if watts >= run_w:
                dev.updateStateOnServer("lowSince", value=0)
                dev.updateStateOnServer("cycleState", value="running")
                if self.debug:
                    self.logger.debug(f"[{dev.name}] returned to running")
            else:
                low_since = _i(dev.states.get("lowSince"), 0)
                if low_since and (now - low_since) >= debounce_s:
                    self._enter_door_wait(dev, finished_at=low_since)

        elif state == "doorWait":
            if watts >= run_w:
                # new cycle - cancel pending notifications, jump to running
                self._enter_running(dev, now)
                return
            finished_at     = _i(dev.states.get("cycleFinishedAt"), 0)
            elapsed         = now - finished_at if finished_at else 0
            door_notified   = bool(dev.states.get("doorNotified", False))
            socket_notified = bool(dev.states.get("socketNotified", False))

            if not door_notified and elapsed >= door_delay:
                dev.updateStateOnServer("doorNotified", value=True)
                self._notify(dev, "doorReady")
                log(f"{dev.name}: door ready ({elapsed // 60} min after cycle end)")

            if not socket_notified and elapsed >= socket_delay:
                dev.updateStateOnServer("socketNotified", value=True)
                self._notify(dev, "socketReminder")
                log(f"{dev.name}: socket-off reminder ({elapsed // 60} min after cycle end)")
                # Job done - back to idle, ready for the next cycle.
                self._reset_to_idle(dev)

    # --------------------------------------------------------
    # Transitions
    # --------------------------------------------------------

    def _enter_running(self, dev, now):
        prev = dev.states.get("cycleState", "idle")
        dev.updateStateOnServer("cycleState",      value="running")
        dev.updateStateOnServer("cycleStartedAt",  value=now)
        dev.updateStateOnServer("lowSince",        value=0)
        dev.updateStateOnServer("doorNotified",    value=False)
        dev.updateStateOnServer("socketNotified",  value=False)
        log(f"{dev.name}: cycle started")
        if prev != "running":
            self._notify(dev, "cycleStarted")

    def _enter_door_wait(self, dev, finished_at):
        started_at = _i(dev.states.get("cycleStartedAt"), 0)
        minutes    = (finished_at - started_at) // 60 if started_at else 0
        dev.updateStateOnServer("cycleState",       value="doorWait")
        dev.updateStateOnServer("cycleFinishedAt",  value=finished_at)
        dev.updateStateOnServer("lastCycleMinutes", value=minutes)
        dev.updateStateOnServer("lowSince",         value=0)
        dev.updateStateOnServer("doorNotified",     value=False)
        dev.updateStateOnServer("socketNotified",   value=False)
        log(f"{dev.name}: cycle ended (duration {minutes} min)")

    def _reset_to_idle(self, dev):
        dev.updateStateOnServer("cycleState",   value="idle")
        dev.updateStateOnServer("lowSince",     value=0)

    # --------------------------------------------------------
    # Menu handlers
    # --------------------------------------------------------

    def menuDumpState(self, valuesDict=None, typeId=None):
        if not self.devices:
            log("No Appliance Monitor devices configured.")
            return
        for dev_id in self.devices:
            dev = indigo.devices[dev_id]
            log(
                f"{dev.name}: state={dev.states.get('cycleState')} "
                f"watts={dev.states.get('currentWatts')} "
                f"startedAt={dev.states.get('cycleStartedAt')} "
                f"finishedAt={dev.states.get('cycleFinishedAt')} "
                f"lowSince={dev.states.get('lowSince')} "
                f"doorNotified={dev.states.get('doorNotified')} "
                f"socketNotified={dev.states.get('socketNotified')}"
            )

    def showPluginInfo(self, valuesDict=None, typeId=None):
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion, extras=[
                ("Tick interval:", f"{TICK_SECONDS} s"),
                ("Tracked devices:", str(len(self.devices))),
            ])
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion}")
