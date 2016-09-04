#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

VERSION = "0.1.dev1"
COPYRIGHT = "Copyright © 2016 Brett Smith <brettcsmith@brettcsmith.org>"
LICENSE = """This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>."""

import argparse
import ast
import collections
import functools
import imp
import importlib
import io
import itertools
import locale
import os
import re
import select
import shlex
import subprocess
import sys
import warnings

# Since this script stands alone, there's no need for relative imports.
# Remove the script's directory from sys.path to avoid surprising or
# dangerous behavior when importing for UserExpressions.
del sys.path[0]

try:
    unicode
except NameError:
    unicode = str

ENCODING = locale.getpreferredencoding()
PY_MAJVER = sys.version_info.major

class UserInputError(ValueError):
    pass


class UserArgumentsError(UserInputError):
    pass


class UserExpressionError(UserInputError):
    pass


class InputShlexer(object):
    SHLEX_CODING = 'iso-8859-1'

    class _WordChars(object):
        def __init__(self, exclude_chars):
            self.exclude_chars = frozenset(exclude_chars)

        def __contains__(self, char):
            return char not in self.exclude_chars


    def __init__(self, in_stream, eof_str):
        self.in_stream = in_stream
        self.eof_line = None if (eof_str is None) else (eof_str + '\n')
        self.shlex = shlex.shlex('', getattr(in_stream, 'name', None), posix=True)
        self.shlex.commenters = ''
        self.shlex.whitespace_split = True
        exclude_chars = [getattr(self.shlex, name) for name in
                         ['whitespace', 'quotes', 'escape']]
        chars_type = type(exclude_chars[0])
        exclude_chars = chars_type().join(exclude_chars)
        if not issubclass(chars_type, unicode):
            exclude_chars = exclude_chars.decode(self.SHLEX_CODING)
        self.shlex.wordchars = self._WordChars(exclude_chars)

    @staticmethod
    def _is_backslash(char):
        return char == '\\'

    def _line_tokens(self, line):
        trailing_backslash_count = sum(
            1 for _ in itertools.takewhile(self._is_backslash, reversed(line)))
        if trailing_backslash_count % 2:
            line = line[:-1]
        with io.StringIO(line) as line_stream:
            self.shlex.state = ' '
            self.shlex.token = ''
            self.shlex.instream = line_stream
            tokens = iter(self.shlex)
            while True:
                try:
                    yield next(tokens)
                except (StopIteration, ValueError):
                    break

    def __iter__(self):
        pre_lines = []
        for line in self.in_stream:
            if line.endswith('\\\n'):
                pre_lines.append(line)
                continue
            elif pre_lines:
                pre_lines.append(line)
                line = ''.join(pre_lines)
                pre_lines = []
            if line == self.eof_line:
                break
            for token in self._line_tokens(line):
                yield token
        for token in self._line_tokens(''.join(pre_lines)):
            yield token


class InputSplitter(object):
    def __init__(self, in_stream, delimiter):
        self.in_stream = in_stream
        self.delimiter = delimiter

    def __iter__(self):
        delimiter_len = len(self.delimiter)
        pre_strings = []
        for hunk in iter(lambda: self.in_stream.read(4096), ''):
            try:
                split_index = hunk.index(self.delimiter)
            except ValueError:
                pre_strings.append(hunk)
                continue
            yield ''.join(pre_strings) + hunk[:split_index]
            pre_strings = []
            while True:
                start_index = split_index + delimiter_len
                try:
                    split_index = hunk.index(self.delimiter, start_index)
                except ValueError:
                    if start_index < len(hunk):
                        pre_strings.append(hunk[start_index:])
                    break
                yield hunk[start_index:split_index]
        if pre_strings:
            yield ''.join(pre_strings)


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


