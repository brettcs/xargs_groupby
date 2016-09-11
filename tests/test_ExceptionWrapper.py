#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import xargs_groupby as xg

class TestExceptionWrapper(Exception):
    pass


class ExceptionWrapperTestCase(unittest.TestCase):
    def test_exception_instance_wraps(self):
        wrapper_exc = TestExceptionWrapper("test wrapper")
        wrapper = xg.ExceptionWrapper(wrapper_exc, LookupError)
        with self.assertRaises(TestExceptionWrapper), wrapper:
            raise KeyError("test source")

    def test_exception_class_wraps(self):
        exc_args = ("test error args",)
        wrapper = xg.ExceptionWrapper(TestExceptionWrapper, ArithmeticError)
        with self.assertRaises(TestExceptionWrapper) as exc_check, wrapper:
            raise FloatingPointError(*exc_args)
        self.assertEqual(exc_check.exception.args, exc_args)

    def test_raised_exception_no_match(self):
        error = IndexError("test unwrapped")
        wrapper = xg.ExceptionWrapper(TestExceptionWrapper, UnicodeError)
        with self.assertRaises(IndexError) as exc_check, wrapper:
            raise error
        self.assertIs(exc_check.exception, error)

    def test_multiple_wrapped_exceptions(self):
        wrapper = xg.ExceptionWrapper(TestExceptionWrapper, KeyError, OSError)
        with self.assertRaises(TestExceptionWrapper), wrapper:
            raise OSError("test source")

    def test_multiple_wrapped_exceptions_none_match(self):
        wrapper = xg.ExceptionWrapper(TestExceptionWrapper, KeyError, OSError)
        with self.assertRaises(ValueError), wrapper:
            raise ValueError("test source")

    def test_nothing_raised(self):
        wrapper = xg.ExceptionWrapper(TestExceptionWrapper("unraised"), Exception)
        with wrapper:
            actual = 2 + 2
        self.assertEqual(actual, 4)

    def test_instance_cause(self):
        source = OverflowError("test cause for instance")
        wrapper_exc = TestExceptionWrapper("test cause wrapper")
        wrapper = xg.ExceptionWrapper(wrapper_exc, ArithmeticError)
        with self.assertRaises(TestExceptionWrapper) as exc_check, wrapper:
            raise source
        self.assertIs(exc_check.exception.__cause__, source)

    def test_class_cause(self):
        source = ZeroDivisionError("test cause for class")
        wrapper = xg.ExceptionWrapper(TestExceptionWrapper, ArithmeticError)
        with self.assertRaises(TestExceptionWrapper) as exc_check, wrapper:
            raise source
        self.assertIs(exc_check.exception.__cause__, source)
