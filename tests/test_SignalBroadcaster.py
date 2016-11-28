#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import itertools
import os
import random
import unittest

from argparse import Namespace

import xargs_groupby as xg
from . import mock
from .helpers import NoopMock

class FakePopen(object):
    def __init__(self, signal_error=None, returncode=0):
        self.send_signal = mock.Mock(name='FakePopen.send_signal')
        if signal_error is not None:
            self.send_signal.side_effect = signal_error
        self.wait = mock.Mock(name='FakePopen.wait', return_value=returncode)


class SignalBroadcasterTestCase(unittest.TestCase):
    def _make_error(errno):
        return OSError(errno, os.strerror(errno))

    def name_iter(prefix_list, error_list):
        yield 'test'
        for s in prefix_list:
            yield s
        for error in error_list:
            try:
                yield errno.errorcode[error.errno]
            except AttributeError:
                yield 'NoError'

    def setUp(self):
        self.broadcaster = xg.SignalBroadcaster()
        self.processes = []

    def add_process(self, proc_or_error=None):
        if isinstance(proc_or_error, FakePopen):
            new_proc = proc_or_error
        else:
            new_proc = FakePopen(proc_or_error)
        self.processes.append(new_proc)
        self.broadcaster.add(new_proc)

    def send_and_check(self, signum=None):
        if signum is None:
            signum = random.randint(1, 16)
        frame = NoopMock(name='frame')
        self.broadcaster.send(signum, frame)
        for process in self.processes:
            process.send_signal.assert_called_with(signum)

    _locals = locals()
    ERRORS_LIST = [None, _make_error(errno.ESRCH), _make_error(errno.EPERM)]
    for proc_count in range(4):
        for error_list in itertools.combinations(ERRORS_LIST, proc_count):
            def test_procs(self, error_list=error_list):
                for error in error_list:
                    self.add_process(error)
                self.send_and_check()
            _locals['_'.join(name_iter(['processes'], error_list))] = test_procs
    del test_procs

    def test_no_signal_removed_proc(self, error_list=(None,), rm_count=1):
        for error in error_list:
            self.add_process(error)
        removed_procs = []
        for _ in range(rm_count):
            rm_proc = self.processes.pop()
            self.broadcaster.remove(rm_proc)
            removed_procs.append(rm_proc)
        self.send_and_check()
        for process in removed_procs:
            process.send_signal.assert_not_called()

    for error_list in itertools.combinations(ERRORS_LIST, 2):
        def test_removal(self, error_list=error_list):
            self.test_no_signal_removed_proc(error_list)
        _locals['_'.join(name_iter(['removal'], error_list))] = test_removal
    del test_removal

    def test_no_signal_all_procs_removed(self):
        self.test_no_signal_removed_proc(self.ERRORS_LIST, len(self.ERRORS_LIST))

    def test_wait(self):
        self.add_process()
        self.add_process()
        error = self._make_error(errno.ECHILD)
        side_effect = [0, 1, error, error]
        waitpid = mock.Mock(name='os.waitpid', side_effect=side_effect)
        self.broadcaster.wait(1, NoopMock(name='frame'), waitpid)
        waitpid.assert_has_calls([mock.call(-1, 0)] * 3)

    _make_error = staticmethod(_make_error)
