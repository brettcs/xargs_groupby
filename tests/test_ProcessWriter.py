#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import contextlib
import random
import unittest

import xargs_groupby as xg
from . import mock
from .helpers import ExceptionWrapperTestHelper
from .mocks import FakePipe, FakePopen

ORIG_SYNC_PROCESS = staticmethod(xg.ProcessWriter.sync_process)
SEPARATOR = b'\0'[0]

Registry = type(xg.ProcessWriter.process_registry)

class ProcessWriterTestCase(unittest.TestCase, ExceptionWrapperTestHelper):
    def setUp(self):
        xg.ProcessWriter.Popen = FakePopen
        xg.ProcessWriter.process_registry = Registry()
        xg.ProcessWriter.sync_process = ORIG_SYNC_PROCESS

    def assertDone(self, proc, expect_returncode=0):
        self.assertTrue(proc.done_writing())
        self.assertEqual(proc.poll(), expect_returncode)
        self.assertEqual(proc.success(), expect_returncode == 0)

    def assertStdin(self, expected, index=-1):
        self.assertEqual(FakePopen.get_stdin(index), expected)

    def test_done_writing_immediately(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [], SEPARATOR)
            self.assertDone(proc)
            self.assertStdin(b'')

    def test_write_bytes(self):
        test_b = '←→'.encode('utf-8')
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [test_b], SEPARATOR)
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
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], SEPARATOR)
            proc.write(3)
            self.assertFalse(proc.done_writing())
            self.assertStdin(b'a\0b')

    def test_done_after_exact_write(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], SEPARATOR)
            proc.write(4)
            self.assertDone(proc)
            self.assertStdin(b'a\0b\0')

    def test_write_sequence(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], SEPARATOR)
            proc.write(3)
            proc.write(3)
            self.assertDone(proc)
            self.assertStdin(b'a\0b\0')

    def test_error_code(self):
        with FakePopen.with_returncode(9):
            proc = xg.ProcessWriter(['cat'], [], SEPARATOR)
            self.assertDone(proc, 9)
            self.assertStdin(b'')

    def setup_write_error(self, error=IOError("test error")):
        FakePopen.open_procs[-1].stdin.write = mock.Mock(side_effect=error)

    def test_stop_after_io_error(self):
        with FakePopen.with_returncode(8):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], SEPARATOR)
            self.setup_write_error()
            proc.write(2)
            self.assertDone(proc, 8)

    def test_no_success_after_io_error(self):
        with FakePopen.with_returncode(0):
            proc = xg.ProcessWriter(['cat'], [b'a', b'b'], SEPARATOR)
            self.setup_write_error()
            proc.write(2)
            self.assertEqual(proc.poll(), 0)
            self.assertFalse(proc.success())

    def test_command_not_found_wrapped(self):
        xg.ProcessWriter.Popen = mock.Mock(side_effect=OSError)
        with self.assertRaisesWrapped(OSError, xg.UserCommandError, 'echo'):
            xg.ProcessWriter(['echo', 'hello world'], [], SEPARATOR)


class ProcessWriterSyncTestCase(unittest.TestCase):
    # These tests work by rigging up ProcessWriter such that it *has* to use
    # sync_process at the right times.  If it fails to do so, it will crash
    # or become inconsistent with our expected state, because we've detached
    # our own registry from its.
    @contextlib.contextmanager
    def sync_process(self):
        xg.ProcessWriter.process_registry = self.registry
        with FakePopen.with_returncode(self.use_returncode):
            yield
            self.last_procs = FakePopen.open_procs
        xg.ProcessWriter.process_registry = None

    @staticmethod
    def random_returncode():
        return random.randint(0, 256)

    def setUp(self):
        xg.ProcessWriter.Popen = FakePopen
        xg.ProcessWriter.sync_process = self.sync_process
        self.use_returncode = self.random_returncode()
        self.registry = set()
        # Let sync_process do whatever setup it wants, especially cleanup
        # which detaches our own state from ProcessWriter's.
        with self.sync_process():
            pass

    def assertProcsRegistered(self, expect_procs=None):
        if expect_procs is None:
            expect_procs = set(self.last_procs)
        self.assertEqual(self.registry, expect_procs)

    def test_register_on_create(self, writes=[], expect_procs=None):
        writer = xg.ProcessWriter(['cat'], [b'a', b'b'], SEPARATOR)
        if expect_procs is None:
            expect_procs = set(self.last_procs)
        for write_count in writes:
            writer.write(write_count)
            writer.poll()
        self.assertProcsRegistered(expect_procs)

    def test_still_registered_mid_writing(self):
        self.test_register_on_create([2])

    def test_unregistered_after_done_writing(self):
        self.test_register_on_create([4096], set())

    def test_unregistered_after_write_error(self):
        writer = xg.ProcessWriter(['cat'], [b'a', b'b'], SEPARATOR)
        self.last_procs[-1].stdin.write = mock.Mock(side_effect=IOError("test error"))
        writer.write(2)
        writer.poll()
        self.assertProcsRegistered(set())

    def test_no_registration_when_command_not_found(self):
        xg.ProcessWriter.Popen = mock.Mock(side_effect=OSError)
        try:
            xg.ProcessWriter(['cat'], [], SEPARATOR)
        except Exception:
            pass
        self.assertProcsRegistered(set())

    def test_multiple_process_registration(self):
        writer1 = xg.ProcessWriter(['cat'], [b'c', b'd'], SEPARATOR)
        proc1 = set(self.last_procs)
        writer2 = xg.ProcessWriter(['cat'], [b'e', b'f'], SEPARATOR)
        writer2.write(4096)
        writer1.poll()
        writer2.poll()
        self.assertProcsRegistered(proc1)
