---
title: When something goes wrong
nav_order: 9
---

# When something goes wrong

Each section starts with what you see, then what it means and what to do.

## The appliance never leaves "idle"

The power never reaches the run threshold for two readings in a row.

- Check **Current Watts** on the appliance. If it stays at 0 while the appliance runs, the meter is not reporting, or **Power meter device** points at the wrong plug.
- If **Current Watts** moves but stays below **Run threshold (W)**, lower the threshold. Some appliances draw very little in their first minutes.

## A cycle ends too early, and a second one starts

The appliance rested part-way through its cycle for longer than the debounce time, so the plugin took the rest as the end.

- Make **End-of-cycle debounce (min)** longer than the longest rest.
- Or lower **Idle threshold (W)**, if the power during the rest stays above what the appliance draws once it has really stopped.

## Standby power is reported as a cycle

A short burst of power, such as the appliance's display waking, has been counted as a cycle.

- Set **Ignore cycles shorter than (min)** or **Ignore cycles peaking below (W)**, or both. The cycle-started alert and trigger still go out when such a burst starts, but it is then thrown away with no door-ready alert or socket reminder.
- Or raise **Run threshold (W)** above the standby draw.

## The appliance stays at "running" long after it has finished

The meter's reading has not fallen below **Idle threshold (W)**, or it keeps rising back to the run threshold.

- Check **Current Watts** once the appliance has stopped. If it sits above the idle threshold, raise the idle threshold a little above it.
- Use **Reset Appliance to Idle** to clear the cycle stuck now.
- Set **Warn if a cycle runs longer than (min)**, so you hear about it next time.

## The device shows "no source device" in red

No meter is chosen, or the meter has been deleted. Open the appliance's settings and pick the meter in **Power meter device**.

## The device shows "no power state" in red

The meter no longer has a reading with the name in **Power state name** — perhaps its plugin has renamed it. Open the appliance's settings and click **Save**. Indigo lists the names the meter does have, and you can pick the right one.

## The device shows "meter silent" in red

The meter says it is online but has not been in touch for longer than **Treat the meter as faulty after silence of (min)** allows.

- Check the meter has power and is on the network.
- If the meter only reports when its reading changes, it goes quiet whenever the appliance is off, so set this back to 0.

## The appliance shows "off" when it is not switched off

The meter says it is offline. Check the meter in Indigo. If its online reading is wrong or means something else, clear **Meter online state key** to switch that check off.

## The last cycle's energy shows "n/a"

The plugin could not measure the energy. Unless the first reason applies, the Event Log says why:

- **Energy state name is blank,** so there is no energy count to use.
- **The meter has no reading with the name in Energy state name.** Check the name, or clear the box if the meter has no energy count.
- **The meter's energy count reset part-way through the cycle,** usually at midnight on a daily count. Only that cycle is affected.
- **The figure was impossible,** more than the cycle's highest draw could have used over its length, so it was rejected. If this happens often, have a look at the meter's energy reading.

## The last cycle's cost shows "—"

There was no cost to show.

- **Rate variable** is blank. The Event Log says so after each cycle whose energy was measured.
- The energy was not measured, as above.
- The Event Log says the price was outside 0.5 to 200 pence per kWh. Make sure the variable holds pence, such as `24.5`, not pounds, such as `0.245`.
- The Event Log says the variable could not be read. Check it still exists under that name.

## No Pushover alert arrives

- Check the matching **Notify on** box is ticked for the appliance.
- If the Event Log says the Pushover plugin is not enabled, enable it.
- Run **Send Test Notification**. The Event Log says how many people it reached. If it reached them but your phone showed nothing, check **Pushover priority** is not **No notification**, and have a look in the Pushover app.

## No email arrives

- Check **Send email alerts** is ticked and **Email recipients** holds the address.
- Check the matching **Notify on** box is ticked. The same boxes decide what is emailed.
- Check the Email+ plugin is set up and can send mail.
- Run **Send Test Notification** to try it without waiting for a cycle.

## A trigger never runs

- Open the trigger and check it has an appliance chosen. The Event Log says once if it has none.
- Check it is the right event. **Door Ready** and **Socket-Off Reminder** only run after a cycle has ended, and **Cycle Overrun** only runs if you have set **Warn if a cycle runs longer than (min)**.

## Still stuck?

Choose **Plugins → Appliance Monitor → Dump Appliance State (event log)** and **Show Plugin Info**, copy the lines they write to the Event Log, and post them on the [Indigo forum](https://forums.indigodomo.com) with a description of what you see. You can also [raise an issue on GitHub](https://github.com/Highsteads/ApplianceMonitor/issues).
