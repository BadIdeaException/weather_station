import lgpio

class SPI:
    def __init__(self, bus=0, device=0, speed=1_000_000, mode=0):
        self._handle = lgpio.spi_open(bus, device, speed, mode & 0x03)

    def close(self):
        lgpio.spi_close(self._handle)

    def write(self, data):
        lgpio.spi_write(self._handle, data)

    def read(self): 
        lgpio.spi_read(self._handle)

    def xfer(self, data):
        count, out_data = lgpio.spi_xfer(self._handle, data)
        return out_data