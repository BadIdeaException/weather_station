import pytest
from sensors.tchibo import Tchibo
from sensors.tchibo.receiver import Receiver

class TestTchibo:
    @pytest.mark.asyncio
    async def test_yields_readings(self, mocker):
        async def packets():
            yield mocker.sentinel.packet

        receiver = mocker.MagicMock(spec=Receiver)
        receiver.__enter__.return_value = receiver
        receiver.receive.return_value = packets()
        decoder = mocker.patch('sensors.tchibo.tchibo.InFactory').return_value
        decoder.decode.return_value = mocker.sentinel.readings
        tchibo = Tchibo(receiver)

        result = await anext(tchibo.readings())
        
        receiver.receive.assert_called_once()
        decoder.decode.assert_called_once_with(mocker.sentinel.packet)
        assert result is mocker.sentinel.readings
        
    @pytest.mark.asyncio
    async def test_swallows_malformed(self, mocker):
        async def packets():
            yield mocker.sentinel.good_packet
            yield mocker.sentinel.malformed_packet

        receiver = mocker.MagicMock(spec=Receiver)
        receiver.__enter__.return_value = receiver
        receiver.receive.return_value = packets()
        decoder = mocker.patch('sensors.tchibo.tchibo.InFactory').return_value
        decoder.decode.side_effect = [ ValueError('CRC check failed'), mocker.sentinel.readings ]
        tchibo = Tchibo(receiver)

        result = await anext(tchibo.readings())

        assert decoder.decode.call_count == 2
        assert result is mocker.sentinel.readings
