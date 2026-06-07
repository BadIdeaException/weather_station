import pytest
from httpx2 import HTTPStatusError
from sensors.online.openmeteo import OpenMeteo


class TestOpenMeteo:
    @pytest.mark.asyncio
    @pytest.mark.respx(assert_all_called=True)
    async def test_correct_url(self,httpx2_mock):
        httpx2_mock.get(OpenMeteo.URL).respond(json={})
        openmeteo = OpenMeteo((None, None))
        await openmeteo.read()

        
    @pytest.mark.asyncio
    @pytest.mark.respx(assert_all_called=True)
    async def test_passes_location(self, httpx2_mock):
        LOCATION = (10.0, 20.0)
        route = httpx2_mock.get(OpenMeteo.URL, params={ 'latitude': LOCATION[0], 'longitude': LOCATION[1] }).respond(json={})

        openmeteo = OpenMeteo(LOCATION)
        await openmeteo.read()


    @pytest.mark.asyncio
    async def test_requests_all_values(self, httpx2_mock):
        # We can't use params={ 'current': [ 'weather_code', 'wind_speed_10m', 'wind_direction_10m', 'wind_gusts_10m' ] } here,
        # because that treats current as an ORDERED list
        route = httpx2_mock.get(OpenMeteo.URL).mock().respond(json={})
        openmeteo = OpenMeteo((None, None))
        reading = await openmeteo.read()

        requested_data_points = route.calls.last.request.url.params.get_list('current')
        for data_point in [ 'weather_code', 'wind_speed_10m', 'wind_gusts_10m', 'wind_direction_10m' ]:
            assert data_point in requested_data_points
        

    @pytest.mark.asyncio
    async def test_returns_all_values(self, httpx2_mock):
        RESPONSE = {
            "wind_speed_10m": 11.5, 
            "wind_gusts_10m": 23.7, 
            "wind_direction_10m": 244, 
            "weather_code": 73
        }
        httpx2_mock.get(OpenMeteo.URL).mock().respond(json=RESPONSE)
        
        openmeteo = OpenMeteo((None, None))
        reading = await openmeteo.read()

        for key in RESPONSE:
            assert reading[key] == RESPONSE[key]


    @pytest.mark.asyncio
    async def test_throws_on_error_response(self, httpx2_mock):
        # Can't just use params={...} here because we don't care about the order
        httpx2_mock.get(OpenMeteo.URL).mock().respond(403)
        
        openmeteo = OpenMeteo((None, None))

        with pytest.raises(HTTPStatusError):
            await openmeteo.read()
