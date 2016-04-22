#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import types

class UserExpression(object):
    _VARS = __builtins__.copy()
    _VARS['os'] = types.ModuleType(str('os'))
    _VARS['os'].path = os.path

    def __init__(self, expr_s):
        try:
            self.expr = eval(expr_s, self._VARS)
        except SyntaxError as error:
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
        value = self.expr(arg)
        while callable(value):
            value = value()
        return value
