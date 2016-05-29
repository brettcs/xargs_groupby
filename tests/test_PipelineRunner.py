#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools
import unittest

import xargs_groupby as xg
from . import mock, mocks

class PipelineRunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.writer_fake = mocks.FakeMultiProcessWriter()
        self.writer_mock = mock.Mock(wraps=self.writer_fake)
        xg.PipelineRunner.MultiProcessWriter = mock.Mock(return_value=self.writer_mock)

    def setup_pipelines(self, pipelines_count_or_kwargs, writer_kwargs=None):
        try:
            pipelines_kwargs = iter(pipelines_count_or_kwargs)
        except TypeError:
            pipelines_kwargs = itertools.repeat({}, pipelines_count_or_kwargs)
        if writer_kwargs is None:
            writer_kwargs = [{'returncode': 0}] * 2
        self.pipelines = [mocks.FakeProcessPipeline(
            (mocks.FakeProcessWriter(**pwkw) for pwkw in writer_kwargs),
            **ppkw) for ppkw in pipelines_kwargs]

    def count_poll_timeouts(self):
        return sum(1 for call in self.writer_mock.write_ready.call_args_list
                   if any(call[0][:1]) or call[1].get('timeout'))

    def count_successful_pipelines(self):
        return sum(1 for p in self.pipelines if p.success())

    def assertPipelinesRun(self, runner, run_count, failures_count=0):
        self.assertEqual(runner.run_count(), run_count)
        self.assertEqual(runner.failures_count(), failures_count)
        self.assertEqual(self.count_successful_pipelines(), run_count - failures_count)

    def test_run_one_pipeline_no_writes(self, writer_kwargs=None):
        self.setup_pipelines(1, writer_kwargs)
        runner = xg.PipelineRunner(1)
        runner.run(self.pipelines)
        self.assertPipelinesRun(runner, 1)

    def test_run_one_pipeline_with_writes(self):
        self.test_run_one_pipeline_no_writes([{'need_writes': 3}])
        self.assertEqual(self.writer_mock.write_ready.call_count, 3)

    def test_run_two_pipelines_in_sequence(self, max_procs=1):
        self.setup_pipelines(2, [{'need_writes': 1}])
        runner = xg.PipelineRunner(max_procs)
        runner.run(self.pipelines)
        self.assertPipelinesRun(runner, 2)
        self.assertEqual(self.writer_fake.writes_max, max_procs)

    def test_run_two_pipelines_parallel(self):
        self.test_run_two_pipelines_in_sequence(2)

    def test_writes_block_below_max_procs(self, max_procs=4):
        self.setup_pipelines(2, [{'need_writes': 1}])
        runner = xg.PipelineRunner(max_procs)
        runner.run(self.pipelines)
        self.assertPipelinesRun(runner, 2)
        self.assertEqual(self.count_poll_timeouts(), 0)

    def test_writes_block_at_max_procs(self):
        self.test_writes_block_below_max_procs(2)

    def test_writes_block_above_max_procs(self):
        self.test_writes_block_below_max_procs(1)

    def test_writes_timeout_while_polling_procs(self):
        self.pipelines = [
            mocks.FakeProcessPipeline([mocks.FakeProcessWriter(need_writes=0)]),
            mocks.FakeProcessPipeline([mocks.FakeProcessWriter(need_writes=1)]),
        ]
        runner = xg.PipelineRunner(2)
        runner.run(self.pipelines)
        self.assertPipelinesRun(runner, 2)
        write_calls = self.writer_mock.write_ready.call_count
        self.assertGreater(write_calls, 0)
        self.assertEqual(self.count_poll_timeouts(), write_calls)

    def test_all_pipelines_run_after_failure(self):
        self.setup_pipelines({'success': s} for s in [False, True, False, True])
        runner = xg.PipelineRunner(1)
        runner.run(self.pipelines)
        self.assertPipelinesRun(runner, 4, 2)

    def test_runs_asymmetric_pipelines(self):
        self.pipelines = [
            mocks.FakeProcessPipeline([mocks.FakeProcessWriter(need_writes=4),
                                       mocks.FakeProcessWriter(need_writes=2),
                                       mocks.FakeProcessWriter(need_writes=2)]),
            mocks.FakeProcessPipeline([mocks.FakeProcessWriter(need_writes=2)]),
            mocks.FakeProcessPipeline([mocks.FakeProcessWriter(need_writes=3),
                                       mocks.FakeProcessWriter(need_writes=0)])
        ]
        runner = xg.PipelineRunner(2)
        runner.run(self.pipelines)
        self.assertPipelinesRun(runner, 3)
