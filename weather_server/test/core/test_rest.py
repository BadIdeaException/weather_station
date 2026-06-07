import pytest
from core.data_engine import DataEngine
from model.weather import WeatherData
from core.rest import REST
from fastapi.testclient import TestClient
from dataclasses import fields, asdict


class TestREST:
    @pytest.fixture
    def engine(self, mocker):
        data =  WeatherData(
            inside_temperature = 10.0,
            inside_humidity = 11,
            outside_temperature = 20.0,
            outside_humidity = 21,
            pressure = 1000            
        )
        engine = mocker.MagicMock(spec=DataEngine)
        engine.data = data
        return engine

    @pytest.mark.parametrize('field_name', [ field.name for field in fields(WeatherData) ])
    def test_field_endpoint(self, field_name, engine):
        rest = REST(engine)
        client = TestClient(rest.api)

        resp = client.get(REST.PREFIX + f'/weather/{field_name}')

        assert resp.status_code == 200
        assert resp.json() == getattr(engine.data, field_name)

    def test_weather_endpoint(self, engine):
        rest = REST(engine)
        client = TestClient(rest.api)

        resp = client.get(REST.PREFIX + '/weather')

        assert resp.status_code == 200
        assert resp.json() == asdict(engine.data)