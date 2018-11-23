
import machine
import ssd1306

txt = "Hello world - this is my first scroller!!! *** welcome to the scroller magic!"


ssd = ssd1306.SSD1306_I2C(128, 32, machine.I2C(-1, machine.Pin(5), machine.Pin(4)))

i = 0
while(1):
    i += 1
    ofs = (i // 8) % len(txt)
    pxs = 8 - (i % 8)

    ssd.fill(0)
    ssd.text(txt[ofs:ofs+15], pxs, 0)
    ssd.show()
