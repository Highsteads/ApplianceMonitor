#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_restart_and_upgrade.py
# Description: Restarting part-way through a cycle, and the one-time upgrade
#              step for devices created before v1.7.0. cycleState persists
#              across a restart, so the metrics belonging to it must too.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import logging

T0 = 1784600000


# --------------------------------------------------------------------------
# The one-time upgrade step
# --------------------------------------------------------------------------

def test_pre_v170_device_gets_no_baseline_from_a_fresh_zero_state(plugin, appliance):
    """A newly created Number state materialises as 0.0, NOT None.

    Trusting that as a real energy baseline was a live bug during the v1.7.0
    work: the device reported 'baseline recovered' when nothing was recovered.
    """
    appliance.states["cycleState"] = "running"
    plugin.deviceStartComm(appliance)
    assert appliance.states["cycleKwhStart"] == -1.0
    assert plugin.runtime[appliance.id]["kwh_start"] is None


def test_upgrade_step_sets_the_schema_marker(plugin, appliance):
    plugin.deviceStartComm(appliance)
    import plugin as plugin_mod
    assert appliance.states["cycleStateVersion"] == plugin_mod.CYCLE_STATE_VERSION


def test_upgrade_clears_an_impossible_stored_energy(plugin, appliance, indigo_mod):
    """The live case: 3446.586 kWh left on the device by an earlier version."""
    appliance.states["lastCycleEnergyKwh"] = 3446.586
    appliance.states["lastCycleCostGbp"]   = 911.97
    plugin.deviceStartComm(appliance)
    assert appliance.states["lastCycleEnergyKwh"] == 0.0
    assert appliance.states["lastCycleCostGbp"] == 0.0
    warnings = [m for m, lvl in indigo_mod.server.lines if lvl == logging.WARNING]
    assert any("impossible stored cycle energy" in m for m in warnings)


def test_upgrade_keeps_a_legitimate_stored_energy(plugin, appliance):
    """The tumble dryer's real 2.423 kWh must survive the upgrade untouched."""
    appliance.states["lastCycleEnergyKwh"] = 2.423
    plugin.deviceStartComm(appliance)
    assert appliance.states["lastCycleEnergyKwh"] == 2.423


def test_upgrade_runs_only_once(plugin, appliance):
    plugin.deviceStartComm(appliance)
    appliance.states["cycleKwhStart"] = 12.5      # a real baseline mid-cycle
    plugin.deviceStopComm(appliance)
    plugin.deviceStartComm(appliance)             # second start must not wipe it
    assert appliance.states["cycleKwhStart"] == 12.5
    assert plugin.runtime[appliance.id]["kwh_start"] == 12.5


# --------------------------------------------------------------------------
# Restart part-way through a cycle
# --------------------------------------------------------------------------

def test_restart_midcycle_recovers_peak_and_baseline(plugin, appliance):
    """The bug the 05-Jun sweep predicted: metrics were in memory only."""
    appliance.states.update({
        "cycleState":        "running",
        "cycleStateVersion": 1,          # already upgraded
        "cyclePeakWatts":    2945.4,
        "cycleKwhStart":     0.1876,
    })
    plugin.deviceStartComm(appliance)
    rt = plugin.runtime[appliance.id]
    assert rt["peak"] == 2945.4
    assert rt["kwh_start"] == 0.1876


def test_restart_midcycle_then_finish_reports_real_energy(plugin, appliance, meter):
    """End to end: a restart must no longer produce a silent 0.000 kWh."""
    appliance.states.update({
        "cycleState":        "running",
        "cycleStateVersion": 1,
        "cyclePeakWatts":    2945.4,
        "cycleKwhStart":     0.1876,
        "cycleStartedAt":    T0,
    })
    plugin.deviceStartComm(appliance)
    meter.states["energyKwhToday"] = 2.6106
    plugin._enter_door_wait(appliance, finished_at=T0 + 3600,
                            src=meter, energy_key="energyKwhToday")
    assert appliance.states["lastCycleEnergyKwh"] == 2.423
    assert appliance.states["lastCyclePeakWatts"] == 2945.4


def test_resume_says_so_honestly_when_the_baseline_is_gone(plugin, appliance, caplog):
    appliance.states["cycleState"] = "running"
    with caplog.at_level(logging.INFO, logger="appliancemonitor.test"):
        plugin.deviceStartComm(appliance)
    assert "will not report energy" in caplog.text


def test_peak_is_persisted_as_it_climbs(plugin, appliance):
    plugin.runtime[appliance.id] = {"peak": 0.0, "kwh_start": None, "above": 0}
    plugin._track_peak(appliance, 100.0)
    assert appliance.states["cyclePeakWatts"] == 100.0
    plugin._track_peak(appliance, 250.0)
    assert appliance.states["cyclePeakWatts"] == 250.0
    # A lower reading must not overwrite the peak, nor cost a state write.
    writes = len(appliance.state_writes)
    plugin._track_peak(appliance, 10.0)
    assert appliance.states["cyclePeakWatts"] == 250.0
    assert len(appliance.state_writes) == writes


def test_cycle_end_clears_the_in_flight_metrics(plugin, appliance, meter):
    appliance.states["cycleStartedAt"] = T0
    plugin.runtime[appliance.id] = {"peak": 2000.0, "kwh_start": 1.0, "above": 0}
    meter.states["energyKwhToday"] = 2.0
    plugin._enter_door_wait(appliance, finished_at=T0 + 3600,
                            src=meter, energy_key="energyKwhToday")
    assert appliance.states["cyclePeakWatts"] == 0.0
    assert appliance.states["cycleKwhStart"] == -1.0
    assert plugin.runtime[appliance.id]["kwh_start"] is None
