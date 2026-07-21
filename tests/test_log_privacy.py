#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_log_privacy.py
# Description: A Pushover user key is a credential and Indigo event logs get
#              pasted whole into forum support posts. Neither a key nor a full
#              email address may reach the log.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import logging

from conftest import FakePushoverPlugin

KEY   = "uQiRzpo4DXghDmr9QzzfQu27cmVRsG"
EMAIL = "jane.smith@example.com"


def _all_log_text(caplog):
    return "\n".join(r.getMessage() for r in caplog.records)


def test_a_pushover_key_is_masked_on_the_debug_path(plugin, appliance, indigo_mod, caplog):
    indigo_mod.server.plugins["io.thechad.indigoplugin.pushover"] = FakePushoverPlugin()
    appliance.pluginProps["pushoverUserToken"] = KEY
    plugin.debug = True
    with caplog.at_level(logging.DEBUG, logger="appliancemonitor.test"):
        plugin._send_pushover(appliance, "Cycle done", "body")
    text = _all_log_text(caplog)
    assert KEY not in text
    assert "uQiR" in text          # enough to tell recipients apart


def test_a_pushover_key_is_masked_on_the_failure_path(plugin, appliance, indigo_mod, caplog):
    indigo_mod.server.plugins["io.thechad.indigoplugin.pushover"] = \
        FakePushoverPlugin(raises=True)
    appliance.pluginProps["pushoverUserToken"] = KEY
    with caplog.at_level(logging.DEBUG, logger="appliancemonitor.test"):
        plugin._send_pushover(appliance, "Cycle done", "body")
    assert KEY not in _all_log_text(caplog)


def test_the_key_still_reaches_pushover_itself(plugin, appliance, indigo_mod):
    """Masking is for the log only — the real key must still be sent."""
    push = FakePushoverPlugin()
    indigo_mod.server.plugins["io.thechad.indigoplugin.pushover"] = push
    appliance.pluginProps["pushoverUserToken"] = KEY
    plugin._send_pushover(appliance, "Cycle done", "body")
    assert push.sent[0][1]["msgUser"] == KEY


def test_an_email_address_is_masked_on_the_debug_path(plugin, appliance, indigo_mod, caplog):
    appliance.pluginProps["emailRecipients"] = EMAIL
    plugin.debug = True
    with caplog.at_level(logging.DEBUG, logger="appliancemonitor.test"):
        plugin._send_email(appliance, "Cycle done", "body")
    text = _all_log_text(caplog)
    assert EMAIL not in text
    assert "j...@example.com" in text
    # The email itself still went to the real address.
    assert indigo_mod.server.emails[0][0] == EMAIL


def test_the_default_recipient_is_named_plainly(plugin_mod):
    assert plugin_mod._mask_key("") == "default user"
    assert plugin_mod._mask_key(None) == "default user"


def test_a_short_key_is_still_masked(plugin_mod):
    assert plugin_mod._mask_key("abc123") == "ab..."


def test_a_malformed_address_is_hidden_entirely(plugin_mod):
    assert plugin_mod._mask_email("not-an-address") == "(address hidden)"
