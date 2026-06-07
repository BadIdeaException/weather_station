import asyncio
import contextlib
from .receiver import Receiver
from .infactory import InFactory, CRCError, PacketLengthError

class Tchibo:
    def __init__(self, receiver: Receiver | None = None):
        if receiver is None:
            timings = {
                'zero': 2000e-6,
                'one': 4000e-6,
                'timeout': 5000e-6,
                'tolerance': 750e-6
            }
            receiver = Receiver(timings)

        self.receiver = receiver
        self._status = asyncio.Queue(maxsize=100)


    async def readings(self):
        decoder = InFactory()
        with self.receiver as receiver:
            async for packet in receiver.receive():
                try:
                    reading = decoder.decode(packet)
                    yield reading
                except CRCError as e:
                    with contextlib.suppress(asyncio.QueueFull):
                        self._status.put_nowait(e)
                except PacketLengthError:
                    pass # silently ignore packets with wrong length, as they are a normal part of RF operation                


    async def status(self):
        async def forward_receiver_status():
            async for event in self.receiver.status():
                with contextlib.suppress(asyncio.QueueFull):
                    self._status.put_nowait(event)
        
        task = asyncio.create_task(forward_receiver_status())
        try:
            while True:
                yield await self._status.get()
        finally:
            task.cancel()


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


    def close(self):
        self.receiver.close()