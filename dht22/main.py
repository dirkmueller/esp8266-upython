import gc
import math
import sys

if sys.implementation.name == 'micropython':
    import machine
    import dht
    import esp
    import network
    import usocket
    import utime

    wlan = network.WLAN(network.STA_IF)
    dht_sensor = dht.DHT22(machine.Pin(13))
    rtc = machine.RTC()

    machineid = machine.unique_id()

    # Enable suspending of CPU, we don't need PWM or I2S
    esp.sleep_type(esp.SLEEP_LIGHT)
    # Turn off access point
    network.WLAN(network.AP_IF).active(False)

else:
    import socket as usocket
    import random
    import time as utime
    wlan = None
    rtc = None
    machineid = 'host1'


def get_measure():
    if sys.implementation.name == 'micropython':
        dht_sensor.measure()
        return dht_sensor.temperature(), dht_sensor.humidity()

    return random.randint(180, 220)/10, 42


desthost = 'air.dmllr.de'


def do_connect():
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


def send_measurement(temperature, humidity, abs_humidity):
    if sys.implementation.name != 'micropython':
        print('Not sending')
        return

    try:
        s = usocket.socket()
        s.connect(usocket.getaddrinfo(desthost, 80)[0][-1])

        data_to_send = (
            'templog,host=%s temperature=%f,humidity=%f,abshumidity=%f') % (
             machineid, temperature, humidity, abs_humidity)

        req = '''POST /TVgsSPvTSLMC6/write?db=templogger HTTP/1.1
Host: %(hostname)s
Accept: */*
Content-Length: %(postlength)d
Content-Type: application/x-www-form-urlencoded

%(body)s
''' % ({'hostname': desthost, 'postlength': len(data_to_send),
        'body': data_to_send})

        s.sendall(req.encode())
        print('>',  s.recv(1024).decode().split('\n')[0])
    except OSError:
        print(' * Error during sending measurement')
        pass
    finally:
        s.close()


def get_ah(temperature, humidity):
    # from https://carnotcycle.wordpress.com/2012/08/04/
    #      how-to-convert-relative-humidity-to-absolute-humidity/

    return ((13.2471 * humidity *
             math.exp((17.67 * temperature) / (temperature + 243.5))) /
            (273.15 + temperature))


def do_sleep(sleeptime):

    utime.sleep(sleeptime)
    print('> Wakup from sleep')
    gc.collect()


do_loop_samples = []


def do_loop():
    global do_loop_samples
    samples = do_loop_samples
    condition = True
    while condition:
        temp, humidity = get_measure()
        abs_humidity = get_ah(temp, humidity)

        sample = (temp, humidity, abs_humidity)

        print('[%02d:%02d:%02d.%03d]' % utime.localtime()[3:7],
              ' %.01f C (%.01f %% rel.H %4.1f abs.H)' % sample)

        samples.append((utime.time(), sample))

        if (hasattr(utime, 'sleep_ms')):
            utime.sleep_ms(1000 - utime.localtime()[7] + 30 * 1000)

        print('# Samples: ', len(samples))

        condition = (utime.time() - samples[0][0] < 10 * 60 and
                     # less than 0.1 C difference
                     abs(samples[0][1][0] - sample[0]) < 0.1 and
                     # less than 0.3 % humidity difference
                     abs(samples[0][1][1] - sample[1]) < 0.3)

    do_connect()
    current_sample = samples.pop()
    send_measurement(*(current_sample[1]))
    do_loop_samples = [current_sample]


while True:
    do_loop()

    hour_of_day = utime.localtime()[3]

    if hour_of_day in range(0, 4):
        do_sleep(7 * 60 + 20)
    else:
        do_sleep(2 * 60 + 10)

    print('.')
