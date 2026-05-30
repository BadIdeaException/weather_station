from .receiver import Receiver
from .infactory import InFactory

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

    async def readings(self):
        decoder = InFactory()
        with self.receiver as receiver:
            async for packet in receiver.receive():
                try:
                    reading = decoder.decode(packet)
                    yield reading
                except ValueError:
                    pass # silently ignore packets with wrong length, as they are a normal part of RF operation
