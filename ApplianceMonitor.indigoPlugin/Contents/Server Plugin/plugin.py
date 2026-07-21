#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    plugin.py
# Description: Appliance Monitor - detect cycle start/end on appliances metered
#              by a power-monitoring device (e.g. Shelly). Sends Pushover
#              notifications directly and also fires three Indigo custom
#              events: cycleStarted, doorReady, socketReminder.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.8.0
#
# v1.8.0 (21-07-2026): Deep-review batch 3 — the mediums.
# * A cycle is no longer thrown away when the meter goes offline while the
#   plugin is waiting out the end-of-cycle debounce. The duration, peak and
#   energy are written first, then the appliance moves to "off".
# * A missing or deleted source device used to log the same error every 20
#   seconds forever. It is now logged once on entry, repeated at most hourly,
#   marks the appliance device red in the Indigo device list, and clears with
#   a single line when the meter comes back.
# * A mistyped power state name behaved exactly like a meter reading 0 W, so
#   the appliance simply never ran and nothing was ever logged. Both state
#   names are now checked when the config dialog is saved, and a key that
#   disappears at runtime raises the same one-shot fault.
# * A cycle spanning midnight on a daily kWh counter used to swallow the whole
#   reading behind a debug-only line. It now warns for real and reports the
#   energy as unmeasured rather than as a confident 0.000 kWh, so no cost is
#   invented from it.
# * A trigger saved without an appliance chosen quietly fired for EVERY
#   appliance. It is now rejected when the trigger is saved, and an existing
#   one warns once and fires for nothing.
# * One deleted or broken trigger no longer swallows the Pushover, the email
#   and the rest of that appliance's tick.
# * Pushover user keys and email addresses are masked in the log. A Pushover
#   user key is a credential, and event logs get pasted into forum posts.
#
# v1.7.1 (21-07-2026): Deep-review batch 2 — first test suite (87 tests,
# tests/ at the repo root, no Indigo or hardware needed). Writing it found
# two real defects in v1.7.0, both fixed here:
# * validateDeviceConfigUi refused a device whose new optional minimums were
#   absent, which is every device upgraded from an earlier version — it
#   blocked saving the config dialog. Missing/blank now reads as 0 (off).
# * The cycle-energy ceiling was derived from a duration of 0 when the start
#   time was UNKNOWN, collapsing the ceiling and rejecting real cycles. An
#   unknown duration now falls back to the absolute cap.
#
# v1.7.0 (21-07-2026): TRUST NOTHING FROM THE METER. Deep-review batch 1.
# * Cycle energy is now bounded by physics. A cycle cannot use more than its
#   peak draw sustained for its whole duration, so an absurd delta from a
#   glitching source meter is rejected with a WARNING instead of being stored,
#   costed and pushed to the user. Live case: a source reporting a lifetime
#   total in a "today" counter recorded 3446.586 kWh for a 3-minute, 5.2 W
#   cycle, armed to notify "~£912" once a rate variable was configured.
# * Costing is skipped outright whenever the energy figure was not believable,
#   and the import rate must now fall in a sane pence/kWh band.
# * In-flight cycle metrics (peak watts, energy baseline) are now device states
#   as well as in-memory, so a restart part-way through a cycle no longer
#   reports 0.000 kWh and a partial peak.
# * A cycle needs two consecutive above-threshold ticks to start, and can be
#   discarded on completion by new per-appliance minimums (minCycleMinutes,
#   minCyclePeakWatts, both default 0 = off), so a standby blip no longer
#   fires three notifications.
# * log() now maps its level name to a real logging level. Indigo silently
#   ignores a STRING level, so every warning this plugin raised had been
#   logging as a plain Info line.
# * A mistyped energy state key now warns instead of failing silently forever,
#   and the socket reminder must be later than the door-ready delay.
#
# v1.6.0 (15-06-2026): EMAIL ENABLE/SILENCE TOGGLE. New per-appliance
# ConfigUI checkbox emailEnabled (default True). When unticked, the email
# recipients stay saved on the device but NO email is sent — so the email
# channel can be kept on file as a dormant fallback without double-notifying
# alongside Pushover. _send_email returns early when the box is unticked.
# Defaults True so existing installs that rely on emailRecipients are
# unaffected. Read live from pluginProps, so no restart needed.
#
# v1.5.0 (15-06-2026): EXTRA PUSHOVER RECIPIENTS. New optional per-appliance
# ConfigUI field pushoverAlsoNotify — a comma-separated list of additional
# Pushover user keys (or a delivery-group key). Each gets an identical copy
# of every alert ON TOP OF the primary recipient (the override token if set,
# otherwise the Pushover plugin's default user). Use it to add a partner who
# has their own Pushover account without losing your own alerts. _send_pushover
# now loops over the de-duped recipient list, sending one Pushover per key.
# Blank field = primary recipient only (unchanged behaviour). Read live from
# pluginProps, so no restart needed.
#
# v1.4.0 (15-06-2026): EMAIL NOTIFICATIONS. New optional per-appliance
# ConfigUI field emailRecipients — a comma-separated list of email
# addresses. When set, every notification that already goes out by
# Pushover (gated by the same notifyCycleStarted / notifyDoorReady /
# notifySocketReminder checkboxes) is ALSO emailed to those recipients
# via indigo.server.sendEmailTo() — the Email+ plugin's first SMTP
# server. The Pushover title becomes the subject and the Pushover body
# the message. Lets people without the Pushover app (e.g. a partner)
# still get the alerts. Blank field = feature off (Pushover only, no
# behaviour change). Read live from pluginProps, so no restart needed.
#
# v1.3.0 (11-06-2026): COST-PER-CYCLE. New optional ConfigUI field
# rateVariableName — the name of an Indigo variable holding the electricity
# import rate in pence/kWh (e.g. "tracker_rate_today"). When set, every
# finished cycle computes cost = cycle kWh × rate at cycle end, written to
# new states lastCycleCostGbp + lastCycleRateP, appended to the cycle-ended
# log line, and added to the doorReady Pushover ("Used 0.84 kWh (~£0.20)").
# Honest caveat: this is "at today's import rate" — solar/battery homes may
# have drawn some of it free. Unreadable/missing variable logs a WARNING and
# skips costing; blank field = feature off (no behaviour change).
#
# v1.2.5 (30-05-2026): Source-offline detection — when the source
# power-meter (e.g. Shelly) reports deviceOnline=False, the appliance
# has been physically powered off (wall switch / unplugged). AM now
# transitions to a new cycleState "off" (added to VALID_STATES) in
# the non-running states (idle / finishing / doorWait), cancels any
# pending socket-reminder Pushover, and stays there until the source
# comes back online (then reverts to idle, ready to detect the next
# cycle). Mid-cycle (running state) ignores transient offline events
# to avoid false drops on a network blip. No new ConfigUI — the
# behaviour only triggers when the source actually emits
# deviceOnline=False, so devices with no such state are unaffected.
#
# v1.2.4 (30-05-2026): Per-device Pushover title overrides — three new
# ConfigUI fields (titleCycleStarted / titleDoorReady / titleSocketReminder)
# let each appliance customise its own notification titles. Defaults are
# appliance-agnostic ("Cycle started" / "Cycle done" / "Switch off socket"),
# replacing the wash-specific wording that previously came through on
# every appliance (e.g. "Wash done" appearing on Tumble Dryer alerts).
# Empty field falls back to the appliance-agnostic default — existing
# devices upgrade silently with no config touch needed.
#
# v1.2.3 (30-05-2026): debounceMinutes now accepts 0 (disables debounce —
# cycle declared ended on first sub-idle reading). Useful for appliances
# whose final phase never dips below idleThresholdWatts before fully
# stopping (e.g. washing machines whose drain pump finishes >2 W and then
# drops cleanly to 0 W).
#
# v1.2.1 (23-05-2026): Millisecond timestamp [HH:MM:SS.mmm] prefix on every
# log line via plugin_utils.install_timestamp_filter() — matches Device
# Activity Monitor convention. New "Toggle Timestamps in Log" menu item.

