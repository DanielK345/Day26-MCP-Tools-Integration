# 01 — Function Calling thuần (Google Gemini SDK)

Tool `get_weather` được **định nghĩa schema thủ công** và **thực thi ngay trong app**.
Model chỉ quyết định gọi tool nào — app gọi **WeatherAPI.com thật** để lấy dữ liệu
hiện tại rồi gửi kết quả cho Gemini tổng hợp. Không còn bảng thời tiết mock.

```
User hỏi  →  Model quyết định gọi get_weather(city="Hà Nội")
                     │
                     ▼
          Open-Meteo xác thực tên + lấy tọa độ VN
                     │
                     ▼
              App gọi WeatherAPI.com bằng tọa độ
                     │
                     ▼
              Model tổng hợp câu trả lời
```

## Cách chạy

```bash
pip install -r ../requirements.txt
cp .env.example .env
# Điền GEMINI_API_KEY và WEATHER_API_KEY vào .env
python weather_function_calling.py
```

Có thể truyền câu hỏi trực tiếp:

```bash
python weather_function_calling.py "Thời tiết Huế hiện tại thế nào?"
```

Lấy API key:

- Gemini: <https://aistudio.google.com/app/apikey>
- WeatherAPI.com: <https://www.weatherapi.com/signup.aspx>

File `.env` đã được `.gitignore` loại trừ. Không commit hoặc in API key ra log.

