# DramaFlux REST API Contract Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the existing DramaFlux REST endpoints with explicit pagination inputs, richer response fields, additional rank boards, real cache-hit reporting, and richer video metadata without adding API-key authentication or pretending encrypted streams are playable.

**Architecture:** Keep FastAPI routes, `CachedHongguoService`, `HongguoClient`, signed transport, and response parsers as separate layers. Add shared pagination/value models, keep upstream continuation state inside versioned opaque cursors, and make the cache decorator return value-plus-hit metadata so the route envelope can report `cached` accurately.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic v2, httpx, cachetools, pytest, pytest-asyncio, respx, Ruff, uv

---

## File Structure

### Files to modify

- `services/api-server/src/hongguo_api/models.py`
  - Rich shared drama summary and paginated response models.
- `services/api-server/src/hongguo_api/api/schemas.py`
  - Cache-aware public response envelope.
- `services/api-server/src/hongguo_api/api/routes.py`
  - New list pagination inputs, rank enum, ID limits, and video `fast`.
- `services/api-server/src/hongguo_api/cache.py`
  - Value-plus-cache-hit results and complete cache keys.
- `services/api-server/src/hongguo_api/bootstrap_app.py`
  - Updated missing-session method signatures.
- `services/api-server/src/hongguo_api/upstream/client.py`
  - Pagination state, latest page collection, rank mappings, search request, and video `fast`.
- `services/api-server/src/hongguo_api/parsers/search.py`
  - Rich fields and current captured search shape.
- `services/api-server/src/hongguo_api/parsers/latest.py`
  - Rich latest fields and page-level parsing.
- `services/api-server/src/hongguo_api/parsers/rank.py`
  - Rich fields, rank numbering, and continuation state.
- `services/api-server/src/hongguo_api/parsers/detail.py`
  - Rich series and episode metadata.
- `services/api-server/src/hongguo_api/parsers/video.py`
  - `vid`, expiry metadata, and model-level fallback fields.
- `services/api-server/README.md`
  - Final public contracts and examples.
- `services/api-server/tests/live/test_api_live.py`
  - Expanded opt-in live coverage.

### Files to create

- `services/api-server/src/hongguo_api/pagination.py`
  - Shared validated page request and versioned opaque cursor helpers.
- `services/api-server/tests/unit/test_pagination.py`
  - Cursor and page-request tests.
- `services/api-server/tests/unit/test_upstream_client_lists.py`
  - Multi-page latest/rank/search request behavior.
- `services/api-server/tests/fixtures/search_current.json`
  - Sanitized current App search response captured during Task 7.

### Existing tests to modify

- `services/api-server/tests/unit/test_list_parsers.py`
- `services/api-server/tests/unit/test_cache.py`
- `services/api-server/tests/unit/test_detail_video_parsers.py`
- `services/api-server/tests/unit/test_upstream_client_detail_video.py`
- `services/api-server/tests/integration/test_routes.py`
- `services/api-server/tests/integration/test_error_mapping.py`

---

### Task 1: Add Rich Shared Models and Pagination Primitives

**Files:**
- Create: `services/api-server/src/hongguo_api/pagination.py`
- Create: `services/api-server/tests/unit/test_pagination.py`
- Modify: `services/api-server/src/hongguo_api/models.py`
- Modify: `services/api-server/tests/unit/test_list_parsers.py`

- [ ] **Step 1: Write failing tests for page validation and opaque cursor round trips**

Create `test_pagination.py` with focused tests:

