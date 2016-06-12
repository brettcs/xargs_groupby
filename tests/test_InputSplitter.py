#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import unittest

import xargs_groupby as xg
from . import mock, mocks

class InputSplitterCharacterTestCase(unittest.TestCase):
    DELIMITER = '_'

    def source_from_tokens(self, tokens, delimiter=None):
        if delimiter is None:
            delimiter = self.DELIMITER
        return delimiter.join(tokens)

    def assertTokens(self, expected, source=None, delimiter=None):
        if delimiter is None:
            delimiter = self.DELIMITER
        if source is None:
            source = self.source_from_tokens(expected, delimiter)
        in_stream = io.StringIO(source)
        splitter = xg.InputSplitter(in_stream, delimiter)
        self.assertEqual(list(splitter), expected)

    # These test cases represent xargs' observed behavior.  Try:
    # echo -en 'STR' | xargs -d DELIM python3 -c 'import sys; print(sys.argv)'

    def test_easy_split(self):
        self.assertTokens(['foo', 'bar', 'baz'])

    def test_no_delimiter(self):
        self.assertTokens(['AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'])

    def test_whitespace_not_special(self):
        whitespace = set(' \t\n')
        whitespace.discard(self.DELIMITER)
        expected = [c.join(s) for c, s in zip(whitespace, ['one', 'two', 'three'])]
        self.assertTokens(expected)

    def test_adjacent_delimiters(self):
        self.assertTokens(['quux', '', 'qix', '', 'quack'])

    def test_leading_delimiter(self):
        self.assertTokens(['', 'one', 'two'])

    def test_trailing_delimiter(self):
        expected = ['penultimate', 'ultimate']
        source = self.source_from_tokens(expected) + self.DELIMITER
        self.assertTokens(expected, source)


class InputSplitterNewlineTestCase(InputSplitterCharacterTestCase):
    DELIMITER = '\n'


class InputSplitterNullTestCase(InputSplitterCharacterTestCase):
    DELIMITER = '\0'


class InputSplitterNonprintingTestCase(InputSplitterCharacterTestCase):
    DELIMITER = '\a'


class InputSplitterMultibyteTestCase(InputSplitterCharacterTestCase):
    DELIMITER = '♥'


class InputSplitterMultiCharacterTestCase(InputSplitterCharacterTestCase):
    DELIMITER = 'AC'

    def test_splits_with_partial_overlap(self):
        self.assertTokens(['AAB', 'ADAAB' 'AD'])
