#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import random
import sys
import unittest

from argparse import Namespace

import xargs_groupby as xg
from . import mock, NoopMock

class ProgramTestCase(unittest.TestCase):
    def program_from_args(self, **opts):
        # args_dict should represent the default namespace returned by
        # ArgumentParser.parse_args.
        args_dict = {
            'arg_file': None,
            'delimiter': None,
            'encoding': 'utf-8',
            'eof_str': None,
            'group_str': None,
            'max_procs': 1,
            'preexec': None,
            'group_code': '_.lower()',
            'command': ['echo'],
        }
        args_dict.update(opts)
        self.xg_opts = Namespace(**args_dict)
        self.xargs_opts = Namespace()
        return xg.Program(self.xg_opts, self.xargs_opts)

    def tearDown(self):
        for name in ['xg_opts', 'xargs_opts']:
            try:
                delattr(self, name)
            except AttributeError:
                pass

    def test_group_function(self, code_s='_.lower()'):
        program = self.program_from_args(group_code=code_s)
        code_builder = mock.Mock(name='UserExpression')
        group_func = program.group_function(code_builder)
        code_builder.assert_called_with(code_s)
        self.assertIs(group_func, code_builder())

    def test_input_file(self, arg_file=None, encoding='utf-8'):
        program = self.program_from_args(arg_file=arg_file, encoding=encoding)
        open_func = mock.Mock(name='io.open')
        input_file = program.input_file(open_func)
        input_source = sys.stdin.fileno() if (arg_file is None) else arg_file
        open_func.assert_called_with(input_source, encoding=encoding)
        self.assertIs(input_file, open_func())

    def test_input_file_stdin_encoding(self):
        self.test_input_file(encoding='latin-1')

    def test_input_file_argument(self):
        self.test_input_file(arg_file='/test/file')

    def test_input_file_encoding(self):
        self.test_input_file(arg_file='/test/file', encoding='latin-1')

    def test_input_parser(self, delimiter=None, eof_str=None):
        parsers = (mock.Mock('shlexer'), mock.Mock('splitter'))
        input_file = NoopMock(name='input_file')
        program = self.program_from_args(delimiter=delimiter, eof_str=eof_str)
        actual_parser = program.input_parser(input_file, *parsers)
        if delimiter is None:
            expected_parser = parsers[0]
            expected_calls = [mock.call(input_file, eof_str)]
        else:
            expected_parser = parsers[1]
            expected_calls = [mock.call(input_file, delimiter)]
        expected_parser.assert_has_calls(expected_calls)
        self.assertIs(actual_parser, expected_parser())

    def test_input_parser_delimited(self):
        self.test_input_parser(delimiter='\0')

    def test_input_parser_eof_str(self):
        self.test_input_parser(eof_str='EOF')

    def test_input_parser_useless_eof_str(self):
        self.test_input_parser(delimiter='\t', eof_str='UNUSED')

    def test_prep_input(self, delimiter=None, encoding='utf-8'):
        program = self.program_from_args(delimiter=delimiter, encoding=encoding)
        group_func = NoopMock(name='group_func')
        input_source = NoopMock(name='input_source')
        prepper_class = mock.Mock(name='InputPrepper')
        prepper = program.prep_input(group_func, input_source, prepper_class)
        prepper_class.assert_called_with(group_func, delimiter, encoding)
        prepper_class().add.assert_called_with(input_source)
        self.assertIs(prepper, prepper_class())

    def test_command_template(self, group_str=None, preexec=None, command=['echo']):
        group_class = mock.Mock(name='GroupCommand')
        xargs_class = mock.Mock(name='XargsCommand')
        program = self.program_from_args(preexec=preexec, group_str=group_str, command=command[:])
        templates = program.command_templates(group_class, xargs_class)
        expected_group_calls = []
        if preexec is not None:
            expected_group_calls.append(mock.call(preexec, group_str))
        expected_group_calls.append(mock.call(command, group_str))
        self.assertEqual(len(templates), len(expected_group_calls))
        group_class.assert_has_calls(expected_group_calls)
        self.assertEqual(xargs_class.call_count, 1)
        xargs_base, group_cmd = xargs_class.call_args[0]
        self.assertEqual(xargs_base[0], 'xargs')
        self.assertIs(group_cmd, group_class())
        xargs_class().set_options.assert_called_with(self.xargs_opts)

    def test_command_template_preexec(self):
        self.test_command_template(preexec=['mkdir'])

    def test_command_template_group_str(self):
        self.test_command_template(group_str='{G}')

    def test_command_template_preexec_group_str(self):
        self.test_command_template(group_str='_G_', preexec=['test', '-d'])

    def test_pipeline_sources(self, pre_template=[]):
        input_prepper = mock.MagicMock(name='input_prepper')
        xargs_cmd = mock.Mock(name='xargs_command')
        group_key = NoopMock(name='group_key')
        templates = pre_template + [xargs_cmd]
        program = self.program_from_args()
        sources = list(program.pipeline_sources(templates, input_prepper, group_key))
        self.assertEqual(len(sources), len(templates))
        expected_delimiter = input_prepper.delimiter(group_key)
        for cmd_src, (cmdlist, input_seq, sep_byte) in zip(templates, sources):
            cmd_src.command.assert_called_with(group_key)
            self.assertIs(cmdlist, cmd_src.command())
            if cmd_src is xargs_cmd:
                self.assertIs(input_seq, input_prepper[group_key])
                self.assertIs(sep_byte, expected_delimiter)
            else:
                with self.assertRaises(StopIteration):
                    next(iter(input_seq))
                self.assertIsNone(sep_byte)
        xargs_cmd.set_delimiter.assert_called_with(expected_delimiter)

    def test_pipeline_sources_with_preexec(self):
        self.test_pipeline_sources([mock.Mock(name='group_command')])

    def assertMapsToKeys(self, seq, key_count, expected_item):
        seq_len = 0
        for seq_len, item in enumerate(seq, 1):
            self.assertIs(item, expected_item)
        self.assertEqual(seq_len, key_count)

    def test_iter_pipelines(self, *keys):
        key_count = len(keys)
        input_prepper = mock.MagicMock(name='input_prepper')
        input_prepper.__iter__.return_value = iter(keys)
        input_prepper.__len__.return_value = key_count
        templates = mock.MagicMock(name='templates')
        source_func = mock.Mock(name='pipeline_sources')
        pipeline_class = mock.Mock(name='ProcessPipeline')
        program = self.program_from_args()
        pipelines = list(program.iter_pipelines(
            templates, input_prepper, source_func, pipeline_class))
        source_func.assert_has_calls(
            [mock.call(templates, input_prepper, key) for key in keys],
            any_order=True)
        self.assertMapsToKeys(
            (call[0][0] for call in pipeline_class.call_args_list),
            key_count, source_func())
        self.assertMapsToKeys(pipelines, key_count, pipeline_class())

    def test_iter_one_pipeline(self):
        self.test_iter_pipelines('a')

    def test_iter_many_pipelines(self):
        self.test_iter_pipelines('e', 'i', 'o', 'u')

    def test_iter_pipelines_sets_parallel(self):
        cores_count = random.randint(1, 99)
        groups_count = random.randint(101, 199)
        input_prepper = mock.MagicMock(name='input_prepper')
        input_prepper.__iter__.return_value = 'abc'
        input_prepper.__len__.return_value = groups_count
        templates = mock.MagicMock(name='templates')
        source_func = mock.Mock(name='pipeline_sources')
        pipeline_class = mock.Mock(name='ProcessPipeline')
        program = self.program_from_args(max_procs=cores_count)
        next(program.iter_pipelines(templates, input_prepper, source_func, pipeline_class))
        templates[-1].set_parallel.assert_called_with(cores_count, groups_count)

    def run_main(self, run_count=8, failures_count=0, **opts):
        pipeline_runner = mock.Mock(name='PiplineRunner')
        pipeline_runner().run_count.return_value = max(run_count, failures_count)
        pipeline_runner().failures_count.return_value = failures_count
        program = self.program_from_args(**opts)
        prog_mock = mock.Mock(name='program', spec=program)
        prog_mock.args = program.args
        exitcode = xg.Program.main(prog_mock, pipeline_runner)
        return pipeline_runner, prog_mock, exitcode

    def test_main_connections(self):
        cores_count = random.randint(1, 99)
        pipeline_runner, program, _ = self.run_main(max_procs=cores_count)
        program.group_function.assert_called_with()
        program.input_file.assert_called_with()
        program.input_parser.assert_called_with(program.input_file())
        program.prep_input.assert_called_with(
            program.group_function(), program.input_parser())
        program.command_templates.assert_called_with()
        program.iter_pipelines.assert_called_with(
            program.command_templates(), program.prep_input())
        pipeline_runner.assert_called_with(cores_count)
        pipeline_runner().run.assert_called_with(program.iter_pipelines())

    def test_main_exitcode(self, run_count=8, failures_count=0, expected=0):
        _, _, exitcode = self.run_main(run_count, failures_count)
        self.assertEqual(exitcode, expected)

    def test_main_exitcode_with_some_failures(self):
        self.test_main_exitcode(8, 4, 14)

    def test_main_exitcode_with_all_failures(self):
        self.test_main_exitcode(9, 9, 19)

    def test_main_exitcode_with_many_failures(self):
        self.test_main_exitcode(1000, 999, 99)

    def test_main_exitcode_none_run(self):
        self.test_main_exitcode(0, 0, 0)

    def test_from_arglist(self):
        parser = mock.Mock(name='ArgumentParser')
        args = NoopMock(name='args')
        xargs_opts = NoopMock(name='xargs_opts')
        parser().parse_args.return_value = (args, xargs_opts)
        prog_mock = mock.Mock(name='Program', spec=xg.Program)
        program = xg.Program.from_arglist.__func__(prog_mock, ['_', 'echo'], parser)
        prog_mock.assert_called_with(args, xargs_opts)
        self.assertIs(program, prog_mock())
