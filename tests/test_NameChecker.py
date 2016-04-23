#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import ast
import unittest

import xargs_groupby as xg

class NameCheckerTestCase(unittest.TestCase):
    def build_ast(self, code_s):
        return ast.parse(code_s, '<{}>'.format(self.id()), 'eval')

    def test_all_names_known(self):
        names = {'foo': None, 'bar': None}
        used, unknown = xg.NameChecker(names).check(self.build_ast('foo(bar)'))
        self.assertEqual(used, set(names))
        self.assertEqual(unknown, set())

    def test_all_names_unknown(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('foo(bar)'))
        self.assertEqual(used, set())
        self.assertEqual(unknown, set(['foo', 'bar']))

    def test_names_mix(self):
        names = {'foo': None}
        used, unknown = xg.NameChecker(names).check(self.build_ast('foo(bar)'))
        self.assertEqual(used, set(names))
        self.assertEqual(unknown, set(['bar']))

    def test_underscore_is_name(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('int(_)'))
        self.assertEqual(unknown, set(['int', '_']))

    def test_attribute_not_name(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('open(_).name'))
        self.assertEqual(unknown, set(['open', '_']))

    def test_method_arg_name(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('os.stat(_)'))
        self.assertEqual(unknown, set(['os', '_']))

    def test_method_arg_const(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('os.stat("foo")'))
        self.assertEqual(unknown, set(['os']))

    def test_slice(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('_[:5]'))
        self.assertEqual(unknown, set(['_']))

    def test_slice_arg(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('"test"[1:int(_)]'))
        self.assertEqual(unknown, set(['int', '_']))

    def test_operator_lhs(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('left * 2'))
        self.assertEqual(unknown, set(['left']))

    def test_operator_rhs(self):
        used, unknown = xg.NameChecker({}).check(self.build_ast('"test" + right'))
        self.assertEqual(unknown, set(['right']))
