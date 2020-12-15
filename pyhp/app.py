import logging
from flask import Flask, make_response, send_from_directory
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import os
from .extension import PythonExtension

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
