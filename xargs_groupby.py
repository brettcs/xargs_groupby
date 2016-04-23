#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import ast
import imp
import io
import os
import sys
import types
import warnings

class NameChecker(ast.NodeVisitor):
    def __init__(self, names):
        self.names = names

    def check(self, parsed_ast):
        self._used_names = set()
        self._unknown_names = set()
        self.visit(parsed_ast)
        used_names = self._used_names
        unknown_names = self._unknown_names
        del self._used_names, self._unknown_names
        return used_names, unknown_names

    def visit_Name(self, node):
        if node.id in self.names:
            record_set = self._used_names
        else:
            record_set = self._unknown_names
        record_set.add(node.id)


class UserExpression(object):
    SOURCE = '<user expression>'

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
            parsed_ast = ast.parse(expr_s, self.SOURCE, 'eval')
        except SyntaxError as error:
            raise ValueError(*error.args)
        name_checker = NameChecker(self._EVAL_VARS)
        _, unused_names = name_checker.check(parsed_ast)
        unused_names_count = len(unused_names)
        if unused_names_count > 1:
            raise ValueError("names {} are not defined".format(
                ", ".join(repr(name) for name in unused_names)))
        elif unused_names_count == 1:
            unused_name = unused_names.pop()
            name_error = ValueError("name {!r} is not defined".format(unused_name))
            # If the name refers to a module that isn't in _EVAL_VARS,
            # always treat it as an error, rather than overloading the name.
            try:
                module_file = imp.find_module(unused_name)[0]
            except ImportError:
                pass
            else:
                if module_file is not None:
                    module_file.close()
                raise name_error
            # Ensure the unused name is the argument of a callable.
            # If this expression isn't callable, wrap it in a lambda.
            try:
                arg_node = parsed_ast.body.args.args[0]
            except AttributeError:
                parsed_ast = ast.parse(
                    'lambda {}: {}'.format(unused_name, expr_s),
                    self.SOURCE, 'eval')
            except IndexError:
                raise ValueError("callable expression accepts no argument")
            else:
                try:
                    arg_name = arg_node.arg
                except AttributeError:
                    arg_name = arg_node.id
                if unused_name != arg_name:
                    raise name_error
        expr_code = compile(parsed_ast, self.SOURCE, 'eval')
        try:
            self.func = eval(expr_code, self._EVAL_VARS)
        except AttributeError as error:
            raise ValueError(*error.args)
        if not callable(self.func):
            raise ValueError("{!r} expression is not callable".
                             format(type(self.func)))

    def __call__(self, arg):
        with warnings.catch_warnings():
            try:
                warnings.filterwarnings('ignore', category=ResourceWarning)
            except NameError:
                pass
            return self.func(arg)
