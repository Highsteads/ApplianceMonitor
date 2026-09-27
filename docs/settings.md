---
title: Settings
nav_order: 7
---

# Settings

## The plugin's settings

Open these with **Plugins → Appliance Monitor → Configure**. Almost everything is set per appliance, so there is only one setting here.

| Setting | What it does |
|---|---|
| **Verbose debug logging** | Adds a line to the Event Log for every reading of every appliance, showing its state and the watts. Useful while you set the thresholds for a new appliance, but it adds about three lines a minute for each one. Unticked to start with. |

The plugin needs no passwords or keys of its own. Pushover and email are set up in their own plugins.

## Each appliance's settings

Open these by double-clicking an Appliance Monitor device in Indigo. A change takes effect with the next reading, with no restart needed.

### The meter

| Setting | What it does | To start with |
|---|---|---|
| **Power meter device** | The plug or meter that measures the appliance's power. It cannot be the appliance itself. | — |
| **Power state name** | The name of the meter's reading that gives the power in watts. Indigo will not save a name the meter does not have, and lists the ones it does have. | `powerWatts` |
| **Energy state name (optional)** | The name of the meter's running energy count in kWh. Leave it blank if the meter has none, and cycles are recorded without their energy. A daily count that resets at midnight works, but a cycle running past midnight is then recorded without its energy. | `energyKwhToday` |
| **Rate variable (optional)** | The name of an Indigo variable holding your electricity price in **pence per kWh**, such as `24.5`. When it is set, each finished cycle is given a cost, using the price at the end of the cycle. The variable must exist, and the price must be between 0.5 and 200 pence. Leave it blank for no costs. | blank |

The starting names are the ones my Shelly Direct plugin uses. For another meter, look at its device in Indigo to see what its readings are called.

### Deciding when a cycle starts and ends

| Setting | What it does | To start with |
|---|---|---|
| **Run threshold (W)** | At or above this many watts, the appliance is running. It must be more than 0. | 5.0 |
| **Idle threshold (W)** | Below this many watts, the appliance may have stopped. It must be lower than the run threshold. | 2.0 |
| **End-of-cycle debounce (min)** | How long the power must stay low before the cycle counts as ended, so a rest in the middle of a cycle is not taken as the end. 0 ends the cycle on the first low reading, which only suits an appliance that never rests part-way through. | 3 |
| **Ignore cycles shorter than (min)** | A finished cycle shorter than this is thrown away — nothing is recorded and no door-ready or socket-reminder alert or trigger follows — and the Event Log says so. It stops a short burst of standby power being reported as a wash. 0 switches it off. | 0 |
| **Ignore cycles peaking below (W)** | A finished cycle whose highest reading never reached this is thrown away in the same way. Set it well above standby but below the appliance's real running draw. 0 switches it off. | 0 |
| **Warn if a cycle runs longer than (min)** | Runs the **Cycle Overrun** trigger and puts a warning in the Event Log, once, if a cycle is still going after this long. It does not end the cycle. It must be longer than the debounce time. 0 switches it off. | 0 |

### Checking the meter is working

| Setting | What it does | To start with |
|---|---|---|
| **Meter online state key** | The name of the meter's reading that says whether it can be reached. When it says the meter is offline, the appliance shows **off** and any socket reminder still to come is cancelled, as the [How it works](how-it-works.md) page explains. If your meter has no such reading, you can leave the name as it is. The plugin ignores a name the meter does not have, and says so once in the log when you save. Clear the box if you would rather switch the check off without that note. | `deviceOnline` |
| **Treat the meter as faulty after silence of (min)** | Shows **meter silent** in red if the meter says it is online but has not been in touch for this long. It goes by the last time the meter reported successfully, or the last time one of its readings changed if Indigo has no record of that. Only use it with a meter that reports at regular times. One that only reports when a reading changes goes quiet whenever the appliance is off, and would then look faulty. 0 switches it off. | 0 |

### Alert timings

| Setting | What it does | To start with |
|---|---|---|
| **Door-ready delay (min)** | How long after the power stops the door-ready alert and trigger go out. Set it to the time your appliance keeps its door locked. It runs from the moment the power stopped, not from the end of the debounce time. | 2 |
| **Socket-reminder delay (min)** | How long after the power stops the socket reminder and trigger go out, if no new cycle has started. It must be longer than the door-ready delay. | 30 |

### Pushover

| Setting | What it does | To start with |
|---|---|---|
| **Notify on cycle start** | Send an alert when a cycle starts. | Unticked |
| **Notify on door ready** | Send an alert when the door is ready. | Ticked |
| **Notify on socket reminder** | Send the reminder to switch the socket off. | Ticked |
| **Cycle-started title** | The title of the cycle-start alert. Blank gives "Cycle started". | blank |
| **Door-ready title** | The title of the door-ready alert. Blank gives "Cycle done". | blank |
| **Socket-reminder title** | The title of the socket reminder. Blank gives "Switch off socket". | blank |
| **Pushover priority** | Pushover's own priority for the alert: No notification, Silent, Normal, High or Emergency. | Normal |
| **Pushover sound** | The sound the phone makes: `vibrate` for a silent buzz, `pushover` for Pushover's usual tone, or any other Pushover sound name. | `vibrate` |
| **Pushover user token (optional)** | A Pushover user key to send the alerts to instead of the person set up in the Pushover plugin. Leave it blank to use that person. | blank |
| **Also notify (extra Pushover users)** | More Pushover user keys, or a delivery group key, separated by commas. Each gets a copy as well. | blank |

The three **Notify on** tick boxes also decide which alerts are emailed.

### Email

| Setting | What it does | To start with |
|---|---|---|
| **Send email alerts** | Untick to stop the emails while keeping the addresses below. | Ticked |
| **Email recipients (optional)** | Email addresses, separated by commas, sent the same alerts as Pushover. They go out through the Email+ plugin. Leave it blank for no emails. | blank |

## Settings Indigo refuses

When you click **Save**, the plugin checks the settings and Indigo will not close the window until anything wrong is put right. It refuses:

- no meter chosen, or the appliance chosen as its own meter,
- a power or energy state name the meter does not have, listing the names it does have,
- a rate variable that does not exist,
- an email address that is clearly not one,
- a run threshold of 0 or less, or an idle threshold that is not lower than it,
- a socket-reminder delay that is not longer than the door-ready delay,
- a cycle-length warning that is not longer than the debounce time,
- a negative number in any of the minutes or watts boxes.
