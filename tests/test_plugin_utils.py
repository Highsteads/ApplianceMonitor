#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Filename:    test_plugin_utils.py
# Description: The shared logging helper. Installing the timestamp filter twice
#              used to prefix every line twice, and a malformed log call lost
#              its arguments.
# Author:      CliveS & Claude Opus 4.8
# Date:        21-07-2026
# Version:     1.0

import logging

import pytest


@pytest.fixture
def utils(indigo_mod):
    import plugin_utils
    return plugin_utils


class _Holder:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.filters.clear()


def _record(msg, args=()):
    return logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)


def test_installing_twice_leaves_one_filter(utils):
    holder = _Holder("appliancemonitor.utils.twice")
    first  = utils.install_timestamp_filter(holder)
    second = utils.install_timestamp_filter(holder)
    assert first is second
    assert len(holder.logger.filters) == 1


def test_a_second_install_still_sets_the_enabled_flag(utils):
    holder = _Holder("appliancemonitor.utils.flag")
    f = utils.install_timestamp_filter(holder, enabled=True)
    utils.install_timestamp_filter(holder, enabled=False)
    assert f.enabled is False


def test_one_prefix_per_line(utils):
    holder = _Holder("appliancemonitor.utils.prefix")
    utils.install_timestamp_filter(holder)
    utils.install_timestamp_filter(holder)
    rec = _record("hello")
    for f in holder.logger.filters:
        f.filter(rec)
    assert rec.msg.count("] hello") == 1
    assert rec.msg.endswith("] hello")


def test_disabled_leaves_the_message_alone(utils):
    f   = utils.MillisecondTimestampFilter(enabled=False)
    rec = _record("hello")
    f.filter(rec)
    assert rec.msg == "hello"


def test_a_broken_format_keeps_the_evidence(utils):
    """A %-placeholder mismatch used to vanish, leaving no clue why."""
    f   = utils.MillisecondTimestampFilter()
    rec = _record("value is %d and %d", (1,))
    f.filter(rec)
    assert "log format error" in rec.msg
    assert "args=(1,)" in rec.msg
    assert rec.args is None


def test_args_are_cleared_after_formatting(utils):
    f   = utils.MillisecondTimestampFilter()
    rec = _record("value is %d", (7,))
    f.filter(rec)
    assert rec.args is None
    assert rec.msg.endswith("value is 7")


def test_a_plugin_without_a_logger_is_survivable(utils):
    assert utils.install_timestamp_filter(object()) is None


@pytest.mark.parametrize("value,expected", [
    (True, True), (False, False), ("false", False), ("true", True),
    ("0", False), ("1", True), (0, False), (3, True),
])
def test_as_bool(utils, value, expected):
    assert utils.as_bool(value, default=None) is expected


def test_as_bool_default(utils):
    assert utils.as_bool(None, True) is True
    assert utils.as_bool("", False) is False
