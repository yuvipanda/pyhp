from jinja2.ext import Extension
from textwrap import dedent
from io import StringIO
import os
import sys
import re
import ctypes
from jinja2 import nodes, Environment
import contextlib

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

        # when a pyhp file is executed, the cwd should be set to the directory the
        # file is in. Similarly, when it tries to import python files, we should
        # look for it in the directory the pyhp file is in, *not* the directory
        # where the server started. So we save the current values and restore them
        # when done.
        # FIXME: If the {% py %} block calls os.chdir, that will not persist across
        # other blocks in the file. Same for `sys.path` manipulation
        cur_cwd = os.getcwd()
        cur_sys_path = sys.path

        # Capture stdout from this code block
        sout = StringIO()
        try:
            # FIXME: Make sure this isn't allowing for path traversal attacks?
            file_dir = os.path.dirname(os.path.abspath(filename))
            os.chdir(file_dir)
            new_sys_path = sys.path.copy()
            # The first entry in sys.path will always (haha) be the current directory.
            # By setting it to the directory of our pyhp file, our pyhp file can import
            # other .py files there!
            new_sys_path[0] = file_dir
            sys.path = new_sys_path
            with contextlib.redirect_stdout(sout):
                # Execute the code, with globals & locals from our jinja2 context
                exec(compiled_code, ctx.parent, ctx.vars)
        finally:
            sys.path = cur_sys_path
            os.chdir(cur_cwd)


        # WARNING: Everything from below here is Yuvi's guess of what's actually
        # happening.

        # jinja2 generates python code for each template, and executes it.
        # This generated python code calls this method to execute our
        # {% py %} block. Once the code block executes, the following must
        # be true:
        #
        # 1. Any new top-level locals defined in our code block must be available
        #    for any new jinja2 blocks
        # 2. Any pre-existing top level locals modified in our code block must have
        #    their new values reflected in any further jinja2 blocks
        #
        # This is pretty messy!
        #
        # We will:
        #
        # 1. Peer into this generated code that is calling us, by looking
        #    two frames in the call stack below our current frame. This is
        #    probably very brittle, but it works for now.
        # 2. Find local variables declared there, by making use of the fact that
        #    local variables are defined in the jinja2 generated code of the
        #    form `l_\d+_<variable-name>`. Again, very brittle.
        # 3. If our block overrides any of those top level locals, we explicitly
        #    *modify this generated code frame* so their values point to our
        #    new values. This is pretty nuts.

        # Get list of all local variable names defined in the top level in
        # our code.
        code_names = set(compiled_code.co_names)

        #
        generated_code_frame = sys._getframe(2)

        for local_var_name in generated_code_frame.f_locals:
            # Look for variables that are jinja2 generated top-level locals
            match = re.match(r"l_(\d+)_(?P<var_name>.+)", local_var_name)

            if match:
                var_name = match.group('var_name')

                # If the variable name appears in our code block, and is also a top-level local,
                # we update it to match its new value
                if (var_name in code_names) and (var_name in ctx.vars):
                    # Copy the value to the frame's locals.
                    generated_code_frame.f_locals[local_var_name] = ctx.vars[var_name]
                    # Do some ctypes vodo to make sure the frame locals are actually updated.
                    ctx.exported_vars.add(var_name)
                    # https://pydev.blogspot.com/2014/02/changing-locals-of-frame-frameflocals.html
                    ctypes.pythonapi.PyFrame_LocalsToFast(
                        ctypes.py_object(generated_code_frame),
                        ctypes.c_int(1))

        # Return the captured text.
        return sout.getvalue()