try:
    import indigo
except ImportError:
    pass

import logging
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
PLUGIN_VERSION  = "1.8.0"
PUSHOVER_PLUGIN = "io.thechad.indigoplugin.pushover"
TICK_SECONDS    = 20

VALID_STATES    = ("idle", "running", "finishing", "doorWait", "off")
# Non-running states where source-offline → "off" is meaningful.
# "running" is excluded so a transient mid-cycle network blip never
# falsely drops cycle tracking.
_OFFLINE_OK_STATES = ("idle", "finishing", "doorWait")

# Cycle-energy plausibility guard (v1.7.0). A cycle cannot use more energy
# than its peak draw sustained for its whole duration, so the measured peak
# and duration give a hard ceiling. SLACK covers metering jitter and a peak
# sampled slightly below the true one.
KWH_PLAUSIBILITY_SLACK = 1.5
# Absolute ceiling for one appliance cycle, used when no usable peak was
# measured (e.g. the peak was lost with a restart part-way through).
MAX_CYCLE_KWH          = 20.0
# Import-rate sanity band in pence/kWh. Outside this the variable almost
# certainly holds something other than pence — pounds, a typo, a sentinel.
MIN_RATE_P             = 0.5
MAX_RATE_P             = 200.0
# Consecutive above-threshold ticks before a cycle is declared, so a single
# stray reading cannot invent one.
START_CONFIRM_TICKS    = 2
# Schema marker for the in-flight cycle states. Bump only when their meaning
# changes and existing values must be discarded rather than trusted.
CYCLE_STATE_VERSION    = 1
# A persistent source fault (missing device, missing state key) is logged once
# when it starts and then at most this often, rather than on every 20 s tick.
FAULT_REPEAT_SECONDS   = 3600


# ============================================================
# Helpers
# ============================================================

_LOG_LEVELS = {
    "DEBUG":   logging.DEBUG,
    "INFO":    logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR":   logging.ERROR,
}


def log(message, level="INFO"):
    """Log through indigo.server.log with a millisecond timestamp.

    Indigo's level= wants a Python logging level INT. Passing the string
    "WARNING" does not raise — it is silently ignored and the line logs as
    plain Info, which hid every warning this plugin raised until v1.7.0.
    Map the name to the int and fall back to Info for anything unrecognised.
    """
    if not isinstance(level, int):
        level = _LOG_LEVELS.get(str(level).upper(), logging.INFO)
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


def _as_bool(value, default=False):
    """Coerce an Indigo value to a bool without being fooled by "false".

    Device states and pluginProps can both come back as strings — a state
    published by another plugin, or a checkbox re-serialised when a config
    dialog is saved. bool("false") is True, which is exactly the wrong answer.
    """
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _mask_key(value):
    """Mask a Pushover user key for the log.

    A Pushover user key is a credential and Indigo event logs get pasted whole
    into forum support posts. The first few characters are enough to tell two
    recipients apart while leaving the key unusable.
    """
    key = (value or "").strip()
    if not key:
        return "default user"
    if len(key) <= 8:
        return f"{key[:2]}..."
    return f"{key[:4]}...{key[-2:]}"


