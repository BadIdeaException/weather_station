import lgpio

class I2C:
    def __init__(self, bus, address):
        self.address = address
        self._handle = lgpio.i2c_open(bus, address)

    def close(self):
        lgpio.i2c_close(self._handle)

    def read_byte(self, register):
        return lgpio.i2c_read_byte_data(self._handle, register)

    def write_byte(self, register, value):
        lgpio.i2c_write_byte_data(self._handle, register, value)

    def read_block(self, register, count):
        _, data = lgpio.i2c_read_i2c_block_data(self._handle, register, count)
        return bytes(data)

