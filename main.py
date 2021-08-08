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
                logging.debug(e)
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
                logging.debug(e)
                time.sleep(5)
                self.turn_on()
            else:
                break


def check_status():
    global STATUS
    host_temp = fh.get_specific_host_entry_by_ip(data_loaded['to_track'])
    new_status = 1 if host_temp['NewActive'] else 0
    changed = True if STATUS != new_status else False
    STATUS = new_status
    return changed


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
            return
        between = is_between(iot.on_time, (datetime.now().strftime('%H:%M'),
                                           (datetime.now() + timedelta(seconds=30)).strftime('%H:%M')))
        if between:
            iot.turn_on()
            logging.info("Turned IOT ({}) on as time ({}) is reached.".format(iot.name, iot.on_time))


def check_present(iots):
    if 'night_time' in data_loaded:
        if datetime.now().strftime('%H:%M') > data_loaded['night_time'] and STATUS == 1:
            for iot in iots:
                if iot.night:
                    iot.turn_on()
                    logging.info("Turned IOT ({}) on because of night enabled.".format(iot.name))
    elif STATUS == 0:
        turn_off_all(iots)
        logging.info("Turned all IOTs off as device is not present.")


def check_tv_status():
    try:
        result = requests.get('http://192.168.178.30:8001/api/v2/', timeout=5)
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
        ws = create_connection(url, sslopt={'cert_reqs': ssl.CERT_NONE}, connection='Connection: Upgrade')
        result = ws.recv()
        TOKEN = json.loads(result)['data']['token']
        logging.info("Successfully loaded token for TV.")
    except (WebSocketException, WebSocketTimeoutException) as e:
        TOKEN = None
        logging.error("Could not create connection with error: {}".format(e))


def send_tv_command(key):
    if not check_tv_status():
        logging.info("TV is already off...")
        return

    if TOKEN is None:
        get_tv_token()

    url = "wss://{}:8002/api/v2/channels/samsung.remote.control?name={}&token={}".format(data_loaded['tv_ip'], REMOTE_NAME, TOKEN)
    ws = create_connection(url, sslopt={'cert_reqs': ssl.CERT_NONE}, connection='Connection: Upgrade')
    payload = json.dumps(
        {'method': 'ms.remote.control',
         'params': {
             'Cmd': 'Click',
             'DataOfCmd': key,
             'Option': 'false',
             'TypeOfRemote': 'SendRemoteKey'
         }})
    ws.send(payload=payload)
    logging.info("Turned tv off, because device is not present.")


def main():
    while True:
        iots = load_config()
        changed = check_status()
        if STATUS == 1 or changed:
            check_between(iots)
        if STATUS == 0 and changed and data_loaded['tv_ip']:
            send_tv_command('KEY_POWER')
        logging.info("Device present: {}.".format("false" if STATUS == 0 else "true"))
        time.sleep(15)


def load_config():
    iots = []
    for entry in data_loaded['iot']:
        iot = IOT(entry, data_loaded['iot'][entry]['ip'],
                  data_loaded['iot'][entry]['time'] if "time" in data_loaded['iot'][entry] else None,
                  True if "night" in data_loaded['iot'][entry] else False)
        iots.append(iot)
    logging.debug("Reloaded config. Found {} IOT devices to handle.".format(len(iots)))

    return iots


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
fh = FritzHosts(address=data_loaded['address'], password=data_loaded['password'])
host = fh.get_specific_host_entry_by_ip(data_loaded['to_track'])

if data_loaded['tv_ip']:
    REMOTE_NAME = base64.b64encode('HomeControl'.encode()).decode('utf-8')
    TOKEN = None
    from websocket import create_connection, WebSocketException, WebSocketTimeoutException
    get_tv_token()

STATUS = 1 if host['NewActive'] else 0
logging.info("Initializing done...")
main()
