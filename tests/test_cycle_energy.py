#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_cycle_energy.py
# Description: The cycle-energy plausibility guard — the defect that drove the
#              21-07-2026 deep review. A source meter reported a lifetime total
#              in a "today" counter and the plugin stored 3446.586 kWh for a
#              three-minute, 5.2 W cycle, armed to push "~£912" to the user.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import pytest

# A realistic epoch. 0 is 1970 and the plugin reads it as 'start time unknown'.
T0 = 1784600000


def _run_cycle(plugin, dev, src, *, started_at, finished_at, peak_w,
               kwh_start, kwh_now, energy_key="energyKwhToday"):
    """Drive one cycle end with fully controlled inputs."""
    dev.states["cycleStartedAt"] = started_at
    plugin.runtime[dev.id] = {"peak": peak_w, "kwh_start": kwh_start, "above": 0}
    src.states[energy_key] = kwh_now
    plugin._enter_door_wait(dev, finished_at=finished_at, src=src, energy_key=energy_key)
    return dev.states


# --------------------------------------------------------------------------
# The live regression. These are the real numbers off the server.
# --------------------------------------------------------------------------

def test_live_bogus_reading_is_rejected(plugin, appliance, meter):
    """3446.586 kWh from a 3-minute, 5.2 W cycle must never be stored."""
    states = _run_cycle(plugin, appliance, meter,
                        started_at=T0, finished_at=T0 + 180,      # 3 minutes
                        peak_w=5.2, kwh_start=0.1876, kwh_now=3446.7738)
    assert states["lastCycleEnergyKwh"] == 0.0
    assert states["lastCycleEnergyKwh.ui"] == "n/a"


def test_rejected_energy_never_becomes_money(plugin, appliance, meter, indigo_mod):
    """The whole point: a bad kWh must not reach a cost or a notification."""
    from conftest import FakeVariable
    indigo_mod.variables["tracker_rate_today"] = FakeVariable("tracker_rate_today", "26.46")
    appliance.pluginProps["rateVariableName"] = "tracker_rate_today"

    states = _run_cycle(plugin, appliance, meter,
                        started_at=T0, finished_at=T0 + 180,
                        peak_w=5.2, kwh_start=0.1876, kwh_now=3446.7738)
    # 3446.586 x 26.46p would have been ~£911.97
    assert states["lastCycleCostGbp"] == 0.0
    assert states["lastCycleRateP"] == 0.0


def test_rejection_logs_a_real_warning(plugin, appliance, meter, indigo_mod):
    """Indigo silently ignores a STRING level, so assert the level itself."""
    import logging
    _run_cycle(plugin, appliance, meter,
               started_at=T0, finished_at=T0 + 180,
               peak_w=5.2, kwh_start=0.1876, kwh_now=3446.7738)
    warnings = [m for m, lvl in indigo_mod.server.lines if lvl == logging.WARNING]
    assert any("implausible cycle energy" in m for m in warnings)
    # and it must name both counter readings so the user can diagnose it
    assert any("0.188" in m and "3446.774" in m for m in warnings)


# --------------------------------------------------------------------------
# Real cycles must still pass. A guard that rejects genuine data is worse
# than no guard, so these are the important half of the suite.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kwh, peak_w, minutes", [
    (2.423, 2945.4, 63),   # the live tumble-dryer cycle
    (0.673, 2100.0, 55),   # real wash off the history table
    (0.912, 2400.0, 48),   # real wash off the history table
    (0.015,  300.0,  4),   # tiny real cycle, sits on the 0.05 floor
    (0.753, 2200.0, 50),   # real wash off the history table
])
def test_real_cycles_are_accepted(plugin, appliance, meter, kwh, peak_w, minutes):
    states = _run_cycle(plugin, appliance, meter,
                        started_at=T0, finished_at=T0 + minutes * 60,
                        peak_w=peak_w, kwh_start=0.0, kwh_now=kwh)
    assert states["lastCycleEnergyKwh"] == pytest.approx(kwh, abs=0.001)
    assert states["lastCycleEnergyKwh.ui"].endswith("kWh")


def test_absolute_cap_applies_when_peak_was_lost(plugin, appliance, meter):
    """After a restart the peak can be 0, so only the absolute cap protects us."""
    states = _run_cycle(plugin, appliance, meter,
                        started_at=T0, finished_at=T0 + 1800,
                        peak_w=0.0, kwh_start=0.0, kwh_now=3446.586)
    assert states["lastCycleEnergyKwh"] == 0.0

    states = _run_cycle(plugin, appliance, meter,
                        started_at=T0, finished_at=T0 + 3600,
                        peak_w=0.0, kwh_start=0.0, kwh_now=2.4)
    assert states["lastCycleEnergyKwh"] == pytest.approx(2.4)


# --------------------------------------------------------------------------
# Pre-existing behaviour that must not regress.
# --------------------------------------------------------------------------

def test_midnight_rollover_reports_energy_as_unmeasured(plugin, appliance, meter):
    """A negative delta is a counter reset, not an implausible reading.

    Changed in v1.8.0: the cycle's real energy cannot be recovered from a reset
    counter, so it is reported as unmeasured rather than as a confident 0.000
    kWh — and no cost is derived from it.
    """
    states = _run_cycle(plugin, appliance, meter,
                        started_at=T0, finished_at=T0 + 3600,
                        peak_w=2000.0, kwh_start=26.9, kwh_now=0.18)
    assert states["lastCycleEnergyKwh"] == 0.0
    assert states["lastCycleEnergyKwh.ui"] == "n/a"
    assert states["lastCycleCostGbp"] == 0.0


def test_no_energy_key_reports_unknown_not_zero(plugin, appliance, meter):
    """With no counter available the cycle must not claim it used nothing."""
    appliance.states["cycleStartedAt"] = T0
    plugin.runtime[appliance.id] = {"peak": 2000.0, "kwh_start": None, "above": 0}
    plugin._enter_door_wait(appliance, finished_at=T0 + 3600, src=meter, energy_key="")
    assert appliance.states["lastCycleEnergyKwh.ui"] == "n/a"


def test_negative_duration_from_clock_step_does_not_poison_the_ceiling(plugin, appliance, meter):
    """finished_at before started_at must not produce a negative ceiling."""
    states = _run_cycle(plugin, appliance, meter,
                        started_at=T0 + 7200, finished_at=T0 + 3600,   # clock stepped back
                        peak_w=2000.0, kwh_start=0.0, kwh_now=0.5)
    assert states["lastCycleMinutes"] == 0
    assert states["lastCycleEnergyKwh"] == pytest.approx(0.5)
