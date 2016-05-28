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
    ENCODING = 'utf-8'

    def setUp(self):
        xg.ProcessWriter.Popen = FakePopen

    def assertDone(self, proc, expect_returncode=0):
        self.assertTrue(proc.done_writing())
        self.assertEqual(proc.poll(), expect_returncode)
        self.assertEqual(proc.success(), expect_returncode == 0)

    def assertStdin(self, expected, index=-1):
        if not isinstance(expected, bytes):
            expected = expected.encode(self.ENCODING)
        self.assertEqual(FakePopen.get_stdin(index), expected)

    def test_done_writing_immediately(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [])
            self.assertDone(proc)
            self.assertStdin('')

    def test_write_bytes(self):
        test_s = '←→'
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [test_s], self.ENCODING)
            proc.write(4096)
            self.assertDone(proc)
            self.assertStdin(test_s + '\0')

    def test_partial_write(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], ['a', 'b'], self.ENCODING)
            proc.write(3)
            self.assertFalse(proc.done_writing())
            self.assertStdin('a\0b')

    def test_done_after_exact_write(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], ['a', 'b'], self.ENCODING)
            proc.write(4)
            self.assertDone(proc)
            self.assertStdin('a\0b\0')

    def test_write_sequence(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], ['a', 'b'], self.ENCODING)
            proc.write(3)
            proc.write(3)
            self.assertDone(proc)
            self.assertStdin('a\0b\0')

    def test_error_code(self):
        with FakePopen.with_returncode(9):
            proc = xg.ProcessWriter(['cat'], [], self.ENCODING)
            self.assertDone(proc, 9)
            self.assertStdin('')

    def setup_write_error(self, error=IOError("test error")):
        FakePopen.open_procs[-1].stdin.write = mock.Mock(side_effect=error)

    def test_stop_after_io_error(self):
        with FakePopen.with_returncode(8):
            proc = xg.ProcessWriter(['cat'], ['a', 'b'], self.ENCODING)
            self.setup_write_error()
            proc.write(2)
            self.assertDone(proc, 8)

    def test_no_success_after_io_error(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], ['a', 'b'], self.ENCODING)
            self.setup_write_error()
            proc.write(2)
            self.assertEqual(proc.poll(), 0)
            self.assertFalse(proc.success())
