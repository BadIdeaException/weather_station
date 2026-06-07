import pytest
import asyncio
import time
from threading import Thread, Lock
from collections.abc import Callable
from sensors.tchibo.receiver.framer import Framer, FrameError

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
                    cb(t_next * 1e9, v_next, self)

        Thread(target=run, daemon=True).start()

    def stop(self):
        self._cancelled = True

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()

class TestFramer:
    @pytest.mark.asyncio
    async def test_silence_ends_frame(self):
        # A single spike
        edges = [
            (0.02, 0), (0.04, 1), (0.06, 0)
        ]
        with FakeEdgeSource(edges) as source, Framer(0.06, source) as framer:
            try:
                frame = await asyncio.wait_for(
                    anext(framer.frames()),
                    timeout=1.0)
            except TimeoutError:
                pytest.fail('Frame did not end')


    @pytest.mark.asyncio
    async def test_frame_contains_all_edges_in_right_sequence(self):
        # Two spikes in one frame
        edges = [
            (0.02, 0), (0.04, 1), (0.06, 0), (0.08, 1), (0.12, 0)
        ]
        with FakeEdgeSource(edges) as source, Framer(0.06, source) as framer:            
            frame = await asyncio.wait_for(anext(framer.frames()), timeout=1.0)

        # timestamps relative to the first edge
        # remember that first "edge" is actually starting state and therefore will have been dropped
        timestamps_actual = [ t - frame[0][0] for t, _ in frame ]
        timestamps_expected = [ t - edges[1][0] for t, _ in edges[1:] ]

        values_actual = [ v for _, v in frame ]
        values_expected = [ v for _, v in edges[1:] ]

        assert timestamps_actual == pytest.approx(timestamps_expected, abs=0.01)
        assert values_actual == values_expected


    @pytest.mark.asyncio
    async def test_yields_several_frames(self):
        # Two spikes in two frames
        # Note that because our fake edge source is a bit rudimentary we need to put quite a bit of silence in between
        edges = [
            (0.02, 0), (0.04, 1), (0.06, 0), 
            (0.14, 1), (0.16, 0)
        ]
        with FakeEdgeSource(edges) as source, Framer(0.06, source) as framer:
            gen = framer.frames()
            frames = [ await asyncio.wait_for(anext(gen), timeout=1.0), await asyncio.wait_for(anext(gen), timeout=1.0) ]

        assert len(frames) == 2


    @pytest.mark.asyncio
    async def test_aborts_on_very_long_frames(self):
        edges = [
            (0.02, 0), (0.04, 1), (0.06, 0), (0.08, 1), (0.12, 0)
        ]    

        with FakeEdgeSource(edges) as source, Framer(0.06, source, max_length=3) as framer:
            with pytest.raises(asyncio.TimeoutError):
                frame = await asyncio.wait_for(anext(framer.frames()), timeout=1.0)

            status = await asyncio.wait_for(anext(framer.status()), timeout=1.0)
            assert isinstance(status, FrameError)
