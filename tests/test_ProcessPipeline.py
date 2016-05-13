#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg
from . import mock

class FakeProcessWriter(object):
    def __init__(self, returncode, success=None):
        self.returncode = returncode
        self._success = (returncode == 0) if (success is None) else success

    def poll(self):
        return self.returncode

    def success(self):
        return self._success


class ProcessPipelineTestCase(unittest.TestCase):
    STOP_SENTINEL = object()

    def setUp(self):
        self.procs = []
        xg.ProcessPipeline.ProcessWriter = mock.MagicMock(name='ProcessWriter')
        xg.ProcessPipeline.ProcessWriter.side_effect = self.procs

    def add_procs(self, returncodes):
        self.procs.extend(FakeProcessWriter(status) for status in returncodes)

    def assertPipeline(self, actual_pipeline, expected_pipeline):
        pipeline_iter = iter(actual_pipeline)
        for expected_args in expected_pipeline:
            try:
                next(pipeline_iter)
            except StopIteration:
                self.fail("actual pipeline produced no proc for {!r}".format(expected_args))
            actual_args = xg.ProcessPipeline.ProcessWriter.call_args[0]
            self.assertEqual(actual_args[0], expected_args[0])
            self.assertIs(actual_args[1], expected_args[1])
        self.assertIs(next(pipeline_iter, self.STOP_SENTINEL), self.STOP_SENTINEL)

    def test_one_step_pipeline(self):
        self.add_procs([0])
        raw_pipeline = [(['a'], iter([]))]
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline)
        self.assertTrue(pipeline.success())

    def test_two_step_pipeline(self):
        self.add_procs([0, 0])
        raw_pipeline = [(['b'], iter([])), (['c'], iter([]))]
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline)
        self.assertTrue(pipeline.success())

    def test_first_step_fails(self):
        self.add_procs([1, 0])
        raw_pipeline = [(['d'], iter([])), (['e'], iter([]))]
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline[:1])
        self.assertFalse(pipeline.success())

    def test_second_step_fails(self):
        self.add_procs([0, 2])
        raw_pipeline = [(['f'], iter([])), (['g'], iter([]))]
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline)
        self.assertFalse(pipeline.success())

    def test_success_uses_proc_success(self):
        self.procs.append(FakeProcessWriter(0, False))
        raw_pipeline = [(['h'], iter([]))]
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline)
        self.assertFalse(pipeline.success())

    def test_pipeline_stops_after_unsuccessful_proc(self):
        self.procs.append(FakeProcessWriter(0, False))
        self.add_procs([0])
        raw_pipeline = [(['i'], iter([])), (['j'], iter([]))]
        pipeline = xg.ProcessPipeline(raw_pipeline)
        self.assertPipeline(pipeline, raw_pipeline[:1])
        self.assertFalse(pipeline.success())
