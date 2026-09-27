---
title: Version history
nav_order: 10
---

# Version history

The newest version is at the top.

## 1.9.3 — 7 September 2026

The appliance's settings window was drawn wider than it could show, so the help beside several settings was cut off part-way through. Fifteen of those help notes now sit on their own lines below their settings, where they wrap and can be read in full. No setting or behaviour changed.

## 1.9.2 — 2 August 2026

The plugin carries the address of its project page, which Indigo asks every plugin for. It gives the **About Appliance Monitor** item in the Plugins menu somewhere to go. Nothing about how the plugin works changed.

## 1.9.1 — 28 July 2026

A fix to the silent-meter check added in 1.9.0. A meter that said it was offline was also silent, so the check reported it as a fault and the appliance never moved to **off**, leaving any socket reminder still due. The silence check now only applies while the meter says it is online. The check is off to start with, so this only affected anyone who had switched it on.

## 1.9.0 — 27 July 2026

Four new checks, all off to start with, so an existing appliance behaves as before until you switch one on.

- **Warn if a cycle runs longer than** runs the new **Cycle Overrun** trigger once, for a cycle stuck at **running** because the meter is stuck above the run threshold. It warns but does not end the cycle.
- **Treat the meter as faulty after silence of** reports a meter that has stopped reporting without saying it is offline.
- **Meter online state key** lets you name the reading that says whether the meter can be reached. Before, only the name Shelly Direct uses was looked for, so the offline check never ran with other meters.
- Two new actions: **Reset Appliance to Idle** clears a stuck cycle without recording it, and **Send Test Notification** checks your Pushover and email alerts without waiting for a cycle, and says how many people each reached.

## 1.8.2 — 21 July 2026

The shared helper file that all my plugins carry was brought up to date. Its fixes had already arrived here in 1.8.1, so nothing about how the plugin behaves changed.

## 1.8.1 — 21 July 2026

- Turning log timestamps off and on again no longer gives every line two timestamps.
- An email address that is clearly wrong is refused when you save the settings, rather than failing with every alert.
- The door-ready delay runs from the moment the power stopped, not from the end of the debounce time, and the settings window says so.

## 1.8.0 — 21 July 2026

- If the meter went offline while a cycle was finishing, the cycle was lost. It is now recorded first, then the appliance moves to **off**.
- A deleted meter logged the same error every 20 seconds. It is now logged once and at most hourly after that, and the appliance shows red in the device list until the meter is back.
- A mistyped power state name behaved like a meter reading 0 watts, so the appliance never ran and nothing was logged. Both state names are checked when you save, and a name that later disappears is reported.
- A cycle running past midnight on a daily energy count used to record 0 kWh. It now warns and records the energy as not measured, so no cost is made up from it.
- A trigger saved without an appliance chosen ran for every appliance. It can no longer be saved, and an existing one warns once and does nothing.
- One broken trigger no longer stops the Pushover alert, the email and the rest of that appliance's checks.
- Pushover keys and email addresses are partly hidden in the log, since logs get pasted into forum posts.
- The timestamp setting is saved the moment you change it.

## 1.7.1 — 21 July 2026

- An appliance created before 1.7.0 could not have its settings saved, because the two new minimums were missing. Missing now counts as off.
- A cycle whose start time was not known could have real energy rejected as too high. It no longer is.

## 1.7.0 — 21 July 2026

- **Impossible energy figures are rejected.** A meter once reported its lifetime total as the day's figure, and a three-minute cycle peaking at just over 5 watts was recorded as using 3,446 kWh. A cycle cannot use more than its highest draw kept up for its whole length, so anything more is now rejected with a warning, and no cost is worked out from it. The electricity price must also look like pence per kWh. An impossible figure left from an earlier version is cleared on the first start after upgrading.
- **A restart part-way through a cycle no longer loses it.** The cycle's highest draw and starting energy count are kept on the device.
- **A brief burst of power no longer counts as a cycle.** The power must be above the run threshold for two readings in a row, and two new optional minimums, **Ignore cycles shorter than** and **Ignore cycles peaking below**, throw away anything too short or too weak.
- **Warnings show as warnings.** Before, every warning the plugin raised appeared in the log as an ordinary line.
- A mistyped energy state name gives a warning, and the socket-reminder delay must be longer than the door-ready delay.

## 1.6.0 — 15 June 2026

New **Send email alerts** tick box, to stop an appliance's emails without clearing its addresses.

## 1.5.0 — 15 June 2026

New **Also notify (extra Pushover users)** setting, to send each alert to more than one person.

## 1.4.0 — 15 June 2026

New **Email recipients** setting. Each alert that goes by Pushover can be emailed as well, through the Email+ plugin.

## 1.3.0 — 11 June 2026

Cost per cycle. Name an Indigo variable holding your electricity price in **Rate variable**, and each finished cycle is given a cost, shown in the log, in the door-ready alert and in two new states on the device.

## 1.2.5 — 30 May 2026

When the meter says it is offline, meaning the appliance has been switched off at the wall, the appliance shows the new state **off** and any socket reminder still due is cancelled. It goes back to **idle** when the meter returns.

## 1.2.4 — 30 May 2026

Each appliance can have its own alert titles. The titles to start with no longer mention washing, so a tumble dryer no longer sends "Wash done".

## 1.2.3 — 30 May 2026

**End-of-cycle debounce** can be set to 0, for an appliance that never rests part-way through its cycle.

## 1.2.2 — 25 May 2026

Changing an appliance's thresholds or alert settings no longer restarts it. Only a change of meter or reading name does.

## 1.2.1 — 23 May 2026

Every log line starts with the time to the thousandth of a second, with a menu item to turn that off.

## 1.2.0 — 23 May 2026

Each finished cycle records its highest power draw and the energy it used, from the meter's energy count. A new **Energy state name** setting names that count.

## 1.1.0 — 21 May 2026

The first published version: it watches an appliance's power, works out when a cycle starts and ends, sends Pushover alerts, and runs the Cycle Started, Door Ready and Socket-Off Reminder triggers.
