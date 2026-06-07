import pytest
import asyncio
import time
import contextlib
from httpx2 import HTTPStatusError, ConnectTimeout, NetworkError
from sensors.online import Online
from sensors.online.openmeteo import OpenMeteo


class TestOnline:
    @pytest.mark.asyncio
    async def test_emits_readings(self, mocker):
        DATA = {
            'weather_code': 10,
            'wind_speed_10m': 20.0,
            'wind_gusts_10m': 30.0,
            'wind_direction_10m': 330
        }
        provider = mocker.MagicMock(spec=OpenMeteo)
        provider.read.return_value = { 'current': DATA }
        
        online = Online(0.1, provider=provider)
        reading = await asyncio.wait_for(anext(online.readings()), 0.1)

        assert reading == {
            'code': DATA['weather_code'],
            'wind_speed': DATA['wind_speed_10m'],
            'wind_gusts': DATA['wind_gusts_10m'],
            'wind_direction': DATA['wind_direction_10m']
        }
        

    @pytest.mark.asyncio
    async def test_emits_according_to_interval(self, mocker):
        INTERVAL = 0.2
        provider = mocker.MagicMock(spec=OpenMeteo)
        online = Online(INTERVAL, provider=provider)

        gen = online.readings()
        await asyncio.wait_for(anext(gen), INTERVAL * 2)
        t0 = time.monotonic()
        await asyncio.wait_for(anext(gen), INTERVAL * 2)
        t1 = time.monotonic()

        assert t1 == pytest.approx(t0 + INTERVAL, rel=0.01)


    @pytest.mark.asyncio
    async def test_continues_to_emit_after_http_errors(self, mocker):
        INTERVAL = 0.1
        DATA = {
            'weather_code': 10,
            'wind_speed_10m': 20.0,
            'wind_gusts_10m': 30.0,
            'wind_direction_10m': 330
        }
        provider = mocker.MagicMock(spec=OpenMeteo)
        provider.read.side_effect = [ HTTPStatusError(403, request=None, response=None), { 'current': DATA } ]
        
        online = Online(INTERVAL, provider=provider)
        reading = await asyncio.wait_for(anext(online.readings()), 2 * INTERVAL)

        assert reading == {
            'code': DATA['weather_code'],
            'wind_speed': DATA['wind_speed_10m'],
            'wind_gusts': DATA['wind_gusts_10m'],
            'wind_direction': DATA['wind_direction_10m']
        }
    

    @pytest.mark.asyncio
    async def test_emits_errors_as_status(self, mocker):
        INTERVAL = 0.01
        ERRORS = [
            HTTPStatusError(429, request=None, response=None), # e.g. 429: Too Many Requests
            HTTPStatusError(503, request=None, response=None), # e.g. 503: Service Unavailable
            ConnectTimeout('Connection timed out'),
            NetworkError('Network unavailable')
        ]
        provider = mocker.MagicMock(spec=OpenMeteo)
        provider.read.side_effect = ERRORS
        
        online = Online(INTERVAL, provider=provider)
        task = asyncio.create_task(anext(online.readings()))
        for error in ERRORS:
            status = await asyncio.wait_for(anext(online.status()), 2 * INTERVAL)
            assert status == error

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task            

