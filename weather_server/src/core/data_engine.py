import asyncio
from sensors.builtin import Builtin
from sensors.tchibo import Tchibo
from dataclasses import dataclass


@dataclass
class WeatherData:
    inside_temperature: float
    inside_humidity: float
    outside_temperature: float
    outside_humidity: float
    pressure: float


class DataEngine:
    data: WeatherData

    def __init__(self, builtin_interval: float = 1.0):
        self.builtin = Builtin(builtin_interval)
        self.tchibo  = Tchibo()
        self.data = WeatherData(
            inside_temperature = 0.0,
            inside_humidity = 0.0,
            outside_temperature = 0.0,
            outside_humidity = 0.0,
            pressure = 0.0
        )

    async def run(self):
        queue = asyncio.Queue()

        async def collect(source): 
            # Helper function that collects readings as they are emitted from the source and pushes them to the central queue,
            # tagged with the source they came from
            async for reading in source.readings():
                await queue.put((source, reading))


        async with asyncio.TaskGroup() as tg:
            tg.create_task(collect(self.builtin))
            tg.create_task(collect(self.tchibo))

            while True:
                source, reading = await queue.get()
                
                if source is self.builtin:
                    self.data.inside_temperature = reading['temperature']
                    self.data.pressure           = reading['pressure']
                    self.data.inside_humidity    = reading['humidity']
                elif source is self.tchibo:
                    self.data.outside_temperature = reading['temperature']
                    self.data.outside_humidity    = reading['humidity']

    def close(self):
        self.builtin.close()
        self.tchibo.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
