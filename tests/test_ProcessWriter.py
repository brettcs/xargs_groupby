#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg
from . import mock
from .mocks import FakePipe, FakePopen

class ProcessWriterTestCase(unittest.TestCase):
    SEPARATOR = b'\0'[0]

    def setUp(self):
        xg.ProcessWriter.Popen = FakePopen

    def assertDone(self, proc, expect_returncode=0):
        self.assertTrue(proc.done_writing())
        self.assertEqual(proc.poll(), expect_returncode)
        self.assertEqual(proc.success(), expect_returncode == 0)

    def assertStdin(self, expected, index=-1):
        self.assertEqual(FakePopen.get_stdin(index), expected)

    def test_done_writing_immediately(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [], self.SEPARATOR)
            self.assertDone(proc)
            self.assertStdin(b'')

    def test_write_bytes(self):
        test_b = '←→'.encode('utf-8')
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [test_b], self.SEPARATOR)
            proc.write(4096)
            self.assertDone(proc)
            self.assertStdin('←→\0'.encode('utf-8'))

    def test_separator(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], b'\t'[0])
            proc.write(4096)
            self.assertDone(proc)
            self.assertStdin(b'a\tb\t')

    def test_no_separator(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], None)
            proc.write(4096)
            self.assertDone(proc)
            self.assertStdin(b'ab')

    def test_partial_write(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], self.SEPARATOR)
            proc.write(3)
            self.assertFalse(proc.done_writing())
            self.assertStdin(b'a\0b')

    def test_done_after_exact_write(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], self.SEPARATOR)
            proc.write(4)
            self.assertDone(proc)
            self.assertStdin(b'a\0b\0')

    def test_write_sequence(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], self.SEPARATOR)
            proc.write(3)
            proc.write(3)
            self.assertDone(proc)
            self.assertStdin(b'a\0b\0')

    def test_error_code(self):
        with FakePopen.with_returncode(9):
            proc = xg.ProcessWriter(['cat'], [], self.SEPARATOR)
            self.assertDone(proc, 9)
            self.assertStdin(b'')

    def setup_write_error(self, error=IOError("test error")):
        FakePopen.open_procs[-1].stdin.write = mock.Mock(side_effect=error)

    def test_stop_after_io_error(self):
        with FakePopen.with_returncode(8):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], self.SEPARATOR)
            self.setup_write_error()
            proc.write(2)
            self.assertDone(proc, 8)

    def test_no_success_after_io_error(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], self.SEPARATOR)
            self.setup_write_error()
            proc.write(2)
            self.assertEqual(proc.poll(), 0)
            self.assertFalse(proc.success())
