#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import contextlib
import io
import locale
import subprocess
import sys
import tempfile
import unittest

from argparse import Namespace

import xargs_groupby as xg
from . import TEST_FLAGS

try:
    unicode
except NameError:
    unicode = str

ZERO_SET = frozenset([0])

def read_and_discard(read_file):
    with read_file:
        for line in read_file:
            pass

def run_and_check(cmd, ok_exitcodes=ZERO_SET):
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError:
        return False
    proc.stdin.close()
    read_and_discard(proc.stdout)
    return proc.wait() in ok_exitcodes

runnable_tools = {
    'xargs': run_and_check(['xargs', '--version']),
    'echo': run_and_check(['echo', '--version']),
    'test': run_and_check(['test', 'string'])
}

@unittest.skipUnless(TEST_FLAGS.want_integration,
                     "integration tests not requested")
@unittest.skipUnless(runnable_tools['xargs'],
                     "integration tests require 'xargs'")
class IntegrationTestCase(unittest.TestCase):
    ENCODING = 'utf-8'
    MAX_PROCS = unicode(TEST_FLAGS.max_procs)

    @staticmethod
    @contextlib.contextmanager
    def io_wrapper(file_obj, encoding=ENCODING):
        mode = file_obj.mode.replace('b', '')
        with file_obj, io.open(file_obj.fileno(), mode,
                               encoding=encoding, closefd=False) as io_file:
            yield io_file

    def require_tools(*tool_names):
        for name in tool_names:
            if not runnable_tools[name]:
                return unittest.skip("test requires {!r}".format(name))
        return lambda func: func

    def setUp(self):
        self.stdout_lines = []

    def run_xg(self, cmd_args, stdin_s, ok_exitcodes=ZERO_SET, encoding=ENCODING):
        cmd = [
            sys.executable, xg.__file__,
            '--encoding', encoding,
            '--max-procs', self.MAX_PROCS,
        ]
        cmd.extend(cmd_args)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with self.io_wrapper(proc.stdin) as stdin:
            stdin.write(stdin_s)
        extra_lines = []
        with self.io_wrapper(proc.stdout) as stdout:
            self.stdout_lines.extend(stdout)
        read_and_discard(proc.stderr)
        self.assertIn(proc.wait(), ok_exitcodes)

    def expect_stdout(self, *expected_lines):
        missing_lines = set(expected_lines)
        extra_lines = []
        for line in self.stdout_lines:
            try:
                missing_lines.remove(line.rstrip('\n'))
            except KeyError:
                extra_lines.append(line)
        if missing_lines or extra_lines:
            fail_msg = ["standard output did not match expected lines.",
                        "Missing lines:"]
            fail_msg.extend(repr(line) for line in expected_lines
                            if line in missing_lines)
            fail_msg.append("\nExtra lines:")
            fail_msg.extend(repr(line) for line in extra_lines)
            self.fail("\n".join(fail_msg))

    @require_tools('echo')
    def test_len_echo(self):
        self.run_xg(
            ['len', 'echo'],
            "cat snake hedgehog\ndog horse\n",
        )
        self.expect_stdout("cat dog", "snake horse", "hedgehog")

    @require_tools('echo')
    def test_delimiter_groupstr_preexec_user_function(self):
        self.run_xg(
            [
                '--null',
                '--group-str', '{G}',
                '--preexec', 'echo', 'group:', '{G}', ';',
                'arg[:3]',
                'echo',
            ],
            "123\x00456\x00123\t456\x00456789",
        )
        self.expect_stdout(
            "group: 123",
            "group: 456",
            "123 123\t456",
            "456 456789",
        )

    @require_tools('echo')
    def test_arg_file_replace_str_multibyte_delimiter(self):
        with tempfile.NamedTemporaryFile(prefix='xgtest') as argfile:
            args = ['A', 'b\tB', 'a\ta', 'bb']
            argfile.write('\t\t'.join(args).encode(self.ENCODING))
            argfile.flush()
            self.run_xg(
                [
                    '--delimiter', '\\t\\t',
                    '--replace-str', 'II',
                    '--group-str', 'GG',
                    '--arg-file', argfile.name,
                    's[0].upper()',
                    'echo', 'II', 'in', 'GG',
                ],
            "unused stdin",
            )
        self.expect_stdout(
            "A in A",
            "b\tB in B",
            "a\ta in A",
            "bb in B",
        )

    @require_tools('test')
    def test_failures(self):
        self.run_xg(
            ['argument', 'test', 'B', '='],
            "A B A C",
            [12],
        )
