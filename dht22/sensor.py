import gc
import machine
import math
import sys
import usocket
import utime

use_deep_sleep = False

try:
    import network
except ImportError:
    dht_sensor = None
    wlan = None
    rtc = None
    machineid = '<fake>'
    import random
else:
    import dht
    dht_sensor = dht.DHT22(machine.Pin(13))
    wlan = network.WLAN(network.STA_IF)

    # Turn off access point
    network.WLAN(network.AP_IF).active(False)

    use_deep_sleep_pin = machine.Pin(
        14, mode=machine.Pin.IN, pull=machine.Pin.PULL_UP)
    use_deep_sleep = not use_deep_sleep_pin.value()
    rtc = machine.RTC()
    machineid = machine.unique_id()


def get_measure():
    if dht_sensor:
        dht_sensor.measure()
        return dht_sensor.temperature(), dht_sensor.humidity()

    return (random.getrandbits(5) + 180)/10, (random.getrandbits(4)+40)


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
    if wlan is None:
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
''' % (
            {'hostname': desthost,
             'postlength': len(data_to_send),
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
    if use_deep_sleep:
        rtc.irq(trigger=rtc.ALARM0, wake=machine.DEEPSLEEP)
        rtc.alarm(rtc.ALARM0, sleeptime * 1000)
        print('[%02d:%02d:%02d.%03d] ' % utime.localtime()[3:7],
              'deep sleep for %d s ' % sleeptime)
        machine.deepsleep()
        return

    if wlan:
        wlan.disconnect()
        wlan.active(False)

    if hasattr(machine, 'lightsleep'):
        print(f'> Entering lightsleep for {sleeptime} s')
        machine.lightsleep(sleeptime * 1000)
    else:
        utime.sleep(sleeptime)
    print('> Wakup from sleep')


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
        print('# Samples: ', len(samples))

        if not use_deep_sleep:
            sample_interval_wait = 1000 - utime.localtime()[7] + 30 * 1000
            if hasattr(machine, 'lightsleep'):
                machine.lightsleep(sample_interval_wait)
            elif hasattr(utime, 'sleep_ms'):
                utime.sleep_ms(sample_interval_wait)

            condition = (utime.time() - samples[0][0] < 10 * 60 and
                         # less than 0.1 C difference
                         abs(samples[0][1][0] - sample[0]) < 0.1 and
                         # less than 0.3 % humidity difference
                         abs(samples[0][1][1] - sample[1]) < 0.3)
        else:
            break

    do_connect()
    current_sample = samples.pop()
    send_measurement(*(current_sample[1]))
    do_loop_samples = [current_sample]


if 'ESP' in sys.implementation._machine:
    print('Waiting 5s')
    # Give us some time to abort the code
    utime.sleep(5)

    # Warm up sensor
    for i in range(1, 4):
        try:
            print('warmup', get_measure())
            utime.sleep(2)
        except Exception:
            pass

while True:
    do_loop()

    hour_of_day = utime.localtime()[3]

    if hour_of_day in range(0, 4):
        do_sleep(10 * 60)
    else:
        do_sleep(6 * 60)

    gc.collect()
    print('.')
