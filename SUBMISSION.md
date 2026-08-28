# Đối chiếu yêu cầu nộp bài MCP Server

## Mức cơ bản

- [x] **Source code MCP Server tự xây:**
  [`02-mcp-basics/weather_server.py`](02-mcp-basics/weather_server.py) công bố
  tool; [`02-mcp-basics/weather_api.py`](02-mcp-basics/weather_api.py) chứa
  logic định vị, gọi API thật và chuẩn hóa output.
- [x] **Ít nhất 1–2 tools:** `get_weather` và `get_weather_forecast`.
- [x] **README cài đặt/chạy:** xem
  [`02-mcp-basics/README.md`](02-mcp-basics/README.md).
- [x] **Công việc thực tế:** tra cứu current weather và dự báo nhiều ngày cho
  địa điểm Việt Nam để hỗ trợ đi lại, du lịch, sự kiện và vận hành.
- [x] **Input/output:** có bảng kiểu dữ liệu, tham số bắt buộc/default và nội
  dung JSON trả về cho từng tool trong README phần 02.
- [x] **Đăng ký Claude Code:** có lệnh `claude mcp add --transport stdio`, lệnh
  `claude mcp get` và hướng dẫn kiểm tra bằng `/mcp`.
- [x] **Kiểm tra tool:** có unit tests, CLI chatbot và kịch bản gọi thật qua MCP.

## Mức Trung bình

- [x] **Streamable HTTP:**
  [`03-production/auth_server.py`](03-production/auth_server.py), endpoint mặc
  định `http://localhost:8000/mcp`.
- [x] **Bearer-token authentication:** custom `TokenVerifier`, token chỉ đọc từ
  `MCP_AUTH_TOKEN`, so sánh constant-time; không hardcode token trong source.
- [x] **Test token đúng:** `python auth_client.py` phải list/call tool thành công
  và in `PASS`.
- [x] **Test token sai:**
  `python auth_client.py --token definitely-wrong-token --expect-denied` phải
  nhận HTTP 401/403 và in `PASS`.
- [x] **Test thiếu token:**
  `python auth_client.py --no-token --expect-denied` phải nhận HTTP 401/403 và
  in `PASS`.
- [x] **Claude Code qua HTTP:** README phần 03 có CLI command và `.mcp.json`
  dùng `${MCP_AUTH_TOKEN}` để tránh commit secret.

## Bằng chứng kiểm tra trong checkout hiện tại

Ngày kiểm tra: 2026-08-28.

```text
Unit tests phần 02: 4/4 PASS
Streamable HTTP, token đúng: PASS; list_tools + call_tool dữ liệu thật thành công
Streamable HTTP, token sai: PASS; HTTP 401
Streamable HTTP, thiếu token: PASS; HTTP 401
Secret scan trong output MCP trước đó: không phát hiện API key sau khi bật redaction/log guard
```

Lệnh chạy lại đầy đủ nằm trong README của
[`02-mcp-basics`](02-mcp-basics/README.md) và
[`03-production`](03-production/README.md). Kết quả API thời tiết thay đổi theo
thời điểm; không so sánh nhiệt độ với một con số hardcode.
