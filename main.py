import time
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import requests
import sys
import os
import yaml
from fritzconnection.lib.fritzhosts import FritzHosts

iots = []
devices = []


class Devices:
    def __init__(self, name, status):
        self.id = len(devices)
        self.name = name
        self.status = status
        devices.append(self)

    def set_status(self, status):
        changed = True if self.status != status else False
        self.status = status
        return changed


class IOT:
    def __init__(self, name, ip, time, night):
        self.id = len(iots)
        self.name = name
        self.ip = str(ip)
        self.time = time
        self.night = night
        iots.append(self)

    def turn_on(self):
        resp = requests.get("http://" + self.ip + "/cm?cmnd=Power%20On")
        if resp.status_code != 200:
            requests.get("http://" + self.ip + "/cm?cmnd=Power%20On")

    def turn_off(self):
        resp = requests.get("http://" + self.ip + "/cm?cmnd=Power%20Off")
        if resp.status_code != 200:
            requests.get("http://" + self.ip + "/cm?cmnd=Power%20Off")


def get_iot(name):
    for entry in iots:
        if entry.name == name:
            return entry


def is_between(time_check, time_range):
    if time_range[1] < time_range[0]:
        return time_check >= time_range[0] or time_check <= time_range[1]
    return time_range[0] <= time_check <= time_range[1]


def turn_off_all():
    for entry in iots:
        iot = get_iot(entry.name)
        iot.turn_off()
    logging.info("Turned all IOTs off as device is not present.")


def check_between():
    for entry in iots:
        between = is_between(entry.time, (datetime.now().strftime('%H:%M'),
                                          (datetime.now() + timedelta(seconds=30)).strftime('%H:%M')))
        if between:
            iot = get_iot(entry.name)
            iot.turn_on()
            logging.info("Turned IOT ({}) on as time ({}) is reached.".format(iot.name, iot.time))


def check_present(status):
    if datetime.now().strftime('%H:%M') > "19:00" and status == 1:
        for entry in iots:
            if entry.night:
                iot = get_iot(entry.name)
                iot.turn_on()
                logging.info("Turned IOT ({}) on because of night enabled.".format(iot.name))


def main():
    while True:
        hosts = fh.get_hosts_info()
        for device in devices:
            for host in hosts:
                status = 1 if host['status'] else 0
                name = host['name']
                if device.name == name:
                    if device.status == 1:
                        check_between()
                    if device.status == 0:
                        turn_off_all()
                    if device.set_status(status):
                        check_present(status)
                    logging.debug("Device present: {}.".format("false" if device.status == 0 else "true"))
        time.sleep(30)


def init():
    for entry in data_loaded['iot']:
        IOT(entry, data_loaded['iot'][entry]['ip'], data_loaded['iot'][entry]['time'],
            True if "night" in data_loaded['iot'][entry] else False)

    to_track = data_loaded['to_track']

    hosts = fh.get_hosts_info()
    for host in hosts:
        status = 1 if host['status'] else 0
        name = host['name']
        if name == to_track:
            Devices(name, status)

    logging.info("Init step done. Found {} IOT devices to handle.".format(len(iots)))


logFormatter = logging.Formatter('%(asctime)s - (%(levelname)s) - %(message)s')
rootLogger = logging.getLogger()
rootLogger.setLevel(logging.INFO)

fileHandler = RotatingFileHandler(os.path.join(sys.path[0], 'log.log'), maxBytes=(1048576*5), backupCount=7)
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
init()
main()
