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

class InputShlexerTestCase(unittest.TestCase):
    def assertTokensFrom(self, source, expected, eof_str=None):
        in_stream = io.StringIO(source)
        shlexer = xg.InputShlexer(in_stream, eof_str)
        self.assertEqual(list(shlexer), expected)

    # These test cases represent xargs' observed behavior.  Try:
    # echo -en 'STR' | xargs [-E=EOF] python3 -c 'import sys; print(sys.argv)'

    def test_excess_whitespace_ignored(self):
        self.assertTokensFrom('  a b \n\tc d \n', list('abcd'))

    def test_double_quoting(self):
        self.assertTokensFrom(' " a b  "c d', [' a b  c', 'd'])

    def test_single_quoting(self):
        self.assertTokensFrom(" a'b cd' e ", ['ab cd', 'e'])

    def test_backslash_escape(self):
        self.assertTokensFrom('\\\'\\"', ['\'"'])

    def test_backslash_escapes_newline(self):
        self.assertTokensFrom('a b\\\nc d', ['a', 'b\nc', 'd'])

    def test_backslash_at_eof_ignored(self):
        self.assertTokensFrom('a b\nc d\\', list('abcd'))

    def test_no_token_after_newline_at_eof(self):
        self.assertTokensFrom('a b\n', list('ab'))

    def test_tokens_from_partial_line(self):
        self.assertTokensFrom('a e\no u', list('aeou'))

    def test_tokens_ignored_after_unclosed_quote(self):
        self.assertTokensFrom('a c "e g\n"hi"\n', ['a', 'c', 'hi'])

    def test_eof_str(self):
        self.assertTokensFrom('a b\nc EOF\nEOF d\nEOF\ng\n',
                              ['a', 'b', 'c', 'EOF', 'EOF', 'd'], 'EOF')

    def test_eof_before_escaped_newline_treated_literally(self):
        self.assertTokensFrom('a\nEOF\\\nb', ['a', 'EOF\nb'], 'EOF')

    def test_eof_after_escaped_newline_treated_literally(self):
        self.assertTokensFrom('a\\\nEOF\nb', ['a\nEOF', 'b'], 'EOF')
