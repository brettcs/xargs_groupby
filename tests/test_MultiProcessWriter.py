#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import select
import unittest

import xargs_groupby as xg
from . import mock, mocks

class MultiProcessWriterTestCase(unittest.TestCase):
    def setUp(self):
        self.poller = mock.Mock(wraps=mocks.FakePoll())
        self.poll_init = mock.Mock(return_value=self.poller)
        xg.MultiProcessWriter.Poll = self.poll_init
        xg.MultiProcessWriter.PIPE_BUF = 1

    def test_add(self):
        proc = mocks.FakeProcessWriter(0, need_writes=1)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        self.poller.register.assert_called_with(proc.fileno(), select.POLLOUT)

    def test_add_doesnt_register_when_no_write_needed(self):
        proc = mocks.FakeProcessWriter(0, need_writes=0)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        self.assertFalse(self.poller.register.called)

    def test_one_process(self):
        proc = mocks.FakeProcessWriter(0, need_writes=1)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        writer.write_ready()
        self.assertEqual(self.poller.poll.call_count, 1)
        self.assertTrue(proc.success())

    def test_two_processes(self):
        procs = [mocks.FakeProcessWriter(0, need_writes=n) for n in range(1, 3)]
        expect_unregisters = [mock.call(proc.fileno()) for proc in procs]
        writer = xg.MultiProcessWriter()
        for proc in procs:
            writer.add(proc)
        writer.write_ready()
        self.poller.unregister.assert_has_calls(expect_unregisters[:1])
        self.assertTrue(procs[0].success())
        self.assertIsNone(procs[1].success())
        writer.write_ready()
        self.poller.unregister.assert_has_calls(expect_unregisters)
        self.assertTrue(procs[1].success())

    def test_zero_processes(self):
        writer = xg.MultiProcessWriter()
        writer.write_ready()
        self.assertEqual(self.poller.poll.call_count, 0)

    def test_no_poll_after_procs_done(self):
        proc = mocks.FakeProcessWriter(0, need_writes=1)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        writer.write_ready()
        writer.write_ready()
        self.assertEqual(self.poller.poll.call_count, 1)

    def test_write_ready_passes_timeout(self):
        proc = mocks.FakeProcessWriter(0, need_writes=1)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        writer.write_ready(5)
        self.poller.poll.assert_called_with(5)
        self.assertIsNone(proc.success())

    def test_no_timeout_poll_with_no_fds(self):
        writer = xg.MultiProcessWriter()
        writer.write_ready(3)
        self.assertFalse(self.poller.poll.called)

    def assertDoneProcs(self, writer, expect_procs):
        done_procs = set(writer.done_procs())
        self.assertEqual(len(done_procs), len(expect_procs))
        for proc in expect_procs:
            self.assertIn(proc, done_procs)

    def test_done_procs(self):
        proc = mocks.FakeProcessWriter(0, need_writes=1)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        writer.write_ready()
        self.assertDoneProcs(writer, [proc])

    def test_proc_without_write_is_done(self):
        proc = mocks.FakeProcessWriter(0, need_writes=0)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        self.assertDoneProcs(writer, [proc])

    def test_done_procs_resets(self):
        proc = mocks.FakeProcessWriter(0, need_writes=0)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        for proc in writer.done_procs():
            pass
        self.assertDoneProcs(writer, [])

    def test_not_done_proc(self):
        proc = mocks.FakeProcessWriter(0, need_writes=2)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        writer.write_ready()
        self.assertDoneProcs(writer, [])

    def test_two_done_procs(self):
        procs = [mocks.FakeProcessWriter(0, need_writes=n) for n in range(1, 3)]
        writer = xg.MultiProcessWriter()
        for proc in procs:
            writer.add(proc)
        for proc in procs:
            writer.write_ready()
            self.assertDoneProcs(writer, [proc])
