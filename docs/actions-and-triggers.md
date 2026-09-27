---
title: Actions and triggers
nav_order: 6
---

# Actions and triggers

## Triggers

The plugin has four events you can build Indigo triggers on, for anything beyond its own alerts — switching a light on, speaking an announcement, or sending a message through another plugin.

| Event | When it runs |
|---|---|
| **Appliance Monitor: Cycle Started** | When the appliance goes from idle to running. |
| **Appliance Monitor: Door Ready** | When the door-ready delay has passed after the power stopped. |
| **Appliance Monitor: Socket-Off Reminder** | When the socket-reminder delay has passed after the power stopped, if no new cycle has started. |
| **Appliance Monitor: Cycle Overrun** | Once, when a cycle has run longer than the appliance's **Warn if a cycle runs longer than** setting. |

These run whether or not you have ticked the matching Pushover and email alerts.

To use one, create a new trigger, set its type to **Appliance Monitor**, choose the event, and pick the appliance in **Appliance**. Then add whatever you want to happen.

Each trigger listens to one appliance. Indigo will not save the trigger until you have picked one, and a trigger with no appliance, left over from an earlier version, does nothing and says so once in the Event Log.

## Cycle Overrun

A cycle that never ends usually means the meter is stuck above the run threshold. The appliance then shows **running** for ever and no door-ready alert ever comes, with nothing else to tell you. **Cycle Overrun** is there to catch that.

It is switched off until you set **Warn if a cycle runs longer than** in the appliance's settings. Set it well beyond the appliance's longest real cycle. When a cycle passes it, the Event Log has a warning saying how long the cycle has run and the trigger runs, once for that cycle.

The plugin does not end the cycle for you, because a cycle that never really ended has no true length or energy to record. Once you have looked, use **Reset Appliance to Idle** to clear it.

## Actions

Both actions work on one appliance. Add them to an action group, a schedule or a trigger like any other action, choose the action from the Appliance Monitor actions, and pick the appliance.

### Reset Appliance to Idle

Puts the appliance back to **idle** and forgets the cycle under way, without recording it and without sending anything. Use it to clear a cycle stuck at **running**. The Event Log says what state the appliance was in and, if a cycle was under way, how long it had been running.

### Send Test Notification

Sends a test message by Pushover, and by email if the appliance has email switched on, using the appliance's own recipients and settings. The Event Log says how many people each channel reached. The appliance's state is not touched. The [Notifications](notifications.md) page has more on the alerts.
