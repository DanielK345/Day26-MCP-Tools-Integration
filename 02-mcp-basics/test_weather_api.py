"""Regression tests cho current weather và forecast MCP provider."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("weather_api.py")
SPEC = importlib.util.spec_from_file_location("weather_api", MODULE_PATH)
weather_api = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(weather_api)

RESOLVED_DA_NANG = {
    "name": "Đà Nẵng",
    "admin1": "Đà Nẵng",
    "country": "Việt Nam",
    "latitude": 16.06778,
    "longitude": 108.22083,
}


class WeatherApiTests(unittest.TestCase):
    def test_current_weather_maps_real_provider_fields(self):
        provider_data = {
            "location": {"localtime": "2026-08-28 11:00"},
            "current": {
                "last_updated": "2026-08-28 10:45",
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
        with (
            patch.object(
                weather_api,
                "geocode_vietnamese_city",
                return_value=RESOLVED_DA_NANG,
            ),
            patch.object(
                weather_api, "_weather_api_request", return_value=provider_data
            ) as request,
        ):
            result = weather_api.get_current_weather_data("Đà Nẵng")

        request.assert_called_once_with(
            "current.json", RESOLVED_DA_NANG, aqi="no"
        )
        self.assertEqual(result["địa_điểm"]["tên"], "Đà Nẵng")
        self.assertEqual(result["nhiệt_độ_c"], 31.1)

    def test_forecast_returns_requested_number_of_daily_summaries(self):
        forecast_days = []
        for date in ("2026-08-28", "2026-08-29", "2026-08-30"):
            forecast_days.append(
                {
                    "date": date,
                    "day": {
                        "condition": {"text": "Mưa vừa"},
                        "mintemp_c": 25.0,
                        "maxtemp_c": 32.0,
                        "avgtemp_c": 28.0,
                        "daily_chance_of_rain": 80,
                        "totalprecip_mm": 4.2,
                        "avghumidity": 78,
                        "maxwind_kph": 24.0,
                        "uv": 7.0,
                    },
                    "astro": {"sunrise": "05:30 AM", "sunset": "06:05 PM"},
                }
            )
        provider_data = {
            "location": {"localtime": "2026-08-28 11:00"},
            "forecast": {"forecastday": forecast_days},
        }

        with (
            patch.object(
                weather_api,
                "geocode_vietnamese_city",
                return_value=RESOLVED_DA_NANG,
            ),
            patch.object(
                weather_api, "_weather_api_request", return_value=provider_data
            ) as request,
        ):
            result = weather_api.get_weather_forecast_data("Đà Nẵng", days=3)

        request.assert_called_once_with(
            "forecast.json",
            RESOLVED_DA_NANG,
            days=3,
            aqi="no",
            alerts="no",
        )
        self.assertEqual(result["số_ngày_yêu_cầu"], 3)
        self.assertEqual(len(result["dự_báo"]), 3)
        self.assertEqual(result["dự_báo"][0]["xác_suất_mưa_phần_trăm"], 80)

    def test_forecast_rejects_days_outside_supported_range(self):
        for invalid_days in (0, 15, True, 2.5):
            with self.subTest(days=invalid_days):
                with self.assertRaises(ValueError):
                    weather_api.get_weather_forecast_data(
                        "Đà Nẵng", days=invalid_days
                    )


if __name__ == "__main__":
    unittest.main()
