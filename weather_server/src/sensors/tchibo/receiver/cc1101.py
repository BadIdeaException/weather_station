from __future__ import annotations
from enum import IntEnum
from typing import Generic, TypeVar
import lgpio


F_X_OSC = 26e06  # Frequency of the crystal oscillator is 26.0 MHz

# Wiring
GDO_PINS = (25, None, 24)  # GDO1 is disabled by default because it is shared with MISO

# Communication constants
WRITE_SINGLE = 0x00
WRITE_BURST = 0x40
READ_SINGLE = 0x80
READ_BURST = 0xC0

# Configuration register addresses
IOCFG2 = 0x00
IOCFG1 = 0x01
IOCFG0 = 0x02
PKTCTRL0 = 0x08
FREQ2 = 0x0D
FREQ1 = 0x0E
FREQ0 = 0x0F
MDMCFG4 = 0x10
MDMCFG3 = 0x11
MDMCFG2 = 0x12
MCSM2 = 0x16
MCSM1 = 0x17
MCSM0 = 0x18
AGCCTRL2 = 0x1B
FREND1 = 0x21
FSCAL3 = 0x23
FSCAL2 = 0x24
FSCAL1 = 0x25
FSCAL0 = 0x26

# Status register addresses
PARTNUM = 0x30
VERSION = 0x31
RSSI = 0x34

# Command strobes
SRES = 0x30
SRX = 0x34
SIDLE = 0x36


def withbits(value, mask, bits):
    shift = (mask & -mask).bit_length() - 1
    return (value & ~mask) | ((bits << shift) & mask)


def atbits(value, mask):
    shift = (mask & -mask).bit_length() - 1
    return (value & mask) >> shift


T = TypeVar("T")
class RegisterField(Generic[T]):
    def __init__(self, register, mask, typ=int):
        self.register = register
        self.mask = mask
        self.typ = typ

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None) -> T:
        if obj is None:
            return self

        value = atbits(obj.spi.read_single(self.register), self.mask)
        return self.typ(value)

    def __set__(self, obj, value: T):
        if self.typ is bool:
            value = int(value)

        elif issubclass(self.typ, IntEnum):
            if not isinstance(value, self.typ):
                raise ValueError(
                    f"{value} is not a valid {self.typ.__name__} for field {self.name}"
                )

            value = value.value

        register_value = obj.spi.read_single(self.register)
        register_value = withbits(register_value, self.mask, value)

        obj.spi.write_single(self.register, register_value)


