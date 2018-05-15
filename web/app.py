import flask
import traceback
import sys
sys.path.append('..')
from patcher import FirmwarePatcher

app = flask.Flask(__name__)


@app.errorhandler(Exception)
def handle_bad_request(e):
    return 'Exception occured:\n{}'.format(traceback.format_exc()), \
            400, {'Content-Type': 'text/plain'}


@app.route('/')
def home():
    return flask.render_template('home.html')


@app.route('/cfw')
def patch_firmware():
    version = flask.request.args.get('version', None)
    if version not in ['DRV130', 'DRV134', 'DRV138']:
        return 'Invalid firmware version.', 400

    with open('../bins/{}.bin'.format(version), 'rb') as fp:
        patcher = FirmwarePatcher(fp.read())

    kers_min_speed = flask.request.args.get('kers_min_speed', None)
    if kers_min_speed is not None:
        kers_min_speed = float(kers_min_speed)
        assert kers_min_speed >= 0 and kers_min_speed <= 100
        patcher.kers_min_speed(kers_min_speed)

    normal_max_speed = flask.request.args.get('normal_max_speed', None)
    if normal_max_speed is not None:
        normal_max_speed = int(normal_max_speed)
        assert normal_max_speed >= 0 and normal_max_speed <= 100
        patcher.normal_max_speed(normal_max_speed)

    eco_max_speed = flask.request.args.get('eco_max_speed', None)
    if eco_max_speed is not None:
        eco_max_speed = int(eco_max_speed)
        assert eco_max_speed >= 0 and eco_max_speed <= 100
        patcher.eco_max_speed(eco_max_speed)

    motor_start_speed = flask.request.args.get('motor_start_speed', None)
    if motor_start_speed is not None:
        motor_start_speed = float(motor_start_speed)
        assert motor_start_speed >= 0 and motor_start_speed <= 100
        patcher.motor_start_speed(motor_start_speed)

    motor_power_constant = flask.request.args.get('motor_power_constant', None)
    if motor_power_constant is not None:
        motor_power_constant = int(motor_power_constant)
        assert motor_power_constant >= 25787 and motor_power_constant <= 65535
        patcher.motor_power_constant(motor_power_constant)

    cruise_control_delay = flask.request.args.get('cruise_control_delay', None)
    if cruise_control_delay is not None:
        cruise_control_delay = float(cruise_control_delay)
        assert cruise_control_delay >= 0.1 and cruise_control_delay <= 20.0
        patcher.cruise_control_delay(cruise_control_delay)

    instant_eco_switch = flask.request.args.get('instant_eco_switch', None)
    if instant_eco_switch:
        patcher.instant_eco_switch()

    boot_with_eco = flask.request.args.get('boot_with_eco', None)
    if boot_with_eco:
        patcher.boot_with_eco()

    idk_what_this_does = flask.request.args.get('idk_what_this_does', None)
    if idk_what_this_does:
        patcher.idk_what_this_does()

    resp = flask.Response(patcher.data)
    resp.headers['Content-Type'] = 'application/octet-stream'
    resp.headers['Content-Disposition'] = 'inline; filename="{0}-patched.bin"'.format(
        version)
    resp.headers['Content-Length'] = len(patcher.data)

    return resp
