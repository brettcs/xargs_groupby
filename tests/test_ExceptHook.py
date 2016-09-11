#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import importlib
import io
import itertools
import os
import random
import re
import signal
import sys
import unittest

import xargs_groupby as xg
from . import FOREIGN_ENCODING

importlib.import_module(Exception.__module__)

class ExceptHookTestCase(unittest.TestCase):
    INTERNAL_ERRORS = (
        AttributeError,
        Exception,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
    )
    ENVIRONMENT_ERRORS = (IOError, OSError)
    USER_ERRORS = (xg.UserArgumentsError, xg.UserExpressionError)
    ENVIRONMENT_ERRNOS = tuple(errno.errorcode)
    _locals = locals()

    def new_excepthook(self, show_tb=False):
        stderr = io.StringIO()
        excepthook = xg.ExceptHook(stderr=stderr)
        excepthook.show_tb = show_tb
        return stderr, excepthook

    def random_message(self):
        # This should include a non-Latin character, to test there aren't
        # implicit conversions in Python 2.
        return "test message №{}".format(random.randint(10000, 99999))

    def new_environment_error(self, exc_type, errnum=None, strerror=None, *args):
        if errnum is None:
            errnum = random.choice(self.ENVIRONMENT_ERRNOS)
        if strerror is None:
            strerror = os.strerror(errnum)
        return exc_type(errnum, strerror, *args)

    def new_error(self, exc_type):
        if issubclass(exc_type, self.ENVIRONMENT_ERRORS):
            return self.new_environment_error(exc_type)
        else:
            return exc_type(self.random_message())

    def assertExitFrom(self, exception, excepthook):
        try:
            raise exception
        except BaseException:
            exc_tb = sys.exc_info()[2]
        with self.assertRaises(SystemExit) as exc_check:
            excepthook(type(exception), exception, exc_tb)
        return exc_check

    def assertErrorHeadline(self, stderr, *message_parts):
        expect_message = "xargs_groupby: {}\n".format(": ".join(message_parts))
        stderr.seek(0)
        self.assertEqual(stderr.read(len(expect_message)), expect_message)

    expected_exitcodes = {MemoryError: 1, KeyboardInterrupt: -signal.SIGINT}
    expected_exitcodes.update({exc_type: 1 for exc_type in INTERNAL_ERRORS})
    expected_exitcodes.update({exc_type: 1 for exc_type in ENVIRONMENT_ERRORS})
    expected_exitcodes.update({exc_type: 3 for exc_type in USER_ERRORS})

    for exc_type in expected_exitcodes:
        def error_code_test(self, exc_type=exc_type,
                            expect_exitcode=expected_exitcodes[exc_type]):
            _, excepthook = self.new_excepthook()
            exc_check = self.assertExitFrom(self.new_error(exc_type), excepthook)
            self.assertEqual(exc_check.exception.code, expect_exitcode)
        _locals['test_{}_error_code'.format(exc_type.__name__)] = error_code_test

    def error_message_test(self, exception, *message_parts):
        stderr, excepthook = self.new_excepthook()
        self.assertExitFrom(exception, excepthook)
        self.assertErrorHeadline(stderr, *message_parts)
        return stderr

    for exc_type in INTERNAL_ERRORS:
        def internal_error_message_test(self, exc_type=exc_type):
            message_prefix = "internal " + exc_type.__name__
            exc_message = self.random_message()
            exception = exc_type(exc_message)
            stderr = self.error_message_test(exception, message_prefix, exc_message)
            rest_stderr = stderr.read()
            self.assertIn("bug in xargs_groupby", rest_stderr)
            self.assertIn("`--debug`", rest_stderr)
        _locals['test_{}_error_message'.format(exc_type.__name__)] = internal_error_message_test

    for exc_type in USER_ERRORS:
        def user_error_message_test(self, exc_type=exc_type):
            exc_message = self.random_message()
            exception = exc_type(exc_message)
            stderr = self.error_message_test(exception, "error", exc_message)
            self.assertEqual(stderr.read(), '')
        _locals['test_{}_error_message'.format(exc_type.__name__)] = user_error_message_test

    def test_environment_error_without_filename(self):
        exception = self.new_environment_error(IOError)
        stderr = self.error_message_test(exception, "error", exception.strerror)
        self.assertEqual(stderr.read(), '')

    def test_environment_error_with_filename(self):
        filename = self.random_message() + '.txt'
        exception = self.new_environment_error(OSError, None, None, filename)
        stderr = self.error_message_test(exception, "error", filename, exception.strerror)
        self.assertEqual(stderr.read(), '')

    def test_keyboard_interrupt_no_message(self):
        stderr, excepthook = self.new_excepthook(show_tb=True)
        self.assertExitFrom(KeyboardInterrupt("no message test"), excepthook)
        self.assertEqual(stderr.tell(), 0)

    for exc_type in itertools.chain(INTERNAL_ERRORS, ENVIRONMENT_ERRORS, USER_ERRORS):
        def show_traceback_test(self, exc_type=exc_type):
            exception = self.new_error(exc_type)
            stderr, excepthook = self.new_excepthook(show_tb=True)
            self.assertExitFrom(exception, excepthook)
            stderr.seek(0)
            for line in stderr:
                self.assertNotIn("`--debug`", line)
                if line.startswith("Traceback "):
                    break
            else:
                self.fail("did not find start of traceback in stderr")
            for line in stderr:
                self.assertNotIn("`--debug`", line)
            # Some classes like OSError can give you a different subtype based
            # on their args.  This means searching the traceback string for
            # the name of the exception type is an insufficient test.
            match = re.match(r'([A-Za-z_][\w]*\.)*([A-Za-z_][\w]*):', line)
            src_module = sys.modules[exc_type.__module__]
            try:
                tb_class = getattr(src_module, match.group(2))
            # Note that AttributeError could come from None.group() or
            # getattr itself.
            except AttributeError:
                ok = False
            else:
                ok = issubclass(tb_class, exc_type)
            if not ok:
                self.fail("last traceback line does not name exception type:\n{!r}".
                          format(line))
        _locals['test_{}_show_traceback'.format(exc_type.__name__)] = show_traceback_test

    def test_with_sys_stderr_default_encoding(self):
        excepthook = xg.ExceptHook.with_sys_stderr()
        stderr = excepthook.stderr
        self.assertEqual(stderr.fileno(), sys.stderr.fileno())
        self.assertTrue(stderr.encoding)

    def test_with_sys_stderr_specified_encoding(self):
        excepthook = xg.ExceptHook.with_sys_stderr(FOREIGN_ENCODING)
        stderr = excepthook.stderr
        self.assertEqual(stderr.fileno(), sys.stderr.fileno())
        self.assertEqual(stderr.encoding, FOREIGN_ENCODING)
