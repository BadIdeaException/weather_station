from .bme280 import BME280
import asyncio

class Builtin:
    def __init__(self, interval, bme280: BME280 | None = None):
        if bme280 is None:
            bme280 = BME280(1, 0x76, ttl=1.0)            
            bme280.temperature_oversampling = BME280.Oversampling.X1
            bme280.pressure_oversampling    = BME280.Oversampling.X1
            bme280.humidity_oversampling    = BME280.Oversampling.X1

        self.bme280 = bme280
        self.interval = interval

    async def readings(self):
        def wait_for_measurement():
            while self.bme280.measuring:
                pass

        while True:
            # Force a measurement
            self.bme280.mode = BME280.Mode.FORCED
            # Wait until measurement is complete
            await asyncio.to_thread(wait_for_measurement)
            yield {
                'temperature': self.bme280.temperature, 
                'pressure':    self.bme280.pressure,
                'humidity':    self.bme280.humidity
            }
            await asyncio.sleep(self.interval)

    def close(self):
        self.bme280.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        