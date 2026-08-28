"""Minh hoạ FUNCTION CALLING thuần với Gemini và dữ liệu thời tiết thật.

Tool `get_weather` được định nghĩa schema thủ công VÀ thực thi ngay trong
chính file app này. Model chỉ QUYẾT ĐỊNH gọi tool nào; app mới là nơi chạy.

Cách chạy:
    pip install -r ../requirements.txt
    cp .env.example .env  # sau đó điền hai API key
    python weather_function_calling.py
"""

import argparse
import os
import unicodedata
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Luôn đọc file .env nằm cạnh script, không phụ thuộc thư mục đang chạy lệnh.
load_dotenv(Path(__file__).with_name(".env"))

MODEL = "gemini-2.5-flash"
WEATHER_API_URL = "https://api.weatherapi.com/v1/current.json"
GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
HTTP_TIMEOUT_SECONDS = 10.0

SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý thời tiết thân thiện, trả lời bằng tiếng Việt tự nhiên. "
    "Với thông tin thời tiết hiện tại, chỉ sử dụng dữ liệu do tool get_weather trả về; "
    "nếu tool báo lỗi thì nói rõ chưa lấy được dữ liệu, không tự đoán. "
    "Dùng emoji phù hợp (🌧️ 🌤️ 💨 💧). "
    "Tóm tắt ngắn gọn, dễ hiểu, và đưa ra lời khuyên thực tế "
    "(ví dụ: mang ô, mặc áo mỏng, ...)."
)

# 1. App tự định nghĩa schema của tool
get_weather_declaration = types.FunctionDeclaration(
    name="get_weather",
    description="Lấy dữ liệu thời tiết hiện tại, realtime của một thành phố Việt Nam",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(
                type=types.Type.STRING,
                description="Tên thành phố hoặc tỉnh của Việt Nam, ví dụ: Hà Nội",
            )
        },
        required=["city"],
    ),
)

TOOLS = [types.Tool(function_declarations=[get_weather_declaration])]


def _ascii_city_name(value: str) -> str:
    """Chuyển tên tiếng Việt sang dạng ASCII mà geocoder tìm ổn định hơn."""
    value = value.replace("Đ", "D").replace("đ", "d")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.split())


def _location_key(value: str) -> str:
    """Chuẩn hoá tên để so khớp, không phụ thuộc dấu/cách/ký tự phân tách."""
    key = "".join(char for char in _ascii_city_name(value).casefold() if char.isalnum())
    for prefix in ("thanhpho", "provinceof", "province", "tinh"):
        if key.startswith(prefix):
            return key.removeprefix(prefix)
    return key


