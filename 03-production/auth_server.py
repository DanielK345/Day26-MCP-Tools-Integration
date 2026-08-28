"""MCP weather server qua Streamable HTTP, có bearer-token authentication.

Server chạy qua HTTP (Streamable HTTP) thay vì stdio, kèm bearer token
verification. Chỉ request mang token hợp lệ mới được phép khám phá và gọi tool.

Luồng hoạt động:
  Client gửi request HTTP kèm header "Authorization: Bearer <token>"
    → MCP SDK tự chạy BearerAuthBackend để xác minh token
    → Token hợp lệ → cho phép truy cập tool
    → Token sai / thiếu → trả về 401/403

Cách chạy:
    pip install -r ../requirements.txt     # từ thư mục gốc repo
    python auth_server.py
    # Server lắng nghe tại http://localhost:8000/mcp
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer


load_dotenv(Path(__file__).with_name(".env"))

BASICS_DIR = Path(__file__).resolve().parents[1] / "02-mcp-basics"
sys.path.insert(0, str(BASICS_DIR))
from weather_api import (  # noqa: E402
    get_current_weather_data,
    get_weather_forecast_data,
)


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Thiếu {name} trong 03-production/.env")
    return value


SERVER_HOST = os.getenv("MCP_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("MCP_PORT", "8000"))
PUBLIC_BASE_URL = os.getenv("MCP_PUBLIC_BASE_URL", f"http://localhost:{SERVER_PORT}")


class StaticTokenVerifier(TokenVerifier):
    """So sánh bearer token với secret cấu hình qua môi trường.

    Production nên thay bằng: JWT decode, OAuth introspection, hoặc
    gọi tới identity provider (Keycloak, Auth0, Google IAM, ...).
    """

    def __init__(self, expected_token: str) -> None:
        self.expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token, self.expected_token):
            return None
        return AccessToken(
            token=token,
            client_id="weather-client",
            scopes=["weather:read"],
        )


# --- MCP Server — logic tool không biết gì về auth --------------------
mcp = MCPServer(
    "weather-secure",
    auth=AuthSettings(
        issuer_url=PUBLIC_BASE_URL,
        resource_server_url=PUBLIC_BASE_URL,
    ),
    token_verifier=StaticTokenVerifier(require_env("MCP_AUTH_TOKEN")),
)


@mcp.tool()
def get_weather(city: str) -> dict[str, Any]:
    """Lấy thời tiết hiện tại, realtime của một thành phố hoặc tỉnh Việt Nam."""
    return get_current_weather_data(city)


@mcp.tool()
def get_weather_forecast(city: str, days: int = 3) -> dict[str, Any]:
    """Dự báo thời tiết 1-14 ngày cho một thành phố hoặc tỉnh Việt Nam."""
    return get_weather_forecast_data(city, days)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host=SERVER_HOST, port=SERVER_PORT)
