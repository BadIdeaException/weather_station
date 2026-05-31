import asyncio
import pytest
import time
from sensors.tchibo import Tchibo
from sensors.tchibo.receiver import Receiver
from threading import Thread, Lock
from collections.abc import Callable

class FakeEdgeSource:
    on_rising: Callable | None
    on_falling: Callable | None

    def __init__(self, edges: list[tuple[float, int]]):
        self.on_rising = None
        self.on_falling = None

        self.edges = edges
        self.current = None
        self._lock = Lock()
        self._cancelled = False

    def read(self) -> int:            
        with self._lock:
            if self.current is None:
                raise RuntimeError('Cannot read an edge source that is not started')

            _, current_value = self.edges[self.current]
            return current_value

    def start(self):
        t0 = time.monotonic()
        self.current = 0

        def run():
            if self.current is None:
                raise RuntimeError('Edge source initialization failed')

            # No need to lock here, because self.current is only updated from this same thread,
            # and writes to self._cancelled are atomic
            # At most we might be one edge late if it races
            while self.current < len(self.edges) - 1 and not self._cancelled:
                t_next = self.edges[self.current + 1][0]
                t = time.monotonic() - t0

                delay = t_next - t
                if delay > 0:
                    time.sleep(delay)

                # Process edge
                with self._lock:
                    v_last = self.edges[self.current][1]
                    self.current += 1
                    t_next, v_next = self.edges[self.current]
                    t_next += t0

                # Run callback for edge
                cb = None
                if v_next - v_last == +1:
                    cb = self.on_rising
                elif v_next - v_last == -1:
                    cb = self.on_falling

                if cb is not None:
                    cb(t_next, v_next, self)

        Thread(target=run, daemon=True).start()

    def stop(self):
        self._cancelled = True

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()


class FakeCC1101:
    def __init__(self, edges):
        self.gdo2 = FakeEdgeSource(edges)        

    def rx(self): pass
    def idle(self): pass

def encode(bits, timings, pulse = None):
    if pulse is None:
        pulse = min(timings['zero'], timings['one']) / 2
    result = [ (0.02, 0) ]
    
    t = 0.04
    result += [ (t, 1), (t + pulse, 0) ]
    t += pulse
    for bit in bits:
        if bit == '1':
            t += timings['one']
        elif bit == '0':
            t += timings['zero']

        result += [ (t, 1), (t + pulse, 0) ]
        t += pulse

    return result

class TestTchiboIntegration:
    @pytest.mark.asyncio
    async def test_decodes_real_packet(self):
        TIMINGS = {
            'zero': 0.02,
            'one': 0.04,
            'timeout': 0.08,
            'tolerance': 0.01
        }
        edges = encode('0000111100110000010111001110011101100001', TIMINGS, pulse=0.01)                        
        cc1101 = FakeCC1101(edges)
        receiver = Receiver(TIMINGS, cc1101)
        tchibo = Tchibo(receiver)

        with cc1101.gdo2:
            readings = await asyncio.wait_for(anext(tchibo.readings()), timeout=40 * max(TIMINGS['one'], TIMINGS['zero']) + 40 * 0.01)

        assert readings['device_id'] == 0x0F
        assert readings['battery_low'] == False
        assert readings['temperature'] == pytest.approx(14.777777)
        assert readings['humidity'] == 76
        assert readings['channel'] == 1
