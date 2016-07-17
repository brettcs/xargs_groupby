#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import importlib
import io
import itertools
import os.path
import re
import tarfile
import unittest
import zipfile

import xargs_groupby as xg
from . import mock, FOREIGN_ENCODING

NONEXISTENT_PATH = os.path.join(__file__, '/_nonexistent/path')

def walk_attrs(obj, attr_seq):
    for attr_name in attr_seq:
        obj = getattr(obj, attr_name)
    return obj

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
        self.test_syntax_error('os.abort')

    def test_other_imported_module_not_usable(self):
        self.test_syntax_error('warnings.resetwarnings')

    def test_unimported_module_not_usable(self):
        self.test_syntax_error('pickle.dumps')

    def test_exit_not_usable(self):
        self.test_syntax_error('exit(_)')

    def test_file_not_usable(self):
        self.test_syntax_error('file(_)')

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

    def empty_tar_expr(self, append=''):
        tar_bytes = io.BytesIO()
        tar_start = tarfile.open(mode='w', fileobj=tar_bytes)
        tar_start.close()
        return 'tarfile.open(fileobj=io.BytesIO({!r})){}'.format(tar_bytes.getvalue(), append)

    def test_tarfile_not_addable(self, method_name='add'):
        expr = xg.UserExpression(self.empty_tar_expr('.{}(_)'.format(method_name)))
        with self.assertRaises(AttributeError):
            expr('.')

    def test_tarfile_not_extractable(self):
        self.test_tarfile_not_addable('extractall')

    def empty_zip_expr(self, class_name, append):
        zip_bytes = io.BytesIO()
        zip_start = zipfile.ZipFile(zip_bytes, 'w')
        zip_start.close()
        return '{}(io.BytesIO({!r})){}'.format(class_name, zip_bytes.getvalue(), append)

    def test_zipfile_not_addable(self, class_name='zipfile.ZipFile', method_name='write'):
        expr = xg.UserExpression(self.empty_zip_expr(class_name, '.{}(_)'.format(method_name)))
        with self.assertRaises(AttributeError):
            expr('.')

    def test_zipfile_not_extractable(self):
        self.test_zipfile_not_addable(method_name='extractall')

    def test_pyzipfile_not_addable(self):
        self.test_zipfile_not_addable(class_name='zipfile.PyZipFile')

    def test_pyzipfile_not_extractable(self):
        self.test_zipfile_not_addable(class_name='zipfile.PyZipFile', method_name='extractall')


def IOWrapperTests(expr_func_name, bad_modes,
                   call_fmt='{0}(_, {1!r}).read(1)', src_func_name=None):
    if src_func_name is None:
        src_func_name = expr_func_name
    name_parts = src_func_name.split('.')
    if len(name_parts) == 1:
        src_func = globals()[name_parts[0]]
    else:
        name_parts = iter(name_parts)
        src_module = importlib.import_module(next(name_parts))
        src_func = walk_attrs(src_module, name_parts)

    class IOWrapperTestCase(unittest.TestCase):
        if not hasattr(unittest.TestCase, 'assertRaisesRegex'):
            assertRaisesRegex = unittest.TestCase.assertRaisesRegexp

        def test_function_wrapped(self):
            expr = xg.UserExpression(expr_func_name)
            name_parts = iter(expr_func_name.split('.'))
            func = walk_attrs(expr._EVAL_VARS[next(name_parts)], name_parts)
            self.assertIsNotNone(func.__closure__)
            self.assertTrue(any(c.cell_contents is src_func for c in func.__closure__))
            self.assertNotEqual(func.__code__.co_name, src_func.__name__)

        _locals = locals()
        for bad_mode in bad_modes:
            def test_bad_mode_fails(self, mode=bad_mode):
                expr = xg.UserExpression(call_fmt.format(expr_func_name, mode))
                with self.assertRaisesRegex(ValueError, r'^invalid mode: '):
                    expr(NONEXISTENT_PATH)
            _locals['test_mode_{}_fails'.format(bad_mode)] = test_bad_mode_fails
        del test_bad_mode_fails
    IOWrapperTestCase.__name__ = str('{}WrapperTestCase'.format(re.sub(
        r'(^|\.)(\w)', lambda match: match.group(2).upper(), expr_func_name)))
    return IOWrapperTestCase

OpenWrapperTest = IOWrapperTests('open', ['w', 'a', 'x', 'r+'], src_func_name='io.open')
IOOpenWrapperTest = IOWrapperTests('io.open', ['w', 'a', 'x', 'r+'])
BZ2FileWrapperTest = IOWrapperTests('bz2.BZ2File', ['w'])
CodecsOpenWrapperTest = IOWrapperTests('codecs.open', ['w', 'a', 'x', 'r+'])
GzipFileWrapperTest = IOWrapperTests('gzip.GzipFile', ['w', 'a', 'x', 'r+'])
GzipOpenWrapperTest = IOWrapperTests('gzip.open', ['w', 'a', 'x', 'r+'])
TAR_BAD_MODES = [''.join(parts) for parts in
                 itertools.product('wa', ':|', ['', 'gz', 'bz2'])]
TAR_BAD_MODES.extend('wa')
TarOpenWrapperTest = IOWrapperTests('tarfile.open', TAR_BAD_MODES)
TarFileWrapperTest = IOWrapperTests('tarfile.TarFile', TAR_BAD_MODES)
ZipFileWrapperTest = IOWrapperTests('zipfile.ZipFile', 'wa')
PyZipFileWrapperTest = IOWrapperTests('zipfile.PyZipFile', 'wa')
