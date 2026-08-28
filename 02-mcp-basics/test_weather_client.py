"""Tests cho phần chào hỏi và giới thiệu tool của CLI chatbot."""

import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = Path(__file__).with_name("weather_client.py")
SPEC = importlib.util.spec_from_file_location("weather_client", MODULE_PATH)
weather_client = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(weather_client)


class WeatherClientTests(unittest.TestCase):
    def test_greeting_uses_discovered_tool_metadata(self):
        tools = [
            SimpleNamespace(
                name="get_weather", description="Lấy thời tiết hiện tại realtime."
            ),
            SimpleNamespace(
                name="get_weather_forecast",
                description="Dự báo thời tiết nhiều ngày.\nChi tiết schema.",
            ),
        ]

        output = io.StringIO()
        with redirect_stdout(output):
            weather_client.print_capabilities(tools)

        text = output.getvalue()
        self.assertIn("Xin chào", text)
        self.assertIn("Lấy thời tiết hiện tại realtime", text)
        self.assertIn("Dự báo thời tiết nhiều ngày", text)
        self.assertIn("get_weather_forecast", text)
        self.assertNotIn("Chi tiết schema", text)


if __name__ == "__main__":
    unittest.main()
