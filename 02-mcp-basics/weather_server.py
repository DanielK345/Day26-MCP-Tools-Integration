"""MCP server công bố các tool thời tiết Việt Nam dùng dữ liệu API thật.

Schema của tool được tự động sinh từ type hints và docstring. Server chịu
trách nhiệm định vị địa danh, gọi WeatherAPI.com rồi trả dữ liệu có cấu trúc;
MCP client không cần biết logic provider ở bên trong.

Cách chạy:
    pip install -r ../requirements.txt
    cp .env.example .env  # điền WEATHER_API_KEY
    python weather_server.py
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from weather_api import get_current_weather_data, get_weather_forecast_data


mcp = MCPServer("weather")


@mcp.tool()
def get_weather(city: str) -> dict[str, Any]:
    """Lấy thời tiết hiện tại, realtime của một thành phố hoặc tỉnh Việt Nam."""
    return get_current_weather_data(city)


@mcp.tool()
def get_weather_forecast(city: str, days: int = 3) -> dict[str, Any]:
    """Dự báo thời tiết 1-14 ngày cho một thành phố hoặc tỉnh Việt Nam.

    Args:
        city: Tên thành phố hoặc tỉnh, ví dụ Hà Nội, Đà Nẵng hoặc Huế.
        days: Số ngày dự báo, từ 1 đến 14; mặc định là 3.
    """
    return get_weather_forecast_data(city, days)


if __name__ == "__main__":
    mcp.run()  # mặc định chạy qua stdio
