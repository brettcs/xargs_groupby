#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg
from . import mock, NoopMock

class MainTestCase(unittest.TestCase):
    def test_main_connections(self):
        arglist = NoopMock(name='arglist')
        prog_mock = mock.Mock(name='Program')
        exitcode = xg.main(arglist, prog_mock)
        prog_mock.from_arglist.assert_called_with(arglist)
        prog_mock.from_arglist().main.assert_called_with()
        self.assertIs(exitcode, prog_mock.from_arglist().main())
