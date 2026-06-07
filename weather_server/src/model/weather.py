from dataclasses import dataclass

@dataclass
class WeatherData:
    inside_temperature: float | None
    inside_humidity: float | None
    outside_temperature: float | None
    outside_humidity: float | None
    pressure: float | None
