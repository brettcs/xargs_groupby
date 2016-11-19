from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from . import mock

class NoopMock(mock.NonCallableMock):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('spec_set', object)
        return super(NoopMock, self).__init__(*args, **kwargs)
