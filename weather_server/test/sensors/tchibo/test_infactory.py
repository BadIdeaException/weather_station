import pytest
from sensors.tchibo.infactory import InFactory

class TestInFactory:
    @pytest.fixture
    def input(self):
        return '0000111100110000010111001110011101100001'
                
    def test_throws_on_wrong_length(self, input):
        decoder = InFactory()
        input = ''

        with pytest.raises(ValueError):
            decoder.decode(input)

    def test_throws_on_crc_fail(self, input):
        decoder = InFactory()
        input = input[:7] + '0000' + input[13:] # Overwrite CRC

        with pytest.raises(ValueError):
            decoder.decode(input)

    def test_decodes_values(self, input):
        decoder = InFactory()       
        values = decoder.decode(input)

        assert values['device_id'] == 0x0F
        assert values['battery_low'] == False
        assert values['temperature'] == pytest.approx(14.777777)
        assert values['humidity'] == 76
        assert values['channel'] == 1
