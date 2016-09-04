import argparse
import multiprocessing
import os
import sys

try:
    from unittest import mock
except ImportError:
    import mock

if sys.getdefaultencoding() == 'utf-8':
    FOREIGN_ENCODING = 'latin-1'
else:
    FOREIGN_ENCODING = 'utf-8'

PY_MAJVER = sys.version_info.major

class NoopMock(mock.NonCallableMock):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('spec_set', object)
        return super(NoopMock, self).__init__(*args, **kwargs)


class TestFlags(argparse.Namespace):
    FLAG_SETTERS = frozenset(['1', 'true', 'y', 'yes'])

    @classmethod
    def get_raw(cls, name, default=None):
        return os.environ.get('XGTEST_' + name.upper(), default)

    @classmethod
    def flag_set(cls, name):
        return cls.get_raw(name, '').lower() in cls.FLAG_SETTERS

    def __init__(self):
        super(TestFlags, self).__init__()
        try:
            self.max_procs = int(self.get_raw('max_procs'))
        except TypeError:
            self.max_procs = multiprocessing.cpu_count()
        self.want_integration = self.flag_set('integration')
TEST_FLAGS = TestFlags()
