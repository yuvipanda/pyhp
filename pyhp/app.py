import logging
from flask import Flask, make_response, send_from_directory, request, session
from werkzeug.middleware.proxy_fix import ProxyFix
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import os
from .extension import PythonExtension

# FIXME: Make this configurable
BASE_DIR = os.getcwd()

# File extensions we serve unchanged by default
# This prevents the common PHP mistake of exposing your credentials file
# as a common static file.
STATIC_EXTENSIONS = [
    # Base web stuff
    '.css', '.js', '.html',
    # Image formats
    '.png', '.jpeg', '.svg', '.ico',
    # webfonts
    '.ttf', '.woff', '.woff2'
]

# File to serve when / is hit
INDEX_FILE = 'index.pyhp'

env = Environment(
    loader=FileSystemLoader(BASE_DIR),
    extensions=[PythonExtension]
)

application = Flask(__name__)

# FIXME: Should this be unconditionally trusted?!
# Trust X-Forwarded-Prefix, so this can run behind jupyter-server-proxy
# This lets you use request.url_root in your pyhp files
application.wsgi_app = ProxyFix(application.wsgi_app, x_prefix=1)

logger = application.logger
logger.setLevel(logging.INFO)


@application.route('/<path:path>')
@application.route('/', defaults={'path': INDEX_FILE})
def render(path):
    full_path = os.path.realpath(path)
    # Guard against directory traversal
    if os.path.commonpath([BASE_DIR, full_path]) != BASE_DIR:
        return make_response(('Access denied', 403))
    _, ext = os.path.splitext(path)
    if ext != '.pyhp':
        if ext in STATIC_EXTENSIONS:
            # FIXME: send_from_directory doesn't send same path as os.path.join(BASE_DIR, path)
            # send_from_directory is more secure & protects against path traversal attacks
            logger.info("Serving {path} from {BASE_DIR} as a static file")
            return send_from_directory(BASE_DIR, path)
        else:
            return make_response(('Access denied', 403))
    try:
        template = env.get_template(path)
    except TemplateNotFound:
        return make_response((f"No such file {path} found", 404))

    return template.render()

if __name__ == '__main__':
    application.run(debug=True)
