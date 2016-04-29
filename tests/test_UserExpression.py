#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os.path
import unittest

import xargs_groupby as xg
from . import mock

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

    def test_arbitrary_shortcut_name(self):
        expr = xg.UserExpression('anything * 3')
        self.assertEqual(expr('t'), 'ttt')

    def test_arbitrary_shortcut_fails_inside_lambda(self):
        with self.assertRaises(ValueError):
            xg.UserExpression('lambda _: anything')

    def test_two_arbitrary_names_fail(self):
        with self.assertRaises(ValueError):
            xg.UserExpression('_ * anything')

    def test_builtin_usable(self):
        expr = xg.UserExpression('int')
        self.assertEqual(expr('019'), 19)

    def test_os_path_usable(self):
        expr = xg.UserExpression('os.path.basename')
        self.assertEqual(expr(os.path.join('dir', 'test')), 'test')

    def patch_open(self, body='one\ntwo\n'):
        return_file = io.StringIO(body)
        io_mock = mock.Mock(name='io.open mock',
                            spec_set=return_file,
                            return_value=return_file)
        return mock.patch('io.open', io_mock)

    def test_open_usable(self):
        expr = xg.UserExpression('open(_).readline()')
        with self.patch_open() as open_mock:
            self.assertEqual(expr('path'), 'one\n')
        open_mock.assert_called_once_with('path', 'r')

    def test_open_supports_encoding(self):
        if sys.getdefaultencoding() == 'utf-8':
            encoding = 'latin-1'
        else:
            encoding = 'utf-8'
        expr = xg.UserExpression('open(_, encoding={!r}).readline()'.
                                 format(encoding))
        with self.patch_open('Ä\nË\n') as open_mock:
            self.assertEqual(expr('path'), 'Ä\n')
        open_mock.assert_called_once_with('path', 'r', encoding=encoding)

    def test_open_write_fails(self, mode='w'):
        expr = xg.UserExpression('open(_, {!r}).readline()'.format(mode))
        with self.patch_open() as open_mock, self.assertRaises(ValueError):
            expr('path')
        self.assertEqual(open_mock.call_count, 0)

    def test_open_append_fails(self):
        self.test_open_write_fails('a')

    def test_open_create_fails(self):
        self.test_open_write_fails('x')

    def test_open_read_write_fails(self):
        self.test_open_write_fails('r+')

    def test_syntax_error(self, expr_s='lambda s:'):
        with self.assertRaises(ValueError):
            xg.UserExpression(expr_s)

    def test_not_callable(self):
        self.test_syntax_error('"test"')

    def test_not_expression(self):
        self.test_syntax_error('f = float')

    # This would be a nice feature to have, but it seems impossible to
    # correctly introspect the arguments of built-in types.
    # For example, try `inspect.getcallargs(int, 42)`.
    @unittest.skip("arity checking seems unreliable")
    def test_wrong_arity_zero(self):
        self.test_syntax_error('lambda: 5')

    @unittest.skip("arity checking seems unreliable")
    def test_wrong_arity_two(self):
        self.test_syntax_error('lambda a, b: a')

    def test_os_not_usable(self):
        self.test_syntax_error('os.stat')

    def test_other_imported_module_not_usable(self):
        self.test_syntax_error('warnings.resetwarnings')

    def test_unimported_module_not_usable(self):
        self.test_syntax_error('pickle.dumps')

    def test_exit_not_usable(self):
        self.test_syntax_error('exit(_)')

    def test_xg_contents_not_usable(self):
        for name in ['NameChecker', 'UserExpression', 'name']:
            expr_s = '{}(_)'.format(name)
            try:
                xg.UserExpression(expr_s)
            except ValueError:
                pass
            else:
                self.fail("expression {!r} did not raise ValueError".
                          format(expr_s))
