#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import contextlib
import io
import subprocess

class FakePipe(io.BytesIO):
    def close(self):
        self.close_value = self.getvalue()
        return super(FakePipe, self).close()


class FakePopen(object):
    @classmethod
    @contextlib.contextmanager
    def with_returncode(cls, returncode):
        cls.end_returncode = returncode
        cls.open_procs = []
        try:
            yield
        finally:
            del cls.end_returncode, cls.open_procs

    @classmethod
    def get_stdin(cls, index=-1):
        stdin = cls.open_procs[index].stdin
        if stdin.closed:
            return stdin.close_value
        else:
            return stdin.getvalue()

    def __init__(self, command, stdin, *args, **kwargs):
        self.command = command
        self.stdin = FakePipe() if (stdin is subprocess.PIPE) else stdin
        self.args = args
        self.kwargs = kwargs
        self.returncode = None
        self.open_procs.append(self)

    def poll(self):
        if self.stdin.closed:
            self.returncode = self.end_returncode
        return self.returncode


class FakeProcessWriter(object):
    def __init__(self, returncode, success=None):
        self.returncode = returncode
        self._success = (returncode == 0) if (success is None) else success

    def poll(self):
        return self.returncode

    def success(self):
        return self._success