```python
import pytest

from hongguo_api.pagination import (
    CursorError,
    PageRequest,
    decode_cursor,
    encode_cursor,
)


def test_page_request_accepts_default_first_page() -> None:
    request = PageRequest(page=1, page_size=30, cursor=None)
    assert request.offset == 0


def test_page_request_rejects_cursor_with_explicit_later_page() -> None:
    with pytest.raises(ValueError, match="cursor"):
        PageRequest(page=2, page_size=30, cursor="next")


def test_cursor_round_trips_versioned_namespace_and_state() -> None:
    cursor = encode_cursor(
        "latest",
        {"offset": 18, "session_id": "s", "filter_ids": ["1", "2"]},
    )
    assert decode_cursor(cursor, "latest") == {
        "offset": 18,
        "session_id": "s",
        "filter_ids": ["1", "2"],
    }


def test_cursor_rejects_wrong_namespace() -> None:
    cursor = encode_cursor("latest", {"offset": 18})
    with pytest.raises(CursorError):
        decode_cursor(cursor, "rank")
```

- [ ] **Step 2: Write failing tests for the additive summary and page fields**

Extend `test_list_parsers.py` to assert that a minimally populated
`DramaItem` has stable defaults:

```python
from hongguo_api.models import DramaItem, DramaPage


def test_drama_models_expose_stable_additive_defaults() -> None:
    item = DramaItem(series_id="1", title="title")
    assert item.author == ""
    assert item.type == ""
    assert item.categories == []
    assert item.duration == ""
    assert item.publish_time == ""
    assert item.intro == ""
    assert item.record_number == ""
    assert item.subtitles == []
    assert item.rank is None
    assert item.score is None

    page = DramaPage(page=2, page_size=30)
    assert page.page == 2
    assert page.page_size == 30
    assert page.total is None
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```powershell
uv run pytest `
  services/api-server/tests/unit/test_pagination.py `
  services/api-server/tests/unit/test_list_parsers.py `
  -q
```

Expected: import/model-field failures because the pagination module and fields
do not exist.

- [ ] **Step 4: Implement the shared pagination module**

Implement:

```python
class CursorError(ValueError):
    pass


class PageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=30, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def validate_mode(self) -> "PageRequest":
        if self.cursor is not None and self.page != 1:
            raise ValueError("cursor cannot be combined with page > 1")
        return self

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
```

Use URL-safe Base64 JSON cursors with:

```json
{"v":1,"ns":"latest","state":{...}}
```

Reject non-dict state, wrong version, wrong namespace, malformed Base64, values
deeper than two nested collection levels, and encoded cursors longer than 4096
characters.

- [ ] **Step 5: Extend the shared models**

Add to `DramaItem`:

```python
author: str = ""
type: str = ""
duration: str = ""
publish_time: str = ""
intro: str = ""
record_number: str = ""
subtitles: list[str] = Field(default_factory=list)
rank: int | None = Field(default=None, ge=1)
score: float | None = None
```

Extend `DramaPage`:

```python
page: int = Field(default=1, ge=1)
page_size: int = Field(default=30, ge=1, le=100)
total: int | None = Field(default=None, ge=0)
```

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the command from Step 3.

Expected: all pagination and model-default tests pass.

- [ ] **Step 7: Commit Task 1**

```powershell
git add services/api-server/src/hongguo_api/models.py `
  services/api-server/src/hongguo_api/pagination.py `
  services/api-server/tests/unit/test_pagination.py `
  services/api-server/tests/unit/test_list_parsers.py
git commit -m "feat(api): add rich list models and pagination primitives"
```

---

### Task 2: Report Real Cache Hits and Accept Expanded Route Inputs

**Files:**
- Modify: `services/api-server/src/hongguo_api/cache.py`
- Modify: `services/api-server/src/hongguo_api/api/schemas.py`
- Modify: `services/api-server/src/hongguo_api/api/routes.py`
- Modify: `services/api-server/src/hongguo_api/bootstrap_app.py`
- Modify: `services/api-server/tests/unit/test_cache.py`
- Modify: `services/api-server/tests/integration/test_routes.py`

- [ ] **Step 1: Write failing cache metadata tests**

Define the expected cache result:

```python
from hongguo_api.cache import CachedResult


