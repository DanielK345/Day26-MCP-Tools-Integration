# 02 — MCP Basics (Server + Client, dữ liệu thời tiết thật)

Hai tool `get_weather` và `get_weather_forecast` nằm trong **MCP server độc lập**.
Server tự công bố schema qua giao thức MCP; bất kỳ client nào cũng có thể khám phá
và gọi tool mà không cần biết code provider bên trong.

```
User input → Gemini chọn tool → MCP client ──stdio──▶ MCP weather server
                 ▲                                      │
                 └──────── JSON current/forecast ◀──────┘
```

Server định vị địa danh bằng Open-Meteo Geocoding (`country_code=VN`), sau đó
gọi WeatherAPI.com bằng tọa độ. Cách này tránh lỗi fuzzy-match tên tiếng Việt
như `Hà Nội` bị trả về một địa danh khác.

## Cách chạy

```bash
pip install -r ../requirements.txt
cp .env.example .env
# Điền GEMINI_API_KEY và WEATHER_API_KEY vào .env
python weather_client.py     # client tự khởi động weather_server.py
```

CLI dùng `GEMINI_API_KEY` để hiểu câu hỏi tự nhiên và chọn MCP tool. Server dùng
`WEATHER_API_KEY` để lấy dữ liệu thật. `.env` đã được Git bỏ qua. Server cũng hạ
log HTTP client xuống `WARNING` vì WeatherAPI xác thực qua query string; không
bật DEBUG/INFO request logging nếu chưa có cơ chế redaction secret.

Khi khởi động, chatbot tự khám phá tool, chào người dùng và giới thiệu khả năng:

```
🤖 Xin chào! Tôi là trợ lý thời tiết Việt Nam.
Tôi hiện có thể hỗ trợ các tác vụ sau:
  • Lấy thời tiết hiện tại, realtime... (`get_weather`)
  • Dự báo thời tiết 1-14 ngày... (`get_weather_forecast`)

Bạn: Dự báo Đà Nẵng 3 ngày tới và cho tôi lời khuyên.
Trợ lý: ...
```

Chatbot tiếp tục nhận câu hỏi cho đến khi người dùng gõ `thoát`, `exit`, `quit`
hoặc nhấn `Ctrl+C`. Gõ `/tools` hay `/help` để xem lại khả năng.

## Files

| File | Mô tả |
|---|---|
| `weather_server.py` | MCP server công bố hai tool, schema tự sinh từ type hints/docstring |
| `weather_api.py` | Định vị Việt Nam, gọi current/forecast API và chuẩn hóa JSON |
| `weather_client.py` | CLI chatbot Gemini, tự khám phá/chọn/gọi MCP tool qua stdio |
| `.env.example` | Mẫu `GEMINI_API_KEY` và `WEATHER_API_KEY`, không chứa secret thật |

## Hai tool thời tiết

### `get_weather(city)`

Trả thời tiết hiện tại gồm thời điểm cập nhật, nhiệt độ/cảm giác như, tình
trạng, độ ẩm, lượng mưa, mây, gió và UV.

### `get_weather_forecast(city, days=3)`

Trả dự báo từ 1–14 ngày. Mỗi ngày gồm nhiệt độ thấp nhất/cao nhất/trung bình,
xác suất và tổng lượng mưa, độ ẩm, gió tối đa, UV, giờ mặt trời mọc/lặn. Số
ngày thực tế khả dụng còn phụ thuộc gói WeatherAPI.com.

---

## MCP là gì? Giải thích đơn giản

### Phép so sánh: ổ cắm điện chuẩn

```
KHÔNG CÓ MCP (mỗi nhà 1 kiểu ổ cắm)
══════════════════════════════════════

  Quạt ──[phích A]──▶ Ổ cắm nhà 1       ← Quạt chỉ dùng được ở nhà 1
  Quạt ──[phích B]──▶ Ổ cắm nhà 2       ← Phải đổi phích cho nhà 2
  Quạt ──[phích C]──▶ Ổ cắm nhà 3       ← Lại đổi phích cho nhà 3

  Mỗi nhà 1 kiểu ổ → mua thiết bị phải xem nhà dùng ổ gì


CÓ MCP (chuẩn hoá ổ cắm)
══════════════════════════

  Quạt  ──┐                    ┌── Nhà 1
  Tivi  ──┼── ổ cắm chuẩn ──   ├── Nhà 2
  Máy lạnh┘                    └── Nhà 3

  Viết tool 1 lần → mọi AI app dùng được
  Viết client 1 lần → mọi tool server cắm vào được
```

### 3 bước MCP hoạt động

