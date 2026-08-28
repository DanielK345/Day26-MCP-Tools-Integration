"""Regression tests cho bước định vị trước khi gọi WeatherAPI.com."""

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("weather_function_calling.py")
SPEC = importlib.util.spec_from_file_location("weather_function_calling", MODULE_PATH)
weather_app = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(weather_app)


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class WeatherLocationTests(unittest.TestCase):
    def test_geocoder_rejects_wrong_fuzzy_match_then_finds_hanoi(self):
        wrong = FakeResponse(
            {
                "results": [
                    {
                        "name": "Province De Hà Tĩnh",
                        "admin1": "",
                        "country": "Việt Nam",
                        "country_code": "VN",
                        "latitude": 18.33,
                        "longitude": 105.9,
                    }
                ]
            }
        )
        correct = FakeResponse(
            {
                "results": [
                    {
                        "name": "Hà Nội",
                        "admin1": "Hanoi",
                        "country": "Việt Nam",
                        "country_code": "VN",
                        "latitude": 21.0245,
                        "longitude": 105.84117,
                    }
                ]
            }
        )

        with patch.object(weather_app.httpx, "get", side_effect=[wrong, correct]):
            result = weather_app.geocode_vietnamese_city("Hà Nội")

        self.assertEqual(result["name"], "Hà Nội")
        self.assertEqual(result["latitude"], 21.0245)
        self.assertEqual(result["longitude"], 105.84117)

    def test_weather_api_receives_resolved_coordinates_not_city_name(self):
        resolved = {
            "name": "Đà Nẵng",
            "admin1": "Đà Nẵng",
            "country": "Việt Nam",
            "latitude": 16.06778,
            "longitude": 108.22083,
        }
        weather_response = FakeResponse(
            {
                "location": {"name": "Da Nang", "localtime": "2026-08-28 10:32"},
                "current": {
                    "last_updated": "2026-08-28 10:15",
                    "temp_c": 31.1,
                    "feelslike_c": 34.7,
                    "condition": {"text": "Trời âm u"},
                    "humidity": 59,
                    "precip_mm": 0.0,
                    "cloud": 100,
                    "wind_dir": "WSW",
                    "wind_kph": 16.6,
                    "gust_kph": 26.7,
                    "uv": 8.6,
                },
            }
        )

        with (
            patch.dict(os.environ, {"WEATHER_API_KEY": "not-a-real-secret"}),
            patch.object(
                weather_app, "geocode_vietnamese_city", return_value=resolved
            ),
            patch.object(
                weather_app.httpx, "get", return_value=weather_response
            ) as request,
        ):
            result = weather_app.get_weather("Đà Nẵng")

        self.assertEqual(
            request.call_args.kwargs["params"]["q"], "16.06778,108.22083"
        )
        self.assertEqual(result["địa_điểm"]["tên"], "Đà Nẵng")
        self.assertEqual(result["nhiệt_độ_c"], 31.1)


if __name__ == "__main__":
    unittest.main()
