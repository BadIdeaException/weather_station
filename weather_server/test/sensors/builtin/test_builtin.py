import pytest
import asyncio
import time
from sensors.builtin import Builtin
from sensors.builtin.bme280 import BME280

class TestBuiltin:
    @pytest.mark.asyncio
    async def test_yields_readings(self, mocker):
        bme280 = mocker.MagicMock(spec=BME280)
        bme280.temperature = mocker.sentinel.temperature
        bme280.pressure = mocker.sentinel.pressure
        bme280.humidity = mocker.sentinel.humidity        
        bme280.measuring = False

        with Builtin(1.0, bme280) as builtin:
            reading = await asyncio.wait_for(anext(builtin.readings()), 0.1)

        assert reading['temperature'] is mocker.sentinel.temperature
        assert reading['pressure'] is mocker.sentinel.pressure
        assert reading['humidity'] is mocker.sentinel.humidity


    @pytest.mark.asyncio
    async def test_yields_according_to_interval(self, mocker):
        INTERVAL = 0.2
        bme280 = mocker.MagicMock(spec=BME280)
        bme280.measuring = False
        with Builtin(INTERVAL, bme280) as builtin:
            gen = builtin.readings()
            await asyncio.wait_for(anext(gen), INTERVAL * 2)
            t0 = time.monotonic()
            await asyncio.wait_for(anext(gen), INTERVAL * 2)
            t1 = time.monotonic()

            assert t1 == pytest.approx(t0 + INTERVAL, rel=0.01)


    @pytest.mark.asyncio
    async def test_close_terminates_generator(self, mocker):
        bme280 = mocker.MagicMock(spec=BME280)
        bme280.measuring = False
        with Builtin(1.0, bme280) as builtin:
            gen = builtin.readings()

            builtin.close()

            with pytest.raises(StopAsyncIteration):
                await asyncio.wait_for(anext(gen), 0.1)