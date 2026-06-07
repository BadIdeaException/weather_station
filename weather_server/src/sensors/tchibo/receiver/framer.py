from __future__ import annotations
from .edge_source import EdgeSource
import threading
import asyncio
import contextlib
from queue import Queue, Full as QueueFullError


class FrameError(RuntimeError):
    def __init__(self, frame):
        super().__init__(f'Frame too long. Frame was {len(frame)} edges')
        self.frame = frame


class Framer:
    def __init__(self, timeout: float, source: EdgeSource, max_length=500):
        self.timeout = timeout
        self.max_length = max_length
        self.source = source
        
        self._frames = Queue()
        self._status = Queue(maxsize=100)
        self._current_frame = []
        self._lock = threading.Lock()
        self._timer = None

        # on_rising will execute on the lgpio interrupt callback thread
        self.source.on_rising = self.handle_edge
        self.source.on_falling = self.handle_edge

    def handle_edge(self, timestamp, level, source):
        timestamp *= 1.0e-9 # callback timestamps are in nanoseconds
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()

            self._current_frame.append((timestamp, level))
            if len(self._current_frame) > self.max_length:
                with contextlib.suppress(QueueFullError):
                    self._status.put_nowait(FrameError(self._current_frame))
                self._current_frame = []
                self._timer = None
                return

            self._timer = threading.Timer(self.timeout, self.handle_timeout)
            self._timer.start()

    def handle_timeout(self):
        with self._lock:
            frame = self._current_frame
            self._current_frame = []
            self._timer = None
        self._frames.put(frame)

    async def frames(self):
        """
        Yield captured frames from the edge source.

        Do not call `frames` multiple times over the same `Framer`.
        Multiple concurrent consumers will compete for frames and
        each frame will be delivered to at most one consumer.
        """        
        while True:
            frame = await asyncio.to_thread(self._frames.get)
            if frame is None:
                return
            yield tuple(frame)


    async def status(self):
        while True:
            event = await asyncio.to_thread(self._status.get)
            if event is None:
                break
            yield event


    def close(self):
        self.source.on_rising = None
        self.source.on_falling = None
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._frames.put_nowait(None)
            self._status.put_nowait(None)


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
