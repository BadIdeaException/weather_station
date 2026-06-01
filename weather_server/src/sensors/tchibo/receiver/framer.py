from __future__ import annotations
from .edge_source import EdgeSource
import threading
import time
import asyncio
from queue import Queue
from collections.abc import Callable

class Framer:
    def __init__(self, timeout: float, source: EdgeSource, max_length=500):
        self.timeout = timeout
        self.max_length = max_length
        self.source = source
        
        self._frames = Queue()
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
                break

            yield tuple(frame)


    def close(self):
        self.source.on_rising = None
        self.source.on_falling = None
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
        self._frames.put(None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