def geocode_vietnamese_city(city: str) -> dict[str, Any]:
    """Tìm tọa độ chính xác tại Việt Nam bằng Open-Meteo Geocoding API."""
    city_only = city.split(",", maxsplit=1)[0].strip()
    target_key = _location_key(city_only)
    ascii_name = _ascii_city_name(city_only)
    query_variants = list(dict.fromkeys((ascii_name, ascii_name.replace(" ", ""))))
    candidates: list[dict[str, Any]] = []

    for query in query_variants:
        try:
            response = httpx.get(
                GEOCODING_API_URL,
                params={
                    "name": query,
                    "count": 10,
                    "language": "vi",
                    "format": "json",
                    "countryCode": "VN",
                },
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except httpx.RequestError:
            raise RuntimeError("Không thể kết nối tới Open-Meteo Geocoding") from None

        if response.status_code != httpx.codes.OK:
            raise RuntimeError(
                f"Open-Meteo Geocoding trả về HTTP {response.status_code}"
            )

        try:
            results = response.json().get("results", [])
        except (ValueError, AttributeError) as exc:
            raise RuntimeError("Open-Meteo trả về dữ liệu định vị không hợp lệ") from exc
        vietnam_results = [
            item for item in results if item.get("country_code") == "VN"
        ]
        candidates.extend(vietnam_results)
        if any(
            _location_key(str(item.get("name", ""))) == target_key
            for item in vietnam_results
        ):
            break

    def match_score(item: dict[str, Any]) -> int:
        name_key = _location_key(str(item.get("name", "")))
        admin_key = _location_key(str(item.get("admin1", "")))
        if name_key == target_key:
            return 4
        if admin_key == target_key:
            return 3
        if len(target_key) >= 4 and target_key in name_key:
            return 2
        if len(target_key) >= 4 and target_key in admin_key:
            return 1
        return 0

    best = max(candidates, key=match_score, default=None)
    if best is None or match_score(best) == 0:
        raise ValueError(f"Không tìm thấy địa danh Việt Nam khớp chính xác với '{city}'")

    try:
        return {
            "name": best["name"],
            "admin1": best.get("admin1"),
            "country": best["country"],
            "latitude": best["latitude"],
            "longitude": best["longitude"],
        }
    except KeyError as exc:
        raise RuntimeError("Open-Meteo thiếu tọa độ của địa danh") from exc


# 2. App thực thi tool bằng WeatherAPI.com, không còn dữ liệu mock/hardcode.
def get_weather(city: str) -> dict[str, Any]:
    """Lấy thời tiết hiện tại của *city* từ WeatherAPI.com."""
    api_key = os.getenv("WEATHER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Thiếu WEATHER_API_KEY trong 01-function-calling/.env")

    city = city.strip()
    if not city:
        raise ValueError("Tên thành phố không được để trống")

    resolved = geocode_vietnamese_city(city)
    location_query = f"{resolved['latitude']},{resolved['longitude']}"
    try:
        response = httpx.get(
            WEATHER_API_URL,
            params={"key": api_key, "q": location_query, "aqi": "no", "lang": "vi"},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.RequestError:
        # Không đưa URL của request vào lỗi vì query string chứa API key.
        raise RuntimeError("Không thể kết nối tới WeatherAPI.com") from None

    if response.status_code != httpx.codes.OK:
        try:
            api_message = response.json().get("error", {}).get("message")
        except ValueError:
            api_message = None
        detail = f": {api_message}" if api_message else ""
        raise RuntimeError(
            f"WeatherAPI.com trả về HTTP {response.status_code}{detail}"
        )

    try:
        data = response.json()
        location = data["location"]
        current = data["current"]
        condition = current["condition"]
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("WeatherAPI.com trả về dữ liệu không hợp lệ") from exc

    return {
        "nguồn": "WeatherAPI.com",
        "định_vị_bởi": "Open-Meteo Geocoding",
        "địa_điểm_yêu_cầu": city,
        "địa_điểm": {
            "tên": resolved["name"],
            "tỉnh_thành": resolved["admin1"],
            "quốc_gia": resolved["country"],
            "vĩ_độ": resolved["latitude"],
            "kinh_độ": resolved["longitude"],
            "giờ_địa_phương": location["localtime"],
        },
        "cập_nhật_lúc": current["last_updated"],
        "nhiệt_độ_c": current["temp_c"],
        "cảm_giác_như_c": current["feelslike_c"],
        "tình_trạng": condition["text"],
        "độ_ẩm_phần_trăm": current["humidity"],
        "mưa_mm": current["precip_mm"],
        "mây_phần_trăm": current["cloud"],
        "gió": {
            "hướng": current["wind_dir"],
            "tốc_độ_km_h": current["wind_kph"],
            "gió_giật_km_h": current["gust_kph"],
        },
        "uv": current["uv"],
    }


def create_gemini_client() -> genai.Client:
    """Tạo Gemini client từ key trong môi trường sau khi đã nạp .env."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY trong 01-function-calling/.env")
    return genai.Client(api_key=api_key)


def run(prompt: str) -> str:
    """Gửi *prompt* tới Gemini, tự động xử lý function calling và trả về câu trả lời cuối."""
    client = create_gemini_client()
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    ]

    # 3. Gọi model — model quyết định có gọi tool hay không
    resp = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=TOOLS,
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )

    # 4. Vòng lặp: nếu model yêu cầu tool, app TỰ THỰC THI rồi đưa kết quả trả lại
    while resp.function_calls:
        # Thêm phản hồi của model vào lịch sử hội thoại
        contents.append(resp.candidates[0].content)

        function_responses = []
        for fc in resp.function_calls:
            print(f"  [model yêu cầu] {fc.name}({fc.args})")
            try:
                result = get_weather(**fc.args)  # <-- app chạy, không phải model
            except (RuntimeError, ValueError) as exc:
                result = {"error": str(exc), "city": fc.args.get("city")}
            print(f"  [app thực thi]  -> {result}")
            function_responses.append(
                types.Part.from_function_response(
                    name=fc.name, response=result
                )
            )

        # Gửi kết quả tool trả về cho model
        contents.append(types.Content(role="user", parts=function_responses))
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )

    # 5. Model tổng hợp câu trả lời cuối
    return resp.text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Hỏi Gemini về thời tiết realtime tại Việt Nam"
    )
    parser.add_argument(
        "question",
        nargs="?",
        default="Thời tiết Hà Nội và Đà Nẵng hiện tại thế nào?",
        help="Câu hỏi thời tiết gửi tới Gemini",
    )
    question = parser.parse_args().question
    print(f"User: {question}\n")
    print("Trả lời:", run(question))
