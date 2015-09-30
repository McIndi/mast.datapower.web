from cStringIO import StringIO
from mast.timestamp import Timestamp
import mast.datapower.datapower as datapower
import pkg_resources
from mast.datapower.datapower import DataPower
from mast.datapower.datapower import Environment, is_environment, get_appliances
from mast.xor import xordecode, xorencode
from mast.config import get_configs_dict
from urllib2 import unquote
from mast.logging import make_logger
import cherrypy
from cherrypy.wsgiserver.ssl_builtin import BuiltinSSLAdapter
from cherrypy.wsgiserver import CherryPyWSGIServer
import logging
import random
import string
import flask
import json
import os
import sys
import getpass

# TODO: map the configuration out better and
# move to function. Also add defaults, so it can
# run independant of any directory structure
config = get_configs_dict()["server.conf"]

static_dir = config["dirs"]["static"]
template_dir = config["dirs"]["template"]
if template_dir != os.path.abspath(template_dir):
    template_dir = os.path.join(os.environ["MAST_HOME"], template_dir)
plugin_dir = config["dirs"]["plugins"]
plugin_dir = os.path.join(os.environ["MAST_HOME"], plugin_dir)
upload_dir = config["dirs"]["upload"]
upload_dir = os.path.join(os.environ["MAST_HOME"], upload_dir)
static_path = config["paths"]["static"]
log_file = config["logging"]["file"]
log_level = int(config["logging"]["level"])
debug = bool(config["server"]["debug"])
port = int(config["server"]["port"])
host = config["server"]["host"]
max_file_upload_size = int(config["server"]["max_file_upload_size"])
threaded = bool(config["server"]["threaded"])
secure = bool(config["server"]["secure"])
cert, key = None, None
if secure:
    key = config["server"]["key"]
    cert = config["server"]["cert"]
    cacert = None
    if "cacert" in config["server"]:
        cacert = config["server"]["cacert"]

# TODO: Move config option gathering closer to here
app = flask.Flask(
    __name__,
    static_folder=static_dir,
    static_url_path=static_path,
    template_folder=template_dir)


app.secret_key = "M_C_I_N_D_I_PA$$W0RD-NEVER=BEFORE=SEEN"
wzl = logging.getLogger("werkzeug")
app.root_path = os.environ["MAST_HOME"]
log_file = os.path.join(os.environ["MAST_HOME"], log_file)
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(log_level)
wzl.addHandler(file_handler)

app.debug = debug

logger = make_logger("gui")

def initialize_plugins():
    """Initializes all of the plugins for the MAST web GUI"""
    logger.debug("Running as user {}".format(getpass.getuser()))
    logger.debug("Running in directory {}".format(os.getcwd()))
    logger.debug("Attempting to retrieve list of web plugins")
    plugins_dict = {}
    for ep in pkg_resources.iter_entry_points(group='mast_web_plugin'):
        logger.debug("found plugin: {}".format(ep.name))
        try:
            plugins_dict.update({ep.name: ep.load()})
        except:
            logger.exception(
                "An unhandled exception occurred during execution.")
            pass
    logger.info("Collected plugins {}".format(str(plugins_dict.keys())))

    plugins = {
        'css': '',
        'html': '',
        'js': '',
        'tabs': ''}

    for name, cls in sorted(plugins_dict.items()):
        _plugin = cls()
        plugins[name] = _plugin

        try:
            plugins["html"] += flask.Markup(_plugin.html())
            plugins["tabs"] += flask.Markup(
                '<li><a href="#mast.datapower.{0}">{0}</a></li>'.format(name))
            plugins["css"] += flask.Markup(_plugin.css())
            plugins["js"] += flask.Markup(_plugin.js())
        except:
            logger.exception(
                "An unhandled exception occured while attempting "
                "to gather the content for web plugin {}".format(name))
            raise
        # Route function
        try:
            app.add_url_rule(
                '/%s' % (name),
                view_func=_plugin.route,
                methods=["GET", "POST", "DELETE", "PUT"])
        except:
            logger.exception(
                "An unhandled exception occured while attempting "
                "to assign a handler for web plugin {}".format(name))
            raise

    return plugins


@app.route('/config/<_file>')
def get_json_config(_file):
    """return merged confiuration from `$MAST_HOME/etc/default/_file`
    and `$MAST_HOME/etc/local/_file` in json format"""
    _file = _file if _file.endswith(".conf") else "{}.conf".format(_file)

    config = get_configs_dict()[_file]
    return flask.jsonify(config)


