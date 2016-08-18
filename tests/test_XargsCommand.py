#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import re
import unittest

import xargs_groupby as xg
from . import mock

class XargsCommandTestCase(unittest.TestCase):
    def setUp(self):
        self.subcommand_arg0 = 'echo'
        self.subcommand = mock.MagicMock(name='group_cmd', spec_set=xg.GroupCommand)
        self.subcommand.command.side_effect = lambda key: [self.subcommand_arg0, key]
        self.xargs = xg.XargsCommand(['xargs', '-0'], self.subcommand)

    def test_base_command_copies(self):
        xargs_base = ['xargs', '-0']
        xargs = xg.XargsCommand(xargs_base, self.subcommand)
        xargs_base.pop()
        self.assertEqual(xargs.command('key')[:2], ['xargs', '-0'])

    def test_command_method_new(self):
        self.assertIsNot(self.xargs.command('t'), self.xargs.command('t'))

    def test_group_key_handled(self):
        self.assertEqual(self.xargs.command('test')[-2:], ['echo', 'test'])
        mock_calls = self.subcommand.command.call_args_list
        self.assertTrue(mock_calls)
        self.assertTrue(all(c == mock.call('test') for c in mock_calls))

    def argument_index(self, command, argument):
        try:
            return command.index(argument)
        except ValueError:
            self.fail("{!r} not found in {!r}".format(argument, command))

    def xargs_part(self, command):
        return command[:self.argument_index(command, self.subcommand_arg0)]

    def assertArgumentAt(self, command, index, value, fail_reason=None):
        try:
            self.assertEqual(command[index], value)
        except IndexError:
            if fail_reason is None:
                fail_reason = "no argument at index {!r}".format(index)
            self.fail("{}: {!r}".format(fail_reason, command))

    def assertSwitchSet(self, command, switch_name, value=None):
        if value is None:
            needle = switch_name
        elif switch_name.startswith('--'):
            needle = '{}={}'.format(switch_name, value)
        else:
            needle = switch_name + value
        self.assertIn(needle, self.xargs_part(command))

    def assertSwitchUnset(self, command, switch_name):
        self.assertFalse([switch for switch in self.xargs_part(command)
                          if re.match(switch_name + '(=|$)', switch)])

    def test_set_options(self, opts={}):
        # args_dict should represent the default xargs options generated
        # by ArgumentParser.
        args_dict = {
            '--exit': None,
            '-I': None,
            '--max-args': None,
            '--max-chars': None,
            '--verbose': None,
        }
        args_dict.update(opts)
        self.xargs.set_options(argparse.Namespace(**{
            key.lstrip('-').replace('-', '_'): args_dict[key]
            for key in args_dict}))
        command = self.xargs.command('key')
        for key in args_dict:
            value = args_dict[key]
            if value is None:
                self.assertSwitchUnset(command, key)
            elif value is True:
                self.assertSwitchSet(command, key)
            else:
                self.assertSwitchSet(command, key, value)

    def test_set_verbose(self):
        self.test_set_options({'--verbose': True})

    def test_set_I(self):
        self.test_set_options({'-I': '_'})

    def test_set_many_options(self):
        self.test_set_options({
            '--exit': True,
            '-I': '__',
            '--max-chars': '9999',
            '--max-args': '999',
        })

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
