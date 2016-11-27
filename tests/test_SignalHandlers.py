#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg
from . import mock
from .helpers import NoopMock

class SignalHandlersTestCase(unittest.TestCase):
    _locals = locals()
    for signum, handlers_count in zip([3, 15], [1, 2]):
        def test_handlers(self, signum=signum, handlers_count=handlers_count):
            handlers = [mock.Mock(name='sig_handler') for _ in range(handlers_count)]
            frame = NoopMock(name='frame')
            handler = xg.SignalHandlers()
            for handler_func in handlers:
                handler.add(handler_func)
            handler.handle(signum, frame)
            for handler_func in handlers:
                handler_func.assert_called_with(signum, frame)
        _locals['test_sig{}_{}_handlers'.format(signum, handlers_count)] = test_handlers
    del test_handlers

    def test_zero_handlers(self):
        frame = NoopMock(name='frame')
        handler = xg.SignalHandlers()
        handler.handle(3, frame)
        handler.handle(15, frame)

    def test_handlers_called_in_order(self):
        call_order = []
        handler = xg.SignalHandlers()
        func_count = list(range(10))
        for count in func_count:
            handler_func = mock.Mock(name='sig_handler')
            def side_effect(s, f, call_order=call_order, count=count):
                call_order.append(count)
            handler_func.side_effect = side_effect
            handler.add(handler_func)
        handler.handle(2, NoopMock(name='frame'))
        self.assertEqual(call_order, func_count)


class SignalHandlersExitTestCase(unittest.TestCase):
    _locals = locals()
    for signum in range(1, 16):
        def test_exit(self, signum=signum):
            exit_mock = mock.Mock(name='sys.exit')
            xg.SignalHandlers.exit(signum, NoopMock(name='frame'), exit_mock)
            exit_mock.assert_called_with(-signum)
        _locals['test_exit_on_signal_{}'.format(signum)] = test_exit
    del test_exit
