---
title: Home
nav_order: 1
---

# Appliance Monitor for Indigo

This plugin lets [Indigo](https://www.indigodomo.com) tell you when a washing machine, tumble dryer, dishwasher or any other appliance with a cycle has started and finished. It does this by watching the power the appliance draws, as reported by a plug or meter that Indigo already reads, so the appliance itself needs nothing fitted and no internet connection.

I built it for our washing machine and tumble dryer, each plugged into a Shelly plug that measures power, and it works with any Indigo device that reports its power in watts.

The plugin only watches. It never switches anything on or off.

## What it does for you

- **Tells you when a cycle starts,** if you want to know, and **when it has finished and the door is ready to open.**
- **Reminds you to switch off the wall socket** a while after the cycle ends, if no new cycle has started, for appliances you like to switch off at the wall.
- **Sends the alerts by Pushover or email, or both,** to one person or several, with titles you choose for each appliance.
- **Records each cycle** — how long it ran, its highest power draw, the energy it used and, if you give it your electricity price, what it cost.
- **Runs your own triggers** when a cycle starts, when the door is ready, when the socket reminder is due, and when a cycle runs for far longer than it should.
- **Keeps an eye on the meter,** so a meter that has been deleted, renamed, switched off or has gone quiet is reported rather than read as an appliance doing nothing.

## Where to go next

| If you want to... | Read |
|---|---|
| Install the plugin and set up your first appliance | [Getting started](getting-started.md) |
| Know what each appliance shows in Indigo | [Your appliances](devices.md) |
| Understand how the plugin decides a cycle has started and finished | [How it works](how-it-works.md) |
| Set up Pushover and email alerts, and see what they say | [Notifications](notifications.md) |
| Run your own actions when a cycle starts or finishes | [Actions and triggers](actions-and-triggers.md) |
| Know what every setting does | [Settings](settings.md) |
| Know what each item in the Plugins menu does | [The plugin menu](plugin-menu.md) |
| Sort out a problem | [When something goes wrong](troubleshooting.md) |
| See what changed in each version | [Version history](changelog.md) |

## Download

The latest version is always on the [Releases page](https://github.com/Highsteads/ApplianceMonitor/releases/latest).