```
Bước 1 — KHÁM PHÁ: "Anh có tool gì?"
══════════════════════════════════════

  Client                          Server
    │                               │
    │── "list_tools()" ───────────▶ │
    │                               │  Server tự trả lời:
    │                               │  "Tôi có get_weather(city: str),"
    │                               │  "get_weather_forecast(city, days)"
    │◀── [{name, description,  ──── │  Schema SINH TỰ ĐỘNG
    │      parameters}]             │  từ type hints + docstring
    │                               │

  So sánh Function Calling:
    FC:  Developer viết schema THỦ CÔNG 15+ dòng
    MCP: @mcp.tool() → schema TỰ SINH từ type hints


Bước 2 — GỌI TOOL: "Cho tôi thời tiết HN"
═══════════════════════════════════════════

  Client                          Server
    │                               │
    │── call_tool("get_weather", ─▶ │
    │    {"city": "Hanoi"})         │
    │                               │  SERVER thực thi hàm
    │                               │  get_weather("Hà Nội")
    │◀── JSON realtime ───────────── │
    │                               │

  So sánh Function Calling:
    FC:  APP phải tự chạy hàm
    MCP: SERVER chạy — client không cần biết code bên trong


Bước 3 — TÁI SỬ DỤNG: viết 1 lần, dùng mọi nơi
═════════════════════════════════════════════════

                     ┌── Claude Code
                     │      "list_tools → get_weather"
  weather_server.py ─┼── Cursor
                     │      "list_tools → get_weather"
                     ├── Gemini CLI
                     │      "list_tools → get_weather"
                     └── App tự viết
                            "list_tools → get_weather"

  1 server phục vụ N client — không sửa dòng code nào
```

---

## So sánh code: Function Calling vs MCP

### Khai báo tool

```
Function Calling (01):                    MCP (02):
30 dòng schema viết tay                   4 dòng, tự sinh schema

types.FunctionDeclaration(                @mcp.tool()
  name="get_weather",                     def get_weather(city: str) -> dict:
  description="Lấy thời tiết...",             """Lấy thời tiết..."""
  parameters=types.Schema(                    return get_current_weather_data(city)
    type=types.Type.OBJECT,
    properties={                           ✅ Schema tự sinh từ:
      "city": types.Schema(                   city: str    → type: string
        type=types.Type.STRING,               -> str       → return type
        description="Tên thành phố"           docstring    → description
      )
    },
    required=["city"],
  ),
)
```

### Nơi thực thi

```
Function Calling:                          MCP:
Mọi thứ trong 1 file                      Tách server / client

┌── weather_app.py ──────────┐             ┌── server.py ─────────┐
│                            │             │  @mcp.tool()         │
│  schema = {...}            │             │  def get_weather():  │
│  def get_weather(): ...    │             │      ...             │
│  model.generate(...)       │             └──────────────────────┘
│  result = get_weather()    │                       ▲
│                            │                       │ MCP
└────────────────────────────┘                       │
                                           ┌── client.py ─────────┐
App = schema + hàm + model                 │  list_tools()        │
    = làm hết mọi thứ                      │  call_tool()         │
                                           └──────────────────────┘

                                           Client chỉ biết giao thức
                                           Server chỉ biết logic tool
```

### Thêm tool mới

```
Function Calling:                          MCP:

  App A: thêm schema + hàm                  Server: thêm 1 hàm @mcp.tool()
  App B: copy schema + hàm                  Client A: không đổi (tự khám phá)
  App C: copy schema + hàm                  Client B: không đổi
                                            Client C: không đổi
  3 chỗ phải sửa                             1 chỗ phải sửa
```

---

## Khác biệt so với Function Calling thuần

| | 01-function-calling | 02-mcp-basics |
|---|---|---|
| Khai báo schema | Viết tay `FunctionDeclaration` | `@mcp.tool()` tự sinh |
| Nơi thực thi tool | Trong app gọi model | Trong MCP server riêng |
| Khám phá tool | Hard-code danh sách | `list_tools()` tại runtime |
| Dùng lại ở app khác | Copy code | Cắm thêm client |

---

## MCP trong thực tế: kết hợp với LLM

CLI trong phần này minh họa luôn luồng MCP kết hợp với Gemini Function Calling:

```
┌──────────────────────────────────────────────────────────┐
│                    Luồng đầy đủ                          │
│                                                          │
│  User: "Thời tiết HN?"                                   │
│    │                                                     │
│    ▼                                                     │
│  AI Client (Claude, Cursor...)                           │
│    │                                                     │
│    ├─ 1. list_tools() ──▶ MCP Server                     │
│    │◀── "có get_weather"                                 │
│    │                                                     │
│    ├─ 2. Gửi prompt + tool list cho LLM                  │
│    │◀── LLM dùng FUNCTION CALLING:                       │
│    │    "gọi get_weather(city='HN')"                     │
│    │                                                     │
│    ├─ 3. call_tool("get_weather") ──▶ MCP Server         │
│    │◀── JSON realtime từ WeatherAPI.com                   │
│    │                                                     │
│    ├─ 4. Gửi kết quả cho LLM tổng hợp                    │
│    │◀── Câu trả lời dựa trên JSON vừa nhận               │
│    │                                                     │
│    ▼                                                     │
│  User nhận câu trả lời                                   │
│                                                          │
│  Function Calling = LLM quyết định gọi tool nào (bước 2) │
│  MCP = giao thức kết nối client ↔ server (bước 1, 3)     │
│  → Chúng BỔ SUNG cho nhau, không thay thế                │
└──────────────────────────────────────────────────────────┘
```

---

## Đăng ký server với AI client

**Claude Code** (làm 1 lần, dùng mãi):

```bash
claude mcp add weather -- python /đường/dẫn/tới/weather_server.py
```

**Gemini CLI**:

```bash
# Thêm vào ~/.gemini/settings.json
"mcpServers": {
  "weather": {
    "command": "python",
    "args": ["/đường/dẫn/tới/weather_server.py"]
  }
}
```

Bước tiếp theo: [03-production/](../03-production/) — Auth, Tool Registry, Versioning.
