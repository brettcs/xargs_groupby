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
        self.subcommand = 'cat'
        self.xargs = xg.XargsCommand(['xargs', '-0'], [self.subcommand, '-A'])

    def test_base_command_copies(self):
        xargs_base = ['xargs', '-0']
        subcmd_base = ['cat', '-A']
        xargs = xg.XargsCommand(xargs_base, subcmd_base)
        xargs_base.pop()
        subcmd_base.pop()
        command = xargs.command('key')
        self.assertEqual(command[:2], ['xargs', '-0'])
        self.assertEqual(command[-2:], ['cat', '-A'])

    def test_command_method_new(self):
        self.assertIsNot(self.xargs.command('t'), self.xargs.command('t'))

    def argument_index(self, command, argument):
        try:
            return command.index(argument)
        except ValueError:
            self.fail("{!r} not found in {!r}".format(argument, command))

    def xargs_part(self, command):
        return command[:self.argument_index(command, self.subcommand)]

    def assertArgumentAt(self, command, index, value, fail_reason=None):
        try:
            self.assertEqual(command[index], value)
        except IndexError:
            if fail_reason is None:
                fail_reason = "no argument at index {!r}".format(index)
            self.fail("{}: {!r}".format(fail_reason, command))

    def assertSwitchSet(self, command, switch_name, value):
        command = self.xargs_part(command)
        index = self.argument_index(command, switch_name)
        self.assertArgumentAt(command, index + 1, value,
                              "no value for switch {!r}".format(switch_name))

    def test_default_procs(self):
        self.assertSwitchSet(self.xargs.command('key'), '--max-procs', '1')

    def test_multiple_procs_when_possible(self):
        self.xargs.set_parallel(8, 3)
        self.assertSwitchSet(self.xargs.command('key'), '--max-procs', '2')

    def test_procs_equals_cores_when_one_group(self):
        self.xargs.set_parallel(6, 1)
        self.assertSwitchSet(self.xargs.command('key'), '--max-procs', '6')

    def test_single_proc_when_more_groupings_than_cores(self):
        self.xargs.set_parallel(4, 6)
        self.assertSwitchSet(self.xargs.command('key'), '--max-procs', '1')

    def test_set_parallel_handles_zero_groups(self):
        self.xargs.set_parallel(2, 0)
        self.test_default_procs()

    def test_key_string(self, subcommand=['echo', '{}'], expected=['echo', 'key'],
                        key_string='{}', group_key='key'):
        xargs = xg.XargsCommand(['xargs'], subcommand, key_string)
        self.assertEqual(xargs.command(group_key)[-len(expected):], expected)

    def test_key_string_ending(self):
        self.test_key_string(['echo', 'hello {}'], ['echo', 'hello key'])

    def test_key_string_embedded(self):
        self.test_key_string(['echo', '!{}!'], ['echo', '!key!'])

    def test_key_string_multiple(self):
        self.test_key_string(['echo', '{{}{}}', '{}!'],
                             ['echo', '{keykey}', 'key!'])
