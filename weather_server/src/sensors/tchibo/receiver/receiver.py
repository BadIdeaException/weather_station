from weather_hardware.cc1101 import CC1101
from .framer import Framer
from .demodulator import Demodulator

class Receiver:
    def __init__(self, timings: dict, cc1101: CC1101 | None = None):
        if cc1101 is None:
            cc1101 = CC1101()
            cc1101.frequency = 433.92
            cc1101.channel_bandwidth = CC1101.closest_channel_bandwidth(203) # 203 kHz
            cc1101.mod_format    = CC1101.ModulationFormat.ASK_OOK
            cc1101.sync_mode     = 0
            cc1101.data_rate     = cc1101.closest_data_rate(4800) # 4.8 kBaud
            if cc1101.gdo2 is not None:
                cc1101.gdo2.mode     = CC1101.IOConfig.SERIAL_DATA_OUT
            cc1101.white_data    = False
            cc1101.pkt_format    = CC1101.PacketFormat.ASYNCHRONOUS_SERIAL
            cc1101.crc_en        = False
            cc1101.length_config = CC1101.PacketLengthMode.INFINITE
            cc1101.cca_mode      = CC1101.CCAMode.RSSI_UNLESS_RECEIVING
            cc1101.rxoff_mode    = CC1101.TXRXOffMode.IDLE
            cc1101.txoff_mode    = CC1101.TXRXOffMode.IDLE
            cc1101.fs_autocal    = CC1101.Autocal.FROM_IDLE
            cc1101.po_timeout    = 2
            cc1101.fscal3        = 3    # SmartRF Studio
            cc1101.fscal3_res    = 0x0A # SmartRF Studio
            cc1101.vco_core_h_en = True
            cc1101.fscal2        = 0x0A # SmartRF Studio
            cc1101.fscal1        = 0x00 # SmartRF Studio
            cc1101.fscal0        = 0x1F # SmartRF Studio

        if cc1101.gdo2 is None:
            raise ValueError(f'Required GDO pin not available on CC1101')

        self.cc1101 = cc1101
        self.framer = Framer(timings['timeout'], cc1101.gdo2)
        self.demodulator = Demodulator(timings['zero'], timings['one'], timings['tolerance'])


    async def receive(self):
        self.cc1101.rx()
        try:
            async for frame in self.framer.frames():
                yield self.demodulator.demodulate(frame)
        finally:
            self.cc1101.idle()


    async def status(self):
        async for event in self.framer.status():
            yield event


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self.cc1101.close()
        self.framer.close()
