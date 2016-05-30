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
