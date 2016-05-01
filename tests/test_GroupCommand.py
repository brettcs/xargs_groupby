#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg

class GroupCommandTestCase(unittest.TestCase):
    def test_no_key_string(self):
        subcmd = ['echo', '{}']
        gcmd = xg.GroupCommand(subcmd, None)
        result = gcmd.command('test')
        self.assertEqual(result, subcmd)
        self.assertIsNot(result, subcmd)

    def test_base_command_copies(self):
        subcmd_base = ['cat', '-A']
        gcmd = xg.GroupCommand(subcmd_base, None)
        subcmd_base.pop()
        self.assertEqual(gcmd.command('test'), ['cat', '-A'])

    def test_command_method_new(self):
        gcmd = xg.GroupCommand(['cat'], None)
        self.assertIsNot(gcmd.command('t'), gcmd.command('t'))

    def test_key_string(self, subcommand=['echo', '{}'], expected=['echo', 'key'],
                        key_string='{}', group_key='key'):
        gcmd = xg.GroupCommand(subcommand, key_string)
        self.assertEqual(gcmd.command(group_key), expected)

    def test_key_string_ending(self):
        self.test_key_string(['echo', 'hello {}'], ['echo', 'hello key'])

    def test_key_string_embedded(self):
        self.test_key_string(['echo', '!{}!'], ['echo', '!key!'])

    def test_key_string_multiple(self):
        self.test_key_string(['echo', '{{}{}}', '{}!'],
                             ['echo', '{keykey}', 'key!'])

    def test_one_char_key_string(self):
        self.test_key_string(['echo', '!!'], ['echo', 'keykey'], '!')
