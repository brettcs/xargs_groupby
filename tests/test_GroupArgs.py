#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from operator import methodcaller

import xargs_groupby as xg

class GroupArgsTestCase(unittest.TestCase):
    def test_varied_groupings(self):
        # A few important properties about the argument list:
        # * There's a group of one argument, 'z'.
        # * Grouped arguments are sometimes, but not always, consecutive.
        # * Groups have different relative orderings.  i.e.,
        #     lowercase first for the 'a' group,
        #     but uppercase first for the 'aa' group.
        groups = xg.group_args(['a', 'AA', 'aA', 'Z', 'A', 'aa', 'Aa'],
                               methodcaller('lower'))
        self.assertEqual(groups, {'a': ['a', 'A'],
                                  'aa': ['AA', 'aA', 'aa', 'Aa'],
                                  'z': ['Z']})

    def test_all_one_group(self):
        args = list('abcde')
        groups = xg.group_args(args, len)
        self.assertEqual(groups, {1: args})
