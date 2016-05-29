#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import ast
import collections
import imp
import io
import itertools
import locale
import operator
import os
import select
import subprocess
import sys
import types
import warnings

try:
    unicode
except NameError:
    unicode = str

ENCODING = locale.getpreferredencoding()

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


class GroupCommand(object):
    def __init__(self, command, key_string):
        self.template = list(command)
        self.key_string = key_string

    def command(self, group_key):
        if self.key_string is None:
            return list(self.template)
        else:
            return list(arg.replace(self.key_string, group_key)
                        for arg in self.template)


class XargsCommand(object):
    def __init__(self, xargs_base, group_cmd):
        self.xargs_base = list(xargs_base)
        self.group_cmd = group_cmd
        self.switches = {'--max-procs': '1'}

    def _iter_switches(self):
        for key in self.switches:
            yield key
            yield self.switches[key]

    def command(self, group_key):
        return list(itertools.chain(self.xargs_base,
                                    self._iter_switches(),
                                    self.group_cmd.command(group_key)))

    def set_parallel(self, cores_count, groups_count):
        if groups_count > 0:
            max_procs = max(1, cores_count // groups_count)
            self.switches['--max-procs'] = unicode(max_procs)


class ProcessWriter(object):
    Popen = subprocess.Popen

    def __init__(self, cmd, input_seq, encoding=ENCODING):
        self.proc = self.Popen(cmd, stdin=subprocess.PIPE)
        self.input_seq = iter(input_seq)
        self.encoding = encoding
        self.returncode = None
        self.write_error = None
        self.write_buffer = bytearray()
        if not self._fill_buffer():
            self.proc.stdin.close()

    def _fill_buffer(self):
        try:
            next_s = next(self.input_seq) + '\0'
        except StopIteration:
            return False
        else:
            self.write_buffer.extend(next_s.encode(self.encoding))
            return True

    def write(self, bytecount):
        while (len(self.write_buffer) < bytecount) and self._fill_buffer():
            # _fill_buffer made progress toward the goal if it returned True.
            pass
        # We expect that the amount of buffer overshoot is small relative to
        # bytecount in the general case, so this should be a reasonably
        # efficient implementation.
        next_buffer = self.write_buffer[bytecount:]
        del self.write_buffer[bytecount:]
        try:
            self.proc.stdin.write(self.write_buffer)
        except EnvironmentError as error:
            self.write_error = error
        self.write_buffer = next_buffer
        if self.write_error or not (self.write_buffer or self._fill_buffer()):
            self.proc.stdin.close()

    def done_writing(self):
        return self.proc.stdin.closed

    def poll(self):
        self.returncode = self.proc.poll()
        return self.returncode

    def success(self):
        return (self.write_error is None) and (self.poll() == 0)

    def fileno(self):
        return self.proc.stdin.fileno()


class MultiProcessWriter(object):
    Poll = select.poll
    PIPE_BUF = select.PIPE_BUF

    def __init__(self):
        self.procs = {}
        self.poller = self.Poll()

    def add(self, proc_writer):
        if not proc_writer.done_writing():
            fd = proc_writer.fileno()
            self.poller.register(fd, select.POLLOUT)
            self.procs[fd] = proc_writer

    def write_ready(self, timeout=None):
        if not self.procs:
            return
        for fd, _ in self.poller.poll(timeout):
            proc = self.procs[fd]
            proc.write(self.PIPE_BUF)
            if proc.done_writing():
                self.poller.unregister(fd)
                del self.procs[fd]

    def writing_count(self):
        return len(self.procs)


class ProcessPipeline(object):
    ProcessWriter = ProcessWriter

    def __init__(self, proc_sources, encoding=ENCODING):
        self.proc_sources = iter(proc_sources)
        self.encoding = encoding
        self.last_proc = None
        self._success = None

    def next_proc(self):
        if self.success() is not None:
            raise StopIteration
        if self.last_proc is not None:
            proc_success = self.last_proc.success()
            if not proc_success:
                self._success = proc_success
                raise StopIteration
        try:
            cmd, input_seq = next(self.proc_sources)
        except StopIteration:
            self._success = True
            raise
        self.last_proc = self.ProcessWriter(cmd, input_seq, self.encoding)
        return self.last_proc

    def success(self):
        return self._success


class PipelineRunner(object):
    MultiProcessWriter = MultiProcessWriter

    def __init__(self, max_procs=1):
        self.multi_writer = self.MultiProcessWriter()
        self.max_procs = max_procs
        self._run_count = 0
        self._failures_count = 0

    def run(self, pipelines):
        pipelines_to_run = iter(pipelines)
        running_pipelines = set()
        while True:
            self._start_pipelines(pipelines_to_run, running_pipelines)
            if not running_pipelines:
                break
            self._write_ready(running_pipelines)
            self._advance_pipelines(running_pipelines)

    def _start_pipelines(self, pipelines_to_run, running_pipelines):
        while len(running_pipelines) < self.max_procs:
            try:
                next_pipeline = next(pipelines_to_run)
            except StopIteration:
                break
            else:
                running_pipelines.add(next_pipeline)
                self.multi_writer.add(next_pipeline.next_proc())
                self._run_count += 1

    def _write_ready(self, running_pipelines):
        writing_count = self.multi_writer.writing_count()
        if writing_count == 0:
            return
        elif writing_count == len(running_pipelines):
            timeout = None
        else:
            timeout = 0.1
        self.multi_writer.write_ready(timeout)

    def _advance_pipelines(self, running_pipelines):
        done_pipelines = set()
        for pipeline in running_pipelines:
            proc_success = pipeline.last_proc.poll()
            if proc_success is None:
                continue
            try:
                new_proc = pipeline.next_proc()
            except StopIteration:
                if not pipeline.success():
                    self._failures_count += 1
                done_pipelines.add(pipeline)
            else:
                self.multi_writer.add(new_proc)
        running_pipelines.difference_update(done_pipelines)

    def run_count(self):
        return self._run_count

    def failures_count(self):
        return self._failures_count


def group_args(args_iter, key_func):
    groups = collections.defaultdict(list)
    for argument in args_iter:
        groups[key_func(argument)].append(argument)
    return groups
