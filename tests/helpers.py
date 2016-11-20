from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import contextlib

from . import mock

class ExceptionWrapperTestHelper(object):
    @contextlib.contextmanager
    def assertRaisesWrapped(self, wrapped_class, wrapper_class, *wrapper_args):
        with self.assertRaises(wrapper_class) as exc_check:
            yield exc_check
        if wrapper_args:
            self.assertEqual(exc_check.exception.args, wrapper_args)
        self.assertIsInstance(exc_check.exception.__cause__, wrapped_class)


class ExitTestHelper(object):
    @contextlib.contextmanager
    def assertExits(self, *exit_codes):
        with self.assertRaises(SystemExit) as exc_check:
            yield exc_check
        if exit_codes:
            self.assertIn(exc_check.exception.code, exit_codes)


class NoopMock(mock.NonCallableMock):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('spec_set', object)
        return super(NoopMock, self).__init__(*args, **kwargs)
