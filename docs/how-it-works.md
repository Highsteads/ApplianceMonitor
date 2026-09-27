---
title: How it works
nav_order: 4
---

# How it works

You do not need to know all of this to use the plugin, but it helps when you set the thresholds for a new appliance.

## Reading the meter every 20 seconds

Every 20 seconds the plugin reads each appliance's meter, updates **Current Watts**, and decides whether anything has changed. It compares the reading with two figures you set for each appliance:

- the **run threshold** — at or above this, the appliance is running,
- the **idle threshold** — below this, the appliance may have stopped.

The idle threshold must be lower than the run threshold. The gap between them stops a reading that hovers around one figure from switching the appliance back and forth.

## A cycle starting

When the appliance is **idle**, the plugin waits for **two readings in a row** at or above the run threshold before it counts a cycle as started, so one stray reading cannot invent a whole cycle. The appliance then shows **running**, the plugin notes the time and the meter's energy count, and it sends the cycle-started alert if you asked for one.

While the cycle runs, the plugin keeps the highest reading it sees.

## A cycle ending

Most appliances rest part-way through a cycle — a washing machine between rinse and spin, say — so a drop in power does not always mean the cycle has ended.

When a reading falls below the idle threshold, the appliance shows **finishing** and the plugin notes the time. If the power rises back to the run threshold, the cycle carries on and the appliance shows **running** again. If it stays below the run threshold for the **end-of-cycle debounce** time, three minutes to start with, the plugin decides the cycle has ended.

It then records the cycle:

- **how long it ran,** from the start to the moment the power first dropped, not to the end of the debounce time,
- **its highest power draw,**
- **the energy it used,** by taking the meter's energy count at the start away from the count now,
- **what it cost,** if you have given it your electricity price.

The Event Log gets one line with all of this, and the appliance shows **doorWait**.

## After the cycle

Many washing machines keep the door locked for a minute or two after they stop, so the door-ready alert waits for the **door-ready delay**, measured from the moment the power stopped. If that delay is shorter than the debounce time, the alert goes out with the next reading after the cycle is recorded.

Later, when the **socket-reminder delay** has passed, again measured from the moment the power stopped, the plugin sends the reminder to switch the wall socket off, if you asked for it, and goes back to **idle**, ready for the next cycle.

The door-ready and socket-reminder triggers run at these times whether or not you have ticked the matching alerts, and the plugin goes back to **idle** either way.

If the power rises to the run threshold again before then, a new cycle has started. The plugin goes straight back to **running**, and the door-ready alert and socket reminder for the old cycle are not sent.

## When the meter goes offline

Many plugs and meters say whether they can be reached. Shelly Direct's plugs have a reading called `deviceOnline` for this, and the plugin looks for it to start with.

If the meter says it is offline while the appliance is **idle**, **finishing** or **doorWait**, the plugin takes it that the appliance has been switched off at the wall. The appliance shows **off**, and any socket reminder still to come is cancelled, because the socket is already off. If the cycle was **finishing**, it is recorded first, but no door-ready alert follows. When the meter comes back, the appliance goes back to **idle**.

While the appliance is **running**, the plugin takes no notice of the meter being offline, so a Wi-Fi hiccup in the middle of a wash does not lose the cycle.

## Not believing everything the meter says

A meter can report nonsense now and then, so the plugin checks what it is given:

- **A cycle cannot use more energy than its highest power draw kept up for the whole cycle.** The plugin allows half as much again for the meter's rounding, never less than 0.05 kWh and never more than 20 kWh. Anything over that is rejected with a warning naming both meter readings, and the cycle is recorded without its energy or cost rather than with a wrong figure.
- **If the meter's energy count resets part-way through a cycle,** as a daily count does at midnight, the energy cannot be worked out, so the plugin says so and records the cycle without it.
- **Your electricity price must be between 0.5 and 200 pence per kWh.** Anything outside that is almost certainly in pounds or a mistake, so the cost is skipped with a warning.
- **A meter that has been deleted, or has lost the reading the plugin uses,** is reported in red, as the [Your appliances](devices.md) page shows, rather than read as zero watts.
- **A meter that goes quiet** without saying it is offline can be reported too, if you switch that check on. The [Settings](settings.md) page explains when it is safe to.

## Restarting part-way through a cycle

The plugin keeps the cycle under way — its start time, highest reading and starting energy count — on the device itself, so if Indigo or the plugin restarts in the middle of a wash, it carries on where it left off. The Event Log says it is resuming a cycle already in progress.

## What goes in the log

The Indigo Event Log gets one line when each cycle starts, when it ends, when the door is ready and when the socket reminder is due, plus any warning about the meter. Ticking **Verbose debug logging** in **Plugins → Appliance Monitor → Configure** adds a line for every reading, which helps when setting the thresholds but fills the log quickly.

Pushover keys and email addresses are partly hidden in the log, so you can paste log lines into a forum post safely.
