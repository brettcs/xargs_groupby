#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import sys
import types
import warnings

class UserExpression(object):
    _VARS = __builtins__.copy()

    def _open(path, mode='r', *args, **kwargs):
        if (not mode.startswith('r')) or ('+' in mode):
            raise ValueError('invalid mode: {!r}'.format(mode))
        return io.open(path, mode, *args, **kwargs)
    _VARS['open'] = _open
    del _open

    _VARS['os'] = types.ModuleType(str('os'))
    _VARS['os'].path = os.path

    def __init__(self, expr_s):
        try:
            self.expr = eval(expr_s, self._VARS)
        except (AttributeError, SyntaxError) as error:
            raise ValueError(*error.args)
        except NameError as error:
            if error.args == ("name '_' is not defined",):
                return self.__init__('lambda _: ' + expr_s)
            else:
                raise ValueError(*error.args)
        if not callable(self.expr):
            raise ValueError("{!r} expression is not callable".
                             format(type(self.expr)))

    def __call__(self, arg):
        with warnings.catch_warnings():
            try:
                warnings.filterwarnings('ignore', category=ResourceWarning)
            except NameError:
                pass
            value = self.expr(arg)
            while callable(value):
                value = value()
        return value
