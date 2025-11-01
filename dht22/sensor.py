import gc
import math
import sys

import machine
import usocket
import utime

from auth import desthost, desturl

try:
    import network
except ImportError:
    dht_sensor = None
    wlan = None
    machineid = '<fake>'
    import random
else:
    import dht

    dht_sensor = dht.DHT22(machine.Pin(13))
    wlan = network.WLAN(network.STA_IF)

    # Turn off access point
    network.WLAN(network.AP_IF).active(False)

    machineid = machine.unique_id()


def get_ah(temperature, humidity) -> float:
    """
    Calculate the absolute humidity from temperature and relative humidity.

    Args:
        temperature (float): The temperature in Celsius.
        humidity (float): The relative humidity as a percentage.

    Returns:
        float: The absolute humidity in g/m³.
    """
    # from https://carnotcycle.wordpress.com/2012/08/04/
    #      how-to-convert-relative-humidity-to-absolute-humidity/
    return (
        13.2471 * humidity * math.exp((17.67 * temperature) / (temperature + 243.5))
    ) / (273.15 + temperature)


class Sensor:
    def __init__(self):
        self.do_loop_samples = []

    def get_measure(self) -> (float, float):
        if dht_sensor:
            dht_sensor.measure()
            return dht_sensor.temperature(), dht_sensor.humidity()

        return (random.getrandbits(5) + 180) / 10, (random.getrandbits(4) + 40)

    def ensure_connected(self) -> None:
        if wlan is None:
            return

        if not wlan.active():
            print('> Activating WLAN')
            wlan.active(True)
        if not wlan.isconnected():
            print('> Connecting to WLAN')
            wlan.connect()
            while not wlan.isconnected():
                machine.idle()
            print(' connected as:', wlan.ifconfig()[0])

    def send_measurement(self, temperature, humidity, abs_humidity) -> None:
        """
        Sends a measurement to the specified destination.

        Args:
            temperature (float): The measured temperature.
            humidity (float): The measured humidity.
            abs_humidity (float): The measured absolute humidity.
        """

        data_to_send = (
            f'templog,host={machineid} temperature={temperature},'
            f'humidity={humidity},abshumidity={abs_humidity}'
        )

        if wlan is None:
            print(f'Not sending {data_to_send}')
            return

        try:
            s = usocket.socket()
            s.connect(usocket.getaddrinfo(desthost, 80)[0][-1])

            s.sendall(
                f"""POST {desturl} HTTP/1.1
Host: {desthost}
Accept: */*
Content-Length: {len(data_to_send)}
Content-Type: application/x-www-form-urlencoded

{data_to_send}
""".encode()
            )
            print('>', s.recv(1024).decode().split('\n')[0])
        except OSError:
            print(' * Error during sending measurement')
            pass
        finally:
            s.close()

    def do_sleep(self, sleep_ms) -> None:
        if wlan:
            if wlan.isconnected():
                wlan.disconnect()
                machine.idle()
            wlan.active(False)
            machine.idle()

        print(f'> Entering lightsleep for {sleep_ms} ms')
        if hasattr(machine, 'lightsleep'):
            machine.lightsleep(sleep_ms)
        else:
            utime.sleep_ms(sleep_ms)
        print('> Wakeup from sleep')

    def do_loop(self) -> None:
        samples = self.do_loop_samples
        condition = True
        while condition:
            temp, humidity = self.get_measure()
            abs_humidity: float = get_ah(temp, humidity)

            sample = (temp, humidity, abs_humidity)

            print(
                '[%02d:%02d:%02d.%03d]' % utime.localtime()[3:7],
                ' %.01f C (%.01f %% rel.H %4.1f abs.H)' % sample,
            )

            samples.append((utime.time(), sample))
            print(f'# Samples: {len(samples)}')

            sample_interval_wait = 1000 - utime.localtime()[7] + 30 * 1000
            self.do_sleep(sample_interval_wait)

            condition = (
                utime.time() - samples[0][0] < 15 * 60
                and
                # less than 0.1 C difference
                abs(samples[0][1][0] - sample[0]) < 0.1
                and
                # less than 0.3 % humidity difference
                abs(samples[0][1][1] - sample[1]) < 0.3
            )

        self.ensure_connected()
        current_sample = samples.pop()
        self.send_measurement(*(current_sample[1]))
        self.do_loop_samples = [current_sample]


sensor = Sensor()

if 'ESP' in sys.implementation._machine:
    print('Waiting 5s')
    # Give us some time to abort the code
    utime.sleep(5)

while True:
    sensor.do_loop()

    hour_of_day = utime.localtime()[3]
    sensor.do_sleep(10 * 60 * 1000 if hour_of_day in range(0, 4) else 6 * 60 * 1000)

    gc.collect()
    print('.')
