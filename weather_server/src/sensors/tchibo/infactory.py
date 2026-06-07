from __future__ import annotations
from crccheck.crc import Crc
crc4 = Crc(4, 0x13).calc


class CRCError(ValueError):
    def __init__(self, expected_crc, actual_crc):
        super().__init__(f'CRC check failed ({actual_crc} /= {expected_crc})')
        self.actual_crc = actual_crc
        self.expected_crc = expected_crc


class InFactory:
    """
    Decoder for the InFactory TH outdoor weather sensor
    """
    def raise_for_crc(self, bitstr):
        packet = bytearray(int(bitstr[i:i+8], 2) for i in range(0, 40, 8))

        # CRC lives in high nibble, so right-shift
        expected_crc = packet[1] >> 4

        # replace CRC nibble with channel nibble. See https://github.com/merbanan/rtl_433/blob/master/src/devices/infactory.c
        packet[1] = (packet[1] & 0x0F) | ((packet[4] & 0x0F) << 4)

        calculated_crc = crc4(packet[:4])
        # final XOR with humidity high nibble. https://github.com/merbanan/rtl_433/blob/master/src/devices/infactory.c
        calculated_crc ^= (packet[4] >> 4)

        if calculated_crc != expected_crc:
            raise CRCError(expected_crc, calculated_crc)
    
    def decode(self, bitstr):
        """
        Decodes an InFactory TH message into a `Reading`.

        Throws if bitstr is the wrong length, or the CRC4 check fails.
        """

        # Code is based on https://github.com/merbanan/rtl_433/blob/master/src/devices/infactory.c
        #
        # As shown there, message layout is as follows.
        #    0000 1111 | 0011 0000 | 0101 1100 | 1110 0111 | 0110 0001
        #    iiii iiii | cccc ub?? | tttt tttt | tttt hhhh | hhhh ??nn
        #
        #      - i: identification // changes on battery switch
        #      - c: CRC-4 // CCITT checksum, see below for computation specifics
        #      - u: TX-button // also set for 3 sec at power-up
        #      - b: battery low // flag to indicate low battery voltage
        #      - h: Humidity // BCD-encoded, each nibble is one digit, 'A0' means 100%rH
        #      - t: Temperature // in °F as binary number with one decimal place + 90 °F offset
        #      - n: Channel // Channel number 1 - 3
        if len(bitstr) != 40:
            raise ValueError(f'Packet has wrong length. Expected 40 but got {len(bitstr)}. Packet was {bitstr}.')          
        
        self.raise_for_crc(bitstr)
        
        device_id   = int(bitstr[0:8], 2)
        # bits 8-11 CRC
        # bit 12 TX button
        battery_low = int(bitstr[13], 2)
        # bits 14-15 unknown
        temp_raw    = int(bitstr[16:28], 2)
        hum_high    = int(bitstr[28:32], 2)
        hum_low     = int(bitstr[32:36], 2)
        # bits 36-37 unknown
        channel     = int(bitstr[38:40], 2)

        temp_f = temp_raw / 10.0 - 90.0

        return {
            'device_id'  : device_id,
            'battery_low': bool(battery_low), 
            'temperature': (temp_f - 32) * 5 /9,    # convert to °C
            'humidity':    hum_high * 10 + hum_low, # convert to int
            'channel':     channel,
        }
