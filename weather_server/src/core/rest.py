from fastapi import FastAPI
from core.data_engine import DataEngine, WeatherData
from dataclasses import fields

class REST:
    PREFIX = '/api/v1'

    def __init__(self, engine: DataEngine):        
        self.engine = engine
        self.api = FastAPI()

        for field in fields(WeatherData):
            self.api.add_api_route(self.PREFIX + f'/weather/{field.name}', getattr(self, field.name), methods=['GET'])

        self.api.add_api_route(self.PREFIX + '/weather', self.weather, methods=['GET'])

    async def weather(self):
        return self.engine.data


def make_getter(field):
    async def getter(self):
        return getattr(self.engine.data, field)
    getter.__name__ = field
    return getter

for field in fields(WeatherData):
    setattr(REST, field.name, make_getter(field.name))