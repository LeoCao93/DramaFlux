# Hongguo Local Server Design

## 1. Purpose

Build a Python 3.10+ learning project that exposes local HTTP endpoints for Hongguo
search, latest releases, rankings, series details, episodes, and single-video
playback metadata.

The project owns the complete local execution path:

1. Discover and control the MuMu 12 instance.
2. Connect through ADB and verify root access.
3. Deploy and start a matching `frida-server`.
4. Attach to the logged-in Hongguo app.
5. Load a Frida JavaScript RPC agent.
6. Ask the app to generate fresh ByteDance security headers.
7. Capture the user's current session and device parameters.
8. Call Hongguo upstream APIs.
9. Normalize upstream responses through a FastAPI server.

The system does not assume that a signing API already exists. It does not
reimplement the native X-Argus/X-Gorgon algorithms offline.

## 2. Confirmed Local Environment

| Item | Value |
|---|---|
| Workspace | `D:\Codex\hongguo-video` |
| MuMu home | `D:\MuMu Player 12` |
| MuMu CLI | `D:\MuMu Player 12\nx_main\mumu-cli.exe` |
| ADB | `D:\MuMu Player 12\shell\adb.exe` |
| MuMu index | `0` |
| ADB endpoint | `127.0.0.1:16384` |
| Android | `12` |
| System ABI | `x86_64` |
| Root | Available through `su` |
| Hongguo package | `com.phoenix.read` |
| Python tooling | `uv`, Python 3.10+ |

The system ABI alone does not prove the target process native architecture.
The bootstrap process must verify that the selected Frida server can attach and
execute Java-layer RPC in the Hongguo process.

## 3. Service Boundaries

The project contains two independently deployable services and one deliberately
small shared package.

### 3.1 Signer Service

The Signer Service owns all device-specific behavior:

- MuMu CLI discovery and app control.
- ADB connection and root checks.
- `frida-server` deployment, startup, and port forwarding.
- Hongguo process attachment.
- Frida JavaScript RPC lifecycle.
- Fresh security-header generation.
- Observation of a natural app request to capture session parameters.
- Watchdog recovery when the app, Frida server, or Frida session changes.

It does not know how search, rankings, series, or video-model responses are
parsed.

### 3.2 API Server

The API Server owns all Hongguo business behavior:

- Load and validate a captured session snapshot.
- Build deterministic upstream URLs and compact JSON request bodies.
- Calculate `x-ss-stub`.
- Request fresh security headers from the Signer Service.
- Call Hongguo upstream APIs.
- Detect session expiry, risk-control responses, timeouts, and malformed data.
- Parse search, latest, ranking, detail, episode, and video-model responses.
- Cache normalized responses.
- Expose the local business HTTP API.

The API Server does not import `frida`, execute ADB, or control MuMu.

### 3.3 Contracts Package

`hongguo-contracts` contains only versioned cross-service HTTP models and error
codes. It must not contain ADB wrappers, Frida lifecycle code, upstream parsers,
service configuration, or cache implementations.

This boundary allows the services to become separate repositories later.

## 4. Repository Layout

```text
hongguo-video/
├── pyproject.toml
├── uv.lock
├── README.md
├── .gitignore
├── packages/
│   └── hongguo-contracts/
│       ├── pyproject.toml
│       └── src/hongguo_contracts/
│           ├── __init__.py
│           ├── signer.py
│           └── errors.py
├── services/
│   ├── signer-service/
│   │   ├── pyproject.toml
│   │   ├── .env.example
│   │   ├── README.md
│   │   ├── scripts/
│   │   │   ├── check_environment.ps1
│   │   │   └── start.ps1
│   │   ├── src/hongguo_signer/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── api/
│   │   │   ├── device/
│   │   │   └── frida_runtime/
│   │   │       ├── manager.py
│   │   │       ├── watchdog.py
│   │   │       └── oracle.js
│   │   └── tests/
│   └── api-server/
│       ├── pyproject.toml
│       ├── .env.example
│       ├── README.md
│       ├── src/hongguo_api/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── signer/
│       │   ├── session/
│       │   ├── upstream/
│       │   ├── parsers/
│       │   └── api/
│       └── tests/
└── docs/
```

## 5. Deployment Topology

### Local development

```text
API Server      127.0.0.1:18000
Signer Service  127.0.0.1:18001
MuMu 12         local Windows host
```

### Future split deployment

```text
Remote API Server
        |
        | authenticated private transport
        v
Local Windows Signer Service
        |
        v
MuMu + logged-in Hongguo app
```

The Signer Service listens on loopback by default. A future remote deployment
must use a private tunnel or VPN plus service authentication, timestamp
validation, request-body HMAC, and allowlisting. It must never be exposed as an
anonymous public signing endpoint.

## 6. Signer Service Design

### 6.1 Device discovery

The service calls:

```powershell
& "D:\MuMu Player 12\nx_main\mumu-cli.exe" info --vmindex 0
```

It reads `adb_host_ip`, `adb_port`, and `player_state`, then connects with the
bundled ADB executable. It verifies:

- The device is online.
- `su -c id` returns UID 0.
- `com.phoenix.read` is installed.
- The app process can be launched and located.

### 6.2 Frida lifecycle

The Python `frida` package and Android `frida-server` must have matching
versions. Bootstrap verifies the local binary before pushing it to:

```text
/data/local/tmp/frida-server
```

It applies mode `755`, starts the process through `su`, and forwards TCP port
27042. No automatic binary download occurs during normal service startup.