def _mask_email(value):
    """Mask an email address for the log — first character plus the domain."""
    addr = (value or "").strip()
    if "@" not in addr:
        return "(address hidden)"
    local, _, domain = addr.partition("@")
    return f"{local[:1]}...@{domain}"


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
        self.source_faults   = {}   # {dev.id: {"key": str, "logged": float}}
                                    # latched source faults, so a missing meter is
                                    # logged once rather than every 20 seconds
        self.bad_triggers    = set()   # trigger ids already warned about
        self.timestamp_enabled = bool(pluginPrefs.get("timestampEnabled", True))

        if install_timestamp_filter:
            self._ts_filter = install_timestamp_filter(self, enabled=self.timestamp_enabled)
        else:
            self._ts_filter = None

        # Startup banner moved to showPluginInfo on demand (revised 25-May-2026 per Jay).

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
        for key in ("lastCyclePeakWatts", "lastCycleEnergyKwh",
                    "lastCycleCostGbp", "lastCycleRateP"):
            if dev.states.get(key) in (None, ""):
                dev.updateStateOnServer(key, value=0.0, uiValue="0.0")
        for key in ("doorNotified", "socketNotified"):
            if dev.states.get(key) is None:
                dev.updateStateOnServer(key, value=False)
        self.devices[dev.id] = dev

        # Rebuild the in-flight cycle metrics from the persisted states rather
        # than zeroing them (v1.7.0). cycleState survives a restart, so the
        # peak and energy baseline that belong to it must survive too —
        # otherwise a restart part-way through a wash finishes the cycle
        # reporting 0.000 kWh and a peak measured only from the tail.
        # One-time upgrade for devices created before v1.7.0. A brand-new Number
        # state materialises as 0.0, which is indistinguishable from a genuine
        # energy baseline of zero, so a marker state is the only safe signal.
        # A new Integer state also reads 0, which is exactly what we want here.
        if _i(dev.states.get("cycleStateVersion"), 0) < CYCLE_STATE_VERSION:
            dev.updateStateOnServer("cyclePeakWatts", value=0.0, uiValue="0 W")
            dev.updateStateOnServer("cycleKwhStart",  value=-1.0, uiValue="n/a")
            # Clear any historical cycle energy that this version would reject.
            # Installs upgrading from an earlier version can be carrying an
            # impossible figure from a source meter that misreported, and it
            # would otherwise sit on control pages until the next cycle ends.
            stale_kwh = _f(dev.states.get("lastCycleEnergyKwh"), 0.0)
            if stale_kwh > MAX_CYCLE_KWH:
                log(f"{dev.name}: clearing an impossible stored cycle energy of "
                    f"{stale_kwh:.3f} kWh left by an earlier version", level="WARNING")
                dev.updateStateOnServer("lastCycleEnergyKwh", value=0.0, uiValue="n/a")
                dev.updateStateOnServer("lastCycleCostGbp",   value=0.0, uiValue="—")
                dev.updateStateOnServer("lastCycleRateP",     value=0.0, uiValue="—")
            dev.updateStateOnServer("cycleStateVersion", value=CYCLE_STATE_VERSION)
            peak_so_far, stored_base = 0.0, -1.0
        else:
            peak_so_far = _f(dev.states.get("cyclePeakWatts"), 0.0)
            stored_base = _f(dev.states.get("cycleKwhStart"), -1.0)
        self.runtime[dev.id] = {
            "peak":      peak_so_far,
            "kwh_start": stored_base if stored_base >= 0 else None,
            "above":     0,
        }
        if dev.states.get("cycleState") == "running":
            self.logger.info(
                f"  {dev.name}: resuming a cycle already in progress "
                f"(peak so far {peak_so_far:.0f} W, energy baseline "
                f"{'recovered' if stored_base >= 0 else 'unavailable — this cycle will not report energy'})"
            )

    def deviceStopComm(self, dev):
        self.devices.pop(dev.id, None)
        self.runtime.pop(dev.id, None)
        self.source_faults.pop(dev.id, None)
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
        elif devId and src_id == _i(devId, 0):
            errors["sourceDeviceId"] = "An appliance cannot watch itself — pick the power meter."
        else:
            # Both state names are free text, and a typo used to behave exactly
            # like a meter reporting 0 W: the appliance never ran and nothing
            # was ever logged. Check them against the meter's real state list.
            src  = indigo.devices[src_id]
            keys = sorted(str(k) for k in src.states.keys() if not str(k).endswith(".ui"))
            offer = ", ".join(keys[:12]) or "(none)"
            power_key = (valuesDict.get("sourceStateKey") or "").strip()
            if not power_key:
                errors["sourceStateKey"] = "Name the state on the meter that reports watts."
            elif power_key not in src.states:
                errors["sourceStateKey"] = (
                    f"'{src.name}' has no state called '{power_key}'. Available: {offer}"
                )
            energy_key = (valuesDict.get("sourceEnergyStateKey") or "").strip()
            if energy_key and energy_key not in src.states:
                errors["sourceEnergyStateKey"] = (
                    f"'{src.name}' has no state called '{energy_key}'. Leave it blank if the "
                    f"meter has no kWh counter. Available: {offer}"
                )
        rate_var = (valuesDict.get("rateVariableName") or "").strip()
        if rate_var and rate_var not in indigo.variables:
            errors["rateVariableName"] = "No Indigo variable with that name."
        run_w  = _f(valuesDict.get("runThresholdWatts"), -1)
        idle_w = _f(valuesDict.get("idleThresholdWatts"), -1)
        if run_w <= 0:
            errors["runThresholdWatts"] = "Must be a positive number of watts."
        if idle_w < 0:
            errors["idleThresholdWatts"] = "Must be zero or a positive number of watts."
        if run_w > 0 and idle_w >= run_w:
            errors["idleThresholdWatts"] = "Idle threshold must be less than run threshold."
        if _i(valuesDict.get("debounceMinutes"), -1) < 0:
            errors["debounceMinutes"] = "Must be zero or a positive integer (minutes); 0 disables debounce."
        if _i(valuesDict.get("doorDelayMinutes"), -1) < 0:
            errors["doorDelayMinutes"] = "Must be zero or a positive integer (minutes)."
        door_min   = _i(valuesDict.get("doorDelayMinutes"), -1)
        socket_min = _i(valuesDict.get("socketReminderMinutes"), -1)
        if socket_min < 1:
            errors["socketReminderMinutes"] = "Must be a positive integer (minutes)."
        elif door_min >= 0 and socket_min <= door_min:
            # Otherwise both notifications land on the same tick and the cycle
            # resets to idle immediately after the door-ready alert.
            errors["socketReminderMinutes"] = (
                "Must be greater than the door-ready delay, otherwise both "
                "notifications fire together."
            )
        # Both minimums are optional and default to 0 (off). Absent or blank is
        # the normal case on a device created before v1.7.0, so it must validate
        # as "off" — treating a missing field as invalid would block every
        # existing user from saving their config after upgrading.
        if _i(valuesDict.get("minCycleMinutes") or 0, -1) < 0:
            errors["minCycleMinutes"] = "Must be zero or a positive integer (minutes); 0 disables the check."
        if _f(valuesDict.get("minCyclePeakWatts") or 0, -1) < 0:
            errors["minCyclePeakWatts"] = "Must be zero or a positive number of watts; 0 disables the check."
        if errors:
            return (False, valuesDict, errors)
        return (True, valuesDict)

    # --------------------------------------------------------
    # Trigger lifecycle - per CLAUDE.md, the only way to fire events
    # --------------------------------------------------------

    def validateEventConfigUi(self, valuesDict, typeId, eventId):
        """An appliance must actually be chosen.

        A blank selection used to mean "fire for every appliance", silently, so
        a trigger saved before the appliance was picked went off for the whole
        house. Reject it at save time instead.
        """
        errors = indigo.Dict()
        target = str(valuesDict.get("applianceDevice", "") or "").strip()
        if not target.isdigit():
            errors["applianceDevice"] = "Choose which appliance this trigger listens to."
        if errors:
            return (False, valuesDict, errors)
        return (True, valuesDict)

    def triggerStartProcessing(self, trigger):
        self.event_triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.event_triggers.pop(trigger.id, None)
        self.bad_triggers.discard(trigger.id)

    def _fire_event(self, dev, event_id):
        """Fire every trigger whose pluginTypeId matches event_id AND whose
        applianceDevice points at dev.id.

        Fails closed: a trigger with no appliance chosen fires for nothing and
        warns once, rather than firing for every appliance the plugin ticks.
        Each execute is guarded on its own so one deleted or broken trigger
        cannot swallow the Pushover, the email and the rest of the tick.
        """
        fired = 0
        for trigger in list(self.event_triggers.values()):
            if trigger.pluginTypeId != event_id:
                continue
            target = str(trigger.pluginProps.get("applianceDevice", "") or "").strip()
            if not target.isdigit():
                if trigger.id not in self.bad_triggers:
                    self.bad_triggers.add(trigger.id)
                    self.logger.warning(
                        f"Trigger '{getattr(trigger, 'name', trigger.id)}' has no appliance "
                        f"chosen, so it will never fire. Open it and pick one."
                    )
                continue
            if int(target) != dev.id:
                continue
            try:
                indigo.trigger.execute(trigger)
                fired += 1
            except Exception:
                self.logger.exception(
                    f"[{dev.name}] could not execute trigger "
                    f"'{getattr(trigger, 'name', trigger.id)}' for event {event_id}"
                )
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
        base = {
            "msgTitle":    title,
            "msgBody":     body,
            "msgPriority": str(props.get("pushoverPriority", "0") or "0"),
            "msgSound":    props.get("pushoverSound", "vibrate") or "vibrate",
        }
        # Primary recipient: the override token if set, otherwise None — which
        # leaves msgUser off so the Pushover plugin uses its configured default.
        primary = (props.get("pushoverUserToken") or "").strip() or None
        # Extra recipients (e.g. a partner's own user key, or a delivery-group
        # key) each get an identical copy on top of the primary.
        extras = [
            key.strip()
            for key in (props.get("pushoverAlsoNotify") or "").split(",")
            if key.strip()
        ]
        # De-dupe while preserving order; None (the default user) is a distinct
        # recipient and must survive the de-dupe.
        recipients = []
        for r in [primary] + extras:
            if r not in recipients:
                recipients.append(r)
        for user in recipients:
            # Masked — a Pushover user key is a credential, and event logs get
            # pasted whole into forum support posts.
            who = _mask_key(user)
            msg = dict(base)
            if user:
                msg["msgUser"] = user
            try:
                pushover.executeAction("send", props=msg)
                if self.debug:
                    self.logger.debug(f"[{dev.name}] Pushover sent to {who}: {title} / {body}")
            except Exception:
                self.logger.exception(f"[{dev.name}] Pushover send to {who} failed")

    def _send_email(self, dev, subject, body):
        """Email the same notification to any per-device recipients.

        Uses indigo.server.sendEmailTo() (NOT executeAction) — it bypasses
        the cross-plugin prop-serialisation bug and picks the first Email+
        SMTP device automatically. Each address is sent individually so one
        bad address doesn't block the rest. Blank field = no email.

        The emailEnabled checkbox (default True) silences this channel without
        clearing the recipients — untick it to keep the addresses on file as a
        dormant fallback while Pushover does the live notifying.
        """
        if not _as_bool(dev.pluginProps.get("emailEnabled", True), True):
            return
        recipients = [
            addr.strip()
            for addr in (dev.pluginProps.get("emailRecipients") or "").split(",")
            if addr.strip()
        ]
        if not recipients:
            return
        for addr in recipients:
            try:
                indigo.server.sendEmailTo(addr, subject=subject, body=body)
                if self.debug:
                    self.logger.debug(
                        f"[{dev.name}] email sent to {_mask_email(addr)}: {subject}")
            except Exception:
                self.logger.exception(
                    f"[{dev.name}] email send to {_mask_email(addr)} failed")

    # Per-event notification config:
    #   checkbox_key   — pluginProps key that gates sending
    #   title_key      — pluginProps key holding a per-device title override
    #                    (empty/missing → use default_title below)
    #   default_title  — appliance-agnostic default (so a Tumble Dryer doesn't
    #                    Pushover "Wash done")
    #   body_template  — supports {name}, {minutes}, {peakW}, {kwh}
    _NOTIFY_CONFIG = {
        "cycleStarted":   ("notifyCycleStarted",   "titleCycleStarted",
                           "Cycle started",
                           "{name}: cycle started."),
        "doorReady":      ("notifyDoorReady",      "titleDoorReady",
                           "Cycle done",
                           "{name}: cycle complete after {minutes} min — door unlocking now."),
        "socketReminder": ("notifySocketReminder", "titleSocketReminder",
                           "Switch off socket",
                           "{name}: no new cycle started — please switch the wall socket off."),
    }

    def _notify(self, dev, event_id):
        """Fire the matching Indigo event AND, if enabled, send a Pushover."""
        self._fire_event(dev, event_id)

        cfg = self._NOTIFY_CONFIG.get(event_id)
        if not cfg:
            return
        checkbox_key, title_key, default_title, body_template = cfg
        if not _as_bool(dev.pluginProps.get(checkbox_key), False):
            return
        # Per-device override wins; empty/missing/whitespace falls back.
        title = (dev.pluginProps.get(title_key) or "").strip() or default_title
        body = body_template.format(
            name    = dev.name,
            minutes = _i(dev.states.get("lastCycleMinutes"), 0),
            peakW   = _f(dev.states.get("lastCyclePeakWatts"), 0.0),
            kwh     = _f(dev.states.get("lastCycleEnergyKwh"), 0.0),
        )
        # Cycle-done notifications carry the cost when one was measured.
        if event_id == "doorReady":
            kwh  = _f(dev.states.get("lastCycleEnergyKwh"), 0.0)
            cost = _f(dev.states.get("lastCycleCostGbp"), 0.0)
            if cost > 0:
                body += f" Used {kwh:.2f} kWh (~£{cost:.2f})."
            elif kwh > 0:
                body += f" Used {kwh:.2f} kWh."
        self._send_pushover(dev, title, body)
        self._send_email(dev, title, body)

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

    def _set_source_fault(self, dev, key, message, ui_message):
        """Record a source fault, logging it once rather than every tick.

        The same missing device used to log an ERROR every 20 seconds for every
        appliance, forever. Log it on entry, repeat at most hourly so it is not
        lost from a long log, and mark the device red so the fault is visible
        in the Indigo device list without reading the log at all.
        """
        now   = time.time()
        fault = self.source_faults.get(dev.id)
        if fault is None or fault["key"] != key:
            self.logger.error(message)
            self.source_faults[dev.id] = {"key": key, "logged": now}
            try:
                dev.setErrorStateOnServer(ui_message)
            except Exception:
                self.logger.debug("could not set the device error state", exc_info=True)
        elif (now - fault["logged"]) >= FAULT_REPEAT_SECONDS:
            self.logger.error(message)
            fault["logged"] = now

    def _clear_source_fault(self, dev):
        """Clear a latched source fault once the meter reads properly again."""
        if self.source_faults.pop(dev.id, None) is None:
            return
        self.logger.info(f"[{dev.name}] power meter readable again")
        try:
            dev.setErrorStateOnServer(None)
        except Exception:
            self.logger.debug("could not clear the device error state", exc_info=True)

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
            self._set_source_fault(
                dev, "missing-device",
                f"[{dev.name}] the power meter it watches is not configured or no longer "
                f"exists (device id {src_id}). Open this appliance's settings and pick one.",
                "no source device")
            return

        src = indigo.devices[src_id]
        if state_key not in src.states:
            # Without this the read below silently returns 0.0 W, so a mistyped
            # state name leaves the appliance idle forever with nothing logged.
            keys = sorted(str(k) for k in src.states.keys() if not str(k).endswith(".ui"))
            self._set_source_fault(
                dev, f"missing-state:{state_key}",
                f"[{dev.name}] meter '{src.name}' has no state called '{state_key}', so no "
                f"power reading can be taken. Available states: "
                f"{', '.join(keys[:12]) or '(none)'}",
                "no power state")
            return
        self._clear_source_fault(dev)

        watts = _f(src.states.get(state_key), 0.0)
        now   = int(time.time())
        state = dev.states.get("cycleState", "idle")

        dev.updateStateOnServer("currentWatts", value=watts, uiValue=f"{watts:.1f} W")

        if self.debug:
            self.logger.debug(f"[{dev.name}] state={state} watts={watts:.1f}")

        # --------------------------------------------------------
        # Source online / offline handling (v1.2.5)
        #
        # If the source device exposes a deviceOnline state and reports
        # False, the appliance has been physically powered off (wall
        # switch / unplugged → Shelly lost mains). In non-running
        # states we drop straight to "off" — this cancels the pending
        # socket-reminder Pushover. We ignore offline in "running" to
        # avoid mid-cycle network blips falsely dropping cycle tracking.
        #
        # Default-True so devices that don't track online status (or
        # never go offline) are unaffected.
        # --------------------------------------------------------
        # Coerced rather than tested for truthiness: the state comes from a
        # third-party plugin and a string "false" would otherwise read as True.
        src_online = _as_bool(src.states.get("deviceOnline", True), True)

        if not src_online:
            if state in _OFFLINE_OK_STATES:
                if state != "off":
                    # A cycle waiting out the end-of-cycle debounce is a real,
                    # finished cycle — write its duration, peak and energy
                    # before the appliance goes to "off", instead of losing it.
                    if state == "finishing":
                        low_since = _i(dev.states.get("lowSince"), 0) or now
                        self.logger.info(
                            f"[{dev.name}] the meter went offline while the cycle was "
                            f"finishing — recording the cycle now, then marking the "
                            f"appliance off. No door-ready alert will be sent."
                        )
                        self._enter_door_wait(dev, finished_at=low_since,
                                              src=src, energy_key=energy_key)
                    elif state == "doorWait" and not _as_bool(
                            dev.states.get("doorNotified"), False):
                        self.logger.info(
                            f"[{dev.name}] the meter went offline before the door-ready "
                            f"alert was due, so the cycle ended without one."
                        )
                    self._enter_off(dev)
                return
            # state == "running": ignore offline, keep ticking
        else:
            # Source is online — if we were sitting in "off", revert to
            # idle and continue into the FSM so an already-drawing
            # appliance is promoted to running on the same tick.
            if state == "off":
                log(f"{dev.name}: source back online — resetting to idle")
                self._reset_to_idle(dev)
                state = "idle"

        if state == "idle":
            # Require consecutive above-threshold ticks before declaring a
            # cycle, so one stray reading cannot invent a whole cycle and its
            # three notifications (v1.7.0).
            rt = self.runtime.setdefault(dev.id, {"peak": 0.0, "kwh_start": None, "above": 0})
            if watts >= run_w:
                rt["above"] = rt.get("above", 0) + 1
                if rt["above"] >= START_CONFIRM_TICKS:
                    self._enter_running(dev, now, src, energy_key, watts)
                elif self.debug:
                    self.logger.debug(
                        f"[{dev.name}] above threshold {rt['above']}/{START_CONFIRM_TICKS}"
                    )
            else:
                rt["above"] = 0

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
                self._enter_running(dev, now, src, energy_key, watts)
                return
            finished_at     = _i(dev.states.get("cycleFinishedAt"), 0)
            raw_elapsed     = now - finished_at if finished_at else 0
            if raw_elapsed < 0:
                # A clock step-back would otherwise hold the appliance in
                # doorWait until real time caught up again.
                self.logger.warning(
                    f"[{dev.name}] the cycle appears to have finished "
                    f"{abs(raw_elapsed)} s in the future — check the system clock."
                )
            elapsed         = max(0, raw_elapsed)
            door_notified   = _as_bool(dev.states.get("doorNotified"), False)
            socket_notified = _as_bool(dev.states.get("socketNotified"), False)

            # The notified flag is set BEFORE notifying on purpose: if a channel
            # blows up we must not re-notify every 20 seconds forever. _notify
            # guards each channel internally, so a failure is logged, not lost.
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
        """Update the in-cycle peak-watts tracker.

        Mirrored to a device state so the peak survives a plugin restart.
        Only written when it actually increases, so this costs at most a
        handful of writes per cycle rather than one every tick.
        """
        rt = self.runtime.setdefault(dev.id, {"peak": 0.0, "kwh_start": None, "above": 0})
        if watts > rt["peak"]:
            rt["peak"] = watts
            dev.updateStateOnServer("cyclePeakWatts", value=watts, uiValue=f"{watts:.0f} W")

    def _enter_running(self, dev, now, src=None, energy_key="", watts=0.0):
        prev = dev.states.get("cycleState", "idle")
        # Snapshot the source energy counter so we can compute kWh used at
        # the end of the cycle. None means "no counter available".
        kwh_start = None
        if src is not None and energy_key:
            if energy_key not in src.states:
                # A mistyped key would otherwise fail silently forever, with
                # every cycle reporting no energy and no explanation.
                log(f"{dev.name}: source '{src.name}' has no state '{energy_key}' — "
                    f"cycle energy and cost cannot be measured. Check the "
                    f"Energy state key in this appliance's settings.", level="WARNING")
            else:
                kwh_start = _f(src.states.get(energy_key), -1.0)
                if kwh_start < 0:
                    kwh_start = None
        # Seed the peak with the reading that triggered the cycle, so a short
        # cycle cannot record a 0 W peak.
        self.runtime[dev.id] = {"peak": _f(watts, 0.0), "kwh_start": kwh_start, "above": 0}
        dev.updateStateOnServer("cyclePeakWatts", value=_f(watts, 0.0),
                                uiValue=f"{_f(watts, 0.0):.0f} W")
        dev.updateStateOnServer(
            "cycleKwhStart",
            value=(kwh_start if kwh_start is not None else -1.0),
            uiValue=(f"{kwh_start:.3f} kWh" if kwh_start is not None else "n/a"),
        )

        dev.updateStateOnServer("cycleState",      value="running")
        dev.updateStateOnServer("cycleStartedAt",  value=now)
        dev.updateStateOnServer("lowSince",        value=0)
        dev.updateStateOnServer("doorNotified",    value=False)
        dev.updateStateOnServer("socketNotified",  value=False)
        log(f"{dev.name}: cycle started")
        if prev != "running":
            self._notify(dev, "cycleStarted")

    def _plausible_cycle_kwh(self, dev, kwh_used, peak_w, minutes, kwh_start, kwh_now,
                             duration_known=True):
        """Reject a physically impossible cycle-energy delta.

        A cycle cannot consume more than its peak draw sustained for its whole
        duration, and both are known by the time this is called. Without the
        check, a source meter that briefly reports a lifetime total in a
        "today" counter writes nonsense straight into the stored state, the
        cost, and the notification the user reads.

        Returns the accepted kWh, or None when the delta is not believable.
        """
        # The duration-based ceiling is only meaningful when the duration is
        # actually known. An UNKNOWN duration reads as 0 minutes, which is not
        # the same as a short cycle — trusting it there would collapse the
        # ceiling and reject perfectly real readings. Fall back to the absolute
        # cap instead.
        ceiling = MAX_CYCLE_KWH
        if peak_w > 0 and duration_known:
            physical = (peak_w / 1000.0) * (max(minutes, 1) / 60.0) * KWH_PLAUSIBILITY_SLACK
            # Keep a small floor so a brief cycle with a modest sampled peak
            # cannot reject a perfectly real reading.
            ceiling = min(ceiling, max(physical, 0.05))
        if kwh_used > ceiling:
            log(f"{dev.name}: implausible cycle energy {kwh_used:.3f} kWh rejected — "
                f"a peak of {peak_w:.0f} W over {minutes} min allows at most "
                f"{ceiling:.3f} kWh. Source counter read {kwh_start:.3f} -> {kwh_now:.3f}. "
                f"Energy and cost not recorded for this cycle.", level="WARNING")
            return None
        return kwh_used

    def _enter_door_wait(self, dev, finished_at, src=None, energy_key=""):
        started_at     = _i(dev.states.get("cycleStartedAt"), 0)
        duration_known = started_at > 0
        minutes        = (finished_at - started_at) // 60 if duration_known else 0
        if minutes < 0:
            # A clock step-back between cycle start and end would otherwise
            # report a negative duration and poison the plausibility ceiling.
            # Treat the duration as unknown rather than as zero.
            minutes, duration_known = 0, False

        # Finalise cycle metrics: peak watts and energy used.
        rt        = self.runtime.get(dev.id, {"peak": 0.0, "kwh_start": None})
        peak_w    = float(rt.get("peak", 0.0))
        kwh_start = rt.get("kwh_start")

        # Discard a cycle that fails the configured minimums before anything is
        # recorded or announced. Both default to 0 (off), so upgrading installs
        # keep their existing behaviour until the user opts in.
        min_minutes = _i(dev.pluginProps.get("minCycleMinutes"), 0)
        min_peak    = _f(dev.pluginProps.get("minCyclePeakWatts"), 0.0)
        if (min_minutes and minutes < min_minutes) or (min_peak and peak_w < min_peak):
            log(f"{dev.name}: ignoring a {minutes} min cycle peaking at {peak_w:.0f} W — "
                f"below the minimum set for this appliance "
                f"(min {min_minutes} min, min {min_peak:.0f} W)")
            self._clear_cycle_metrics(dev)
            self._reset_to_idle(dev)
            return

        kwh_used  = 0.0
        kwh_known = False
        if kwh_start is not None and src is not None and energy_key:
            kwh_now = _f(src.states.get(energy_key), -1.0)
            if kwh_now >= 0:
                delta = kwh_now - kwh_start
                # Counter rollover (e.g. energyKwhToday resetting at midnight)
                # gives a negative delta. The cycle's real energy cannot be
                # recovered, so report it as unmeasured rather than as a
                # confident 0.000 kWh — and say so out loud, because a silent
                # zero looks exactly like a cycle that used nothing.
                if delta < 0:
                    self.logger.warning(
                        f"[{dev.name}] the meter's energy counter reset part-way through "
                        f"this cycle ({kwh_start:.3f} -> {kwh_now:.3f} kWh), most likely "
                        f"at midnight. The energy used cannot be worked out, so it is "
                        f"not recorded and no cost is shown for this cycle."
                    )
                    kwh_used, kwh_known = 0.0, False
                else:
                    checked = self._plausible_cycle_kwh(
                        dev, delta, peak_w, minutes, kwh_start, kwh_now,
                        duration_known=duration_known)
                    if checked is None:
                        kwh_used, kwh_known = 0.0, False
                    else:
                        kwh_used, kwh_known = checked, True

        dev.updateStateOnServer("cycleState",         value="doorWait")
        dev.updateStateOnServer("cycleFinishedAt",    value=finished_at)
        dev.updateStateOnServer("lastCycleMinutes",   value=minutes)
        dev.updateStateOnServer("lastCyclePeakWatts", value=peak_w,
                                uiValue=f"{peak_w:.0f} W")
        dev.updateStateOnServer("lastCycleEnergyKwh", value=round(kwh_used, 3),
                                uiValue=(f"{kwh_used:.3f} kWh" if kwh_known else "n/a"))

        # Cost-per-cycle (v1.3.0): kWh used × the import rate (pence/kWh) read
        # from a user-named Indigo variable at cycle end. This is "what the
        # cycle would cost at today's import rate" — homes with solar/battery
        # may have actually drawn some of it free, which is the honest caveat.
        # Costing is skipped outright when the energy figure was not believable
        # (v1.7.0) — a bad kWh must never be turned into a money figure.
        rate_p = 0.0
        rate_var = (dev.pluginProps.get("rateVariableName") or "").strip()
        if rate_var and kwh_known and kwh_used > 0:
            try:
                rate_p = float(indigo.variables[rate_var].value)
            except Exception as exc:
                log(f"{dev.name}: rate variable {rate_var!r} unreadable "
                    f"({exc}) — cycle cost skipped", level="WARNING")
                rate_p = 0.0
            if rate_p and not (MIN_RATE_P <= rate_p <= MAX_RATE_P):
                log(f"{dev.name}: import rate {rate_p} from {rate_var!r} is outside the "
                    f"sane band {MIN_RATE_P}-{MAX_RATE_P} p/kWh — cycle cost skipped. "
                    f"Check the variable holds pence per kWh, not pounds.", level="WARNING")
                rate_p = 0.0
        elif kwh_known and kwh_used > 0 and not rate_var:
            # Otherwise a permanently blank cost column looks like a fault.
            self.logger.info(
                f"[{dev.name}] no rate variable set for this appliance, so the cycle "
                f"cost is not worked out. Set one in the appliance's settings to see it."
            )
        cost_gbp = kwh_used * rate_p / 100.0 if rate_p > 0 else 0.0
        dev.updateStateOnServer("lastCycleCostGbp", value=round(cost_gbp, 3),
                                uiValue=(f"£{cost_gbp:.2f}" if cost_gbp > 0 else "—"))
        dev.updateStateOnServer("lastCycleRateP", value=round(rate_p, 2),
                                uiValue=(f"{rate_p:.2f} p/kWh" if rate_p > 0 else "—"))

        dev.updateStateOnServer("lowSince",           value=0)
        dev.updateStateOnServer("doorNotified",       value=False)
        dev.updateStateOnServer("socketNotified",     value=False)
        # Reset runtime so the next cycle starts clean.
        self._clear_cycle_metrics(dev)

        if kwh_known:
            cost_txt = f", ~£{cost_gbp:.2f} @ {rate_p:.1f}p" if cost_gbp > 0 else ""
            log(f"{dev.name}: cycle ended (duration {minutes} min, "
                f"peak {peak_w:.0f} W, used {kwh_used:.3f} kWh{cost_txt})")
        else:
            log(f"{dev.name}: cycle ended (duration {minutes} min, "
                f"peak {peak_w:.0f} W, energy not measured)")

    def _clear_cycle_metrics(self, dev):
        """Reset the in-flight cycle metrics, in memory and on the device.

        Both live in device states as well as self.runtime so they survive a
        restart, so both have to be cleared together.
        """
        self.runtime[dev.id] = {"peak": 0.0, "kwh_start": None, "above": 0}
        dev.updateStateOnServer("cyclePeakWatts", value=0.0, uiValue="0 W")
        dev.updateStateOnServer("cycleKwhStart",  value=-1.0, uiValue="n/a")

    def _reset_to_idle(self, dev):
        dev.updateStateOnServer("cycleState",     value="idle")
        dev.updateStateOnServer("lowSince",       value=0)
        # Clear both alert latches too, so the next cycle starts from a known
        # position however it was reached (socket reminder sent, cycle
        # discarded as too short, or the meter simply coming back online).
        dev.updateStateOnServer("doorNotified",   value=False)
        dev.updateStateOnServer("socketNotified", value=False)

    def _enter_off(self, dev):
        """Source device offline → appliance physically powered off
        (wall switch / unplugged). Clears any pending socket-reminder
        timing — when source comes back online we revert to idle.
        """
        dev.updateStateOnServer("cycleState",     value="off")
        dev.updateStateOnServer("lowSince",       value=0)
        dev.updateStateOnServer("doorNotified",   value=False)
        dev.updateStateOnServer("socketNotified", value=False)
        log(f"{dev.name}: source device offline — appliance powered off (no socket reminder)")

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
        # pluginPrefs only reach disk on a clean shutdown, so write them now —
        # otherwise the setting is quietly lost if the server is killed.
        try:
            self.savePluginPrefs()
        except Exception:
            self.logger.debug("could not save plugin prefs", exc_info=True)
        if self._ts_filter:
            self._ts_filter.enabled = self.timestamp_enabled
        state = "ON" if self.timestamp_enabled else "OFF"
        indigo.server.log(f"[{self.pluginDisplayName}] Timestamps in Log -> {state}")
