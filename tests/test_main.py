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

class MainTestCase(unittest.TestCase):
    def test_main_connections(self):
        arglist = NoopMock(name='arglist')
        prog_mock = mock.Mock(name='Program')
        excepthook_mock = mock.Mock(name='ExceptHook')
        exitcode = xg.main(arglist, prog_mock, excepthook_mock)
        prog_mock.from_arglist.assert_called_with(arglist)
        program = prog_mock.from_arglist()
        excepthook_mock.with_sys_stderr.assert_called_with(program.args.encoding)
        self.assertIs(excepthook_mock.with_sys_stderr().show_tb, program.args.debug)
        program.main.assert_called_with()
        self.assertIs(exitcode, program.main())