async def test_cache_reports_miss_then_hit() -> None:
    source = CountingService()
    cached = CachedHongguoService(source)

    first = await cached.search("测试", 1, 30, None)
    second = await cached.search("测试", 1, 30, None)

    assert first == CachedResult(value=first.value, cached=False)
    assert second == CachedResult(value=first.value, cached=True)
```

Add cache-key tests proving these are distinct:

```text
search page_size 30 versus 50
latest today_only true versus false
rank hot versus new
video fast true versus false
```

- [ ] **Step 2: Write failing route-contract tests**

Update `FakeHongguo` signatures:

```python
async def search(self, query, page, page_size, cursor): ...
async def latest(self, genre, today_only, page, page_size, cursor): ...
async def rank(self, board, page, page_size, cursor): ...
async def resolve_video(self, video_id, quality, fast): ...
```

Return `CachedResult(value=..., cached=...)`.

Add assertions:

```python
def test_list_routes_forward_page_inputs() -> None:
    response = client.get(
        "/api/search",
        params={"q": "测试", "page": 2, "page_size": 50},
    )
    assert response.json()["data"]["page"] == 2


def test_route_envelope_reports_cache_hit() -> None:
    response = client.get("/api/search", params={"q": "测试"})
    assert response.json()["cached"] is True


def test_cursor_cannot_be_combined_with_later_page() -> None:
    response = client.get(
        "/api/search",
        params={"q": "测试", "cursor": "c", "page": 2},
    )
    assert response.status_code == 422
```

Parametrize validation for:

```text
page=0
page_size=0
page_size=101
unknown rank board
unsupported quality such as 900p
series/video IDs longer than 64 characters
```

- [ ] **Step 3: Run tests and verify RED**

```powershell
uv run pytest `
  services/api-server/tests/unit/test_cache.py `
  services/api-server/tests/integration/test_routes.py `
  -q
```

Expected: signature and missing `CachedResult` failures.

- [ ] **Step 4: Implement cache result metadata**

Add:

```python
@dataclass(frozen=True)
class CachedResult(Generic[T]):
    value: T
    cached: bool
```

Change `_get()` to return `CachedResult(value=..., cached=True)` for hits and
`cached=False` after a successful factory call.

Update all method signatures and keys:

```python
search(query, page, page_size, cursor)
latest(genre, today_only, page, page_size, cursor)
rank(board, page, page_size, cursor)
detail(series_id)
resolve_video(video_id, quality, fast)
```

For `fast=False`, bypass reading and writing the video cache. This implements
the documented fresh-model behavior without adding a second cache API.

- [ ] **Step 5: Implement route inputs and cache-aware envelopes**

Use `Literal` aliases:

```python
Genre = Literal["short_play", "comic_series", "ai_series"]
RankBoard = Literal[
    "recommend",
    "hot",
    "new",
    "must_watch",
    "followed",
    "hot_search",
]
VideoQuality = Literal["360p", "480p", "540p", "720p", "1080p"]
```

Build `PageRequest` inside list routes and pass its values to the service.
Wrap `CachedResult.value` in `ApiResponse` and set `cached` from the result.

Constrain path IDs with:

```python
Path(min_length=1, max_length=64)
```

- [ ] **Step 6: Update missing-session signatures**

Update `MissingSessionService` to accept every new parameter and continue
raising `SessionMissingError` without reading the values.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run the command from Step 3.

Expected: all cache and route tests pass.

- [ ] **Step 8: Commit Task 2**

```powershell
git add services/api-server/src/hongguo_api/cache.py `
  services/api-server/src/hongguo_api/api/schemas.py `
  services/api-server/src/hongguo_api/api/routes.py `
  services/api-server/src/hongguo_api/bootstrap_app.py `
  services/api-server/tests/unit/test_cache.py `
  services/api-server/tests/integration/test_routes.py
