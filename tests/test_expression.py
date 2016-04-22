#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os.path
import unittest

import xargs_groupby as xg

class UserExpressionTestCase(unittest.TestCase):
    def test_simple_callable(self):
        expr = xg.UserExpression('lambda s: s.upper()')
        self.assertEqual(expr('test'), 'TEST')

    def test_underscore_shortcut_method(self):
        expr = xg.UserExpression('_.upper()')
        self.assertEqual(expr('test'), 'TEST')

    def test_underscore_shortcut_slice(self):
        expr = xg.UserExpression('_[:3]')
        self.assertEqual(expr('test'), 'tes')

    def test_underscore_shortcut_function(self):
        expr = xg.UserExpression('float(_)')
        self.assertEqual(expr('1.24'), 1.24)

    def test_underscore_shortcut_operator(self):
        expr = xg.UserExpression('_ * 2')
        self.assertEqual(expr('test'), 'testtest')

    def test_callable_shortcut(self):
        expr = xg.UserExpression('lambda s: s.upper')
        self.assertEqual(expr('test'), 'TEST')

    def test_all_shortcuts(self):
        expr = xg.UserExpression('_.upper')
        self.assertEqual(expr('test'), 'TEST')

    def test_builtin_usable(self):
        expr = xg.UserExpression('int')
        self.assertEqual(expr('019'), 19)

    def test_os_path_usable(self):
        expr = xg.UserExpression('os.path.basename')
        self.assertEqual(expr(os.path.join('dir', 'test')), 'test')

    def test_not_callable(self):
        with self.assertRaises(ValueError):
            xg.UserExpression('"test"')

    def test_not_expression(self):
        with self.assertRaises(ValueError):
            xg.UserExpression('f = float')

    def test_syntax_error(self):
        with self.assertRaises(ValueError):
            xg.UserExpression('lambda s:')

    def test_names_limited(self):
        with self.assertRaises(ValueError):
            xg.UserExpression('sys.exit')
