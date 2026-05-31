from __future__ import annotations
from enum import IntEnum
import lgpio
import time
from dataclasses import dataclass
from struct import unpack_from
from typing import cast

# Register addresses
ID = 0xD0
RESET = 0xE0
STATUS = 0xF3
CTRL_MEAS = 0xF4
CONFIG = 0xF5
CTRL_HUM = 0xF2

PRESS_MSB = 0xF7

# Operation constants
DEVICE_ADDRESS = 0x76 # As per spec p. 32
CHIP_ID = 0x60 # As per spec p. 27


class BME280:
    class Oversampling(IntEnum):
        SKIP = 0
        X1 = 1
        X2 = 2
        X4 = 3
        X8 = 4
        X16 = 5


    class Mode(IntEnum):
        SLEEP = 0
        FORCED = 1
        NORMAL = 3


    class StandbyTime(IntEnum):
        MS_0_5 = 0
        MS_62_5 = 1
        MS_125 = 2
        MS_250 = 3
        MS_500 = 4
        MS_1000 = 5
        MS_10 = 6
        MS_20 = 7


    class Filter(IntEnum):
        OFF = 0
        X2 = 1
        X4 = 2
        X8 = 3
        X16 = 4

    @dataclass
    class Calibration:
        dig_T1: int
        dig_T2: int
        dig_T3: int

        dig_P1: int
        dig_P2: int
        dig_P3: int
        dig_P4: int
        dig_P5: int
        dig_P6: int
        dig_P7: int
        dig_P8: int
        dig_P9: int

        dig_H1: int
        dig_H2: int
        dig_H3: int
        dig_H4: int
        dig_H5: int
        dig_H6: int

    class I2C:
        def __init__(self, bus, address):
            self.address = address
            self.handle = lgpio.i2c_open(bus, address)

        def close(self):
            lgpio.i2c_close(self.handle)

        def read_byte(self, register):
            return lgpio.i2c_read_byte_data(self.handle, register)

        def write_byte(self, register, value):
            lgpio.i2c_write_byte_data(self.handle, register, value)

        def read_block(self, register, count):
            _, data = lgpio.i2c_read_i2c_block_data(self.handle, register, count)
            return bytes(data)


    def __init__(self, bus=1, address=DEVICE_ADDRESS, ttl=1.0):
        self.i2c = self.I2C(bus, address)

        if self.chip_id != CHIP_ID:
            raise RuntimeError("BME280 not found")

        self._read_calibration()
        self.ttl = ttl

        self._t_last = None
        self._adc_last = None

    def close(self):
        self.i2c.close()

    @property
    def chip_id(self):
        return self.i2c.read_byte(ID)

    def reset(self):
        self.i2c.write_byte(RESET, 0xB6)

    @property
    def measuring(self):
        return bool(self.i2c.read_byte(STATUS) & 0x08)

    @property
    def im_update(self):
        return bool(self.i2c.read_byte(STATUS) & 0x01)

    @property
    def mode(self):
        return self.Mode(self.i2c.read_byte(CTRL_MEAS) & 0x03)

    @mode.setter
    def mode(self, value):
        reg = self.i2c.read_byte(CTRL_MEAS)
        reg = (reg & ~0x03) | value.value
        self.i2c.write_byte(CTRL_MEAS, reg)
        self._t_last = self._adc_last = None # Invalidate cache

    @property
    def temperature_oversampling(self):
        return self.Oversampling(
            (self.i2c.read_byte(CTRL_MEAS) >> 5) & 0x07
        )

    @temperature_oversampling.setter
    def temperature_oversampling(self, value):
        reg = self.i2c.read_byte(CTRL_MEAS)
        reg = (reg & ~0xE0) | (value.value << 5)
        self.i2c.write_byte(CTRL_MEAS, reg)
        self._t_last = self._adc_last = None # Invalidate cache

    @property
    def pressure_oversampling(self):
        return self.Oversampling((self.i2c.read_byte(CTRL_MEAS) >> 2) & 0x07)

    @pressure_oversampling.setter
    def pressure_oversampling(self, value):
        reg = self.i2c.read_byte(CTRL_MEAS)
        reg = (reg & ~0x1C) | (value.value << 2)
        self.i2c.write_byte(CTRL_MEAS, reg)
        self._t_last = self._adc_last = None # Invalidate cache

    @property
    def humidity_oversampling(self):
        return self.Oversampling(self.i2c.read_byte(CTRL_HUM) & 0x07)

    @humidity_oversampling.setter
    def humidity_oversampling(self, value):
        self.i2c.write_byte(CTRL_HUM, value.value)
        self._t_last = self._adc_last = None # Invalidate cache

    def _read_calibration(self):    
        CALIB1 = 0x88 # See spec p24
        CALIB2 = 0xE1
        calib1 = self.i2c.read_block(CALIB1, 26)  
        calib2 = self.i2c.read_block(CALIB2, 7)  

        dig_T1, dig_T2, dig_T3 = unpack_from("<Hhh", calib1, 0)

        (
            dig_P1,
            dig_P2,
            dig_P3,
            dig_P4,
            dig_P5,
            dig_P6,
            dig_P7,
            dig_P8,
            dig_P9,
        ) = unpack_from("<Hhhhhhhhh", calib1, 6)

        dig_H1 = calib1[25]

        dig_H2 = unpack_from("<h", calib2, 0)[0]
        dig_H3 = calib2[2]

        dig_H4 = (calib2[3] << 4) | (calib2[4] & 0x0F)
        if dig_H4 & 0x800:
            dig_H4 -= 4096

        dig_H5 = (calib2[5] << 4) | (calib2[4] >> 4)
        if dig_H5 & 0x800:
            dig_H5 -= 4096

        dig_H6 = calib2[6]
        if dig_H6 > 127:
            dig_H6 -= 256

        self.calibration = self.Calibration(
            dig_T1, dig_T2, dig_T3,
            dig_P1, dig_P2, dig_P3,
            dig_P4, dig_P5, dig_P6,
            dig_P7, dig_P8, dig_P9,
            dig_H1, dig_H2, dig_H3,
            dig_H4, dig_H5, dig_H6,
        )

    @property
    def _t_fine(self):
        def compensate(adc_t: int) -> int:
            # See spec p. 25.l
            # This is the temperature compensation algorithm, except we return t_fine directly.
            # Compared to storing it as hidden state, this is more costly, but architecturally cleaner.
            c = self.calibration

            var1 = (((adc_t >> 3) - (c.dig_T1 << 1)) * c.dig_T2) >> 11
            var2 = (((((adc_t >> 4) - c.dig_T1) * ((adc_t >> 4) - c.dig_T1)) >> 12) * c.dig_T3) >> 14            

            t_fine = var1 + var2
            return t_fine

        adc_t, _ ,_ = self._adc
        return compensate(adc_t)


    @property
    def temperature(self):
        """
        The temperature in degrees Celcius.
        """
        
        # We don't compensate directly here, since most of that is done by self._t_fine
        # Instead we just use t_fine and perform the last step of Bosch's compensation algorithm
        temp = (self._t_fine * 5 + 128) >> 8 # Temperature in centidegrees Celsius.
        return temp / 100.0

    @property
    def pressure(self):
        """
        The barometric pressure in hPa.
        """
        def compensate(adc_p):
            # See spec p. 25:
            # Returns pressure in Pa as unsigned 32 bit integer in Q24.8 format (24 integer bits and 8 fractional bits).
            # Output value of “24674867” represents 24674867/256 = 96386.2 Pa = 963.862 hPa
            c = self.calibration

            var1 = self._t_fine - 128000
            var2 = var1 * var1 * c.dig_P6
            var2 = var2 + ((var1 * c.dig_P5) << 17)
            var2 = var2 + (c.dig_P4 << 35)

            var1 = ((var1 * var1 * c.dig_P3) >> 8) + ((var1 * c.dig_P2) << 12)            
            var1 = (((1 << 47) + var1) * c.dig_P1) >> 33

            if var1 == 0:
                return 0

            p = 1048576 - adc_p
            p = (((p << 31) - var2) * 3125) // var1

            var1 = (c.dig_P9 * (p >> 13) * (p >> 13)) >> 25
            var2 = (c.dig_P8 * p) >> 19

            p = ((p + var1 + var2) >> 8) + (c.dig_P7 << 4)

            return p

        _, adc_p, _ = self._adc
        return compensate(adc_p) / 25600.0

    @property
    def humidity(self):
        """
        The humidity in %RH.
        """
        def compensate(adc_h: int) -> int:
            # See spec p. 25:
            # Returns humidity in %RH as unsigned 32 bit integer in Q22.10 format (22 integer and 10 fractional bits).
            # Output value of “47445” represents 47445/1024 = 46.333 %RH
            c = self.calibration

            h = self._t_fine - 76800

            h = ((((adc_h << 14) - (c.dig_H4 << 20) - (c.dig_H5 * h) + 16384) >> 15) *
                 (((((h * c.dig_H6) >> 10) * (((h * c.dig_H3) >> 11) + 32768) >> 10)
                     + 2097152) * c.dig_H2 + 8192) >> 14)

            h -= ((((h >> 15) * (h >> 15)) >> 7) * c.dig_H1) >> 4

            h = max(h, 0)
            h = min(h, 419430400)

            return h >> 12        

        _, _, adc_h = self._adc
        return compensate(adc_h) / 1024.0

    @property
    def _adc(self):
        def read_raw():
            data = self.i2c.read_block(0xF7, 8)

            adc_p = (
                (data[0] << 12)
                | (data[1] << 4)
                | (data[2] >> 4)
            )

            adc_t = (
                (data[3] << 12)
                | (data[4] << 4)
                | (data[5] >> 4)
            )

            adc_h = (data[6] << 8) | data[7]

            return adc_t, adc_p, adc_h

        if self._t_last is None or time.monotonic() > self._t_last + self.ttl:
            self._adc_last = read_raw()
            self._t_last = time.monotonic()
        
        return cast(tuple[int, int, int], self._adc_last) # self._adc_last is guaranteed to be initialized at this point, but pyright doesn't understand that without being told explicitly