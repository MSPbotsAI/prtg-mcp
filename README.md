# prtg-mcp

MCP server for **PRTG Network Monitor** (Paessler network/infrastructure
monitoring). Exposes PRTG's native HTTP API's sensors, devices, and
historic sensor data as MCP tools.

## Overview

- Stateless HTTP service. No credentials are ever persisted — each request
  supplies its own credentials via headers, used only for the lifetime of
  that single request.
- Supports concurrent requests; per-request credential isolation is done via
  Python `contextvars`, not a global/shared client instance.
- Entry points: `POST /mcp` (MCP protocol) and `GET /health` (health check).
- Default port: `8080` (configurable via `MCP_HTTP_PORT`).

## Authentication

Unlike most integrations in this program, PRTG has **no separate login or
token exchange**: the username and a "passhash" (generated in PRTG's UI
under *My Account -> API Key*, not the literal account password) are sent
as plain query parameters on every single call. There is therefore
nothing to cache — each call is already fully self-contained and
stateless by the vendor's own design.

### HEADER 授权参数说明

| Header | 类型 | 是否必填 | 默认值 | 枚举值 | 字段描述 | Example |
|---|---|---|---|---|---|---|
| `X-PRTG-Server-Url` | string | 是 | 无 | 无 | PRTG core server 主机名（不含协议前缀） | `prtg.example.com` |
| `X-PRTG-Username` | string | 是 | 无 | 无 | PRTG API 用户名 | `api_user` |
| `X-PRTG-Passhash` | string | 是 | 无 | 无 | PRTG "passhash"（在 PRTG UI 的 My Account -> API Key 页面生成，不是账号明文密码） | `1234567890` |

Missing any header returns `401`:
```json
{
  "error": "Missing credentials",
  "message": "This server requires the X-PRTG-Server-Url, X-PRTG-Username, and X-PRTG-Passhash headers",
  "required_headers": ["X-PRTG-Server-Url", "X-PRTG-Username", "X-PRTG-Passhash"],
  "optional_headers": []
}
```

An invalid credential surfaces as a tool-level error (PRTG returns
`content=json` errors as either a JSON error field or, for certain
malformed requests, an XML `<error>` body even on the `.json` endpoint —
this server passes the raw response text through as-is on any non-2xx
status).

## Environment Variables

| Variable | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `MCP_HTTP_PORT` | int | 否 | `8080` | HTTP 监听端口 |
| `MCP_HTTP_HOST` | string | 否 | `0.0.0.0` | HTTP 监听地址 |

## MCP Endpoint

- `POST /mcp` — MCP protocol (streamable HTTP transport)
- `GET /health` — health check, returns `{"status": "ok", "service": "prtg-mcp", "transport": "http"}`

## Tool List

| Tool | 功能 | 参数 |
|---|---|---|
| `prtg_get_sensors` | 列出所有传感器及其当前状态/数值 | `count`（可选，默认 500） |
| `prtg_get_devices` | 列出所有受监控设备及其状态/所属 probe/group | `count`（可选，默认 500） |
| `prtg_get_sensor_historic_data` | 获取指定传感器在某日期范围内的历史监控数据 | `sensor_id`、`start_date`、`end_date`（均必填），`avg`（可选，默认 3600 秒） |

Responses are the vendor's raw JSON, pretty-printed, returned as-is.

## 测试示例

```bash
# Health check
curl -s http://localhost:8080/health

# Call a tool via the MCP protocol (streamable HTTP) — requires an
# initialize handshake first per the MCP spec; abbreviated example below
# shows the tool-call request body only:
curl -s -X POST http://localhost:8080/mcp \
  -H "X-PRTG-Server-Url: prtg.example.com" \
  -H "X-PRTG-Username: api_user" \
  -H "X-PRTG-Passhash: <your-passhash>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <session-id-from-initialize>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "prtg_get_sensors",
      "arguments": {}
    }
  }'
```

**Live-verified** (2026-07-30) against a real PRTG core server, all 3
tools called end-to-end through this running server with real
credentials: `prtg_get_sensors` and `prtg_get_devices` both returned `200`
with a real `prtg-version` string and a valid (empty) result set — this
particular test account has zero sensors/devices provisioned under its
visible scope, confirmed as a genuine "no data" condition (not an auth
failure) by separately querying `content=probes`, which returned real
data (the PRTG Root probe plus several real scheduling objects) using the
exact same credentials. `prtg_get_sensor_historic_data`, called with a
non-sensor object ID (since no real sensor ID was available), correctly
reached the API and returned the vendor's own content-level error ("The
selected object cannot be used here"), proving the request/auth pipeline
is wired correctly.

## API Reference

- Public, no login required:
  - Sensors/Devices table format: https://www.paessler.com/manuals/prtg/multiple_object_property_or_status#supported_output
  - Historic data: https://www.paessler.com/manuals/prtg/historic_data

## Known Gaps

- **Scope is exactly MSPbots' 3 configured endpoints, not the vendor's
  full API surface** — PRTG's API also covers live sensor control
  (pause/resume/acknowledge), object creation/deletion, notifications,
  reports, and more; those are out of scope here.
- **Sensor/device data could not be demonstrated with real records** — the
  provided test account (`Dash_Display`, likely a dashboard-only display
  account) has zero sensors and zero devices provisioned in its visible
  scope on this particular PRTG instance. Live testing confirmed this is
  a genuine empty result (not an auth or implementation bug) by
  successfully querying a different, always-populated object type
  (`content=probes`) with the same credentials and getting real data back.
- **`prtg_get_sensor_historic_data` could not be tested with a real
  sensor ID** for the same reason (no sensors exist to reference); it was
  instead verified by confirming the vendor's own content-level error
  response for an invalid object ID, which proves the request format and
  authentication are correct.
