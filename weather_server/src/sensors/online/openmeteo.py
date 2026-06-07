import httpx2
import asyncio

class OpenMeteo:
    URL = "https://api.open-meteo.com/v1/forecast"
    location: tuple[float, float]

    def __init__(self, location: tuple[float, float]):
        self.location = location

    async def read(self):
        async with httpx2.AsyncClient() as client:
            params = {
                "latitude": self.location[0],
                "longitude": self.location[1],
                "current": [
                    "wind_speed_10m",
                    "wind_gusts_10m",
                    "wind_direction_10m",
                    "weather_code"
                ]
            }
            resp = await client.get(self.URL, params=params)
            resp.raise_for_status()
            return resp.json()
