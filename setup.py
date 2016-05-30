#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys

import setuptools
import xargs_groupby

setup = {
    'name': 'xargs_groupby',
    'version': xargs_groupby.VERSION,
    'py_modules': ['xargs_groupby'],
    'test_suite': 'tests',
}

if sys.version_info < (3,):
    setup['tests_require'] = ['mock']

setuptools.setup(**setup)