git commit -m "feat(api): add pagination inputs and cache metadata"
```

---

### Task 3: Enrich and Paginate Latest Results

**Files:**
- Modify: `services/api-server/src/hongguo_api/parsers/latest.py`
- Modify: `services/api-server/src/hongguo_api/upstream/client.py`
- Create: `services/api-server/tests/unit/test_upstream_client_lists.py`
- Modify: `services/api-server/tests/unit/test_list_parsers.py`
- Modify: `services/api-server/tests/fixtures/latest.json`

- [ ] **Step 1: Extend the fixture and write rich-field parser tests**

Add realistic fields to the first latest item:

```json
{
  "author": "影黎万像",
  "publish_time": "2026-06-13 00:16:00",
  "video_desc": "简介",
  "record_number": "网微剧备字",
  "duration": "1小时48分钟",
  "play_cnt": 1041,
  "sub_title_list": [
    {"content": "今日上新"},
    {"content": "战神归来"}
  ]
}
```

Assert every corresponding `DramaItem` field.

- [ ] **Step 2: Write a failing multi-page collection test**

Use `RecordingTransport` with two queued payloads:

```python
async def test_latest_collects_today_items_across_pages() -> None:
    transport = SequencedTransport([first_page, second_page])
    result = await HongguoClient(transport).latest(
        "short_play",
        True,
        page=1,
        page_size=2,
        cursor=None,
    )

    assert [item.series_id for item in result.items] == ["today-1", "today-2"]
    assert len(transport.calls) == 2
    assert transport.calls[1][2]["body"]["offset"] == 2
    assert transport.calls[1][2]["body"]["filter_ids"] == "today-1,old-1"
    assert result.has_more is True
    assert result.next_cursor is not None
```

Add a cursor-resume test proving `offset`, `session_id`, and `filter_ids` are
restored.

- [ ] **Step 3: Run tests and verify RED**

```powershell
uv run pytest `
  services/api-server/tests/unit/test_list_parsers.py `
  services/api-server/tests/unit/test_upstream_client_lists.py `
  -q
```

Expected: missing rich fields and old single-request behavior.

- [ ] **Step 4: Make `parse_latest` parse one upstream page richly**

Populate:

```text
author <- author or copyright
publish_time <- publish_time
intro <- video_desc or intro
record_number <- record_number
duration <- duration
play_count <- play_cnt
subtitles <- every non-empty sub_title_list.content
type <- first non-operational subtitle/category
categories <- category_schema, falling back to clean subtitles
```

Do not perform `today_only` filtering in the parser. Return all normalized page
items with `is_today` marked so collection policy remains in `HongguoClient`.

- [ ] **Step 5: Implement bounded latest collection**

In `HongguoClient.latest`:

1. Decode a `latest` cursor or start from `PageRequest.offset`.
2. Send at most 20 upstream requests.
3. Append every seen series ID to `filter_ids`.
4. For short-play today mode, append only `is_today` items to output.
5. Stop when enough output exists, upstream ends, or a post-today page has no
   today entries.
6. Slice to `page_size`.
7. Encode remaining continuation state into `next_cursor`.
8. Return `DramaPage(page, page_size, items, next_cursor, has_more)`.

- [ ] **Step 6: Run tests and verify GREEN**

Run the command from Step 3.

- [ ] **Step 7: Commit Task 3**

```powershell
git add services/api-server/src/hongguo_api/parsers/latest.py `
  services/api-server/src/hongguo_api/upstream/client.py `
  services/api-server/tests/unit/test_upstream_client_lists.py `
  services/api-server/tests/unit/test_list_parsers.py `
  services/api-server/tests/fixtures/latest.json
git commit -m "feat(api): paginate and enrich latest results"
```

---

### Task 4: Add Rich Rank Results and Six Board Types

**Files:**
- Modify: `services/api-server/src/hongguo_api/parsers/rank.py`
- Modify: `services/api-server/src/hongguo_api/upstream/client.py`
- Modify: `services/api-server/tests/unit/test_list_parsers.py`
- Modify: `services/api-server/tests/unit/test_upstream_client_lists.py`
- Modify: `services/api-server/tests/fixtures/rank.json`

- [ ] **Step 1: Write failing parser tests for rich fields and absolute ranks**

