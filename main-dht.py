import gc
import sys
import time

if sys.implementation.name == 'micropython':
    import machine
    import dht
    import esp
    import network
    import usocket

    wlan = network.WLAN(network.STA_IF)
    dht_sensor = dht.DHT22(machine.Pin(13))
    rtc = machine.RTC()

    # Enable suspending of CPU, we don't need PWM or I2S
    esp.sleep_type(esp.SLEEP_LIGHT)
    # Turn off access point
    network.WLAN(network.AP_IF).active(False)

else:
    import socket as usocket
    import random
    wlan = None
    rtc = None


def get_measure():
    if sys.implementation.name == 'micropython':
        dht_sensor.measure()
        return dht_sensor.temperature(), dht_sensor.humidity()

    return random.randint(5, 10), random.randint(40, 60)


desthost = 'air.dmllr.de'
machineid = 'host1'


def do_connect():
    if wlan is None:
        return

    if wlan:
        print('> Activating WLAN')
        wlan.active(True)
    if not wlan.isconnected():
        wlan.connect()
        while not wlan.isconnected():
            machine.idle()
        print(' connected as:', wlan.ifconfig()[0])


def send_measurement(temperature, humidity):
    if sys.implementation.name != 'micropython':
        print('Not sending')
        return

    try:
        s = usocket.socket()
        s.connect(usocket.getaddrinfo(desthost, 80)[0][-1])

        data_to_send = (
            'templog,host=%s temperature=%f,humidity=%f') % (
             machineid, temperature, humidity)

        req = '''POST /TVgsSPvTSLMC6/write?db=templogger HTTP/1.1
Host: %(hostname)s
Accept: */*
Content-Length: %(postlength)d
Content-Type: application/x-www-form-urlencoded

%(body)s
''' % ({'hostname': desthost,
        'postlength': len(data_to_send),
        'body': data_to_send})

        s.sendall(req.encode())
        print('>',  s.recv(1024).decode().split('\n')[0])
    except OSError:
        print(' * Error during sending measurement')
        pass
    finally:
        s.close()


def do_sleep():
    sleeptime = 3 * 60 + 20

    if rtc is None:
        time.sleep(sleeptime)
        return

    if wlan:
        wlan.active(False)

    rtc.alarm(0, sleeptime*1000)
    while(rtc.alarm_left()):
        machine.idle()
    print('> Wakup from sleep')
    gc.collect()


def do_loop():
    temp, humidity = get_measure()
    print('Current temp %f (%f %% Humidity)' % (temp, humidity))

    do_connect()
    send_measurement(temp, humidity)


while True:
    do_loop()

    do_sleep()
    print('.')
