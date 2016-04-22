#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import contextlib
import os.path
import sys
import tempfile
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

    @contextlib.contextmanager
    def open_test_path(self, body='one\ntwo\n', mode='w'):
        with tempfile.NamedTemporaryFile(mode) as testfile:
            testfile.write(body)
            testfile.flush()
            yield testfile.name

    def test_open_usable(self):
        expr = xg.UserExpression('open(_).readline')
        with self.open_test_path() as testpath:
            self.assertEqual(expr(testpath), 'one\n')

    def test_open_supports_encoding(self):
        if sys.getdefaultencoding() == 'utf-8':
            encoding = 'latin-1'
        else:
            encoding = 'utf-8'
        expr = xg.UserExpression('open(_, encoding={!r}).readline'.
                                 format(encoding))
        with self.open_test_path('Ä\nË\n'.encode(encoding), 'wb') as testpath:
            self.assertEqual(expr(testpath), 'Ä\n')

    def test_open_write_fails(self, mode='w'):
        expr = xg.UserExpression('open(_, {!r}).readline'.format(mode))
        with self.open_test_path() as testpath, self.assertRaises(ValueError):
            expr(testpath)

    def test_open_append_fails(self):
        self.test_open_write_fails('a')

    def test_open_create_fails(self):
        self.test_open_write_fails('x')

    def test_open_read_write_fails(self):
        self.test_open_write_fails('r+')

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
