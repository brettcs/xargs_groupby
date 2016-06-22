#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from operator import methodcaller

import xargs_groupby as xg

class InputPrepperTestCase(unittest.TestCase):
    ENCODING = 'utf-8'

    def InputPrepper(self, key_func=lambda x: x, delimiter=None, encoding=ENCODING):
        return xg.InputPrepper(key_func, delimiter, encoding)

    def test_varied_groupings(self):
        prepper = self.InputPrepper(methodcaller('lower'))
        # A few important properties about the argument list:
        # * There's a group of one argument, 'z'.
        # * Grouped arguments are sometimes, but not always, consecutive.
        # * Groups have different relative orderings.  i.e.,
        #     lowercase first for the 'a' group,
        #     but uppercase first for the 'aa' group.
        prepper.add(['a', 'AA', 'aA', 'Z', 'A', 'aa', 'Aa'])
        self.assertEqual(prepper.groups(), {'a': [b'a', b'A'],
                                            'aa': [b'AA', b'aA', b'aa', b'Aa'],
                                            'z': [b'Z']})

    def test_all_one_group(self):
        prepper = self.InputPrepper(len)
        prepper.add('abcde')
        self.assertEqual(prepper.groups(), {1: [b'a', b'b', b'c', b'd', b'e']})
