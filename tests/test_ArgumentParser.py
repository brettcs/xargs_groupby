#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import unittest

import xargs_groupby as xg
from . import mock, PY_MAJVER

class ArgumentParserTestCase(unittest.TestCase):
    ARGV_ENCODING = 'utf-8'

    def setUp(self):
        xg.ArgumentParser.ARGV_ENCODING = self.ARGV_ENCODING

    def _build_arglist(self, arglist=None, **arguments):
        if arglist is None:
            arglist = ['_', 'echo']
        switches = ['--{}={}'.format(key, arguments[key]) for key in arguments]
        return switches + arglist

    def _build_arglist_py2(self, arglist=None, **arguments):
        arglist = self._build_arglist(arglist, **arguments)
        return [arg.encode(self.ARGV_ENCODING) for arg in arglist]

    build_arglist = _build_arglist_py2 if (PY_MAJVER < 3) else _build_arglist

    def test_preexec(self):
        pre_cmd = ['mkdir', '{}']
        xargs_cmd = ['mv', '-t', '{}']
        arglist = self.build_arglist(['--pre'] + pre_cmd + ['--', '_'] + xargs_cmd)
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.preexec, pre_cmd)
        self.assertEqual(args.command, xargs_cmd)

    def assertParseError(self, arglist):
        with mock.patch('sys.stderr', io.StringIO()), \
             self.assertRaises(SystemExit) as exc_test:
            xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(exc_test.exception.code, 2)

    def test_delimiter(self):
        arglist = self.build_arglist(delimiter='Z', encoding='ascii')
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.delimiter, b'Z')

    def test_no_multibyte_delimiter(self):
        arglist = self.build_arglist(delimiter='a', encoding='utf-16')
        self.assertParseError(arglist)

    def test_newline_escaped_delimiter(self):
        arglist = self.build_arglist(delimiter=r'\n', encoding='ascii')
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.delimiter, b'\n')

    def test_8bit_delimiter(self):
        # This also tests that we decode arglist correctly on Python 2.
        arglist = self.build_arglist(delimiter='ä', encoding='latin-1')
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.delimiter, 'ä'.encode('latin-1'))

    def test_null(self):
        arglist = self.build_arglist(['-0', '_', 'echo'])
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.delimiter, b'\0')

    def test_xargs_options(self):
        arglist = self.build_arglist(['-E', 'EOF', '-I', '{}', '_', 'echo'])
        args, xargs_opts = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(xargs_opts.I, '{}')
        self.assertEqual(args.eof_str, 'EOF')
        self.assertIsNone(getattr(args, 'I', None))

    @unittest.skip("not sure argparse can do xargs-compatible 0-or-1-argument switches")
    def test_i_parsing(self):
        arglist = self.build_arglist(['-i', '_', 'echo'])
        args, xargs_opts = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(xargs_opts.I, '{}')
