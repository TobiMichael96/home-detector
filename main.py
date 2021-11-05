import base64
import json
import logging
import os
import ssl
import sys
import time
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

import requests
import yaml
from fritzconnection.lib.fritzhosts import FritzHosts


class IOT:
    def __init__(self, name, ip, on_time, night):
        self.name = name
        self.ip = str(ip)
        self.on_time = on_time
        self.night = night

    def turn_on(self):
        for attempt in range(5):
            try:
                resp = requests.get("http://" + self.ip + "/cm?cmnd=Power%20On")
                if resp.status_code != 200:
                    requests.get("http://" + self.ip + "/cm?cmnd=Power%20On")
            except ConnectionError as e:
                logging.error(e)
                time.sleep(5)
                self.turn_on()
            else:
                break

    def turn_off(self):
        for attempt in range(10):
            try:
                resp = requests.get("http://" + self.ip + "/cm?cmnd=Power%20Off")
                if resp.status_code != 200:
                    requests.get("http://" + self.ip + "/cm?cmnd=Power%20Off")
            except ConnectionError as e:
                logging.error(e)
                time.sleep(5)
                self.turn_on()
            else:
                break


def check_status():
    global STATUS
    if FB_CONNECTION is not None:
        host_temp = FB_CONNECTION.get_specific_host_entry_by_ip(data_loaded['to_track'])
        new_status = 1 if host_temp['NewActive'] else 0
        if STATUS != new_status:
            changed = True
        else:
            changed = False
        STATUS = new_status
        return changed
    else:
        STATUS = 1
        return False


def is_between(time_check, time_range):
    if time_range[1] < time_range[0]:
        return time_check >= time_range[0] or time_check <= time_range[1]
    return time_range[0] <= time_check <= time_range[1]


def turn_off_all(iots):
    for iot in iots:
        iot.turn_off()


def check_between(iots):
    for iot in iots:
        if iot.on_time is None:
            logging.debug("Device {} has not on_time configured.".format(iot.name))
            return
        between = is_between(iot.on_time, (datetime.now().strftime('%H:%M'),
                                           (datetime.now() + timedelta(seconds=30)).strftime('%H:%M')))
        if between:
            iot.turn_on()
            logging.info("Turned IOT ({}) on as time ({}) was reached.".format(iot.name, iot.on_time))


def check_present(iots):
    if STATUS == 1 and 'night_time' in data_loaded:
        if datetime.now().strftime('%H:%M') > data_loaded['night_time']:
            for iot in iots:
                if iot.night:
                    iot.turn_on()
                    logging.info("Turned IOT ({}) on because of night enabled.".format(iot.name))
    else:
        turn_off_all(iots)
        logging.info("Turned all IOTs off as device is not present.")


def check_tv_status():
    try:
        result = requests.get('http://{}:8001/api/v2/'.format(data_loaded['tv_ip']), timeout=5)
    except requests.exceptions.ConnectTimeout:
        return False

    if result.json()['device']['PowerState'] == "on":
        return True
    else:
        return False


def get_tv_token():
    global TOKEN

    if not check_tv_status():
        logging.critical("Can not get a token as TV is off.")
        return

    url = "wss://{}:8002/api/v2/channels/samsung.remote.control?name={}".format(data_loaded['tv_ip'], REMOTE_NAME)
    try:
        ws = create_connection(url, sslopt={'cert_reqs': ssl.CERT_NONE},
                               connection='Connection: Upgrade', validate_cert=False)
        result = ws.recv()
        TOKEN = json.loads(result)['data']['token']
        logging.info("Successfully loaded token for TV.")
    except (WebSocketException, WebSocketTimeoutException, KeyError) as e:
        TOKEN = None
        logging.error("Could not create connection with error: {}".format(e))


