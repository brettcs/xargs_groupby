#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg
from . import mock, FOREIGN_ENCODING
from .mocks import FakeProcessWriter

class ProcessPipelineTestCase(unittest.TestCase):
    STOP_SENTINEL = object()

    def setUp(self):
        self.procs = []
        xg.ProcessPipeline.ProcessWriter = mock.MagicMock(name='ProcessWriter')
        xg.ProcessPipeline.ProcessWriter.side_effect = self.procs

    def add_procs(self, returncodes):
        self.procs.extend(FakeProcessWriter(status) for status in returncodes)

    def assertPipeline(self, actual_pipeline, expected_pipeline):
        for index, expected_args in enumerate(expected_pipeline):
            try:
                proc = actual_pipeline.next_proc()
            except StopIteration:
                self.fail("actual pipeline produced no proc for {!r}".format(expected_args))
            actual_args = xg.ProcessPipeline.ProcessWriter.call_args[0]
            self.assertEqual(actual_args[0], expected_args[0])
            self.assertIs(actual_args[1], expected_args[1])
            self.assertIs(actual_args[2], expected_args[2])
            self.assertIs(proc, self.procs[index])
            self.assertIs(actual_pipeline.last_proc, proc)
        with self.assertRaises(StopIteration):
            actual_pipeline.next_proc()

    def build_pipeline(self, *commands):
        return [([command], iter([]), command.encode('utf-8')[0])
                for command in commands]

    def test_one_step_pipeline(self):
        self.add_procs([0])
        raw_pipeline = self.build_pipeline('a')
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline)
        self.assertTrue(pipeline.success())

    def test_two_step_pipeline(self):
        self.add_procs([0, 0])
        raw_pipeline = self.build_pipeline('b', 'c')
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline)
        self.assertTrue(pipeline.success())

    def test_first_step_fails(self):
        self.add_procs([1, 0])
        raw_pipeline = self.build_pipeline('d', 'e')
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline[:1])
        self.assertFalse(pipeline.success())

    def test_second_step_fails(self):
        self.add_procs([0, 2])
        raw_pipeline = self.build_pipeline('f', 'g')
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline)
        self.assertFalse(pipeline.success())

    def test_success_uses_proc_success(self):
        self.procs.append(FakeProcessWriter(0, False))
        raw_pipeline = self.build_pipeline('h')
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline)
        self.assertFalse(pipeline.success())

    def test_pipeline_stops_after_unsuccessful_proc(self):
        self.procs.append(FakeProcessWriter(0, False))
        self.add_procs([0])
        raw_pipeline = self.build_pipeline('i', 'j')
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline[:1])
        self.assertFalse(pipeline.success())

    def test_success_not_set_while_pipeline_running(self):
        self.add_procs([0, 0])
        raw_pipeline = self.build_pipeline('k', 'l')
        pipeline = xg.ProcessPipeline(raw_pipeline)
        pipeline.next_proc()
        pipeline.next_proc()
        self.assertIsNone(pipeline.success())