Call:

```python
page = parse_rank(load("rank.json"), rank_offset=30, page=2, page_size=30)
```

Assert:

```python
assert page.items[0].rank == 31
assert page.items[0].author == "作者"
assert page.items[0].intro == "简介"
assert page.items[0].duration == "1小时"
assert page.items[0].publish_time == "2026-06-12 10:00:00"
```

- [ ] **Step 2: Write failing mapping tests for all boards**

Parametrize:

```python
[
    ("recommend", "comic_series_hot_rank"),
    ("hot", "comic_series_hot_play"),
    ("new", "comic_series_new_rank"),
    ("must_watch", "ranklist_must_watch"),
    ("followed", "ranklist_followed"),
    ("hot_search", "ranklist_hot_search_sc"),
]
```

Also assert that page 2 sends the correct upstream offset and that a rank
cursor restores `next_offset` and `session_id`.

- [ ] **Step 3: Run tests and verify RED**

```powershell
uv run pytest `
  services/api-server/tests/unit/test_list_parsers.py `
  services/api-server/tests/unit/test_upstream_client_lists.py `
  -q
```

- [ ] **Step 4: Extend mappings and rank parser**

Add the three selector IDs. Extend `parse_rank` with keyword-only
`rank_offset`, `page`, and `page_size`.

Read continuation fields from either:

```text
data.cell_view.next_offset / has_more / session_id
data.next_offset / has_more / session_id
```

Populate the shared rich fields using the same normalization rules as latest.

- [ ] **Step 5: Implement rank pagination**

Use public page offset for the first request. For cursor requests, restore the
upstream offset/session. Include the board in cursor state and reject a cursor
created for another board.

Generate `next_cursor` only when upstream `has_more` and a valid next offset
are present.

- [ ] **Step 6: Run tests and verify GREEN**

Run the command from Step 3.

- [ ] **Step 7: Commit Task 4**

```powershell
git add services/api-server/src/hongguo_api/parsers/rank.py `
  services/api-server/src/hongguo_api/upstream/client.py `
  services/api-server/tests/unit/test_list_parsers.py `
  services/api-server/tests/unit/test_upstream_client_lists.py `
  services/api-server/tests/fixtures/rank.json
git commit -m "feat(api): expand rank boards and metadata"
```

---

### Task 5: Enrich Series and Episode Details

**Files:**
- Modify: `services/api-server/src/hongguo_api/parsers/detail.py`
- Modify: `services/api-server/tests/unit/test_detail_video_parsers.py`
- Modify: `services/api-server/tests/fixtures/detail.json`
- Modify: `services/api-server/tests/integration/test_routes.py`
- Modify: `services/api-server/tests/integration/test_error_mapping.py`

- [ ] **Step 1: Write failing rich detail tests**

Extend the fixture with:

```text
author
category/category_schema
duration
publish_time
firstPassTime
volume_name
```

Assert:

```python
assert detail.author == "作者"
assert detail.category == "校园"
assert detail.categories == ["校园", "家庭"]
assert detail.duration == "20分钟"
assert detail.publish_time == "2026-04-08 16:11:04"
assert detail.episodes[0].first_pass_time == "2026-04-08 16:06:06"
assert detail.episodes[0].volume_name == ""
assert detail.episodes[0].duration_seconds == 60
```

- [ ] **Step 2: Write failing 404-versus-502 tests**

Keep explicit missing data mapped to `DetailNotFoundError`, but assert malformed
wrapper/video data maps to HTTP 502.

Add a route test proving `/api/books/{id}/episodes` returns the exact same
episode objects present in detail.

- [ ] **Step 3: Run tests and verify RED**

```powershell
uv run pytest `
  services/api-server/tests/unit/test_detail_video_parsers.py `
  services/api-server/tests/integration/test_routes.py `
  services/api-server/tests/integration/test_error_mapping.py `
  -q