Ứng dụng không gửi thẳng tên có dấu sang WeatherAPI.com vì provider có thể
fuzzy-match sai địa danh Việt Nam. Tên được chuẩn hóa và xác thực bằng
[Open-Meteo Geocoding](https://open-meteo.com/en/docs/geocoding-api), chỉ nhận
kết quả có `country_code=VN`; WeatherAPI.com sau đó nhận cặp vĩ độ/kinh độ.

## File

| File | Mô tả |
|---|---|
| `weather_function_calling.py` | Định nghĩa schema, gọi WeatherAPI.com, gọi Gemini và xử lý vòng lặp function calling |
| `.env.example` | Mẫu tên biến môi trường, không chứa secret thật |

## Một số weather API phù hợp cho địa điểm Việt Nam

| Nhà cung cấp | Điểm phù hợp | Lưu ý |
|---|---|---|
| [WeatherAPI.com](https://www.weatherapi.com/docs/) | Current weather, hỗ trợ `lang=vi`; được dùng trong bài này sau bước định vị | Cần API key; không dùng trực tiếp tên có dấu để tránh fuzzy-match sai |
| [OpenWeather](https://openweathermap.org/api/current) | Dữ liệu hiện tại toàn cầu, hệ sinh thái phổ biến | Nên geocode địa danh thành tọa độ trước; cần API key |
| [Tomorrow.io](https://docs.tomorrow.io/reference/realtime-weather) | Realtime/hyperlocal và nhiều trường dữ liệu | Cần API key, hạn mức tùy gói |
| [Open-Meteo](https://open-meteo.com/en/docs) | Miễn phí cho nhiều trường hợp phi thương mại, không bắt buộc key | Cần tọa độ; chủ yếu là dữ liệu mô hình/dự báo |

Nếu cần bản tin chính thức trong nước, có thể tham khảo
[Trung tâm Dự báo KTTV Quốc gia](https://nchmf.gov.vn/), nhưng cần kiểm tra thỏa
thuận cung cấp dữ liệu/API riêng; website công khai không nên bị coi như một API
ổn định để scraping.

---

## Function Calling là gì? Giải thích đơn giản

Hình dung bạn có một **trợ lý ảo** rất giỏi ngôn ngữ, nhưng **không biết gì về thế giới thật** — không biết thời tiết, không truy cập được database, không gọi được API.

Function Calling là cách bạn **dạy trợ lý ảo sử dụng công cụ**:

```
Không có Function Calling:                 Có Function Calling:

User: "Thời tiết HN?"                     User: "Thời tiết HN?"
       │                                         │
       ▼                                         ▼
   ┌────────┐                                ┌────────┐
   │ Model  │                                │ Model  │
   │        │                                │        │ ← biết có tool get_weather
   │ "Tôi   │                                │ "Hãy   │
   │ không  │                                │  gọi   │
   │ biết"  │                                │ get_   │
   │        │                                │ weather│
   └────────┘                                │("HN")  │
                                             └───┬────┘
   Model bó tay vì                               │
   không có dữ liệu                              ▼
                                             App chạy hàm
                                                  │
                                                  ▼
                                             ┌────────┐
                                             │ Model  │
                                             │ "HN:   │
                                             │ dữ liệu│
                                             │ mới"   │
                                             └────────┘
```

**Điểm mấu chốt:** Model **KHÔNG chạy** hàm. Nó chỉ nói *"hãy gọi hàm X với tham số Y"*.

---

## Minh hoạ từng bước chi tiết

User hỏi: **"Thời tiết Hà Nội và Đà Nẵng hôm nay thế nào?"**

```
Bước 1 — App chuẩn bị "hộp công cụ" cho model
═══════════════════════════════════════════════

    App định nghĩa schema THỦ CÔNG:
    ┌────────────────────────────────────────┐
    │  Tool: get_weather                     │
    │  Mô tả: "Lấy thời tiết thành phố"      │
    │  Tham số:                              │
    │    city: string (bắt buộc)             │
    │                                        │
    │   Schema viết TAY - 15 dòng code       │
    │     phải khớp với hàm thật             │
    └────────────────────────────────────────┘

Bước 2 — Gửi prompt + schema cho model
═══════════════════════════════════════

    App ──────────────────────────────────────────▶ Gemini
    │  "Thời tiết HN và ĐN?"                      │
    │  + schema get_weather                       │
    │                                             │
    │  Model hiểu: "À, có tool get_weather,       │
    │   tôi cần gọi nó 2 lần cho HN và ĐN"        │

Bước 3 — Model TRẢ VỀ yêu cầu gọi tool (không tự chạy!)
═════════════════════════════════════════════════════════

    Gemini ──────────────────────────────────────▶ App
    │  function_calls:                             │
    │    [                                         │
    │      get_weather(city="Hà Nội"),             │
    │      get_weather(city="Đà Nẵng")             │
    │    ]                                         │
    │                                              │
    │    Model CHỈ sinh JSON — không hề chạy       │

Bước 4 — App TỰ THI HÀNH hàm get_weather
═════════════════════════════════════════

    App nhận yêu cầu → CHẠY hàm Python:
    ┌──────────────────────────────────────────┐
    │ get_weather("Hà Nội") → gọi WeatherAPI.com │ ← App chạy
    │ get_weather("Đà Nẵng") → gọi WeatherAPI.com│ ← App chạy
    └──────────────────────────────────────────┘

Bước 5 — Gửi kết quả lại cho model tổng hợp
════════════════════════════════════════════

    App ──────────────────────────────────────────▶ Gemini
    │  Kết quả JSON realtime từ WeatherAPI.com    │
    │                                            │
    │  Gemini tạo câu trả lời từ đúng các trường │
    │  nhiệt độ, mưa, độ ẩm và gió vừa nhận được │
    │  (không dùng các con số viết sẵn trong app)│
```

---

## Nhìn vào code thật

3 phần quan trọng trong `weather_function_calling.py`:

**Phần 1 — Schema viết tay** (model cần biết tool trông như thế nào):

```python
# App phải TỰ MÔ TẢ tool cho model — viết tay, dễ sai
get_weather_declaration = types.FunctionDeclaration(
    name="get_weather",
    description="Lấy thời tiết hiện tại của một thành phố",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(type=types.Type.STRING, description="Tên thành phố")
        },
        required=["city"],
    ),
)
```

**Phần 2 — Hàm thực thi** (app tự chạy khi model yêu cầu):

```python
# App phải CÓ hàm thật để chạy — model không chạy hàm này
def get_weather(city: str) -> dict:
    location = geocode_vietnamese_city(city)
    response = httpx.get(
        "https://api.weatherapi.com/v1/current.json",
        params={
            "key": os.environ["WEATHER_API_KEY"],
            "q": f"{location['latitude']},{location['longitude']}",
            "lang": "vi",
        },
    )
    return response.json()
```

**Phần 3 — Vòng lặp** (nhận yêu cầu → chạy → trả lại):

```python
while resp.function_calls:
    for fc in resp.function_calls:
        result = get_weather(**fc.args)   # ← APP chạy, không phải model
    # gửi result lại cho model để tổng hợp câu trả lời
```

---

## Luồng hoạt động

1. App định nghĩa `FunctionDeclaration` với schema viết tay (tên, tham số, kiểu)
2. App gửi prompt + danh sách tool tới Gemini
3. Model trả về `function_calls` — yêu cầu gọi `get_weather`
4. App **tự chạy** hàm `get_weather()` và đưa kết quả trả lại model
5. Model tổng hợp câu trả lời cuối cho user

## Nhược điểm

```
┌─────────────────────────────────────────────────────────────┐
│  ❌ Schema viết tay                                         │
│     FunctionDeclaration(name=..., parameters=...)           │
│     → 15+ dòng boilerplate, dễ lệch với hàm thật            │
│                                                             │
│  ❌ Tool gắn chặt trong app                                 │
│     App A có get_weather → App B muốn dùng?                 │
│     → Copy schema + hàm sang App B                          │
│     → Sửa hàm ở A? Phải nhớ sửa cả B                        │
│                                                             │
│  ❌ Mỗi provider 1 format                                   │
│     Google: FunctionDeclaration(...)                        │
│     OpenAI: {"type": "function", "function": {...}}         │
│     Anthropic: {"name": ..., "input_schema": {...}}         │
│     → Đổi model = viết lại schema                           │
└─────────────────────────────────────────────────────────────┘
```

**MCP giải quyết tất cả các vấn đề trên** → xem [02-mcp-basics/](../02-mcp-basics/)

Bước tiếp theo: [02-mcp-basics/](../02-mcp-basics/) — tách tool ra MCP server độc lập.
