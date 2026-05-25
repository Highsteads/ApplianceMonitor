#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Appliance Monitor - detect cycle start/end on appliances metered
#              by a power-monitoring device (e.g. Shelly). Sends Pushover
#              notifications directly and also fires three Indigo custom
#              events: cycleStarted, doorReady, socketReminder.
# Author:      CliveS & Claude Opus 4.7
# Date:        23-05-2026
# Version:     1.2.2
#
# v1.2.1 (23-05-2026): Millisecond timestamp [HH:MM:SS.mmm] prefix on every
# log line via plugin_utils.install_timestamp_filter() — matches Device
# Activity Monitor convention. New "Toggle Timestamps in Log" menu item.

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
try:
    from plugin_utils import install_timestamp_filter
except ImportError:
    install_timestamp_filter = None


# ============================================================
# Constants
# ============================================================

PLUGIN_ID       = "com.clives.indigoplugin.appliancemonitor"
PLUGIN_VERSION  = "1.2.2"
PUSHOVER_PLUGIN = "io.thechad.indigoplugin.pushover"
TICK_SECONDS    = 20

VALID_STATES    = ("idle", "running", "finishing", "doorWait")


# ============================================================
# Helpers
# ============================================================

def log(message, level="INFO"):
    indigo.server.log(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}", level=level)


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
        self.runtime         = {}   # {dev.id: {"peak": float, "kwh_start": float|None}}
                                    # transient per-cycle metrics, reset on every _enter_running
        self.timestamp_enabled = bool(pluginPrefs.get("timestampEnabled", True))

        if install_timestamp_filter:
            self._ts_filter = install_timestamp_filter(self, enabled=self.timestamp_enabled)
        else:
            self._ts_filter = None

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
        # New states in v1.2 (lastCyclePeakWatts, lastCycleEnergyKwh) won't
        # appear on devices created before v1.2 until first written —
        # refresh the state list and re-fetch (see global CLAUDE.md gotcha).
        dev.stateListOrDisplayStateIdChanged()
        dev = indigo.devices[dev.id]
        # Seed defaults so the device states are populated even before the
        # first tick (otherwise control pages show blanks).
        if dev.states.get("cycleState") not in VALID_STATES:
            dev.updateStateOnServer("cycleState", value="idle")
        for key in ("cycleStartedAt", "cycleFinishedAt", "lowSince", "lastCycleMinutes"):
            if not dev.states.get(key):
                dev.updateStateOnServer(key, value=0)
        for key in ("lastCyclePeakWatts", "lastCycleEnergyKwh"):
            if dev.states.get(key) in (None, ""):
                dev.updateStateOnServer(key, value=0.0, uiValue="0.0")
        for key in ("doorNotified", "socketNotified"):
            if dev.states.get(key) is None:
                dev.updateStateOnServer(key, value=False)
        self.devices[dev.id] = dev
        self.runtime[dev.id] = {"peak": 0.0, "kwh_start": None}

    def deviceStopComm(self, dev):
        self.devices.pop(dev.id, None)
        self.runtime.pop(dev.id, None)
        self.logger.info(f"Stopped watching: {dev.name}")

    @staticmethod
    def didDeviceCommPropertyChange(oldDevice, newDevice):
        """Restart comm only when the monitored source binding changes.

        sourceDeviceId selects which power-meter device to watch;
        sourceStateKey / sourceEnergyStateKey pick the value keys on it.
        Thresholds, debounce minutes and notification settings are re-read
        live by the running monitor — no restart needed.
        """
        keys = ("sourceDeviceId", "sourceStateKey", "sourceEnergyStateKey")
        return any(oldDevice.pluginProps.get(k) != newDevice.pluginProps.get(k) for k in keys)

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
            peakW   = _f(dev.states.get("lastCyclePeakWatts"), 0.0),
            kwh     = _f(dev.states.get("lastCycleEnergyKwh"), 0.0),
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
        energy_key   = (props.get("sourceEnergyStateKey", "energyKwhToday") or "").strip()
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
                self._enter_running(dev, now, src, energy_key)

        elif state == "running":
            self._track_peak(dev, watts)
            if watts < idle_w:
                dev.updateStateOnServer("lowSince", value=now)
                dev.updateStateOnServer("cycleState", value="finishing")
                if self.debug:
                    self.logger.debug(f"[{dev.name}] entered finishing at {now}")

        elif state == "finishing":
            self._track_peak(dev, watts)
            if watts >= run_w:
                dev.updateStateOnServer("lowSince", value=0)
                dev.updateStateOnServer("cycleState", value="running")
                if self.debug:
                    self.logger.debug(f"[{dev.name}] returned to running")
            else:
                low_since = _i(dev.states.get("lowSince"), 0)
                if low_since and (now - low_since) >= debounce_s:
                    self._enter_door_wait(dev, finished_at=low_since,
                                          src=src, energy_key=energy_key)

        elif state == "doorWait":
            if watts >= run_w:
                # new cycle - cancel pending notifications, jump to running
                self._enter_running(dev, now, src, energy_key)
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

    def _track_peak(self, dev, watts):
        """Update the in-cycle peak-watts tracker."""
        rt = self.runtime.setdefault(dev.id, {"peak": 0.0, "kwh_start": None})
        if watts > rt["peak"]:
            rt["peak"] = watts

    def _enter_running(self, dev, now, src=None, energy_key=""):
        prev = dev.states.get("cycleState", "idle")
        # Snapshot the source energy counter so we can compute kWh used at
        # the end of the cycle. None means "no counter available".
        kwh_start = None
        if src is not None and energy_key:
            kwh_start = _f(src.states.get(energy_key), -1.0)
            if kwh_start < 0:
                kwh_start = None
        self.runtime[dev.id] = {"peak": 0.0, "kwh_start": kwh_start}

        dev.updateStateOnServer("cycleState",      value="running")
        dev.updateStateOnServer("cycleStartedAt",  value=now)
        dev.updateStateOnServer("lowSince",        value=0)
        dev.updateStateOnServer("doorNotified",    value=False)
        dev.updateStateOnServer("socketNotified",  value=False)
        log(f"{dev.name}: cycle started")
        if prev != "running":
            self._notify(dev, "cycleStarted")

    def _enter_door_wait(self, dev, finished_at, src=None, energy_key=""):
        started_at = _i(dev.states.get("cycleStartedAt"), 0)
        minutes    = (finished_at - started_at) // 60 if started_at else 0

        # Finalise cycle metrics: peak watts and energy used.
        rt        = self.runtime.get(dev.id, {"peak": 0.0, "kwh_start": None})
        peak_w    = float(rt.get("peak", 0.0))
        kwh_start = rt.get("kwh_start")
        kwh_used  = 0.0
        if kwh_start is not None and src is not None and energy_key:
            kwh_now = _f(src.states.get(energy_key), -1.0)
            if kwh_now >= 0:
                kwh_used = kwh_now - kwh_start
                # Counter rollover (e.g. energyKwhToday at midnight) would
                # produce a negative delta — clamp to 0 and log if debug.
                if kwh_used < 0:
                    if self.debug:
                        self.logger.debug(
                            f"[{dev.name}] energy counter rollover detected "
                            f"({kwh_start:.3f} -> {kwh_now:.3f}); cycle kWh set to 0"
                        )
                    kwh_used = 0.0

        dev.updateStateOnServer("cycleState",         value="doorWait")
        dev.updateStateOnServer("cycleFinishedAt",    value=finished_at)
        dev.updateStateOnServer("lastCycleMinutes",   value=minutes)
        dev.updateStateOnServer("lastCyclePeakWatts", value=peak_w,
                                uiValue=f"{peak_w:.0f} W")
        dev.updateStateOnServer("lastCycleEnergyKwh", value=round(kwh_used, 3),
                                uiValue=f"{kwh_used:.3f} kWh")
        dev.updateStateOnServer("lowSince",           value=0)
        dev.updateStateOnServer("doorNotified",       value=False)
        dev.updateStateOnServer("socketNotified",     value=False)
        # Reset runtime so the next cycle starts clean.
        self.runtime[dev.id] = {"peak": 0.0, "kwh_start": None}

        if kwh_start is not None:
            log(f"{dev.name}: cycle ended (duration {minutes} min, "
                f"peak {peak_w:.0f} W, used {kwh_used:.3f} kWh)")
        else:
            log(f"{dev.name}: cycle ended (duration {minutes} min, "
                f"peak {peak_w:.0f} W)")

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
                f"lastCycle={dev.states.get('lastCycleMinutes')}min "
                f"peak={dev.states.get('lastCyclePeakWatts')}W "
                f"kwh={dev.states.get('lastCycleEnergyKwh')} "
                f"doorNotified={dev.states.get('doorNotified')} "
                f"socketNotified={dev.states.get('socketNotified')}"
            )

    def showPluginInfo(self, valuesDict=None, typeId=None):
        extras = [
            ("Tick interval:", f"{TICK_SECONDS} s"),
            ("Tracked devices:", str(len(self.devices))),
            ("Timestamps in Log:", "ON" if self.timestamp_enabled else "OFF"),
        ]
        if log_startup_banner:
            log_startup_banner(self.pluginId, self.pluginDisplayName, self.pluginVersion, extras=extras)
        else:
            indigo.server.log(f"{self.pluginDisplayName} v{self.pluginVersion}")
            for label, value in extras:
                indigo.server.log(f"  {label} {value}")

    def menuToggleTimestamps(self):
        self.timestamp_enabled = not self.timestamp_enabled
        self.pluginPrefs["timestampEnabled"] = self.timestamp_enabled
        if self._ts_filter:
            self._ts_filter.enabled = self.timestamp_enabled
        state = "ON" if self.timestamp_enabled else "OFF"
        indigo.server.log(f"[{self.pluginDisplayName}] Timestamps in Log -> {state}")