```

- [ ] **Step 4: Extend detail models and parsing**

Add to `Episode`:

```python
first_pass_time: str = ""
volume_name: str = ""
duration_seconds: int | None = Field(default=None, ge=0)
```

Replace the old public `duration` integer with `duration_seconds`. Preserve
fixture compatibility by reading the same upstream `duration` field.

Add to `SeriesDetail`:

```python
author: str = ""
category: str = ""
categories: list[str] = Field(default_factory=list)
duration: str = ""
publish_time: str = ""
```

Normalize categories from a list or JSON category schema, deduplicating while
preserving source order.

- [ ] **Step 5: Run tests and verify GREEN**

Run the command from Step 3.

- [ ] **Step 6: Commit Task 5**

```powershell
git add services/api-server/src/hongguo_api/parsers/detail.py `
  services/api-server/tests/unit/test_detail_video_parsers.py `
  services/api-server/tests/fixtures/detail.json `
  services/api-server/tests/integration/test_routes.py `
  services/api-server/tests/integration/test_error_mapping.py
git commit -m "feat(api): enrich series and episode details"
```

---

### Task 6: Add Video `fast`, `vid`, and Expiry Metadata

**Files:**
- Modify: `services/api-server/src/hongguo_api/parsers/video.py`
- Modify: `services/api-server/src/hongguo_api/upstream/client.py`
- Modify: `services/api-server/tests/unit/test_detail_video_parsers.py`
- Modify: `services/api-server/tests/unit/test_upstream_client_detail_video.py`
- Modify: `services/api-server/tests/integration/test_routes.py`

- [ ] **Step 1: Write failing parser tests**

Add an unencrypted object-shaped video model with:

```json
{
  "video_id": "v02-model-id",
  "video_list": {
    "video_1": {
      "definition": "720p",
      "main_url": "https://video.test/stream?x-expires=1893456000",
      "video_id": "vod-id",
      "encrypt": false
    }
  }
}
```

Assert:

```python
assert video.vid == "v02-model-id"
assert video.vod_id == "vod-id"
assert video.expires_at == "2030-01-01T00:00:00Z"
```

The fixed epoch keeps this test independent of the current date and local
timezone.

- [ ] **Step 2: Write failing client and route tests for `fast`**

Assert `fast=false` reaches `HongguoClient.resolve_video(..., fast=False)` and
that the route only accepts the five documented qualities.

The upstream request body remains the same for both modes; freshness is
implemented by Task 2's cache bypass.

- [ ] **Step 3: Run tests and verify RED**

```powershell
uv run pytest `
  services/api-server/tests/unit/test_detail_video_parsers.py `
  services/api-server/tests/unit/test_upstream_client_detail_video.py `
  services/api-server/tests/integration/test_routes.py `
  -q
```

- [ ] **Step 4: Extend `VideoResult` and parser context**

Add:

```python
vid: str = ""
expires_at: str | None = None
```

Pass the model-level `video_id` into candidate/result fallback so `vid` does
not depend on stream-level fields.

Recognize expiry query keys:

```text
x-expires
expires
expire
```

Only accept positive Unix-second values and format them as UTC ISO 8601 with a
trailing `Z`.

- [ ] **Step 5: Preserve encrypted-stream rejection**

Keep the existing rule:

```python
if not unencrypted:
    raise EncryptedStreamError(...)
```

Add a regression assertion that `fast=false` does not alter the 422 behavior.

- [ ] **Step 6: Run tests and verify GREEN**

Run the command from Step 3.

- [ ] **Step 7: Commit Task 6**

```powershell
git add services/api-server/src/hongguo_api/parsers/video.py `
  services/api-server/src/hongguo_api/upstream/client.py `
  services/api-server/tests/unit/test_detail_video_parsers.py `
  services/api-server/tests/unit/test_upstream_client_detail_video.py `
  services/api-server/tests/integration/test_routes.py
