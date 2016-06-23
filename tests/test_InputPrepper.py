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
    ENCODING = 'latin-1'
    USABLE_DELIMITERS = bytearray(range(256)).decode(ENCODING)

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

    def test_uses_1byte_delimiter(self, delimiter='\0', expected='\\000'):
        prepper = self.InputPrepper(delimiter=delimiter)
        self.assertEqual(prepper.delimiter(), expected)

    def test_uses_1byte_delimiter_with_high_bit(self):
        self.test_uses_1byte_delimiter('ä', '\\344')

    def test_bad_delimiter_refused(self, delimiter='\0\0', *keys):
        prepper = self.InputPrepper(delimiter=delimiter)
        prepper.add([self.USABLE_DELIMITERS])
        with self.assertRaises(ValueError):
            prepper.delimiter(*keys)

    def test_unencodable_delimiter_refused(self):
        self.test_bad_delimiter_refused('♥')

    def test_no_delimiter_found_when_input_covers_all_bytes(self):
        self.test_bad_delimiter_refused(None)

    def test_no_delimiter_found_when_group_covers_all_bytes(self):
        self.test_bad_delimiter_refused(None, self.USABLE_DELIMITERS)

    def test_finds_usable_delimiter(self):
        prepper = self.InputPrepper()
        prepper.add([self.USABLE_DELIMITERS[:-1]])
        self.assertEqual(prepper.delimiter(), '\\377')

    def test_finds_delimiter_per_group(self):
        width = 128
        inputs = [self.USABLE_DELIMITERS[:width], self.USABLE_DELIMITERS[width:]]
        prepper = self.InputPrepper()
        prepper.add(inputs + [self.USABLE_DELIMITERS])
        for index, key in enumerate(inputs):
            delimiter = prepper.delimiter(key)
            self.assertEqual(delimiter[0], '\\')
            delim_char = int(delimiter[1:], 8)
            start_char = width * index
            self.assertNotIn(delim_char, range(start_char, start_char + width))
