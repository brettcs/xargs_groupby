#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from operator import itemgetter, methodcaller

import xargs_groupby as xg

class InputPrepperTestCase(unittest.TestCase):
    ENCODING = 'latin-1'
    USABLE_DELIMITER_BYTES = bytes(bytearray(range(256)))
    USABLE_DELIMITERS = USABLE_DELIMITER_BYTES.decode(ENCODING)

    def InputPrepper(self, key_func=lambda x: x, delimiter=None, encoding=ENCODING):
        return xg.InputPrepper(key_func, delimiter, encoding)

    def assertPrepperHasExactly(self, prepper, expected):
        actual = {key: prepper[key] for key in prepper}
        self.assertEqual(actual, expected)

    def test_varied_groupings(self):
        prepper = self.InputPrepper(methodcaller('lower'))
        # A few important properties about the argument list:
        # * There's a group of one argument, 'z'.
        # * Grouped arguments are sometimes, but not always, consecutive.
        # * Groups have different relative orderings.  i.e.,
        #     lowercase first for the 'a' group,
        #     but uppercase first for the 'aa' group.
        prepper.add(['a', 'AA', 'aA', 'Z', 'A', 'aa', 'Aa'])
        self.assertPrepperHasExactly(prepper, {
            'a': [b'a', b'A'],
            'aa': [b'AA', b'aA', b'aa', b'Aa'],
            'z': [b'Z'],
        })

    def test_all_one_group(self):
        prepper = self.InputPrepper(len)
        prepper.add('abcde')
        self.assertPrepperHasExactly(prepper, {1: [b'a', b'b', b'c', b'd', b'e']})

    def test_len(self, seq='', expected=0):
        prepper = self.InputPrepper(itemgetter(0))
        prepper.add(seq)
        self.assertEqual(len(prepper), expected)

    def test_len_one(self):
        self.test_len('aa', 1)

    def test_len_many(self):
        self.test_len('abbcca', 3)

    def test_uses_1byte_delimiter(self, delimiter='\0', expected=b'\0'[0]):
        prepper = self.InputPrepper(delimiter=delimiter)
        self.assertEqual(prepper.delimiter(), expected)

    def test_uses_1byte_delimiter_with_high_bit(self):
        self.test_uses_1byte_delimiter('ä', 'ä'.encode(self.ENCODING)[0])

    def test_bad_delimiter_refused(self, delimiter='\0\0', *keys):
        prepper = self.InputPrepper(delimiter=delimiter)
        actual = prepper.delimiter()
        self.assertNotEqual(actual, delimiter)
        self.assertIn(actual, self.USABLE_DELIMITER_BYTES)

    def test_unencodable_delimiter_refused(self):
        self.test_bad_delimiter_refused('♥')

    def test_no_delimiter_found_when_input_covers_all_bytes(self):
        self.test_bad_delimiter_refused(None)

    def test_error_when_group_covers_all_bytes(self):
        prepper = self.InputPrepper(delimiter=None)
        with self.assertRaises(xg.UserArgumentsError):
            prepper.add([self.USABLE_DELIMITERS])

    def test_finds_usable_delimiter(self):
        prepper = self.InputPrepper()
        prepper.add([self.USABLE_DELIMITERS[:-1]])
        self.assertEqual(prepper.delimiter(), bytes(self.USABLE_DELIMITER_BYTES)[-1])

    def test_finds_delimiter_per_group(self):
        width = 128
        inputs = [self.USABLE_DELIMITERS[:width], self.USABLE_DELIMITERS[width:]]
        prepper = self.InputPrepper()
        prepper.add(inputs)
        for index, key in enumerate(inputs):
            delimiter = prepper.delimiter(key)
            bad_range = self.USABLE_DELIMITER_BYTES[width * index:width * (index + 1)]
            self.assertNotIn(delimiter, bad_range)