git commit -m "feat(api): enrich video resolution metadata"
```

---

### Task 7: Capture and Repair the Current Red Fruit Search Request

**Files:**
- Create: `services/api-server/tests/fixtures/search_current.json`
- Modify: `services/api-server/src/hongguo_api/upstream/client.py`
- Modify: `services/api-server/src/hongguo_api/parsers/search.py`
- Modify: `services/api-server/tests/unit/test_list_parsers.py`
- Modify: `services/api-server/tests/unit/test_upstream_client_lists.py`
- Modify: `services/api-server/tests/live/test_api_live.py`

- [ ] **Step 1: Capture a natural search request**

Start capture:

```powershell
$env:HONGGUO_API_SIGNER_TOKEN="local-development"
.\services\api-server\scripts\capture_session.ps1
```

In the installed Red Fruit App, search for the exact known title `烬九州` and
open the result list. Save the newly captured session.

Inspect the capture without printing cookies, tokens, or dynamic signature
headers. Record only:

```text
HTTP method
URL path
non-device business query keys
whether a request body exists
top-level response keys
selected search tab shape
```

- [ ] **Step 2: Save a sanitized current response fixture**

Create `search_current.json` from the captured response:

- Keep structural keys and two representative result cells.
- Replace cookies, tokens, log IDs, device IDs, signed URLs, and user IDs.
- Keep series/video IDs as harmless test strings such as `"current-100"`.
- Preserve the actual nesting and field names byte-for-byte.

- [ ] **Step 3: Write failing tests from the captured evidence**

Add:

```python
def test_search_parser_accepts_current_app_shape() -> None:
    page = parse_search(load("search_current.json"), page=1, page_size=30)
    assert page.items
    assert page.items[0].series_id == "current-100"
    assert page.items[0].author
    assert page.items[0].intro
```

Add a client test that asserts the exact captured business path, method, and
business parameters. Do not assert dynamic device/base-query parameters owned
by `SignedTransport`.

- [ ] **Step 4: Run tests and verify RED**

```powershell
uv run pytest `
  services/api-server/tests/unit/test_list_parsers.py `
  services/api-server/tests/unit/test_upstream_client_lists.py `
  -q
```

Expected: current parser/request construction does not match captured evidence.

- [ ] **Step 5: Implement the captured request exactly**

Replace only the search-specific method/path/business parameters in
`HongguoClient.search`. Keep URL construction, `_rticket`, body hashing, and
X-Argus/X-Gorgon signing inside `SignedTransport`.

Support:

```text
page 1 offset 0
page N offset (page - 1) * page_size when upstream offset supports it
captured passback/search_id state via search cursor
page_size mapped to the captured count/limit field
```

- [ ] **Step 6: Extend search parsing without breaking the legacy fixture**

Extract shared rich fields from both the legacy and captured cell shapes.
Continue treating a successful `data=null` response as an empty page.

- [ ] **Step 7: Run unit and opt-in live verification**

```powershell
uv run pytest `
  services/api-server/tests/unit/test_list_parsers.py `
  services/api-server/tests/unit/test_upstream_client_lists.py `
  -q

$env:HONGGUO_RUN_LIVE_TESTS="1"
uv run pytest services/api-server/tests/live/test_api_live.py `
  -k search -v
```

Expected: unit tests pass and live search for `妈妈` returns at least one Red
Fruit result. The result count is not compared with the reference service
because that service aggregates multiple platforms.

- [ ] **Step 8: Commit Task 7**

```powershell
git add services/api-server/tests/fixtures/search_current.json `
  services/api-server/src/hongguo_api/upstream/client.py `
  services/api-server/src/hongguo_api/parsers/search.py `
  services/api-server/tests/unit/test_list_parsers.py `
  services/api-server/tests/unit/test_upstream_client_lists.py `
  services/api-server/tests/live/test_api_live.py
