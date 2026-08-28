# 03 — Production (Auth, Tool Registry, Versioning)

`02-mcp-basics` chạy tốt trên máy cá nhân. Đưa vào production cần giải quyết thêm 3 vấn đề:

| Vấn đề | Demo | Production |
|---|---|---|
| **Auth** | stdio, cùng máy, ai cũng gọi | HTTP + Bearer token / OAuth |
| **Discovery** | Hard-code tool/server | Tool Registry — agent tìm tool theo task |
| **Versioning** | 1 tool duy nhất | v1 + v2 song song, deprecation notice |

## Files

| File | Vấn đề | Mô tả |
|---|---|---|
| `auth_server.py` | Auth | MCP weather server thật qua Streamable HTTP + bearer verifier |
| `auth_client.py` | Auth | Positive/negative test cho token đúng, sai và thiếu |
| `.env.example` | Auth | Mẫu token, weather key và URL; không chứa secret thật |
| `registry.json` | Discovery | Tool Registry — danh mục tool-centric, agent tìm theo tag/keyword |
| `registry_client.py` | Discovery | Agent tra cứu registry, chọn best match, tự kết nối |
| `versioned_server.py` | Versioning | Server v2: giữ tool v1 (deprecated) + thêm v2 + resource metadata |
| `versioned_client.py` | Versioning | Client test gọi tool v1, v2 và đọc `server://info` metadata |

---

## 3a. Authentication

Server chạy qua **Streamable HTTP** thay vì stdio, kèm bearer-token verification.
Nó công bố cùng hai tool thật như phần 02:

| Tool | Input | Output |
|---|---|---|
| `get_weather` | `city: string` | JSON thời tiết hiện tại và địa điểm đã xác thực |
| `get_weather_forecast` | `city: string`, `days: integer = 3` | JSON dự báo theo ngày |

### Cấu hình

```bash
cd 03-production
cp .env.example .env

# Tạo MCP_AUTH_TOKEN mạnh rồi điền token và WEATHER_API_KEY vào .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Không dùng token mẫu trong production và không commit `.env`.

### Khởi động server

```bash
# Terminal 1 — khởi động server
python auth_server.py
# Server lắng nghe tại http://localhost:8000/mcp
```

### Test token đúng

```bash
# Terminal 2 — client kết nối kèm token
python auth_client.py
```

Kỳ vọng: in danh sách hai tool, gọi `get_weather("Hà Nội")` thành công và kết
thúc bằng `PASS: token hợp lệ...`.

### Test token sai

```bash
python auth_client.py --token definitely-wrong-token --expect-denied
```

Kỳ vọng: `PASS: server đã từ chối request (...)`. Nếu request được chấp nhận,
client thoát mã 1 và in `FAIL`.

### Test thiếu token

```bash
python auth_client.py --no-token --expect-denied
```

Kỳ vọng tương tự: server từ chối trước khi `list_tools`/`call_tool` được phép
thực thi. HTTP status cụ thể có thể là 401 hoặc 403 tùy phiên bản MCP SDK; cả
hai đều là kết quả từ chối hợp lệ.

Luồng:

```
Client                                Server
  │                                      │
  │── POST /mcp ──────────────────────▶  │
  │   Authorization: Bearer <token>      │
  │                                      │── TokenVerifier.verify_token()
  │                                      │   token hợp lệ → AccessToken
  │◀── 200 OK (tools, results) ────────  │
  │                                      │
  │── POST /mcp (token sai) ──────────▶  │
  │◀── 401 Unauthorized ───────────────  │
```

- Token hợp lệ → truy cập tool bình thường
- Thiếu/sai token → `401` hoặc `403`, không được khám phá/gọi tool
- Logic tool không biết gì về auth — SDK xử lý ở tầng transport

### Đăng ký bản HTTP với Claude Code

Khởi động `auth_server.py`, export token trong shell chạy Claude Code rồi thêm
server HTTP:

```bash
claude mcp add --transport http \
  --header "Authorization: Bearer YOUR_MCP_AUTH_TOKEN" \
  weather-vietnam-secure http://localhost:8000/mcp

