# Home-Detector

This script will check if a device is connected to your FritzBox 
and turn your sonoff-devices (flashed with [Tasmota](https://github.com/arendst/Tasmota)) 
off or on based on time or present of your device.

It can also turn off your Smart-TV (if you have a Samsung TV with Tizen).

## Configuration

Create a copy of `sample.config.yaml` with the name `config.yaml` and add your
values to it.

### Further explanation

The key ``night_time`` enables a feature: It will turn on your devices 
when the device becomes present after the specified time (if you enabled this feature 
at the device level).

The key ``tv_ip`` enables another feature: It will turn off your Samsung TV when the device
is not present anymore. This requires the ``websocket-client`` module.

Devices can either look like this:

```yaml
  example1:
    ip: "192.168.2.234"
    time: "19:00"
````

or like this if you want to use the **night_time** feature:

```yaml
  example2:
    ip: "192.168.2.111"
    time: "20:00"
    night: true
````

## Additional note

This is highly WIP.