### 6.3 Frida RPC agent

`oracle.js` exposes:

```javascript
rpc.exports = {
  health: function () {},
  sign: function (url, headers) {},
  grab: function (timeoutMs) {}
};
```

`sign()` converts the Python header object into the Java map shape expected by
`NetworkParams.tryAddSecurityFactor(String, Map)`, calls that method inside the
app process, and returns only approved security headers.

The approved response-header set is:

```text
X-Argus
X-Gorgon
X-Ladon
X-Khronos
X-Helios
X-Medusa
X-SS-REQ-TICKET
```

`grab()` temporarily observes a natural Hongguo request and returns a sanitized
session snapshot to an authenticated local caller.

### 6.4 HTTP contract

```http
GET  /v1/health
POST /v1/sign
POST /v1/session/capture
POST /v1/admin/reconnect
```

Frida RPC calls are serialized. The watchdog checks the MuMu instance, ADB,
root, app PID, Frida server, attached session, and agent health. A changed app
PID or detached session causes a new attachment.

## 7. Session Snapshot

The captured snapshot contains:

```text
api_host
iid
device_id
cdid
klink_egdi
aid
app_name
version_code
version_name
channel
device_platform
device_type
os_version
cookie
x-tt-token
user-agent
x-tt-store-region
x-tt-store-region-src
passport-sdk-version
sdk-version
```

The API Server stores it at `.local/session.json`, outside version control.
Logs must redact cookies, tokens, authorization values, and signed playback URL
query strings.

## 8. Signed Upstream Transport

For every upstream request the API Server:

1. Builds the final URL, including device query fields and `_rticket`.
2. Serializes JSON with UTF-8 and compact separators.
3. Calculates uppercase MD5 over the exact body bytes as `x-ss-stub`.
4. Sends the final URL and signing headers to the Signer Service.
5. Merges returned security headers.
6. Sends the unchanged URL, body bytes, and headers with `httpx`.

Nothing that affects signing may change after step 4.

The transport includes connection pooling, explicit timeouts, low concurrency,
throttling, bounded retries, session-expiry detection, risk-control detection,
JSON validation, and sensitive-log redaction.

## 9. Upstream Capabilities

### Search

```http
GET /reading/bookapi/search/tab/v
```

Pagination uses `next_offset`, `passback`, `search_id`, and `has_more`. The local
API exposes an opaque cursor so callers do not depend on upstream cursor shape.

### Latest releases

```http
POST /reading/distribution/category/landpage/v
```

Short-play items are considered today's releases only when
`sub_title_list[].content` contains `今日上新`. Comic and AI categories use the
available seven-day/latest semantics and are labelled honestly.

### Rankings

```http
GET /reading/bookapi/bookmall/cell/change/v
```

The initial ranking cell is `7470092475068071998`. Public board names map to
the appropriate upstream selection values.

### Series details and episodes

```http
POST /novel/player/multi_video_detail/v1/
```

The parser reads series metadata and ordered entries from
`video_data.video_list[]`.

### Video model

```http
POST /novel/player/multi_video_model/v1/
```

The parser decodes the nested `video_model` JSON, filters unusable entries, and
selects an exact or best fallback quality using definition, height, bitrate,
codec, and encryption metadata.

Encrypted streams are reported as unsupported. The project does not implement
DRM or CENC decryption.

## 10. API Server Endpoints

```http
GET /health
GET /api/search?q=&cursor=
GET /api/latest?genre=short_play&today_only=true&cursor=
GET /api/rank?board=hot&cursor=
GET /api/books/{series_id}
GET /api/books/{series_id}/episodes
GET /api/videos/{video_id}?quality=1080p
```

Success responses contain `code`, `message`, `data`, `cached`, and
`request_id`. Errors use stable machine-readable codes.

## 11. Caching and Throttling

Initial in-memory TTL values:

| Data | TTL |
|---|---|
| Search | 5 minutes |
| Latest | 10 minutes |
| Ranking | 10 minutes |
| Series details | 6 hours |
| Video model | 30 minutes or before known expiry |

Upstream calls use low concurrency. The first API version resolves only one
video per request.

## 12. Error Model

Stable error codes include:

```text
device_unavailable
root_unavailable
frida_server_unavailable
frida_attach_failed
signer_method_not_found
signer_unavailable
session_missing
session_expired
risk_controlled
upstream_timeout
upstream_invalid_response
book_not_found
video_not_found
encrypted_stream_unsupported
```

Signer health and API health remain separate. API health reports Signer
reachability and session state without exposing credentials.

## 13. Testing

Unit tests cover command parsing, deterministic request construction,
`x-ss-stub`, header allowlisting, redaction, all response parsers, cursor
encoding, quality fallback, and encryption detection.

Integration tests replace Frida RPC and upstream HTTP with fakes while exercising
the real FastAPI routes and service clients.

Live tests are opt-in and require the local MuMu instance:

```powershell
$env:HONGGUO_RUN_LIVE_TESTS="1"
uv run pytest tests/live -v
```

Signer acceptance requires repeated signing, app restart recovery,
`frida-server` restart recovery, successful harmless upstream validation, and
no secret leakage in logs.

## 14. Scope Exclusions

The first version does not include:

- Offline reconstruction of ByteDance signing algorithms.
- DRM or CENC decryption.
- Video proxying or bulk downloading.
- Full-catalog scraping.
- Public anonymous signing.
- User, billing, VIP, database, or web frontend features.
- Private aggregation fields that are not present in Hongguo responses.

