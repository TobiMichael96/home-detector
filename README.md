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

There are also 3 other keys which will enable this feature: `night_long`, `night_lat` and `night_offset`.
With `night_long` and `night_lat` you can set the longitude and latitude of your location and Home-Detector
will then calculate the **civil twilight end** and apply your offset (if set) to it.
Setting these keys will overwrite the ``night_time`` key.

The key ``tv_ip`` enables another feature: It will turn off your Samsung TV when the device
is not present anymore. This requires the ``websocket-client`` module.

Additionally, there are two keys (`pin_green` and `pin_red`) which enable another feature.
With these keys you can tell Home-Detector what pins your LEDs are connected to.

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