#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg

class XargsCommandTestCase(unittest.TestCase):
    def setUp(self):
        self.xargs = xg.XargsCommand(['xargs', '-0'])

    def test_base_command_copies(self):
        base = ['xargs', '-0']
        xargs = xg.XargsCommand(base)
        base.pop()
        self.assertEqual(xargs.command()[:2], ['xargs', '-0'])

    def test_command_method_new(self):
        self.assertIsNot(self.xargs.command(), self.xargs.command())

    def argument_index(self, command, argument):
        try:
            return command.index(argument)
        except ValueError:
            self.fail("{!r} not found in {!r}".format(argument, command))

    def assertArgumentAt(self, command, index, value, fail_reason=None):
        try:
            self.assertEqual(command[index], value)
        except IndexError:
            if fail_reason is None:
                fail_reason = "no argument at index {!r}".format(index)
            self.fail("{}: {!r}".format(fail_reason, command))

    def assertSwitchSet(self, command, switch_name, value):
        index = self.argument_index(command, switch_name)
        self.assertArgumentAt(command, index + 1, value,
                              "no value for switch {!r}".format(switch_name))

    def test_default_procs(self):
        self.assertSwitchSet(self.xargs.command(), '--max-procs', '1')

    def test_multiple_procs_when_possible(self):
        self.xargs.set_parallel(8, 3)
        self.assertSwitchSet(self.xargs.command(), '--max-procs', '2')

    def test_procs_equals_cores_when_one_group(self):
        self.xargs.set_parallel(6, 1)
        self.assertSwitchSet(self.xargs.command(), '--max-procs', '6')

    def test_single_proc_when_more_groupings_than_cores(self):
        self.xargs.set_parallel(4, 6)
        self.assertSwitchSet(self.xargs.command(), '--max-procs', '1')

    def test_set_parallel_handles_zero_groups(self):
        self.xargs.set_parallel(2, 0)
        self.test_default_procs()
