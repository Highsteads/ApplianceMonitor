# Appliance Monitor

Detect when a household appliance (washing machine, dishwasher, tumble dryer,
oven) starts and ends a cycle by watching the **power draw** reported by a
separate metering device — typically a Shelly Plug/PM running under the
ShellyDirect plugin, but anything that exposes a watts state will work.

Sends Pushover notifications directly (configurable per appliance), and
also fires three custom Indigo events for anyone who wants to layer
additional actions (email backup, logging, etc.):

| Event | When it fires |
|---|---|
| `cycleStarted` | Power has risen above the run threshold (appliance has started) |
| `doorReady` | The configured door-ready delay has elapsed after cycle end |
| `socketReminder` | The configured reminder delay has elapsed after cycle end with no new cycle |

The plugin does **not** switch anything off — it only observes. Use the
events to drive notifications (e.g. a Pushover saying "please switch off
the wall socket" when the manual wall switch can't be controlled).

## How it works

A tiny state machine runs per appliance on a 20-second tick:

```
   idle ──[ watts ≥ run_threshold ]──▶ running
                                          │
                                          │ watts < idle_threshold
                                          ▼
                                      finishing ──[ watts ≥ run_threshold ]──▶ running
                                          │
                                          │ stays low for `debounce` minutes
                                          ▼
                                       doorWait
                                          │
                                          ├─ T+doorDelay      → fire doorReady
                                          ├─ T+socketDelay    → fire socketReminder → idle
                                          └─ watts ≥ run_threshold (new cycle) → running
```

The debounce stops mid-cycle quiet phases (e.g. between rinse and spin)
being mis-read as the end. A second cycle starting before the socket
reminder cancels the pending reminder automatically.

## Installation

1. Go to the [Releases](../../releases) page and download `ApplianceMonitor.indigoPlugin.zip`
2. Unzip — you'll get `ApplianceMonitor.indigoPlugin`
3. Double-click `ApplianceMonitor.indigoPlugin` — Indigo installs it automatically

## Configuration

Create one Appliance Monitor device per appliance:
**Indigo → Devices → New… → Plugin: Appliance Monitor → Appliance Monitor**.

| Field | Purpose | Default |
|---|---|---|
| Power meter device | The metering device (e.g. the Shelly) | – |
| Power state name | Which state on the meter reports watts | `powerWatts` |
| Run threshold (W) | Power at/above this = running | `5.0` |
| Idle threshold (W) | Power below this = idle / possibly ended | `2.0` |
| End-of-cycle debounce (min) | Sustained idle before cycle is declared ended | `3` |
| Door-ready delay (min) | Time after cycle end before `doorReady` fires | `2` |
| Socket-reminder delay (min) | Time after cycle end before `socketReminder` fires | `30` |
| Notify on cycle start | Send Pushover when running detected | off |
| Notify on door ready | Send Pushover at the door-ready mark | on |
| Notify on socket reminder | Send Pushover at the socket-reminder mark | on |
| Cycle-started title | Per-device Pushover title for the cycle-started alert | blank → `Cycle started` |
| Door-ready title | Per-device Pushover title for the door-ready alert | blank → `Cycle done` |
| Socket-reminder title | Per-device Pushover title for the socket-reminder alert | blank → `Switch off socket` |
| Pushover priority | -2/-1/0/1/2 (Pushover API values) | `0` |
| Pushover sound | Pushover sound name (`vibrate` for silent buzz) | `vibrate` |
| Pushover user token | Override Pushover plugin default user (optional) | — |
| Email recipients | Comma-separated email addresses notified alongside Pushover, for the same events ticked above (v1.4.0) | — |
| Energy state name | State on the meter that reports a running kWh counter (e.g. `energyKwhToday`). Leave blank to skip per-cycle kWh capture | `energyKwhToday` |

The plugin sends Pushover itself via the Pushover plugin
(`io.thechad.indigoplugin.pushover`) — no Indigo triggers needed for the
default flow. If you also want extra actions (email backup, logging, etc.),
create an Indigo trigger using the matching "Appliance Monitor: …" event
type — the plugin fires the events on every transition regardless of the
Pushover toggles.

## Tested defaults

| Appliance | Run W | Idle W | Debounce | Door | Socket reminder |
|---|---|---|---|---|---|
| Washing machine (58-min cycle) | 5.0 | 2.0 | 3 min | 2 min | 30 min |

Adjust the thresholds for your appliance by watching the Shelly's
`powerWatts` during a full cycle and noting the floor and active draw.

## Per-cycle metrics (v1.2+)

At the end of every cycle the plugin writes two extra device states so you
can use them on control pages, in triggers, or for solar/energy automations:

| State | What it captures |
|---|---|
| `lastCyclePeakWatts` | Maximum watts seen during the cycle (e.g. heater peak) |
| `lastCycleEnergyKwh` | kWh consumed during the cycle, taken as the delta on the source meter's energy counter (default `energyKwhToday`). Set to 0 on midnight rollover or if the meter has no counter. |
| `lastCycleCostGbp` | **v1.3.0** — what the cycle cost: cycle kWh times your import rate at cycle end. Needs the optional rate variable below, otherwise stays at 0. |
| `lastCycleRateP` | **v1.3.0** — the pence-per-kWh rate that was applied to the last cycle. |

These are also available inside the Pushover body template via the
`{peakW}` and `{kwh}` placeholders if you want to customise the message
(the default templates ignore them for backward compatibility).

### Cost per cycle (v1.3.0)

Point the new **Rate variable** field in the device config at an Indigo
variable holding your electricity import rate in pence per kWh (for example
a variable your tariff plugin keeps current, like `tracker_rate_today`).
From then on every finished cycle gets a price: the cycle-ended log line
shows it, the cycle-done Pushover gains a "Used 0.84 kWh (~£0.20)" line, and
the two states above feed control pages and dashboards. One honest caveat:
the figure is "at today's import rate" — if you have solar or a battery,
some of that energy may have actually been free. Leave the field blank and
nothing changes.

## Email notifications (v1.4.0)

Pushover is great if everyone in the house has the app, but a partner who
doesn't isn't going to see "wash done". The **Email recipients** field on
each appliance fixes that — put one or more comma-separated addresses in it
and every alert that already goes out by Pushover gets emailed to those
people as well. The Pushover title becomes the subject and the Pushover
text becomes the body, so the two channels say exactly the same thing.

It's gated by the same **Notify on …** checkboxes as Pushover, so you don't
get a flood of extra mail — only the events you've already opted into. Mail
goes out through the Email+ plugin's first SMTP server, so that needs to be
set up. Leave the field blank and nothing changes — Pushover only, exactly
as before.

## Requirements

- Indigo 2025.2 or later (Python 3.13)
- The Email+ plugin configured with an SMTP server (only if you use the
  Email recipients field)
- A device that exposes a watts state — ShellyDirect, Shelly Gen1,
  Z-Wave power meters, etc.

## Logging

Every log line is prefixed with a millisecond timestamp `[HH:MM:SS.mmm]` so
events can be correlated tightly with other CliveS plugins (Device Activity
Monitor uses the same convention).

To turn the prefix off (or back on) at any time:

**Plugins → Appliance Monitor → Toggle Timestamps in Log (on/off)**

The setting is stored in `pluginPrefs` (`timestampEnabled`) and persists across
restarts. Defaults to ON.

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
