---
title: Your appliances
nav_order: 3
---

# Your appliances

Each appliance you add becomes one Indigo device of the type **Appliance Monitor**. This page explains what it shows.

## Where the appliance is in its cycle

The device list shows the appliance's **Cycle State**, which is one of these:

| Shown as | What it means |
|---|---|
| **idle** | Nothing is running. The plugin is waiting for the power to rise. |
| **running** | A cycle is under way. |
| **finishing** | The power has dropped, and the plugin is waiting to be sure the cycle has really ended rather than paused. If the power rises again, it goes back to **running**. |
| **doorWait** | The cycle has ended and been recorded. The plugin is counting down to the door-ready alert and the socket reminder. After the socket reminder it goes back to **idle**. |
| **off** | The meter says it is offline, which usually means the appliance has been switched off at the wall. It goes back to **idle** when the meter comes back. |

The [How it works](how-it-works.md) page explains how the plugin moves between these.

## What each appliance shows

These are the names Indigo shows on control pages and in triggers.

### While a cycle runs

| Shown as | What it means |
|---|---|
| **Current Watts** | The power the appliance is drawing now, as the meter last reported it. It is updated every 20 seconds. |
| **Cycle Started (epoch)** | When the current or last cycle started. |
| **This Cycle Peak (W)** | The highest power draw seen so far in the cycle under way. |
| **This Cycle Energy Baseline (kWh)** | The meter's energy count when the cycle started, which the plugin takes away from the count at the end to work out the energy used. It shows **n/a** when there is none. |
| **Low Since (epoch)** | When the power last dropped below the idle threshold, while the plugin waits to be sure the cycle has ended. It is 0 the rest of the time. |

The three times marked **(epoch)** are stored as a count of seconds since 1 January 1970, the way computers usually keep time. They are there for scripts and control pages that do sums with them, and they read 0 when there is no time to show.

### The last finished cycle

| Shown as | What it means |
|---|---|
| **Cycle Finished (epoch)** | When the power stopped at the end of the last cycle. |
| **Last Cycle (min)** | How long the last cycle ran, in minutes, from its start to the moment the power stopped. |
| **Last Cycle Peak (W)** | Its highest power draw. |
| **Last Cycle Energy (kWh)** | The energy it used. It shows **n/a** when the plugin could not measure it — the meter has no energy count, the count reset part-way through, or the figure was impossible. |
| **Last Cycle Cost (GBP)** | What it cost, in pounds: the energy used times your electricity price at the end of the cycle. It shows **—** when there is no cost to show. |
| **Last Cycle Rate (p/kWh)** | The price, in pence per kWh, used to work out that cost. |

The cost is worked out at your import price, so if you have solar panels or a battery some of that energy may have cost you nothing.

### Alert flags

| Shown as | What it means |
|---|---|
| **Door Notified** | The door-ready alert for the last cycle has gone out. |
| **Socket Notified** | The socket reminder for the last cycle has gone out. |
| **Cycle Overrun Warned** | The plugin has warned that the cycle under way has run too long. It clears when a new cycle starts or the appliance goes back to idle. |

**Cycle State Schema Version** is for the plugin's own use. It records that the device's stored figures are in the current layout, so you can ignore it.

## When the meter cannot be read

If the plugin cannot get a trustworthy reading from the meter, the appliance shows one of these in red in the device list, and the Event Log says why:

| Shown as | What it means |
|---|---|
| **no source device** | No meter is chosen, or the chosen meter has been deleted. |
| **no power state** | The meter no longer has a reading with the name in **Power state name**. |
| **meter silent** | The meter says it is online but has not reported for longer than you allowed. This only happens if you have switched that check on. |

While it shows red, the appliance stays where it was, so nothing is recorded from a reading that cannot be trusted. The log line appears once and is repeated at most once an hour. Only the meter reading properly again clears the red, and the log then says the power meter is readable again. Resetting the appliance to idle does not clear it.
