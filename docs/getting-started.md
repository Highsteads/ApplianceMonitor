---
title: Getting started
nav_order: 2
---

# Getting started

This takes about ten minutes for the first appliance, and a couple of minutes for each one after that.

## What you need

- Indigo 2022.1 or later.
- A plug or meter for each appliance that Indigo can already read, and that reports the appliance's power in **watts**. I use Shelly plugs running under my [Shelly Direct](https://github.com/Highsteads/ShellyDirect) plugin, and the plugin's starting settings suit those, but any Indigo device with a watts reading will do.
- For phone alerts, the **Pushover** plugin installed and set up in Indigo, with a Pushover account.
- For email alerts, the **Email+** plugin set up in Indigo with a mail server to send through.

You can use Pushover, email, both, or neither — the plugin still records every cycle and runs your triggers without them.

## 1. Install the plugin

1. Go to the [Releases page](https://github.com/Highsteads/ApplianceMonitor/releases/latest) and download `ApplianceMonitor.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `ApplianceMonitor.indigoPlugin`
3. Double-click `ApplianceMonitor.indigoPlugin` — Indigo will install it automatically

Indigo asks whether to enable the plugin. Say yes.

There is nothing to set in **Plugins → Appliance Monitor → Configure** apart from a debug switch, because every setting belongs to an appliance.

## 2. Add an appliance

1. In Indigo, choose **New Device**.
2. Set **Type** to **Appliance Monitor** and the model to **Appliance Monitor**.
3. In **Power meter device**, pick the plug or meter the appliance is plugged into.
4. Check **Power state name**. It starts as `powerWatts`, which is what Shelly Direct calls its watts reading. If your meter calls it something else, type that name in. If you get it wrong, Indigo will not save the settings and tells you the names the meter does have, the first twelve in alphabetical order, so you can pick the right one.
5. Check **Energy state name** the same way. It starts as `energyKwhToday`. If your meter has no energy count in kWh — kilowatt hours, the units on your electricity bill — clear the box, and the plugin records each cycle without its energy use.
6. Leave the thresholds and delays as they are to start with. They suit a washing machine.
7. Tick the alerts you want under the Pushover and email headings. **Notify on door ready** and **Notify on socket reminder** are ticked to start with.
8. Click **Save**.

Every setting is explained on the [Settings](settings.md) page.

## 3. Check it works

The new appliance appears in Indigo's device list showing **idle**, and its **Current Watts** follows the meter within 20 seconds. The Event Log has a line saying the plugin is watching the appliance.

To check your alerts without waiting for a real wash, add an action of type **Send Test Notification** for the appliance and run it, as the [Actions and triggers](actions-and-triggers.md) page explains. The Event Log says how many people each alert reached.

Then run the appliance. Within about 40 seconds of it starting, the device shows **running** and the Event Log says the cycle has started. When the cycle ends, the log gives its length, highest power draw and energy used, and your door-ready alert follows.

## Tuning it for your appliance

The starting settings came from our washing machine, whose 58-minute cycle peaks at about 2,000 watts and never drops below 3.8 watts while it is running:

| Setting | Starting value |
|---|---|
| Run threshold | 5 watts |
| Idle threshold | 2 watts |
| End-of-cycle debounce | 3 minutes |
| Door-ready delay | 2 minutes |
| Socket-reminder delay | 30 minutes |

For another appliance, watch its meter's watts reading through a whole cycle and note two things: the lowest reading while it is running, and the reading once it has stopped. Set **Idle threshold** a little above the stopped reading, and **Run threshold** below the lowest running reading. If the appliance rests for a while in the middle of its cycle — some pause between rinse and spin — make **End-of-cycle debounce** longer than that rest. Ticking **Verbose debug logging** in **Plugins → Appliance Monitor → Configure** puts every reading in the Event Log while you do this.

If the plugin ever reports a cycle that never happened, such as a few seconds of standby power, the [Settings](settings.md) page shows how to make it ignore short or weak cycles.
