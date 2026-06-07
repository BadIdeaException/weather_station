import asyncio
from sensors.builtin import Builtin
from sensors.tchibo import Tchibo
from sensors.online import Online
from dataclasses import dataclass
from model.weather import WeatherData


class DataEngine:
    data: WeatherData

    def __init__(self, builtin_interval: float = 1.0):
        self.builtin = Builtin(builtin_interval)
        self.tchibo  = Tchibo()
        self.online = Online(15.0)
        self.data = WeatherData(
            inside_temperature = None,
            inside_humidity = None,
            outside_temperature = None,
            outside_humidity = None,
            pressure = None,
            code = None,
            wind_direction = None,
            wind_speed = None,
            wind_gusts = None
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
            tg.create_task(collect(self.online))

            while True:
                source, reading = await queue.get()
                
                if source is self.builtin:
                    self.data.inside_temperature = reading['temperature']
                    self.data.pressure           = reading['pressure']
                    self.data.inside_humidity    = reading['humidity']
                elif source is self.tchibo:
                    self.data.outside_temperature = reading['temperature']
                    self.data.outside_humidity    = reading['humidity']
                elif source is self.online:
                    self.data.code = reading['code']
                    self.data.wind_direction = reading['wind_direction']
                    self.data.wind_speed = reading['wind_speed']
                    self.data.wind_gusts = reading['wind_gusts']

    def close(self):
        self.builtin.close()
        self.tchibo.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
