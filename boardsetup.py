import machine
import esp
import network

def ntp_freshup():
    import ntptime
    ntptime.host = '172.22.222.1'
    ntptime.settime()

print('Board setup started')

if machine.reset_cause() is not machine.DEEPSLEEP_RESET:
    # Disable AP
    network.WLAN(network.AP_IF).active(False)
    # Enable Sta WIFI
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        print('> Activating WLAN')
        wlan.active(True)
    if not wlan.isconnected():
        print('> Connecting to WLAN')
        wlan.connect()
        while not wlan.isconnected():
            machine.idle()
        print(' connected as:', wlan.ifconfig()[0])
    # Enable suspending of CPU, we don't need PWM or I2S
    esp.sleep_type(esp.SLEEP_LIGHT)

    ntp_freshup()
    import utime
    print('> Board setup complete at ', utime.localtime())
