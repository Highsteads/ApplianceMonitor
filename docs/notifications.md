---
title: Notifications
nav_order: 5
---

# Notifications

The plugin sends its own alerts by Pushover and by email, so you do not need to build any triggers for the usual "the wash is done" message. Each appliance has its own alert settings.

## Which alerts go out

There are three alerts, each with its own tick box in the appliance's settings:

| Tick box | When it goes out | Ticked to start with |
|---|---|---|
| **Notify on cycle start** | When a cycle starts. Mostly useful while you are setting the thresholds. | No |
| **Notify on door ready** | When the door-ready delay has passed after the power stopped. | Yes |
| **Notify on socket reminder** | When the socket-reminder delay has passed after the power stopped, if no new cycle has started. | Yes |

The same tick boxes decide what goes by Pushover and what goes by email, so an alert you have not ticked goes by neither.

A cycle that runs far too long does not send an alert of its own. It runs the **Cycle Overrun** trigger instead, as the [Actions and triggers](actions-and-triggers.md) page explains, so you can send yourself a Pushover from there.

## What they say

Each alert has a title and a message. The message starts with the appliance's name as it appears in Indigo.

| Alert | Title to start with | Message |
|---|---|---|
| Cycle start | Cycle started | *Washing Machine: cycle started.* |
| Door ready | Cycle done | *Washing Machine: cycle complete after 58 min — door unlocking now. Used 0.84 kWh (~£0.20).* |
| Socket reminder | Switch off socket | *Washing Machine: no new cycle started — please switch the wall socket off.* |

The door-ready message ends with the energy used, and the cost when there is one. When the energy could not be measured, that part is left off.

You can give each appliance its own titles, such as "Wash done" or "Dryer done", with the three title settings. Leave a title blank to use the one shown above.

## Pushover

Pushover alerts go out through the Pushover plugin, which must be installed and enabled in Indigo. If it is not, the Event Log says the message was not sent.

- **Who gets it.** To start with, the alert goes to the person set up in the Pushover plugin. Put a Pushover user key in **Pushover user token** to send it to someone else instead.
- **Telling more than one person.** Put more Pushover user keys in **Also notify (extra Pushover users)**, separated by commas, and each gets a copy as well as the person above. A Pushover delivery group key works here too. Each person needs their own Pushover account for their own user key. A key that is in both boxes gets one copy, not two.
- **How it arrives.** **Pushover priority** and **Pushover sound** set how the phone shows the alert. The sound starts as `vibrate`, a silent buzz. `pushover` gives Pushover's usual tone, and any other sound name from Pushover's own list works too.

## Email

Put one or more email addresses in **Email recipients**, separated by commas, and every alert you have ticked is emailed to them as well as sent by Pushover. The Pushover title becomes the email's subject and the Pushover message its body, so both say the same thing. This suits someone in the house who does not use Pushover.

Email goes out through the Email+ plugin, which must be set up with a mail server in Indigo.

**Send email alerts** is ticked to start with. Untick it to stop the emails without clearing the addresses, so they are kept on file for when you want them again.

Indigo will not save the settings if an address in the list is clearly not an email address, and it tells you which one.

## Testing your alerts

The **Send Test Notification** action sends a message titled *Appliance Monitor test* to everyone this appliance would alert, by Pushover and by email if it is switched on, without waiting for a real cycle. The Event Log then says how many people each channel reached, and whether email is switched off for the appliance. It does not change the appliance's state. The [Actions and triggers](actions-and-triggers.md) page shows how to run it.
