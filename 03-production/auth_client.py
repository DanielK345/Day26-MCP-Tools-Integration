"""Client kiểm tra Streamable HTTP server với token đúng/sai/thiếu.

Client truyền bearer token thông qua httpx.AsyncClient. MCP SDK tự gắn
token vào mọi request HTTP (POST, GET, DELETE) tới server.

Cách chạy (cần auth_server.py đang chạy ở terminal khác):
    cd 03-production
    python auth_server.py            # terminal 1
    python auth_client.py            # terminal 2
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SERVER_URL = "http://localhost:8000/mcp"


async def call_server(token: str | None) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    http_client = httpx.AsyncClient(headers=headers)

    async with http_client:
        async with streamable_http_client(
            os.getenv("MCP_SERVER_URL", SERVER_URL), http_client=http_client
        ) as streams:
            # MCP SDK từng trả 2 phần tử và bản mới có thể trả thêm session id.
            read, write = streams[:2]
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print("Tools (có auth):")
                for t in tools.tools:
                    print(f"  - {t.name}: {t.description}")

                result = await session.call_tool("get_weather", {"city": "Hà Nội"})
                print(f"\nKết quả: {result.content[0].text}")


async def probe_auth_status(token: str | None) -> int:
    """Gửi initialize request tối thiểu để kiểm tra chính xác HTTP 401/403."""
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "auth-negative-test", "version": "1.0"},
        },
    }
    async with httpx.AsyncClient(headers=headers) as client:
        response = await client.post(
            os.getenv("MCP_SERVER_URL", SERVER_URL), json=payload
        )
    return response.status_code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    token_group = parser.add_mutually_exclusive_group()
    token_group.add_argument("--token", help="Bearer token gửi tới server")
    token_group.add_argument(
        "--no-token", action="store_true", help="Không gửi Authorization header"
    )
    parser.add_argument(
        "--expect-denied",
        action="store_true",
        help="Pass khi server từ chối request; dùng cho negative test",
    )
    return parser.parse_args()


def exception_leaves(exc: BaseException) -> list[str]:
    """Tóm tắt lỗi gốc mà không in request headers/token."""
    if isinstance(exc, BaseExceptionGroup):
        details = []
        for child in exc.exceptions:
            details.extend(exception_leaves(child))
        return details
    if isinstance(exc, httpx.HTTPStatusError):
        return [f"HTTPStatusError({exc.response.status_code})"]
    return [f"{type(exc).__name__}: {exc}"]


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    args = parse_args()
    token = None if args.no_token else args.token or os.getenv("MCP_AUTH_TOKEN")

    if args.expect_denied:
        try:
            status = asyncio.run(probe_auth_status(token))
        except Exception as exc:
            print(
                "FAIL: không kiểm tra được HTTP status: "
                f"{'; '.join(exception_leaves(exc))}"
            )
            return 1
        if status in {401, 403}:
            print(f"PASS: server đã từ chối request (HTTP {status}).")
            return 0
        print(f"FAIL: server trả HTTP {status}, kỳ vọng 401 hoặc 403.")
        return 1

    try:
        asyncio.run(call_server(token))
    except Exception as exc:
        print(
            "FAIL: request không đạt kết quả mong đợi "
            f"({type(exc).__name__}): {'; '.join(exception_leaves(exc))}"
        )
        return 1

    print("PASS: token hợp lệ, list_tools và call_tool thành công.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
