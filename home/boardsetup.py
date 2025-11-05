import machine
import network
import auth

def ntp_freshup():
    import ntptime
    ntptime.host = '172.22.222.1'
    ntptime.settime()

print('Board setup started')

if True:
    # Disable AP
    network.WLAN(network.AP_IF).active(False)
    # Enable Sta WIFI
    wlan = network.WLAN(network.STA_IF)
    if not wlan.active():
        print('> Activating WLAN')
        wlan.active(True)
    if not wlan.isconnected():
        print('> Connecting to WLAN')
        wlan.connect(auth.wlan_name, auth.wlan_pass)
        while not wlan.isconnected():
            machine.idle()
        print(' connected as:', wlan.ifconfig()[0])

    ntp_freshup()
    import utime
    print('> Board setup complete at ', utime.localtime())
