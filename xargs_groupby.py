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
    _EVAL_VARS = {key: __builtins__[key] for key in __builtins__
                  if not (key.startswith('_') or (key in set(
                          ['eval', 'exec', 'exit', 'open', 'quit'])))}
    _EVAL_VARS['__builtins__'] = _EVAL_VARS

    def _open(path, mode='r', *args, **kwargs):
        if not all(c in set('rbtU') for c in mode):
            raise ValueError('invalid mode: {!r}'.format(mode))
        return io.open(path, mode, *args, **kwargs)
    _EVAL_VARS['open'] = _open

    _EVAL_VARS['os'] = types.ModuleType(os.__name__)
    _EVAL_VARS['os'].path = os.path

    del _open

    def __init__(self, expr_s):
        try:
            self.expr = eval(expr_s, self._EVAL_VARS)
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
        return value