@app.route('/test/connectivity/<hostname>')
def check_connectivity(hostname):
    resp = {}
    credentials = flask.request.args.get("credentials")
    credentials = xordecode(
        credentials,
        key=xorencode(flask.request.cookies["9x4h/mmek/j.ahba.ckhafn"]))
    check_hostname = flask.request.args.get("check_hostname", True)
    check_hostname = False if "false" in check_hostname else check_hostname

    appl = datapower.DataPower(hostname, credentials, check_hostname=check_hostname)
    resp["soma"] = appl.is_reachable()
    if "Authentication failure" in appl.last_response:
        resp["soma"] = False
    try:
        _resp = appl.ssh_connect(port=appl.ssh_port)
        appl.ssh_disconnect()
        resp["ssh"] = 'DataPower' in _resp
    except:
        resp["ssh"] = False
    return flask.jsonify(resp)


@app.route('/')
def index():
    """Render index.html"""
    global PLUGINS
    random.seed()
    flask.session["csrf"] = random.randint(100000, 999999)
    ephemeral_session = random.randint(10000, 99999)
    resp = flask.make_response(
        flask.render_template(
            'index.html',
            ephemeral_session=ephemeral_session,
            plugins=app.PLUGINS))
    resp.set_cookie(
        "9x4h/mmek/j.ahba.ckhafn",
        ''.join(random.choice(
            string.ascii_lowercase + string.ascii_uppercase + string.digits)
            for _ in range(64)))
    return resp


@app.route('/upload', methods=["POST"])
def upload():
    """This handles uploads of files, stores them in a temporary directory,
    and returns the path and filename in JSON format"""
    global upload_dir
    UPLOAD_DIRECTORY = upload_dir
    t = Timestamp()
    fin = flask.request.files["_file_in"]
    filename = os.path.join(
        UPLOAD_DIRECTORY,
        t.timestamp)
    os.makedirs(filename)
    filename = os.path.join(filename, fin.filename)
    fin.save(filename)
    return flask.jsonify({"filename": filename})


@app.route('/download_history', methods=["POST"])
def download_history():
    _id = flask.request.form.get("id")
    ts = _id.split("-")[0]
    filename = os.path.join(
        "var",
        "www",
        "static",
        "tmp",
        "request_history",
        ts,
        _id)
    return flask.send_file(
        filename,
        attachment_filename=_id,
        as_attachment=True)


@app.route('/download', methods=["GET", "POST"])
def download():
    # This needs to be more universal. This is currently only useful for
    # ssh transcripts. This should allow any relevant file to be downloaded.
    if flask.request.method == "POST":
        t = Timestamp()
        hostname = flask.request.form.get("hostname")
        filename = '%s-%s-ssh-transcript.txt' % (t.timestamp, hostname)
        f = StringIO()
        f.write(
            unquote(
                flask.request.form.get("content")).replace(
                    '\n',
                    os.linesep).replace(
                        "+",
                        " "))
        f.seek(0)
        return flask.send_file(
            f,
            attachment_filename=filename,
            as_attachment=True)


@app.route('/environments/<name>')
def list_environment(name):
    """Return a JSON response of the appliances in environment name.
    If name is not an environment then return name."""
    if not is_environment(name):
        return flask.jsonify({'appliances': [name]})
    return flask.jsonify({'appliances': get_appliances(name)})


@app.before_request
def log_access():
    r = flask.request
    logger = make_logger("mast.web.access")
    logger.info("method: {}, url: {}, client: {}".format(
        r.method,
        r.url,
        r.remote_addr))
    logger.debug("data: {}, headers: {}".format(
        r.data,
        str(r.headers).replace("\n", "; ")))

with app.app_context():
    flask.current_app.PLUGINS = initialize_plugins()


def main():
    logger = make_logger("gui.main")
    logger.debug("Running as user {}".format(getpass.getuser()))
    logger.debug("Running in directory {}".format(os.getcwd()))

    cherrypy.tree.graft(app, '/')

    # Set the configuration of the web server
    cherrypy.config.update({
        'engine.autoreload.on': False,
        'log.screen': False,
        'server.socket_port': port,
        'server.socket_host': host,
        'server.max_request_body_size': max_file_upload_size
    })

    if secure:
        logger.debug("Configuring TLS")
        cherrypy.server.ssl_module = 'builtin'
        CherryPyWSGIServer.ssl_adapter = BuiltinSSLAdapter(
            cert,
            key,
            cacert)

    # Start the CherryPy WSGI web server
    try:
        engine = cherrypy.engine
        engine.signal_handler.subscribe()
        if hasattr(engine, "console_control_handler"):
            engine.console_control_handler.subscribe()

        print "MAST Web listening on {}:{}".format(host, port)

        cherrypy.engine.start()
        cherrypy.engine.block()
    except KeyboardInterrupt:
        cherrypy.engine.exit()
    except:
        logger.exception(
            "Sorry, an unhandled exception occurred while starting CherryPy")


def stop_server():
    cherrypy.engine.exit()

if __name__ == "__main__":
    main()
