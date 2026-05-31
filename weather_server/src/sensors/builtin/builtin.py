from .bme280 import BME280
import asyncio

class Builtin:
    def __init__(self, interval, bme280: BME280 | None = None):
        if bme280 is None:
            bme280 = BME280(1, 0x76, ttl=1.0)
            bme280.mode = BME280.Mode.FORCED

        self.bme280 = bme280
        self.interval = interval
        self._closed = False

    async def readings(self):
        while not self._closed:
            yield {
                'temperature': self.bme280.temperature, 
                'pressure':    self.bme280.pressure,
                'humidity':    self.bme280.humidity
            }
            await asyncio.sleep(self.interval)

    def close(self):
        self._closed = True
        self.bme280.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        