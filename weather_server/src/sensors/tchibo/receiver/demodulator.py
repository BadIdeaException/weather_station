class Demodulator:
    def __init__(self, zero, one, tolerance=0):
        self.zero = zero
        self.one  = one
        self.tolerance = tolerance

    def demodulate(self, frame):
        RISING = +1
        FALLING = -1
        ZERO_MIN = self.zero - self.tolerance
        ZERO_MAX = self.zero + self.tolerance
        ONE_MIN  = self.one  - self.tolerance
        ONE_MAX  = self.one  + self.tolerance

        if len(frame) < 2:
            return ''

        t_last, v_last = frame[0]
        packet = []

        for t, v in frame[1:]:
            gap = t - t_last
            direction = v - v_last

            t_last = t
            v_last = v

            if direction == FALLING:
                continue

            if ZERO_MIN <= gap <= ZERO_MAX:
                packet.append(0)
            elif ONE_MIN <= gap <= ONE_MAX:
                packet.append(1)
            else:
                # silently ignore invalid symbols
                pass

        return ''.join(map(str, packet))