class CC1101:
    CHANNEL_BANDWIDTHS = [
        (F_X_OSC / (8 * (4 + mantissa) * 2**exponent)) / 1e3
        for exponent in range(4)
        for mantissa in range(4)
    ]

    DATA_RATES = [
        # Per spec:
        # F_X_OSC * ((256 + mantissa) * 2**exponent) / 2**28
        (256 + mantissa) * 2**exponent * F_X_OSC
        for exponent in range(-28, -12)
        for mantissa in range(256)
    ]

    class SPI:
        def __init__(self, bus=0, device=0, mode=0):
            self._handle = lgpio.spi_open(bus, device, 50000, mode & 0x03)

        def close(self):
            lgpio.spi_close(self._handle)

        def write_single(self, addr, value):
            lgpio.spi_write(self._handle, [addr | WRITE_SINGLE, value])

        def read_single(self, addr):
            _, rx = lgpio.spi_xfer(self._handle, [addr | READ_SINGLE, 0x00])
            return rx[1]

        def write_burst(self, addr, value):
            lgpio.spi_write(self._handle, [addr | WRITE_BURST, value])

        def read_burst(self, addr):
            _, rx = lgpio.spi_xfer(self._handle, [addr | READ_BURST, 0x00])
            return rx[1]

        def strobe(self, cmd):
            lgpio.spi_write(self._handle, [cmd])

    class GDO:
        def __init__(self, pin, parent, gdo_number):
            self.pin = pin

            self._parent = parent
            self._gdo_number = gdo_number

            self._gpio = lgpio.gpiochip_open(0)
            self._cb_handle = None

            # Register callbacks lazily to avoid callback storm on
            # unused GDO pins
            self._on_rising = None
            self._on_falling = None

            self.on_error = None

        def _callback(self, chip, pin, level, timestamp):
            cb = self._on_rising if level == 1 else self._on_falling

            if cb is not None:
                cb(timestamp, level, source=self)

        @property
        def on_rising(self):
            return self._on_rising

        @on_rising.setter
        def on_rising(self, cb):
            # Register GPIO callback if not already present
            # Only one callback can be registered, so it needs to be
            # both for rising and falling edge
            if cb and not self._cb_handle:
                lgpio.gpio_claim_alert(self._gpio, self.pin, lgpio.BOTH_EDGES)

                self._cb_handle = lgpio.callback(
                    self._gpio,
                    self.pin,
                    lgpio.BOTH_EDGES,
                    self._callback,
                )

            # Deregister GPIO callback if this was the last callback
            # and it is being unset
            elif not cb and self._cb_handle and not self._on_falling:
                lgpio.gpio_free(self._gpio, self.pin)
                self._cb_handle.cancel()
                self._cb_handle = None

            self._on_rising = cb

        @property
        def on_falling(self):
            return self._on_falling

        @on_falling.setter
        def on_falling(self, cb):
            # Register GPIO callback if not already present
            # Only one callback can be registered, so it needs to be
            # both for rising and falling edge
            if cb and not self._cb_handle:
                self._cb_handle = lgpio.callback(
                    self._gpio,
                    self.pin,
                    lgpio.BOTH_EDGES,
                    self._callback,
                )

            # Deregister GPIO callback if this was the last callback
            # and it is being unset
            elif not cb and self._cb_handle and not self._on_rising:
                self._cb_handle.cancel()
                self._cb_handle = None

            self._on_falling = cb

        @property
        def mode(self) -> CC1101.IOConfig:
            return getattr(self._parent, f"gdo{self._gdo_number}_cfg")

        @mode.setter
        def mode(self, value: CC1101.IOConfig):
            setattr(self._parent, f"gdo{self._gdo_number}_cfg", value)

        @property
        def inverted(self) -> bool:
            return getattr(self._parent, f"gdo{self._gdo_number}_inv")

        @inverted.setter
        def inverted(self, value: bool):
            setattr(self._parent, f"gdo{self._gdo_number}_inv", value)

        def read(self) -> int:
            return lgpio.gpio_read(self._gpio, self.pin)

        def close(self):
            if self._cb_handle:
                self._cb_handle.cancel()
                self._cb_handle = None

                lgpio.gpio_free(self._gpio, self.pin)

            lgpio.gpiochip_close(self._gpio)

    class ModulationFormat(IntEnum):
        FSK2 = 0
        GFSK = 1
        ASK_OOK = 3
        FSK4 = 4
        MSK = 7

    class PacketFormat(IntEnum):
        NORMAL = 0
        SYNCHRONOUS_SERIAL = 1
        RANDOM = 2
        ASYNCHRONOUS_SERIAL = 3

    class PacketLengthMode(IntEnum):
        FIXED = 0
        VARIABLE = 1
        INFINITE = 2

    class IOConfig(IntEnum):
        RX_FIFO_THRESHOLD = 0x00
        RX_FIFO_THRESHOLD_OR_EOP = 0x01
        TX_FIFO_THRESHOLD = 0x02
        TX_FIFO_FULL = 0x03
        RX_FIFO_OVERFLOW = 0x04
        TX_FIFO_UNDERFLOW = 0x05
        SYNC_WORD_SENT_OR_RECEIVED = 0x06
        PACKET_CRC_OK = 0x07
        CLEAR_CHANNEL_ASSESSMENT = 0x09
        PLL_LOCK_DETECT = 0x0A
        SERIAL_CLOCK = 0x0B
        SERIAL_SYNC_DATA_OUT = 0x0C
        SERIAL_DATA_OUT = 0x0D
        CARRIER_SENSE = 0x0E
        CRC_OK = 0x0F
        RX_HARD_DATA_0 = 0x11
        TX_HARD_DATA_0 = 0x12
        RX_SYMBOL_TICK = 0x13
        PA_PD = 0x1B
        LNA_PD = 0x1C
        RX_TIMEOUT = 0x1D
        WOR_EVENT0 = 0x24
        WOR_EVENT1 = 0x25
        CLK_32K = 0x27
        CHIP_RDY_N = 0x29
        XOSC_STABLE = 0x2B
        HIGH_IMPEDANCE = 0x2E
        HARDWARE_0 = 0x2F
        CLK_XOSC_1 = 0x30
        CLK_XOSC_1_5 = 0x31
        CLK_XOSC_2 = 0x32
        CLK_XOSC_3 = 0x33
        CLK_XOSC_4 = 0x34
        CLK_XOSC_6 = 0x35
        CLK_XOSC_8 = 0x36
        CLK_XOSC_12 = 0x37
        CLK_XOSC_16 = 0x38
        CLK_XOSC_24 = 0x39
        CLK_XOSC_32 = 0x3A
        CLK_XOSC_48 = 0x3B
        CLK_XOSC_64 = 0x3C
        CLK_XOSC_96 = 0x3D
        CLK_XOSC_128 = 0x3E
        CLK_XOSC_192 = 0x3F

    class CCAMode(IntEnum):
        ALWAYS = 0
        RSSI = 1
        UNLESS_RECEIVING = 2
        RSSI_UNLESS_RECEIVING = 3

    class TXRXOffMode(IntEnum):
        IDLE = 0
        FSTXON = 1
        TX = 2
        RX = 3

    class Autocal(IntEnum):
        NEVER = 0
        FROM_IDLE = 1
        TO_IDLE = 2
        TO_IDLE_INTERMITTENT = 3

    def __init__(self):
        self.spi = CC1101.SPI()
        self.reset()
        for i, pin in enumerate(GDO_PINS):
            setattr(                
                self, 
                f"gdo{i}", 
                CC1101.GDO(pin, self, i) if pin is not None else None,
            )

        if self.partnum != 0x00 or self.version != 0x14:
            raise RuntimeError('Radio module not found')

    def close(self):
        for i in range(3):
            gdo = getattr(self, f"gdo{i}")

            if gdo is not None:
                gdo.close()

        self.spi.close()

    # Typed dynamic attributes
    gdo0: GDO | None
    gdo1: GDO | None
    gdo2: GDO | None

    # Register fields
    mod_format = RegisterField(MDMCFG2, 0x70, ModulationFormat)
    sync_mode = RegisterField(MDMCFG2, 0x07)

    white_data = RegisterField(PKTCTRL0, 0x40, bool)
    pkt_format = RegisterField(PKTCTRL0, 0x30, PacketFormat)
    crc_en = RegisterField(PKTCTRL0, 0x04, bool)
    length_config = RegisterField(PKTCTRL0, 0x03, PacketLengthMode)

    gdo2_cfg = RegisterField(IOCFG2, 0x3F, IOConfig)
    gdo1_cfg = RegisterField(IOCFG1, 0x3F, IOConfig)
    gdo0_cfg = RegisterField(IOCFG0, 0x3F, IOConfig)

    gdo2_inv = RegisterField(IOCFG2, 0x40, bool)
    gdo1_inv = RegisterField(IOCFG1, 0x40, bool)
    gdo0_inv = RegisterField(IOCFG0, 0x40, bool)

    rx_time_rssi = RegisterField(MCSM2, 0x10, bool)
    rx_time_qual = RegisterField(MCSM2, 0x08, bool)
    rx_time = RegisterField(MCSM2, 0x07)

    cca_mode = RegisterField(MCSM1, 0x30, CCAMode)
    rxoff_mode = RegisterField(MCSM1, 0x0C, TXRXOffMode)
    txoff_mode = RegisterField(MCSM1, 0x03, TXRXOffMode)

    fs_autocal = RegisterField(MCSM0, 0x30, Autocal)
    po_timeout = RegisterField(MCSM0, 0x0C)
    pin_ctrl_en = RegisterField(MCSM0, 0x02, bool)
    xosc_force_on = RegisterField(MCSM0, 0x01, bool)

    max_dvga_gain = RegisterField(AGCCTRL2, 0xC0)
    max_lna_gain = RegisterField(AGCCTRL2, 0x38)
    magn_target = RegisterField(AGCCTRL2, 0x07)

    lna_current = RegisterField(FREND1, 0xC0)
    lna2mix_current = RegisterField(FREND1, 0x30)
    lodiv_buf_current_rx = RegisterField(FREND1, 0x0C)
    mix_current = RegisterField(FREND1, 0x03)

    fscal3 = RegisterField(FSCAL3, 0xC0)
    chp_curr_cal_en = RegisterField(FSCAL3, 0x30)
    fscal3_res = RegisterField(FSCAL3, 0x0F)

    vco_core_h_en = RegisterField(FSCAL2, 0x20, bool)
    fscal2 = RegisterField(FSCAL2, 0x1F)

    fscal1 = RegisterField(FSCAL1, 0x3F)

    fscal0 = RegisterField(FSCAL0, 0x7F)

    @property
    def frequency(self) -> float:
        freq0 = self.spi.read_single(FREQ0)
        freq1 = self.spi.read_single(FREQ1)
        freq2 = self.spi.read_single(FREQ2)

        return (F_X_OSC / 2**16 * ((freq2 << 16) | (freq1 << 8) | freq0)) / 1e06

    @frequency.setter
    def frequency(self, value: float):
        value = round(value * 1e06 * 2**16 / F_X_OSC)

        freq0 = value & 0xFF
        freq1 = (value >> 8) & 0xFF
        freq2 = (value >> 16) & 0xFF

        self.spi.write_single(FREQ0, freq0)
        self.spi.write_single(FREQ1, freq1)
        self.spi.write_single(FREQ2, freq2)

    @property
    def channel_bandwidth(self):
        register_value = self.spi.read_single(MDMCFG4)

        mantissa = atbits(register_value, 0x30)
        exponent = atbits(register_value, 0xC0)

        return (F_X_OSC / (8 * (4 + mantissa) * 2**exponent)) / 1e3

    @channel_bandwidth.setter
    def channel_bandwidth(self, value):
        if value not in CC1101.CHANNEL_BANDWIDTHS:
            raise ValueError(
                f"Illegal channel bandwidth {value}. "
                f"Must be one of {CC1101.CHANNEL_BANDWIDTHS}"
            )

        index = CC1101.CHANNEL_BANDWIDTHS.index(value)

        exponent = index // 4
        mantissa = index % 4

        register_value = self.spi.read_single(MDMCFG4)
        register_value = withbits(register_value, 0xC0, exponent)
        register_value = withbits(register_value, 0x30, mantissa)

        self.spi.write_single(MDMCFG4, register_value)

    @classmethod
    def closest_channel_bandwidth(cls, value) -> float:
        """
        Finds the closest valid channel bandwidth to `value`.
        """
        return min(cls.CHANNEL_BANDWIDTHS, key=lambda bw: abs(bw - value))

    @property
    def data_rate(self):
        exponent = atbits(self.spi.read_single(MDMCFG4), 0x0F)
        mantissa = self.spi.read_single(MDMCFG3)

        return F_X_OSC * (256 + mantissa) * 2**(exponent - 28)

    @data_rate.setter
    def data_rate(self, value):
        if value not in CC1101.DATA_RATES:
            raise ValueError(f"Illegal data rate {value}")

        index = CC1101.DATA_RATES.index(value)

        exponent = index // 256
        mantissa = index % 256

        register_value = self.spi.read_single(MDMCFG4)
        register_value = withbits(register_value, 0x0F, exponent)

        self.spi.write_single(MDMCFG4, register_value)
        self.spi.write_single(MDMCFG3, mantissa)

    @classmethod
    def closest_data_rate(cls, value) -> float:
        """
        Finds the closest valid data rate to `value`.
        """
        return min(cls.DATA_RATES, key=lambda dr: abs(dr - value))

    @property
    def partnum(self):
        return self.spi.read_burst(PARTNUM)

    @property
    def version(self):
        return self.spi.read_burst(VERSION)

    @property
    def rssi(self):
        return self.spi.read_burst(RSSI)

    def reset(self):
        self.spi.strobe(SRES)

    def rx(self):
        self.spi.strobe(SRX)

    def idle(self):
        self.spi.strobe(SIDLE)
