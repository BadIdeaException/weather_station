from __future__ import annotations
from .edge_source import EdgeSource
import threading
import time
import asyncio
from queue import Queue
from collections.abc import Callable

class Framer:
    """
    The framer collects edges from an edge source into a frame, until it encounters a silence of duration
    `timeout`. Frames are tuples of timestamped edge transitions. 

    It does this through polling on a dedicated thread. The thread is woken on the first rising edge and suspended after
    timeout.

    Frames are emitted from `frames()`. This is a single-consumer generator that yields frames as they are picked up from the
    edge source. 
    """
    class Collector(threading.Thread):
        """
        The collector thread collects edges into a frame.

        Collection starts after each call to `start_capture`. It ends when nothing is received for `timeout` seconds.
        """

        on_finish: Callable | None

        def __init__(self, timeout, source, max_length=500):
            super().__init__(daemon = True)
            self._wake_up = threading.Event()
            self.timeout = timeout
            self.source = source
            self.on_finish = None
            self._closed = False
            self.max_length = max_length

        def start_capture(self):
            if not self._wake_up.is_set():
                self._wake_up.set()

        def close(self):
            self._closed = True
            self._wake_up.set()

        def run(self):
            def collect_edges():
                t_last = time.monotonic()
                val_last = self.source.read()
                edges = [ (t_last, val_last) ]

                while True:
                    t = time.monotonic()
                    val = self.source.read()

                    if val != val_last:
                        edges.append((t, val))
                        t_last = t
                        val_last = val
                    elif t - t_last > self.timeout:
                        break
                    
                    if len(edges) > self.max_length:
                        return []

                return edges

            while True:
                self._wake_up.wait()
                if self._closed: 
                    break

                edges = collect_edges()
                if self.on_finish is not None:
                    self.on_finish(edges)
                self._wake_up.clear()

    def __init__(self, timeout: float, source: EdgeSource, max_length=500):
        def start(timestamp, level, source):
            # Callback to run on the first rising edge from the edge source.
            # Temporarily disabled rising-edge-notifications to prevent callback storm,
            # and wakes up the collector thread to start polling 
            self.source.on_rising = None
            self.collector.start_capture()

        def finish(edges):
            # Callback to run when collector has finished a frame
            # Puts the frame into the frame queue, and re-enables
            # first rising edge notification callback
            self._frames.put(edges)
            self.source.on_rising = start

        self.timeout = timeout
        self.source = source
        self._frames = Queue()

        # on_rising will execute on the lgpio interrupt callback thread
        self.source.on_rising = start
        
        self.collector = self.Collector(timeout, source, max_length=max_length)
        # on_finish will execute on the collector thread (but marshals onto the application main thread)
        self.collector.on_finish = finish
        self.collector.start()

    def close(self):
        self.source.on_rising = None
        self.collector.close()
        self._frames.put(None) # Close the queue

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

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