MODULE_ALL = object()
class UserExpression(object):
    SOURCE = '<user expression>'
    MODULE_WHITELIST = {
        'binascii': MODULE_ALL,
        'bz2': MODULE_ALL,
        'codecs': MODULE_ALL,
        'collections': MODULE_ALL,
        'colorsys': MODULE_ALL,
        'csv': ['reader', 'DictReader', 'Sniffer'],
        'datetime': MODULE_ALL,
        'decimal': MODULE_ALL,
        'difflib': MODULE_ALL,
        'filecmp': MODULE_ALL,
        'fnmatch': MODULE_ALL,
        'functools': MODULE_ALL,
        'gzip': MODULE_ALL,
        'hashlib': MODULE_ALL,
        'imghdr': ['what'],
        'io': ['BytesIO', 'StringIO', 'SEEK_SET', 'SEEK_CUR', 'SEEK_END', 'open'],
        'itertools': MODULE_ALL,
        'json': ['load', 'loads'],
        'keyword': MODULE_ALL,
        'locale': [name for name in dir(locale) if not name.endswith('setlocale')],
        'math': MODULE_ALL,
        'mimetypes': MODULE_ALL,
        'operator': MODULE_ALL,
        'os': ['access', 'path', 'fstat', 'fstatvfs', 'linesep', 'major',
               'minor', 'stat', 'statvfs', 'SEEK_SET', 'SEEK_CUR', 'SEEK_END'],
        'random': MODULE_ALL,
        're': MODULE_ALL,
        'shlex': ['split'],
        'string': MODULE_ALL,
        'struct': MODULE_ALL,
        'tarfile': ['open', 'is_tarfile', 'TarFile'],
        'time': MODULE_ALL,
        'unicodedata': MODULE_ALL,
        'uu': ['decode'],
        'zipfile': MODULE_ALL,
        'zlib': MODULE_ALL,
    }

    def _build_whitelisted_module(module_name, names_whitelist):
        src_module = importlib.import_module(module_name)
        if names_whitelist is MODULE_ALL:
            try:
                names_whitelist = src_module.__all__
            except AttributeError:
                names_whitelist = (name for name in dir(src_module)
                                   if not name.startswith('_'))
        new_module = imp.new_module(module_name)
        for name in names_whitelist:
            setattr(new_module, name, getattr(src_module, name))
        return new_module

    def _load_whitelisted_module(self, module_name):
        names_whitelist = self.MODULE_WHITELIST[module_name]
        new_module = self._build_whitelisted_module(module_name, names_whitelist)
        try:
            load_callback = getattr(self, '_{}_module_loaded'.format(module_name))
        except AttributeError:
            pass
        else:
            load_callback(new_module)
        self._EVAL_VARS[module_name] = new_module

    def _check_open_mode(argname='mode', argindex=1, allowed='rbtU', default='r'):
        def check_open_mode_decorator(orig_func):
            @functools.wraps(orig_func)
            def check_open_mode(*args, **kwargs):
                try:
                    mode = kwargs[argname]
                except KeyError:
                    try:
                        mode = args[argindex]
                    except IndexError:
                        mode = default
                if not all(c in set(allowed) for c in mode):
                    raise ValueError('invalid mode: {!r}'.format(mode))
                return orig_func(*args, **kwargs)
            return check_open_mode
        return check_open_mode_decorator

    def _module_with_openers_loaded(self, new_module, *opener_names):
        if not opener_names:
            opener_names = ('open',)
        for opener_name in opener_names:
            opener = getattr(new_module, opener_name)
            setattr(new_module, opener_name, self._check_open_mode()(opener))

    _codecs_module_loaded = _module_with_openers_loaded
    _io_module_loaded = _module_with_openers_loaded

    def _bz2_module_loaded(self, bz2_module):
        self._module_with_openers_loaded(bz2_module, 'BZ2File')

    def _gzip_module_loaded(self, gzip_module):
        self._module_with_openers_loaded(gzip_module, 'GzipFile', 'open')

    def _tarfile_module_loaded(self, tar_module):
        for attr_name in dir(tar_module.TarFile):
            if attr_name.startswith(('add', 'extract')):
                delattr(tar_module.TarFile, attr_name)
        check_tar_mode = self._check_open_mode(allowed='r:|gbz2')
        tar_module.open = check_tar_mode(tar_module.open)
        tar_module.TarFile = check_tar_mode(tar_module.TarFile)

    def _time_module_loaded(self, time_module):
        del time_module.sleep, time_module.tzset

    def _zipfile_module_loaded(self, zip_module):
        for klass in [zip_module.ZipFile, zip_module.PyZipFile]:
            for attr_name in dir(klass):
                if attr_name.startswith(('extract', 'setpassword', 'write')):
                    delattr(klass, attr_name)
        check_zip_mode = self._check_open_mode(allowed='r')
        zip_module.ZipFile = check_zip_mode(zip_module.ZipFile)
        zip_module.PyZipFile = check_zip_mode(zip_module.PyZipFile)

    _builtins_modname = '__builtin__' if (PY_MAJVER < 3) else 'builtins'
    _builtins_module = importlib.import_module(_builtins_modname)
    _builtins_whitelist = [name for name in dir(_builtins_module)
                           if not (name.startswith('_') or (name in set(
                                   ['eval', 'exec', 'exit', 'file', 'open', 'quit'])))]
    _builtins = _build_whitelisted_module(_builtins_modname, _builtins_whitelist)
    _builtins.open = _check_open_mode()(io.open)
    _EVAL_VARS = vars(_builtins)
    _EVAL_VARS[_builtins_modname] = _builtins
    _EVAL_VARS['__builtins__'] = _builtins
    del _builtins, _builtins_modname, _builtins_module, _builtins_whitelist

    def __init__(self, expr_s):
        try:
            parsed_ast = ast.parse(expr_s, self.SOURCE, 'eval')
        except SyntaxError as error:
            raise UserExpressionError(*error.args)
        name_checker = NameChecker(self._EVAL_VARS)
        _, unloaded_names = name_checker.check(parsed_ast)
        unknown_names = set()
        for name in unloaded_names:
            try:
                self._load_whitelisted_module(name)
            except KeyError:
                unknown_names.add(name)
        unknown_names_count = len(unknown_names)
        if unknown_names_count > 1:
            raise UserExpressionError("names {} are not defined".format(
                ", ".join(repr(name) for name in unknown_names)))
        elif unknown_names_count == 1:
            unknown_name = unknown_names.pop()
            name_error = UserExpressionError("name {!r} is not defined".format(unknown_name))
            # If the name refers to a module that isn't in _EVAL_VARS,
            # always treat it as an error, rather than overloading the name.
            try:
                module_file = imp.find_module(unknown_name)[0]
            except ImportError:
                pass
            else:
                if module_file is not None:
                    module_file.close()
                raise name_error
            # Ensure the unknown name is the argument of a callable.
            # If this expression isn't callable, wrap it in a lambda.
            try:
                arg_node = parsed_ast.body.args.args[0]
            except AttributeError:
                parsed_ast = ast.parse(
                    'lambda {}: {}'.format(unknown_name, expr_s),
                    self.SOURCE, 'eval')
            except IndexError:
                raise UserExpressionError("callable expression accepts no argument")
            else:
                try:
                    arg_name = arg_node.arg
                except AttributeError:
                    arg_name = arg_node.id
                if unknown_name != arg_name:
                    raise name_error
        expr_code = compile(parsed_ast, self.SOURCE, 'eval')
        try:
            self.func = eval(expr_code, self._EVAL_VARS)
        except AttributeError as error:
            raise UserExpressionError(*error.args)
        if not callable(self.func):
            raise UserExpressionError("{!r} expression is not callable".
                             format(type(self.func)))

    def __call__(self, arg):
        with warnings.catch_warnings():
            try:
                warnings.filterwarnings('ignore', category=ResourceWarning)
            except NameError:
                pass
            return self.func(arg)

    _build_whitelisted_module = staticmethod(_build_whitelisted_module)
    _check_open_mode = staticmethod(_check_open_mode)


