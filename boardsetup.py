import machine
import esp
import network

if machine.cause() is machine.PWRON_RESET:
    # Disable AP
    network.WLAN(network.AP_IF).active(False)
    # Enable Sta WIFI
    network.WLAN(network.STA_IF).active(True)
    # Enable suspending of CPU, we don't need PWM or I2S
    esp.sleep_type(esp.SLEEP_LIGHT)
    print('Board setup complete')
