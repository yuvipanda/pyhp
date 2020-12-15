import logging
from flask import Flask, make_response, send_from_directory
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, nodes
from jinja2.ext import Extension
import os
from textwrap import dedent
from io import StringIO
import sys
import re
import ctypes

var_name_regex = re.compile(r"l_(\d+)_(.+)")
#
# From https://stackoverflow.com/a/55545295
class PythonExtension(Extension):
    # a set of names that trigger the extension.
    tags = {'py'}

    def __init__(self, environment: Environment):
        super().__init__(environment)

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        body = parser.parse_statements(['name:endpy'], drop_needle=True)
        return nodes.CallBlock(self.call_method('_exec_python',
                                                [nodes.ContextReference(), nodes.Const(lineno), nodes.Const(parser.filename)]),
                               [], [], body).set_lineno(lineno)

    def _exec_python(self, ctx, lineno, filename, caller):
        # Remove access indentation
        code = dedent(caller())

        # Compile the code.
        compiled_code = compile("\n"*(lineno-1) + code, filename, "exec")

        # Create string io to capture stdio and replace it.
        sout = StringIO()
        stdout = sys.stdout
        sys.stdout = sout

        try:
            # Execute the code with the context parents as global and context vars and locals.
            exec(compiled_code, ctx.parent, ctx.vars)
        except Exception:
            raise
        finally:
            # Restore stdout whether the code crashed or not.
            sys.stdout = stdout

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

env = Environment(
    loader=FileSystemLoader('.'),
    extensions=[PythonExtension]
)

app = Flask(__name__)
logger = app.logger
logger.setLevel(logging.INFO)

BASE_DIR = os.getcwd()

@app.route('/<path:path>')
def render(path):
    _, ext = os.path.splitext(path)
    if ext != '.pyhp':
        # FIXME: send_from_directory doesn't send same path as os.path.join(BASE_DIR, path)
        # send_from_directory is more secure & protects against path traversal attacks
        logger.info("Serving {path} from {BASE_DIR} as a static file")
        return send_from_directory(BASE_DIR, path)
    try:
        template = env.get_template(path)
    except TemplateNotFound:
        return make_response(("No such file {path} found", 404))
    return template.render()

if __name__ == '__main__':
    app.run(debug=True)