class InputPrepper(object):
    NO_GROUP_KEY = object()

    class DelimiterFinder(object):
        def __init__(self):
            if PY_MAJVER < 3:
                self.eligible = set(chr(n) for n in xrange(256))
            else:
                self.eligible = set(bytes(range(256)))

        def exclude(self, bytes_arg):
            self.eligible.difference_update(bytes_arg)
            if not self.eligible:
                raise UserArgumentsError("group arguments use all bytes - no possible delimiter")

        def delimiter(self):
            return next(iter(self.eligible))


    def __init__(self, group_func, delimiter=None, encoding=ENCODING):
        self.group_func = group_func
        self.encoding = encoding
        try:
            delimiter_b = delimiter.encode(self.encoding)
        except (AttributeError, UnicodeEncodeError):
            delimiter_b = b''
        if len(delimiter_b) == 1:
            self._delimiter = delimiter_b[0]
        else:
            self._delimiter = None
            self._delimiter_finder = self.DelimiterFinder()
        self._groups = collections.defaultdict(list)

    def __iter__(self):
        return iter(self._groups)

    def __getitem__(self, key):
        return self._groups[key]

    def __len__(self):
        return len(self._groups)

    def add(self, arg_seq):
        for arg in arg_seq:
            key = self.group_func(arg)
            arg_bytes = arg.encode(self.encoding)
            self[key].append(arg_bytes)
            if self._delimiter is None:
                try:
                    self._delimiter_finder.exclude(arg_bytes)
                except UserArgumentsError:
                    self._groups_delimiter_finders = collections.defaultdict(self.DelimiterFinder)
                    for group_key in self:
                        for group_bytes in self[group_key]:
                            self._groups_delimiter_finders[group_key].exclude(group_bytes)
                    self._delimiter_finder = None
                except AttributeError:
                    self._groups_delimiter_finders[key].exclude(arg_bytes)

    def delimiter(self, group_key=NO_GROUP_KEY):
        if self._delimiter is not None:
            delimiter = self._delimiter
        elif self._delimiter_finder is not None:
            delimiter = self._delimiter_finder.delimiter()
        elif group_key is self.NO_GROUP_KEY:
            raise ValueError("no usable delimiter for all groups")
        else:
            delimiter = self._groups_delimiter_finders[group_key].delimiter()
        return delimiter


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

    def set_options(self, args):
        args_dict = vars(args)
        for key in args_dict:
            switch_name = '{}{}'.format(
                '-' if (len(key) == 1) else '--',
                key.replace('_', '-'))
            self.switches[switch_name] = args_dict[key]

    def _iter_switches(self):
        for key in self.switches:
            value = self.switches[key]
            if not value:
                continue
            elif value is True:
                yield key
            elif key.startswith('--'):
                yield '{}={}'.format(key, value)
            else:
                yield key + value

    def command(self, group_key):
        return list(itertools.chain(self.xargs_base,
                                    self._iter_switches(),
                                    self.group_cmd.command(group_key)))

    def set_parallel(self, cores_count, groups_count):
        if groups_count > 0:
            max_procs = max(1, cores_count // groups_count)
            self.switches['--max-procs'] = unicode(max_procs)

    def set_delimiter(self, byte):
        try:
            byte = ord(byte)
        except TypeError:  # A single byte is an int in Py3.
            pass
        self.switches['--delimiter'] = '\\{:03o}'.format(byte)


class ProcessWriter(object):
    Popen = subprocess.Popen

    def __init__(self, cmd, input_seq, sep_byte):
        self.proc = self.Popen(cmd, stdin=subprocess.PIPE)
        self.input_seq = iter(input_seq)
        self.sep_byte = sep_byte
        self.returncode = None
        self.write_error = None
        self.write_buffer = bytearray()
        if not self._fill_buffer():
            self.proc.stdin.close()

    def _fill_buffer(self):
        try:
            self.write_buffer.extend(next(self.input_seq))
        except StopIteration:
            return False
        else:
            if self.sep_byte is not None:
                self.write_buffer.append(self.sep_byte)
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
            cmd, input_seq, sep_byte = next(self.proc_sources)
        except StopIteration:
            self._success = True
            raise
        self.last_proc = self.ProcessWriter(cmd, input_seq, sep_byte)
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
        running_count = len(running_pipelines)
        writing_count = self.multi_writer.writing_count()
        if writing_count == 0:
            return
        elif writing_count < running_count:
            self.multi_writer.write_ready(0.1)
        else:
            while self.multi_writer.writing_count() >= running_count:
                self.multi_writer.write_ready()

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


class VersionAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print("{} {}".format(parser.prog, VERSION), COPYRIGHT, LICENSE,
              sep="\n\n")
        parser.exit(0)


class CommandAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string):
        parser.error("{} command must be specified as a list of arguments terminated with ';'".
                     format(option_string))