git commit -m "fix(api): align search with current app request"
```

---

### Task 8: Update Documentation and Complete End-to-End Verification

**Files:**
- Modify: `services/api-server/README.md`
- Modify: `services/api-server/tests/live/test_api_live.py`

- [ ] **Step 1: Write live contract tests before documentation**

Add opt-in live tests for:

```text
latest today_only=false returns rich fields
latest today_only=true only returns is_today=true entries
all six rank boards return valid page envelopes
detail episode_count matches episode list when upstream returns all episodes
episodes endpoint equals detail.episodes
video response is either rich HTTP 200 or encrypted-stream HTTP 422
second identical cached request returns cached=true
fast=false returns cached=false
```

- [ ] **Step 2: Run live tests and verify failures expose remaining gaps**

```powershell
$env:HONGGUO_RUN_LIVE_TESTS="1"
$env:HONGGUO_LIVE_SERIES_ID="7647789981687106622"
uv run pytest services/api-server/tests/live -v
```

Fix only implementation defects exposed by these contract tests. If an
upstream board is unavailable for the current session, assert the stable
risk/session error rather than weakening unit coverage.

- [ ] **Step 3: Update README contracts**

Document exact requests:

```text
GET /api/search?q=妈妈&page=1&page_size=30
GET /api/latest?genre=short_play&today_only=true&page=1&page_size=30
GET /api/rank?board=hot&page=1&page_size=30
GET /api/books/{series_id}
GET /api/books/{series_id}/episodes
GET /api/videos/{video_id}?quality=1080p&fast=true
```

Include:

- Complete list/detail/video response examples.
- Six rank board values.
- Cursor/page conflict rule.
- `cached` semantics.
- No `api_key` requirement.
- Search is Red Fruit only, not multi-platform aggregation.
- Encrypted stream 422 boundary.

- [ ] **Step 4: Run the complete verification suite**

```powershell
$env:UV_CACHE_DIR="D:\Codex\hongguo-video\.uv-cache"
uv run ruff check services/api-server
uv run pytest -q
git diff --check
```

Expected:

```text
Ruff: All checks passed
Pytest: all non-live tests passed, live tests skipped unless enabled
git diff --check: no output
```

- [ ] **Step 5: Restart API Server and smoke test public routes**

Restart only the process listening on port 18000, then call:

```powershell
Invoke-RestMethod "http://127.0.0.1:18000/health"
Invoke-RestMethod "http://127.0.0.1:18000/api/search?q=妈妈&page=1&page_size=5"
Invoke-RestMethod "http://127.0.0.1:18000/api/latest?genre=short_play&today_only=false&page=1&page_size=5"
Invoke-RestMethod "http://127.0.0.1:18000/api/rank?board=hot&page=1&page_size=5"
Invoke-RestMethod "http://127.0.0.1:18000/api/books/7647789981687106622"
Invoke-RestMethod "http://127.0.0.1:18000/api/videos/7647791842397801534?quality=1080p&fast=true"
```

Expected:

- Health is 200.
- List and detail envelopes contain the new fields.
- Repeated identical requests report `cached=true`.
- The known encrypted video returns the stable 422 error.

- [ ] **Step 6: Commit Task 8**

```powershell
git add services/api-server/README.md `
  services/api-server/tests/live/test_api_live.py
git commit -m "docs(api): document expanded REST contracts"
```

---

## Final Acceptance Criteria

- Existing REST paths remain valid.
- No public endpoint requires `api_key`.
- Search, latest, and rank accept `page`, `page_size`, and opaque `cursor`.
- Cursor and `page > 1` conflict with HTTP 422 validation.
- Shared list items expose all additive metadata with stable defaults.
- Latest scans bounded upstream pages for official today labels.
- All six rank board names are accepted and mapped.
- Detail and episodes expose the same rich episode objects.
- Video supports the five documented qualities, `fast`, `vid`, and
  `expires_at`.
- Encrypted-only video models still return
  `encrypted_stream_unsupported`, HTTP 422.
- `cached` reflects actual cache hits.
- Search uses a captured current App request rather than inferred parameters.
- Ruff and the complete non-live test suite pass.
