"""CLI chatbot dùng Gemini để lựa chọn các tool khám phá từ MCP server.

Client không hard-code schema hoặc tự thực thi weather tool. Google Gen AI SDK
nhận MCP session, tự chuyển schema của server thành function declarations và
gọi tool qua MCP khi câu hỏi của người dùng cần dữ liệu thời tiết.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ENV_PATH = Path(__file__).with_name(".env")
MODEL = "gemini-2.5-flash"

SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý thời tiết Việt Nam thân thiện. Chỉ mô tả khả năng dựa trên "
    "các MCP tool được cung cấp. Khi người dùng hỏi thời tiết hiện tại hoặc dự "
    "báo, hãy dùng tool phù hợp; không tự bịa số liệu. Trả lời bằng tiếng Việt, "
    "ngắn gọn, nêu thời điểm/ngày của dữ liệu và đưa lời khuyên thực tế. Nếu câu "
    "hỏi nằm ngoài khả năng của tool, hãy nói rõ phạm vi hỗ trợ."
)


def print_capabilities(tools: list[object]) -> None:
    """Chào người dùng và liệt kê khả năng lấy trực tiếp từ MCP tool metadata."""
    print("\n🤖 Xin chào! Tôi là trợ lý thời tiết Việt Nam.")
    print("Tôi hiện có thể hỗ trợ các tác vụ sau:")
    for tool in tools:
        description = (getattr(tool, "description", "") or "").strip()
        summary = description.splitlines()[0] if description else tool.name
        print(f"  • {summary} (`{tool.name}`)")
    print("\nBạn có thể hỏi bằng ngôn ngữ tự nhiên, ví dụ:")
    print('  • "Thời tiết Hà Nội hiện tại thế nào?"')
    print('  • "Dự báo Đà Nẵng 3 ngày tới và cho tôi lời khuyên."')
    print("Gõ /tools để xem lại khả năng hoặc 'thoát' để kết thúc.")


def require_api_key(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Thiếu {name} trong {ENV_PATH}")
    return value


async def main() -> None:
    load_dotenv(ENV_PATH)
    gemini = genai.Client(api_key=require_api_key("GEMINI_API_KEY"))
    require_api_key("WEATHER_API_KEY")

    # Dùng đúng interpreter đang chạy client (tránh lỗi "python" không tồn tại)
    server_path = Path(__file__).with_name("weather_server.py")
    params = StdioServerParameters(command=sys.executable, args=[str(server_path)])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            discovered = await session.list_tools()
            print_capabilities(discovered.tools)

            # Google Gen AI SDK tự chuyển MCP schemas và thực hiện function calling.
            # Dùng dict để SDK chuyển MCP session trước khi copy config. Nếu tạo
            # GenerateContentConfig trực tiếp, asyncio Task trong session không
            # thể deepcopy/pickle ở một số phiên bản google-genai.
            model_config = {
                "tools": [session],
                "system_instruction": SYSTEM_INSTRUCTION,
                "automatic_function_calling": {"maximum_remote_calls": 6},
            }
            history: list[types.Content] = []

            while True:
                try:
                    question = input("\nBạn: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nTrợ lý: Tạm biệt bạn! 👋")
                    break

                if not question:
                    continue
                if question.casefold() in {"thoát", "thoat", "exit", "quit"}:
                    print("Trợ lý: Tạm biệt bạn! 👋")
                    break
                if question.casefold() in {"/tools", "/help"}:
                    print_capabilities(discovered.tools)
                    continue

                try:
                    user_content = types.Content(
                        role="user", parts=[types.Part.from_text(text=question)]
                    )
                    turn_contents = [*history, user_content]
                    response = await gemini.aio.models.generate_content(
                        model=MODEL,
                        contents=turn_contents,
                        config=model_config,
                    )
                    answer = (response.text or "").strip()
                    print(f"Trợ lý: {answer or 'Tôi chưa tạo được câu trả lời.'}")

                    # AFC history chứa cả function call và MCP response. Lưu lại để
                    # câu hỏi tiếp theo hiểu đúng ngữ cảnh của cuộc hội thoại.
                    if response.automatic_function_calling_history:
                        history = list(response.automatic_function_calling_history)
                    else:
                        history = turn_contents
                    if response.candidates and response.candidates[0].content:
                        history.append(response.candidates[0].content)
                except Exception as exc:  # Giữ CLI hoạt động sau lỗi mạng/tool.
                    print(f"Trợ lý: Xin lỗi, yêu cầu gặp lỗi: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