class ArgumentParser(argparse.ArgumentParser):
    ARGV_ENCODING = ENCODING

    def __init__(self):
        self.command_opts = []
        self.xargs_parser = argparse.ArgumentParser(prog='xargs', add_help=False)
        xargs_opts = self.xargs_parser.add_argument_group(
            "xargs options", "Switches passed directly to xargs calls")
        xargs_opts.add_argument(
            '--exit', '-x', action='store_true',
            help="Exit if a command exceeds --max-chars")
        xargs_opts.add_argument(
            '-I', '--replace-str', dest='I', metavar='STR',
            help="Replace this string in the command with arguments")
        # TODO: Support this if possible.
        # xargs_opts.add_argument(
        #     '--interactive', '-p', action='store_true',
        #     help="Prompt user before running commands")
        xargs_opts.add_argument(
            '--max-args', '-n', metavar='NUM',
            help="Maximum number of arguments per command line")
        xargs_opts.add_argument(
            '--max-chars', '-s', metavar='NUM',
            help="Maximum number of characters per command line")
        xargs_opts.add_argument(
            '--verbose', '-t', action='store_true',
            help="Write commands to stderr before executing")

        super(ArgumentParser, self).__init__(
            prog='xargs_groupby',
            parents=[self.xargs_parser],
        )
        self.add_argument(
            '--version', action=VersionAction, nargs=0,
            help="Display version and license information")
        self.add_argument(
            '--arg-file', '-a', metavar='FILE',
            help="Read arguments from file instead of stdin")
        self.add_argument(
            '--encoding', default=ENCODING,
            help="Encoding for all I/O (specify a name Python uses)")
        delim_group = self.add_mutually_exclusive_group()
        delim_group.add_argument(
            '--delimiter', '-d', metavar='STR',
            help="Separator string for arguments")
        delim_group.add_argument(
            '--eof-str', '-E', metavar='EOF',
            help="Stop reading input at a line with this string")
        delim_group.add_argument(
            '--null', '-0',
            dest='delimiter', action='store_const', const=r'\0',
            help="Use the null character as the delimiter")
        self.add_argument(
            '--group-str', '-G', metavar='STR',
            help="Replace this string in commands with the group key")
        self.add_argument(
            '--max-procs', '-P', metavar='NUM', type=int, default=1,
            help="Maximum number of processes to run at once")
        self.add_command_argument(
            '--preexec', '--pre',
            help="Command to run per group before the main command, terminated with ';'")
        self.add_argument(
            'group_code',
            help="Python expression or callable to group arguments")
        self.add_argument(
            'command', nargs=argparse.REMAINDER, metavar='command',
            help="Command to run per group, with the grouped arguments")

    def add_command_argument(self, *option_strings, **kwargs):
        self.command_opts.append(self.add_argument(
            *option_strings,
            nargs='+', metavar='COMMAND', action=CommandAction, **kwargs))
        return self.command_opts[-1]

    @staticmethod
    def _parse_escape(match):
        groups = match.groups()
        if groups[1]:
            return chr(int(groups[1], 8))
        elif groups[2]:
            return chr(int(groups[2], 16))
        else:
            return eval('u"\\{}"'.format(groups[0]), {})

    def _parse_escapes(self, delimiter_s):
        return re.subn(r'\\([abfnrtv]|([0-9]{1,3})|x([0-9a-fA-F]{1,2}))',
                       self._parse_escape, delimiter_s)[0]

    def parse_command_options(self, arglist, namespace):
        switch_dest_map = {switch: option.dest
                           for option in self.command_opts
                           for switch in option.option_strings}
        start_index = 0
        while True:
            try:
                switch = arglist[start_index]
            except IndexError:
                break
            if switch == '--':
                break
            try:
                dest = switch_dest_map[switch]
            except KeyError:
                start_index += 1
                continue
            try:
                end_index = arglist.index(';', start_index)
            except ValueError:
                self.error("{} command not terminated with ';'".format(switch))
            setattr(namespace, dest, arglist[start_index + 1:end_index])
            del arglist[start_index:end_index + 1]

    def parse_args(self, arglist, namespace=None):
        if PY_MAJVER < 3:
            arglist = [arg.decode(self.ARGV_ENCODING) for arg in arglist]
        else:
            arglist = list(arglist)
        if namespace is None:
            namespace = argparse.Namespace()
        self.parse_command_options(arglist, namespace)
        args = super(ArgumentParser, self).parse_args(arglist, namespace)
        xargs_opts = self.xargs_parser.parse_args([])
        for xargs_optname in vars(xargs_opts):
            setattr(xargs_opts, xargs_optname, getattr(args, xargs_optname))
            delattr(args, xargs_optname)
        if args.delimiter is not None:
            args.delimiter = self._parse_escapes(args.delimiter)
        return args, xargs_opts


