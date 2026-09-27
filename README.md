# Appliance Monitor for Indigo

**Know when the washing is done, from the power the machine draws.**

**Version:** 1.10.0 | **Author:** CliveS & Claude | **Needs:** Indigo 2022.1 or later, and a plug or meter that reports watts

**[Read the full guide](https://highsteads.github.io/ApplianceMonitor/)** — setting up, what everything means, and what to do when something goes wrong.

---

## What it does

This plugin lets [Indigo](https://www.indigodomo.com) tell you when a washing machine, tumble dryer, dishwasher or any other appliance with a cycle has started and finished. It watches the power the appliance draws through a plug or meter that Indigo already reads, so the appliance needs nothing fitted. It only watches, and never switches anything on or off.

- **Tells you when the cycle has finished and the door is ready to open,** after a delay you set to match the appliance's door lock, and can tell you when a cycle starts as well.
- **Reminds you to switch off the wall socket** a while after the cycle ends, if no new cycle has started.
- **Sends the alerts by Pushover or email, or both,** to one person or several, with titles you choose for each appliance.
- **Records each cycle** — how long it ran, its highest power draw, the energy it used and, if you give it your electricity price, what it cost.
- **Runs your own triggers** when a cycle starts, when the door is ready, when the socket reminder is due, and when a cycle runs far longer than it should.
- **Does not mistake a pause for the end.** The power has to stay low for a few minutes before a cycle counts as finished, so a rest between rinse and spin is not taken as the end of the wash.
- **Checks what the meter tells it.** A meter that has been deleted, or has lost its watts reading, is shown in red rather than read as an appliance doing nothing, and an energy figure the cycle could not have used is rejected rather than recorded.

## What it works with

Any Indigo device that reports an appliance's power in watts. I use Shelly plugs running under my [Shelly Direct](https://github.com/Highsteads/ShellyDirect) plugin, and the settings start with the names that plugin uses, so with a Shelly Direct plug you only need to pick the plug. For phone alerts you need the Pushover plugin in Indigo, and for email the Email+ plugin.

## Installing

1. Go to the [Releases page](https://github.com/Highsteads/ApplianceMonitor/releases/latest) and download `ApplianceMonitor.indigoPlugin.zip`
2. Unzip the downloaded file — you will get `ApplianceMonitor.indigoPlugin`
3. Double-click `ApplianceMonitor.indigoPlugin` — Indigo will install it automatically

## Setting it up

1. Create a **New Device**, set the type to **Appliance Monitor**, and pick the plug or meter the appliance is plugged into in **Power meter device**.
2. If the meter is not a Shelly Direct plug, change **Power state name** and **Energy state name** to the names your meter uses. Indigo will not save a name the meter does not have, and lists the ones it does have.
3. Tick the Pushover and email alerts you want, and click **Save**. The starting thresholds and delays suit a washing machine.
4. Run the appliance. The device shows **running** within about 40 seconds, and the Event Log records the cycle when it ends.

The [full guide](https://highsteads.github.io/ApplianceMonitor/) goes through each step, explains every setting, and shows how to tune the thresholds for other appliances.

## What's new

**v1.10.0** — A new appliance on a meter other than a Shelly plug now saves without first clearing **Meter online state key**, as the help beside it always said it would.

**v1.9.3** — The help beside several settings in the appliance's settings window was cut off part-way through. It now sits on its own lines, where it can be read in full. No setting or behaviour changed.

**v1.9.2** — The **About Appliance Monitor** item in the Plugins menu opens this project's page.

Every version is listed in the [version history](https://highsteads.github.io/ApplianceMonitor/changelog.html).

## Authors & licence

Vibed into existence by **CliveS**, who knew what he wanted, argued until he got it, and tested it on a real house. Typed at inhuman speed by **Claude** (Anthropic), who mostly did as it was told.

© 2026 CliveS · [MIT licence](LICENSE) — copy it, fork it, bend it, break it, fix it, ship it. If it breaks, you get to keep both pieces.
