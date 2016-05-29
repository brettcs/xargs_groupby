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

    def test_writing_count_zero(self):
        writer = xg.MultiProcessWriter()
        self.assertEqual(0, writer.writing_count())

    def test_writing_count_when_no_writes_needed(self):
        proc = mocks.FakeProcessWriter(0, need_writes=0)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        self.assertEqual(0, writer.writing_count())

    def test_writing_count_one(self):
        proc = mocks.FakeProcessWriter(0, need_writes=1)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        self.assertEqual(1, writer.writing_count())

    def test_writing_count_after_done_writing(self):
        proc = mocks.FakeProcessWriter(0, need_writes=1)
        writer = xg.MultiProcessWriter()
        writer.add(proc)
        writer.write_ready()
        self.assertEqual(0, writer.writing_count())

    def test_writing_count_two(self):
        writer = xg.MultiProcessWriter()
        for n in range(1, 3):
            writer.add(mocks.FakeProcessWriter(0, need_writes=n))
        self.assertEqual(2, writer.writing_count())

    def test_writing_count_after_done_writing_one(self):
        writer = xg.MultiProcessWriter()
        for n in range(1, 3):
            writer.add(mocks.FakeProcessWriter(0, need_writes=n))
        writer.write_ready()
        self.assertEqual(1, writer.writing_count())
