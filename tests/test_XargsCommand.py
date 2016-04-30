#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg

class XargsCommandTestCase(unittest.TestCase):
    def setUp(self):
        self.xargs = xg.XargsCommand(['xargs', '-0'])

    def test_base_command_copies(self):
        base = ['xargs', '-0']
        xargs = xg.XargsCommand(base)
        base.pop()
        self.assertEqual(xargs.command()[:2], ['xargs', '-0'])

    def test_command_method_new(self):
        self.assertIsNot(self.xargs.command(), self.xargs.command())
