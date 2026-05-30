from sensors.tchibo.receiver.demodulator import Demodulator


class TestDemodulator:
    ZERO = 10
    ONE  = 20
    TOLERANCE = 4

    def generate_frame(self, bits, t0: float = 0, jitter: float = 0, pulse: float = 1): 
        t = t0
        sign = -1

        result = []
        for bit in bits:
            delta_t = (self.ZERO, self.ONE)[bit]
            
            result.append((t, 1))
            t += pulse
            result.append((t, 0))
            t += delta_t + jitter * sign
            sign *= -1

        result.append((t, 1))
        t += pulse
        result.append((t, 0))

        return result

    def test_decodes_symbols(self):
        demod = Demodulator(self.ZERO, self.ONE)

        frame = self.generate_frame((0,))
        assert demod.demodulate(frame) == '0'

        frame = self.generate_frame((1,))
        assert demod.demodulate(frame) == '1'

        frame = self.generate_frame((0, 1, 0))
        assert demod.demodulate(frame) == '010'

    def test_respects_tolerances(self):
        demod = Demodulator(self.ZERO, self.ONE, self.TOLERANCE)

        frame = self.generate_frame((0, 1), jitter = self.TOLERANCE / 2)
        assert demod.demodulate(frame) == '01'

    def test_ignores_invalid_symbols(self):
        demod = Demodulator(self.ZERO, self.ONE)

        frame = self.generate_frame((0, 1, 0))
        # Corrupt the leading edge of the "1" bit
        corruption = 0.5 * self.ZERO
        frame = frame[:4] + [
            (t - corruption, v) for t, v in frame[4:]
        ]
                
        assert demod.demodulate(frame) == '00'

    def test_too_short_frame(self):
        demod = Demodulator(self.ZERO, self.ONE)

        assert demod.demodulate(()) == ''
        assert demod.demodulate(((0, 0), )) == ''