claude mcp get weather-vietnam-secure
```

Để tránh token lưu trong shell history, ưu tiên `.mcp.json` dùng biến môi trường:

```json
{
  "mcpServers": {
    "weather-vietnam-secure": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_AUTH_TOKEN}"
      }
    }
  }
}
```

Sau đó chạy `export MCP_AUTH_TOKEN=...`, mở Claude Code và dùng `/mcp` để xác
nhận server kết nối và hiển thị hai tools.

---

## 3b. Tool Registry & Discovery

Agent **không hard-code** tool nào. Nó hỏi Tool Registry theo yêu cầu task:

```bash
python registry_client.py
```

Kết quả mong đợi:

```
=== Tool Registry ===

  get_weather v1.0.0
    Lấy thời tiết hiện tại của một thành phố
    tags: ['weather', 'current', 'vietnam']  →  server: weather
  get_weather_v2 v2.0.0
    Lấy thời tiết chi tiết — JSON, hỗ trợ forecast và đơn vị đo
    tags: ['weather', 'forecast', 'detailed', 'vietnam']  →  server: weather-v2
  ...

--- Agent cần tool có tag "weather" ---
Tìm thấy 2 tool(s):
  • get_weather v1.0.0 (server: weather)
  • get_weather_v2 v2.0.0 (server: weather-v2)

Best match: get_weather_v2 v2.0.0
Kết nối tới server [weather-v2]...
Kết quả: ...
```

Luồng:

```
Agent nhận task
   │
   ▼
ToolRegistry.search(tag="weather")  ← tìm tool theo capability
   │
   ├── get_weather v1.0 → server: weather
   └── get_weather_v2 v2.0 → server: weather-v2
   │
   ▼
ToolRegistry.best_match()  ← chọn version cao nhất, không deprecated
   │
   ▼
connect_and_call()  ← tự kết nối đúng transport (stdio/HTTP) + auth
```

`registry.json` là **tool-centric** — đơn vị khám phá là tool (tag, description, parameters), không phải server. Production thay JSON bằng DB/API với semantic search.

---

## 3c. Versioning & Backward Compatibility

Server v2 dùng 3 kỹ thuật để thêm tính năng mà không break client cũ:

```bash
# Server chạy qua stdio — client tự spawn
python versioned_client.py
```

| Kỹ thuật | Mô tả |
|---|---|
| **Tool mới song song** | `get_weather_v2` tồn tại bên cạnh `get_weather` — không xoá tool cũ |
| **Tham số optional** | `include_forecast`, `units` có default → client cũ gọi `get_weather_v2(city="Hanoi")` vẫn đúng |
| **Server metadata** | Resource `server://info` công bố version, deprecated tools, migration guide |

```
Server v2
├── get_weather(city)              ← v1, deprecated nhưng vẫn hoạt động
├── get_weather_v2(city, ...)      ← v2, thêm forecast + units
└── resource server://info         ← version + migration guide cho client
```

Kết quả mong đợi:

```
Server: weather-v2 v2.0.0
Deprecated tools: ['get_weather']
Migration: Chuyển từ get_weather sang get_weather_v2. Tham số 'city' giữ nguyên, thêm include_forecast và units.

Tools:
  - get_weather: [v1] Lấy thời tiết hiện tại — trả chuỗi đơn giản. Deprecated, dùng get_weather_v2.
  - get_weather_v2: [v2] Lấy thời tiết chi tiết — JSON, hỗ trợ forecast và đơn vị đo.

[v1] get_weather('Hanoi'):
  Hanoi: 29°C, trời mưa

[v2] get_weather_v2('Hanoi', forecast=True):
  { "api_version": "2.0", "city": "Hanoi", "temp": 29, ... }
```

Luồng:

```
versioned_client.py                     versioned_server.py
       │                                        │
       │── read_resource("server://info") ────▶ │  ← đọc metadata trước
       │◀── version, deprecated_tools ────────  │
       │                                        │
       │── list_tools() ─────────────────────▶  │  ← khám phá tool
       │◀── [get_weather, get_weather_v2] ────  │
       │                                        │
       │── call_tool("get_weather") ──────────▶ │  ← v1 deprecated, vẫn chạy
       │── call_tool("get_weather_v2") ───────▶ │  ← v2 đầy đủ tính năng
```

Client thông minh đọc `server://info` để biết tool nào deprecated, tự chọn dùng v2 nếu có, fallback v1 nếu không.
