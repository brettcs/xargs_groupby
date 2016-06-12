#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import unittest

import xargs_groupby as xg
from . import mock, FOREIGN_ENCODING, PY_MAJVER

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

    def test_command_parsed_wholly(self, xargs_cmd=['mv', '-t', '{}']):
        arglist = self.build_arglist(['_'] + xargs_cmd)
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.command, xargs_cmd)

    def test_command_with_switch_conflict(self):
        self.test_command_parsed_wholly(['cat', '-E'])

    def test_preexec(self, pre_cmd=['mkdir', '{}'],
                     xargs_cmd=['mv', '-t', '{}']):
        arglist = self.build_arglist(['--pre'] + pre_cmd + [';', '_'] + xargs_cmd)
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.preexec, pre_cmd)
        self.assertEqual(args.command, xargs_cmd)

    def test_preexec_with_switches(self):
        self.test_preexec(['mkdir', '-p', '{}'])

    def test_preexec_with_switch_conflict(self):
        self.test_preexec(['test', '-d', '{}'])

    def assertParseError(self, arglist):
        with mock.patch('sys.stderr', io.StringIO()), \
             self.assertRaises(SystemExit) as exc_test:
            xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(exc_test.exception.code, 2)

    def test_unterminated_preexec(self):
        arglist = self.build_arglist(['--pre', 'foo', '-bar', '_', 'echo'])
        self.assertParseError(arglist)

    def test_one_arg_preexec(self):
        arglist = self.build_arglist(['--preexec=date', '_', 'echo'])
        self.assertParseError(arglist)

    def test_unicode_delimiter(self, delimiter='♥', expected=None):
        if expected is None:
            expected = delimiter
        # We specify an encoding to ensure it's not used to decode the
        # delimiter itself in Python 2.
        arglist = self.build_arglist(delimiter=delimiter, encoding=FOREIGN_ENCODING)
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.delimiter, expected)

    def test_multichar_delimiter(self):
        self.test_unicode_delimiter('←→')

    def test_newline_escaped_delimiter(self):
        self.test_unicode_delimiter(r'\n', '\n')

    def test_multichar_escaped_delimiter(self):
        self.test_unicode_delimiter(r'\t\t', '\t\t')

    def test_null(self):
        arglist = self.build_arglist(['-0', '_', 'echo'])
        args, _ = xg.ArgumentParser().parse_args(arglist)
        self.assertEqual(args.delimiter, '\0')

    def test_delimiters_exclusive(self):
        arglist = self.build_arglist(['-0', '-d_', '_', 'echo'])
        self.assertParseError(arglist)

    def test_delimiter_exclusive_with_eof(self, delim_opt='-d_'):
        arglist = self.build_arglist([delim_opt, '-E', 'EOF', '_', 'echo'])
        self.assertParseError(arglist)

    def test_null_exclusive_with_eof(self):
        self.test_delimiter_exclusive_with_eof('-0')

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
