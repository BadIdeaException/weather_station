from typing import DefaultDict
import pytest
from sensors.tchibo.receiver import Receiver
from sensors.tchibo.receiver.cc1101 import CC1101
from sensors.tchibo.receiver.framer import Framer
from sensors.tchibo.receiver.demodulator import Demodulator
import asyncio
from enum import Enum

class TestReceiver:
    TIMINGS = {
        'one': 1,
        'zero': 2,
        'timeout': 3,
        'tolerance': 0.5
    }
    def test_missing_gdo_raises_error(self, mocker):
        cc1101 = mocker.MagicMock(spec=CC1101)
        cc1101.gdo0 = None
        cc1101.gdo1 = None
        cc1101.gdo2 = None

        with pytest.raises(ValueError):
            Receiver({}, cc1101)

    @pytest.mark.asyncio
    async def test_receive_runs_pipeline(self, mocker):
        frame = mocker.sentinel.frame
        packet = mocker.sentinel.packet
        async def frames():
            yield frame
        
        cc1101 = mocker.MagicMock(spec=CC1101)
        cc1101.gdo2 = mocker.MagicMock(spec=CC1101.GDO)

        receiver = Receiver(self.TIMINGS, cc1101)
        mock_frames = mocker.patch.object(receiver.framer, 'frames', return_value=frames())
        mock_demodulate = mocker.patch.object(receiver.demodulator, 'demodulate', return_value=packet)

        result = await anext(receiver.receive())
        mock_frames.assert_called_once()
        mock_demodulate.assert_called_once_with(frame)
        assert result is packet


    def test_close_closes_resources(self, mocker):
        cc1101 = mocker.MagicMock(spec=CC1101)
        cc1101.gdo2 = mocker.MagicMock(spec=CC1101.GDO)
        
        receiver = Receiver(self.TIMINGS, cc1101)
        cc1101_close = mocker.patch.object(cc1101, 'close')
        framer_close = mocker.patch.object(receiver.framer, 'close')

        receiver.close()
        cc1101_close.assert_called_once()
        framer_close.assert_called_once()
