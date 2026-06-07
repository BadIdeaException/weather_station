from .openmeteo import OpenMeteo
from httpx2 import HTTPError
import asyncio

class Online:
    def __init__(self, interval: float, provider: OpenMeteo | None = None):
        if provider is None:
            provider = OpenMeteo((52.98163575145548, 8.865286704611929))

        self.provider = provider
        self.interval = interval
        self._closed = False
        self._status = asyncio.Queue()

    async def status(self):
        while True:
            yield await self._status.get()

    async def readings(self):
        while True:
            try:
                data = await self.provider.read()
                yield {
                    'code': data['current']['weather_code'],
                    'wind_direction': data['current']['wind_direction_10m'],
                    'wind_speed': data['current']['wind_speed_10m'],
                    'wind_gusts': data['current']['wind_gusts_10m']
                }
            except HTTPError as e:
                self._status.put_nowait(e)

            await asyncio.sleep(self.interval)