class Program(object):
    def __init__(self, args, xargs_opts):
        self.args = args
        self.xargs_opts = xargs_opts

    @classmethod
    def from_arglist(cls, arglist, parser_class=ArgumentParser):
        parser = parser_class()
        args, xargs_opts = parser.parse_args(arglist)
        return cls(args, xargs_opts)

    def group_function(self, constructor=UserExpression):
        return constructor(self.args.group_code)

    def input_file(self, open_func=io.open):
        source = sys.stdin.fileno() if (self.args.arg_file is None) else self.args.arg_file
        return open_func(source, encoding=self.args.encoding)

    def input_parser(self, input_file, shlexer=InputShlexer, splitter=InputSplitter):
        if self.args.delimiter is None:
            return shlexer(input_file, self.args.eof_str)
        else:
            return splitter(input_file, self.args.delimiter)

    def prep_input(self, group_func, input_seq, new_prepper=InputPrepper):
        prepper = new_prepper(group_func, self.args.delimiter, self.args.encoding)
        prepper.add(input_seq)
        return prepper

    def command_templates(self, group_cmd=GroupCommand, xargs_cmd=XargsCommand):
        templates = []
        if self.args.preexec is not None:
            templates.append(group_cmd(self.args.preexec, self.args.group_str))
        xargs_subcmd = group_cmd(self.args.command, self.args.group_str)
        xargs_template = xargs_cmd(['xargs'], xargs_subcmd)
        xargs_template.set_options(self.xargs_opts)
        templates.append(xargs_template)
        return templates

    def pipeline_sources(self, cmd_templates, input_prepper, group_key):
        last_index = len(cmd_templates) - 1
        for index, cmd_src in enumerate(cmd_templates):
            if index == last_index:
                input_seq = input_prepper[group_key]
                delimiter = input_prepper.delimiter(group_key)
                cmd_src.set_delimiter(delimiter)
            else:
                input_seq = ()
                delimiter = None
            yield cmd_src.command(group_key), input_seq, delimiter

    def iter_pipelines(self, cmd_templates, input_prepper,
                       source_func=None, pipeline_class=ProcessPipeline):
        if source_func is None:
            source_func = self.pipeline_sources
        cmd_templates[-1].set_parallel(self.args.max_procs, len(input_prepper))
        for group_key in input_prepper:
            yield pipeline_class(source_func(cmd_templates, input_prepper, group_key))

    def main(self, runner_class=PipelineRunner):
        group_func = self.group_function()
        input_file = self.input_file()
        parser = self.input_parser(input_file)
        input_prepper = self.prep_input(group_func, parser)
        cmd_templates = self.command_templates()
        pipelines_src = self.iter_pipelines(cmd_templates, input_prepper)
        pipeline_runner = runner_class(self.args.max_procs)
        pipeline_runner.run(pipelines_src)
        failures_count = pipeline_runner.failures_count()
        if not failures_count:
            exitcode = 0
        elif failures_count == pipeline_runner.run_count():
            exitcode = 100
        else:
            exitcode = min(10 + failures_count, 99)
        return exitcode


def main(arglist, program_class=Program):
    program = program_class.from_arglist(arglist)
    return program.main()

if __name__ == '__main__':
    exit(main(sys.argv[1:]))
