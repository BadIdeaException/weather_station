import pytest
import asyncio
from sensors.tchibo import Tchibo
from sensors.tchibo.receiver import Receiver
from sensors.tchibo.infactory import PacketLengthError, CRCError

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
    async def test_does_not_emit_wrong_length_packets_to_status(self, mocker):
        async def packets():
            yield mocker.sentinel.packet

        receiver = mocker.MagicMock(spec=Receiver)
        receiver.__enter__.return_value = receiver
        receiver.receive.return_value = packets()
        decoder = mocker.patch('sensors.tchibo.tchibo.InFactory').return_value
        decoder.decode.side_effect = [ PacketLengthError('') ]
        tchibo = Tchibo(receiver)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(tchibo.status()), timeout=0.1)


    @pytest.mark.asyncio
    async def test_emits_crc_check_failures_to_status(self, mocker):
        async def packets():
            yield mocker.sentinel.packet

        receiver = mocker.MagicMock(spec=Receiver)
        receiver.__enter__.return_value = receiver
        receiver.receive.return_value = packets()
        decoder = mocker.patch('sensors.tchibo.tchibo.InFactory').return_value
        decoder.decode.side_effect = [ CRCError(0, 0, '') ]
        tchibo = Tchibo(receiver)
        
        task = asyncio.create_task(anext(tchibo.readings()))
        try:
            result = await asyncio.wait_for(anext(tchibo.status()), timeout=0.1)
        finally:
            task.cancel()

        assert isinstance(result, CRCError)


    @pytest.mark.asyncio
    async def test_continues_after_malformed_packets(self, mocker):
        async def packets():
            yield mocker.sentinel.short_packet
            yield mocker.sentinel.bad_crc_packet
            yield mocker.sentinel.good_packet

        receiver = mocker.MagicMock(spec=Receiver)
        receiver.__enter__.return_value = receiver
        receiver.receive.return_value = packets()
        decoder = mocker.patch('sensors.tchibo.tchibo.InFactory').return_value
        decoder.decode.side_effect = [ CRCError(0, 0, ''), PacketLengthError(''), mocker.sentinel.readings ]
        tchibo = Tchibo(receiver)

        result = await anext(tchibo.readings())

        assert decoder.decode.call_count == 3
        assert result is mocker.sentinel.readings