def send_tv_command(key):
    if not check_tv_status():
        logging.info("TV is already off...")
        return

    if TOKEN is None:
        get_tv_token()

    url = "wss://{}:8002/api/v2/channels/samsung.remote.control?name={}&token={}".format(data_loaded['tv_ip'],
                                                                                         REMOTE_NAME, TOKEN)
    loop_counter = 0
    while check_tv_status():
        if loop_counter == 2:
            get_tv_token()
        try:
            ws = create_connection(url, sslopt={'cert_reqs': ssl.CERT_NONE},
                                   connection='Connection: Upgrade', validate_cert=False)
            payload = json.dumps(
                {'method': 'ms.remote.control',
                 'params': {
                     'Cmd': 'Click',
                     'DataOfCmd': key,
                     'Option': 'false',
                     'TypeOfRemote': 'SendRemoteKey'
                 }})
            ws.send(payload=payload)
            loop_counter += 1
            time.sleep(5)
            logging.info("Turned tv off, because device is not present.")
        except (WebSocketException, WebSocketTimeoutException, KeyError) as e:
            logging.error("Could not turn off TV with error: {}.".format(e))
            break


def main():
    while True:
        iots = load_config()
        changed = check_status()
        if STATUS == 1:
            if data_loaded['pin_green'] and data_loaded['pin_red']:
                GPIO.output(data_loaded['pin_green'], True)
                GPIO.output(data_loaded['pin_red'], False)
            check_between(iots)
        if changed:
            check_present(iots)
        if STATUS == 0:
            if data_loaded['pin_green'] and data_loaded['pin_red']:
                GPIO.output(data_loaded['pin_green'], False)
                GPIO.output(data_loaded['pin_red'], True)
            if changed and data_loaded['tv_ip']:
                send_tv_command('KEY_POWER')
        logging.debug("Device present: {}.".format("false" if STATUS == 0 else "true"))
        time.sleep(10)


def load_config():
    iots = []
    for entry in data_loaded['iot']:
        iot = IOT(entry, data_loaded['iot'][entry]['ip'],
                  data_loaded['iot'][entry]['time'] if "time" in data_loaded['iot'][entry] else None,
                  True if "night" in data_loaded['iot'][entry] else False)
        iots.append(iot)
    logging.debug("Reloaded config. Found {} IOT devices to handle.".format(len(iots)))
    return iots


def connect_fritz_box():
    try:
        fh = FritzHosts(address=data_loaded['address'], password=data_loaded['password'])
        host = fh.get_specific_host_entry_by_ip(data_loaded['to_track'])
        return fh, host
    except Exception as e:
        logging.error("Connection to FRITZ!Box failed with error: {}".format(e))
    return None, None


logFormatter = logging.Formatter('%(asctime)s - (%(levelname)s) - %(message)s')
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.INFO)

fileHandler = RotatingFileHandler(os.path.join(sys.path[0], 'log.log'), maxBytes=(1048576 * 5), backupCount=7)
fileHandler.setFormatter(logFormatter)
rootLogger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)

with open(os.path.join(sys.path[0], 'config.yaml'), 'r') as stream:
    data_loaded = yaml.safe_load(stream)

if data_loaded['log'] == "debug":
    rootLogger.setLevel(logging.DEBUG)
    logging.warning("Increased loglevel to debug.")

logging.info("Initiating application now...")

if data_loaded['pin_green'] and data_loaded['pin_red']:
    import RPi.GPIO as GPIO
    import time
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(data_loaded['pin_green'], GPIO.OUT)
    GPIO.setup(data_loaded['pin_red'], GPIO.OUT)

FB_CONNECTION, device_to_track = connect_fritz_box()
if device_to_track is None:
    device_to_track = {'NewActive': True}

if data_loaded['tv_ip']:
    REMOTE_NAME = base64.b64encode('HomeControl'.encode()).decode('utf-8')
    TOKEN = None
    from websocket import create_connection, WebSocketException, WebSocketTimeoutException
    if os.path.isfile(os.path.join(sys.path[0], 'tv_token')):
        with open(os.path.join(sys.path[0], 'tv_token'), 'r') as token_file:
            TOKEN = token_file.read()
            logging.info("TV token successfully loaded from file.")
    else:
        get_tv_token()
        if TOKEN:
            with open(os.path.join(sys.path[0], 'tv_token'), 'w') as token_file:
                token_file.write(TOKEN)
                logging.debug("TV token successfully written from file.")

STATUS = 1 if device_to_track['NewActive'] else 0
logging.info("Initializing done...")
main()
