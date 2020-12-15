from jinja2.ext import Extension
from textwrap import dedent
from io import StringIO
import sys
import re
import ctypes
from jinja2 import nodes, Environment
import contextlib

var_name_regex = re.compile(r"l_(\d+)_(.+)")
#
# From https://stackoverflow.com/a/55545295
class PythonExtension(Extension):
    # a set of names that trigger the extension.
    tags = {'py'}

    def __init__(self, environment: Environment):
        super().__init__(environment)

    def parse(self, parser):
        """
        Parse {% py %} blocks in templates.

        Inserts an appropriate CallBlock into the parse tree where a {% py %}
        block is found, so it can be executed when the template is rendered.

        No actual code execution happens here.
        """
        lineno = next(parser.stream).lineno
        # Get contents until an {% endpy %} declaration
        # drop_needle drops the {% endpy %} at the end
        body = parser.parse_statements(['name:endpy'], drop_needle=True)

        # Insert a CallBlock that'll call our `_exec_python` method with
        # the body of {% py %} when rendering
        return nodes.CallBlock(self.call_method('_exec_python',
                                                [nodes.ContextReference(), nodes.Const(lineno), nodes.Const(parser.filename)]),
                               [], [], body).set_lineno(lineno)

    def _exec_python(self, ctx, lineno, filename, caller):
        """
        Execute python code from inside a parsed {% py %} block.

        Anything printed to stdout from the code in the block will be substituted
        in the template output. Locals & imports persist between different {% py %}
        blocks in the same template.
        """

        # Remove excess indentation
        code = dedent(caller())

        # Compile the code in this block so it can be executed.  We prepend
        # enough newlines that when the code is compiled, the line numbers of
        # the code *just* in this compiled block match the line numbers of the
        # code in the template itself. This provides us with useful error
        # messages.
        compiled_code = compile("\n" * (lineno - 1) + code, filename, "exec")

        # Capture stdout from this code
        sout = StringIO()
        with contextlib.redirect_stdout(sout):
            # Execute the code with the context parents as global and context vars and locals.
            exec(compiled_code, ctx.parent, ctx.vars)

        # Get a set of all names in the code.
        code_names = set(compiled_code.co_names)

        # The the frame in the jinja generated python code.
        caller_frame = sys._getframe(2)

        # Loop through all the locals.
        for local_var_name in caller_frame.f_locals:
            # Look for variables matching the template variable regex.
            match = re.match(var_name_regex, local_var_name)
            if match:
                # Get the variable name.
                var_name = match.group(2)

                # If the variable's name appears in the code and is in the locals.
                if (var_name in code_names) and (var_name in ctx.vars):
                    # Copy the value to the frame's locals.
                    caller_frame.f_locals[local_var_name] = ctx.vars[var_name]
                    # Do some ctypes vodo to make sure the frame locals are actually updated.
                    ctx.exported_vars.add(var_name)
                    ctypes.pythonapi.PyFrame_LocalsToFast(
                        ctypes.py_object(caller_frame),
                        ctypes.c_int(1))

        # Return the captured text.
        return sout.getvalue()
