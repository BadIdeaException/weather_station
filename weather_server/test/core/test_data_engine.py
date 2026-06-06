import pytest
import asyncio
from core.data_engine import DataEngine

class ReadingGenerator:             
    def __init__(self, readings):
        self.values = readings
        self._avail = asyncio.Event()

    async def readings(self):
        for reading in self.values:
            await self._avail.wait()
            yield reading
            self._avail.clear()

    def next(self):
        self._avail.set()

    def close(self):
        pass


class Monitor:
    def __init__(self, target, attributes=None, polling=0.001):
        if target is None:
            raise ValueError('Cannot monitor without a target')

        if attributes is None:
            attributes = vars(target).keys()

        self.target = target
        self.attributes = attributes
        self.polling = polling

    async def wait_for_change(self):        
        while True:
            current = vars(self.target)
            if any(current[attr] != self.state[attr] for attr in self.attributes):
                break
            await asyncio.sleep(self.polling)

        self.state = { key: value for key, value in vars(self.target).items() if key in self.attributes }

    def __enter__(self):
        self.state = { key: value for key, value in vars(self.target).items() if key in self.attributes }
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class TestDataEngine:
    def test_close_closes_sensors(self, mocker):
        mocker.patch('core.data_engine.Tchibo', new=mocker.Mock())
        mocker.patch('core.data_engine.Builtin', new=mocker.Mock())
        engine = DataEngine()
        engine.close()

        engine.tchibo.close.assert_called()
        engine.builtin.close.assert_called()

    @pytest.mark.asyncio
    async def test_updates_from_all_sensors(self, mocker):
        TCHIBO_READING = {
            'temperature': 10.0,
            'humidity': 11
        }
        BUILTIN_READING = {
            'temperature': 20.0,
            'humidity': 21,
            'pressure': 1000
        }
        tchibo = ReadingGenerator([ TCHIBO_READING ])
        builtin = ReadingGenerator([ BUILTIN_READING ])
        mocker.patch('core.data_engine.Tchibo', return_value=tchibo)
        mocker.patch('core.data_engine.Builtin', return_value=builtin)

        engine = DataEngine()                
        task = asyncio.create_task(engine.run())
        try:
            with Monitor(engine.data) as monitor:
                tchibo.next()
                builtin.next()
                await asyncio.wait_for(monitor.wait_for_change(), timeout=0.2)
        
                assert engine.data.outside_temperature == TCHIBO_READING['temperature']
                assert engine.data.outside_humidity == TCHIBO_READING['humidity']
                assert engine.data.inside_temperature == BUILTIN_READING['temperature']
                assert engine.data.inside_humidity == BUILTIN_READING['humidity']
                assert engine.data.pressure == BUILTIN_READING['pressure']

        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_updates_multiple_times_from_same_sensor(self, mocker):
        READING_1 = {
            'temperature': 10.0,
            'humidity': 11
        }
        READING_2 = {
            'temperature': 20.0,
            'humidity': 22
        }

        tchibo = ReadingGenerator([ READING_1, READING_2 ])
        builtin = ReadingGenerator([])

        mocker.patch('core.data_engine.Tchibo', return_value=tchibo)
        mocker.patch('core.data_engine.Builtin', return_value=builtin)

        engine = DataEngine()                
        task = asyncio.create_task(engine.run())
        try:
            with Monitor(engine.data, [ 'outside_temperature', 'outside_humidity' ]) as monitor:
                tchibo.next()
                await asyncio.wait_for(monitor.wait_for_change(), timeout=0.2)

                assert engine.data.outside_temperature == READING_1['temperature']
                assert engine.data.outside_humidity == READING_1['humidity']
            
                tchibo.next()
                await asyncio.wait_for(monitor.wait_for_change(), timeout=0.2)
                assert engine.data.outside_temperature == READING_2['temperature']
                assert engine.data.outside_humidity == READING_2['humidity']

        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


    @pytest.mark.asyncio
    async def test_updates_interleaved_sensor_readings(self, mocker):
        TCHIBO_READINGS = [
            {
                'temperature': 10.0,
                'humidity': 11
            }, {
                'temperature': 20.0,
                'humidity': 21
            }

        ]
        BUILTIN_READINGS = [
            {
                'temperature': 30.0,
                'humidity': 31,
                'pressure': 1000
            }, {
                'temperature': 40.0,
                'humidity': 41,
                'pressure': 2000
            }

        ]
        tchibo = ReadingGenerator(TCHIBO_READINGS)
        builtin = ReadingGenerator(BUILTIN_READINGS)
        mocker.patch('core.data_engine.Tchibo', return_value=tchibo)
        mocker.patch('core.data_engine.Builtin', return_value=builtin)

        engine = DataEngine()                
        task = asyncio.create_task(engine.run())
        try:
            with Monitor(engine.data) as monitor:
                for cycle in range(2):
                    tchibo.next()
                    await asyncio.wait_for(monitor.wait_for_change(), timeout=0.2)
                    assert engine.data.outside_temperature == TCHIBO_READINGS[cycle]['temperature']
                    assert engine.data.outside_humidity == TCHIBO_READINGS[cycle]['humidity']
                
                    builtin.next()
                    await asyncio.wait_for(monitor.wait_for_change(), timeout=0.2)
                    assert engine.data.inside_temperature == BUILTIN_READINGS[cycle]['temperature']
                    assert engine.data.inside_humidity == BUILTIN_READINGS[cycle]['humidity']
                    assert engine.data.pressure == BUILTIN_READINGS[cycle]['pressure']

        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task