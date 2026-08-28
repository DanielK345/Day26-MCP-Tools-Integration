"""Weather provider dùng chung cho các MCP tool trong phần 02."""

import logging
import os
import unicodedata
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


# HTTPX log ở mức INFO chứa URL đầy đủ; WeatherAPI truyền key trong query string.
# Chặn log request để secret không xuất hiện khi MCP cấu hình root logger ở INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

load_dotenv(Path(__file__).with_name(".env"))

WEATHER_API_BASE_URL = "https://api.weatherapi.com/v1"
GEOCODING_API_URL = "https://geocoding-api.open-meteo.com/v1/search"
HTTP_TIMEOUT_SECONDS = 10.0
MAX_FORECAST_DAYS = 14


def _ascii_city_name(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.split())


def _location_key(value: str) -> str:
    key = "".join(char for char in _ascii_city_name(value).casefold() if char.isalnum())
    for prefix in ("thanhpho", "provinceof", "province", "tinh"):
        if key.startswith(prefix):
            return key.removeprefix(prefix)
    return key


def geocode_vietnamese_city(city: str) -> dict[str, Any]:
    """Định vị chính xác một địa danh Việt Nam, không chấp nhận fuzzy-match sai."""
    city = city.strip()
    if not city:
        raise ValueError("Tên thành phố không được để trống")

    city_only = city.split(",", maxsplit=1)[0].strip()
    target_key = _location_key(city_only)
    if not target_key:
        raise ValueError("Tên thành phố không hợp lệ")

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


def _weather_api_request(
    endpoint: str, location: dict[str, Any], **params: Any
) -> dict[str, Any]:
    api_key = os.getenv("WEATHER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Thiếu WEATHER_API_KEY trong 02-mcp-basics/.env")

    query = f"{location['latitude']},{location['longitude']}"
    try:
        response = httpx.get(
            f"{WEATHER_API_BASE_URL}/{endpoint}",
            params={"key": api_key, "q": query, "lang": "vi", **params},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except httpx.RequestError:
        # Không lan truyền URL vì query string của WeatherAPI chứa secret.
        raise RuntimeError("Không thể kết nối tới WeatherAPI.com") from None

    if response.status_code != httpx.codes.OK:
        try:
            api_message = response.json().get("error", {}).get("message")
        except (ValueError, AttributeError):
            api_message = None
        detail = f": {api_message}" if api_message else ""
        raise RuntimeError(
            f"WeatherAPI.com trả về HTTP {response.status_code}{detail}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("WeatherAPI.com trả về JSON không hợp lệ") from exc


def _location_payload(
    requested_city: str, resolved: dict[str, Any], provider_location: dict[str, Any]
) -> dict[str, Any]:
    return {
        "địa_điểm_yêu_cầu": requested_city,
        "tên": resolved["name"],
        "tỉnh_thành": resolved["admin1"],
        "quốc_gia": resolved["country"],
        "vĩ_độ": resolved["latitude"],
        "kinh_độ": resolved["longitude"],
        "giờ_địa_phương": provider_location["localtime"],
    }


def get_current_weather_data(city: str) -> dict[str, Any]:
    """Lấy và chuẩn hóa dữ liệu thời tiết hiện tại từ provider."""
    resolved = geocode_vietnamese_city(city)
    data = _weather_api_request("current.json", resolved, aqi="no")

    try:
        current = data["current"]
        condition = current["condition"]
        location = data["location"]
        return {
            "nguồn": "WeatherAPI.com",
            "định_vị_bởi": "Open-Meteo Geocoding",
            "địa_điểm": _location_payload(city, resolved, location),
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
    except (KeyError, TypeError) as exc:
        raise RuntimeError("WeatherAPI.com thiếu dữ liệu thời tiết hiện tại") from exc


def get_weather_forecast_data(city: str, days: int = 3) -> dict[str, Any]:
    """Lấy và chuẩn hóa dự báo thời tiết theo ngày từ provider."""
    if isinstance(days, bool) or not isinstance(days, int):
        raise ValueError("days phải là số nguyên")
    if not 1 <= days <= MAX_FORECAST_DAYS:
        raise ValueError(f"days phải nằm trong khoảng 1-{MAX_FORECAST_DAYS}")

    resolved = geocode_vietnamese_city(city)
    data = _weather_api_request(
        "forecast.json", resolved, days=days, aqi="no", alerts="no"
    )

    try:
        forecast_days = []
        for item in data["forecast"]["forecastday"]:
            day = item["day"]
            astro = item["astro"]
            forecast_days.append(
                {
                    "ngày": item["date"],
                    "tình_trạng": day["condition"]["text"],
                    "nhiệt_độ_c": {
                        "thấp_nhất": day["mintemp_c"],
                        "cao_nhất": day["maxtemp_c"],
                        "trung_bình": day["avgtemp_c"],
                    },
                    "xác_suất_mưa_phần_trăm": day["daily_chance_of_rain"],
                    "tổng_lượng_mưa_mm": day["totalprecip_mm"],
                    "độ_ẩm_trung_bình_phần_trăm": day["avghumidity"],
                    "gió_tối_đa_km_h": day["maxwind_kph"],
                    "uv": day["uv"],
                    "mặt_trời_mọc": astro["sunrise"],
                    "mặt_trời_lặn": astro["sunset"],
                }
            )

        return {
            "nguồn": "WeatherAPI.com Forecast API",
            "định_vị_bởi": "Open-Meteo Geocoding",
            "địa_điểm": _location_payload(city, resolved, data["location"]),
            "số_ngày_yêu_cầu": days,
            "dự_báo": forecast_days,
        }
    except (KeyError, TypeError) as exc:
        raise RuntimeError("WeatherAPI.com thiếu dữ liệu dự báo") from exc
