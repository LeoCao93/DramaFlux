# DramaFlux REST API Contract Expansion Design

## 1. Goal

Expand the existing DramaFlux REST API contracts to cover the useful request
parameters and response fields exposed by the reference service, while keeping
the current REST paths and internal Signer Service architecture.

The public API will remain directly accessible without an `api_key` parameter.
The implementation will not add a PHP-compatible `api.php` route.

## 2. Scope

This change covers:

- Search request pagination and richer search result fields.
- Latest-list pagination and reliable "today new" collection.
- Additional rank boards and richer rank entries.
- Richer series details and episode metadata.
- Richer video-resolution metadata and a `fast` request option.
- Real cache-hit reporting.
- Stable validation and error responses for the expanded parameters.

This change does not cover:

- API key authentication or billing.
- Aggregation from unrelated third-party short-drama platforms.
- DRM/CENC key extraction or video decryption.
- Returning an encrypted CDN URL as if it were directly playable.

## 3. Compatibility Strategy

Existing paths remain unchanged:

```text
GET /health
GET /api/search
GET /api/latest
GET /api/rank
GET /api/books/{series_id}
GET /api/books/{series_id}/episodes
GET /api/videos/{video_id}
```

Existing field names such as `series_id`, `episode_count`, `play_count`,
`next_cursor`, and `has_more` remain valid. New fields are additive.

IDs remain JSON strings. Upstream IDs can exceed JavaScript's safe integer
range, so returning them as JSON numbers would risk precision loss.

The common success envelope remains:

```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "cached": false,
  "request_id": "019f9550-e5b7-4131-850d-768ee73f4c95"
}
```

## 4. Pagination Model

List endpoints accept both opaque cursor pagination and page pagination:

```text
cursor: optional opaque upstream state
page: integer, default 1, minimum 1
page_size: integer, default 30, minimum 1, maximum 100
```

Rules:

1. `cursor` and `page > 1` cannot be supplied together.
2. A valid `cursor` takes precedence over the default `page=1`.
3. `page/page_size` are translated into upstream offsets where the upstream
   API supports offsets.
4. Where an upstream API needs state such as `session_id`, `passback`, or
   `filter_ids`, the public `next_cursor` stores that state opaquely.
5. `has_more=true` must be accompanied by a non-null `next_cursor`.
6. Unsupported upstream random access may require sequential page collection;
   the API must not claim arbitrary page support unless it can return the
   requested page correctly.

List data uses:

```json
{
  "items": [],
  "page": 1,
  "page_size": 30,
  "total": null,
  "next_cursor": null,
  "has_more": false
}
```

`total` is nullable because several upstream responses do not expose a reliable
total count.

## 5. Shared Drama Summary

Search, latest, and rank endpoints return a shared additive summary model:

```json
{
  "series_id": "7618893784398433305",
  "video_id": null,
  "title": "妈妈，别回头，一直跑下去",
  "author": "河马剧场",
  "type": "女性成长",
  "categories": ["女性成长"],
  "play_count": 477705,
  "duration": "1小时38分钟",
  "episode_count": 68,
  "publish_time": "2026-03-27 09:59:36",
  "cover": "https://example.invalid/cover.jpg",
  "intro": "剧情简介",
  "copyright": "河马剧场",
  "record_number": "",
  "subtitles": [],
  "rank": null,
  "score": null,
  "is_today": false
}
```

Field rules:

- Missing strings use `""`.
- Missing numeric counters use `0`.
- Missing collection fields use `[]`.
- `rank` and `score` use `null` when the endpoint has no corresponding value.
- `type` is the primary display category; `categories` contains all known
  normalized categories.
- `author` and `copyright` remain separate because upstream versions may expose
  different values.
- Date-time strings preserve the upstream local representation when no
  reliable timezone is supplied.

## 6. Search Contract

### Request

```http
GET /api/search?q=妈妈&page=1&page_size=30
```

Parameters:

| Name | Type | Default | Rules |
|---|---|---:|---|
| `q` | string | required | 1-100 characters |
| `page` | integer | 1 | minimum 1 |
| `page_size` | integer | 30 | 1-100 |
| `cursor` | string | null | maximum 4096 characters |

### Response

`data` is the common paginated list model containing shared drama summaries.

### Upstream implementation

The current `/reading/bookapi/search/tab/v` request can return `data=null` with
the current App/session even for known titles. Before changing parser logic,
capture a natural search request from the installed App and compare:

- Path and HTTP method.
- `tab_name`, `tab_type`, `search_source`, `offset`, and `count`.
- Required base query parameters and AB-test parameters.
- Request headers that affect search channel selection.

The parser must support both the existing fixture shape and the newly captured
shape. A successful upstream response with `data=null` remains a valid empty
page rather than a parser error.

## 7. Latest Contract

### Request

```http
GET /api/latest?genre=short_play&today_only=true&page=1&page_size=30
```

Parameters:

| Name | Type | Default | Rules |
|---|---|---:|---|
| `genre` | enum | `short_play` | `short_play`, `comic_series`, `ai_series` |
| `today_only` | boolean | true | exact official label filtering for short plays |
| `page` | integer | 1 | minimum 1 |
| `page_size` | integer | 30 | 1-100 |
| `cursor` | string | null | maximum 4096 characters |

### Response

Each item uses the shared drama summary and should populate:

- `author`
- `publish_time`
- `intro`
- `record_number`
- `duration`
- `type`
- `categories`
- `subtitles`
- `play_count`
- `episode_count`
- `is_today`

### Collection algorithm

For `genre=short_play&today_only=true`:

1. Request the category land page ordered by online time.
2. Track upstream `offset`, `session_id`, and already shown IDs.
3. Collect entries whose `sub_title_list` contains the exact label
   `"今日上新"`.
4. Continue across pages until `page_size` items are collected, the upstream
   reports no more data, a page contains no today-labelled entries after the
   today cluster has begun, or a bounded request limit is reached.
5. Encode continuation state in `next_cursor`.

For comic and AI series, the upstream only provides a seven-day filter. The API
returns the latest available entries and does not incorrectly mark them as
`is_today=true`.

## 8. Rank Contract

### Request

```http
GET /api/rank?board=hot&page=1&page_size=30
```

Supported `board` values:

```text
recommend
hot
new
must_watch
followed
hot_search
```

The first three preserve the existing values. Additional boards map to their
upstream selector IDs:

```text
recommend  -> comic_series_hot_rank
hot        -> comic_series_hot_play
new        -> comic_series_new_rank
must_watch -> ranklist_must_watch
followed   -> ranklist_followed
hot_search -> ranklist_hot_search_sc
```

Response items use the shared drama summary and populate `rank` using the
one-based position within the complete board, not just the current page.

Raw selector panels and presentation metadata such as title image URLs are not
part of the normalized REST response.

## 9. Series Detail Contract

### Request

```http
GET /api/books/{series_id}
```

`series_id` is a non-empty string with a maximum length of 64.

### Response

```json
{
  "series_id": "7626291792958213182",
  "title": "妈妈的外卖",
  "author": "短剧版权3155673834",
  "category": "校园",
  "categories": ["校园", "家庭", "剧情"],
  "intro": "剧情简介",
  "duration": "20分钟",
  "cover": "https://example.invalid/cover.jpg",
  "publish_time": "2026-04-08 16:11:04",
  "episode_count": 20,
  "episodes": [
    {
      "index": 1,
      "video_id": "7626295862351629374",
      "title": "第1集",
      "first_pass_time": "2026-04-08 16:06:06",
      "volume_name": "",
      "duration_seconds": 117,
      "cover": ""
    }
  ]
}
```

The existing `/api/books/{series_id}/episodes` endpoint returns the exact same
episode objects without the surrounding series metadata.

When the upstream explicitly reports that the series does not exist, both
detail paths return HTTP 404 with `book_not_found`. Malformed or contradictory
upstream data remains HTTP 502 with `upstream_invalid_response`.

## 10. Video Resolution Contract

### Request

```http
GET /api/videos/{video_id}?quality=1080p&fast=true
```

Parameters:

| Name | Type | Default | Rules |
|---|---|---:|---|
| `quality` | string | `1080p` | `360p`, `480p`, `540p`, `720p`, `1080p` |
| `fast` | boolean | true | resolution strategy hint |

`video_id` is a non-empty string with a maximum length of 64.

`fast=true` allows a cached video model and immediate quality fallback.
`fast=false` requests a fresh video model before applying the same quality
selection rules. It does not disable encryption checks.

### Success response

```json
{
  "video_id": "7647791842397801534",
  "vid": "v02ebeg10000d8h6kafog65hodpbp4og",
  "vod_id": "",
  "requested_quality": "1080p",
  "selected_quality": "720p",
  "url": "https://example.invalid/video.mp4",
  "backup_url": null,
  "encrypted": false,
  "expires_at": null
}
```

`expires_at` is derived only when a recognized expiry parameter is present. It
remains `null` rather than guessing.

### Encrypted streams

The reference service can return a playable URL for videos whose official
video model contains `cenc-aes-ctr` streams. DramaFlux currently cannot.

When every candidate stream is encrypted, DramaFlux continues to return:

```http
HTTP/1.1 422 Unprocessable Entity
```

```json
{
  "code": "encrypted_stream_unsupported",
  "message": "encrypted stream is not supported",
  "request_id": null
}
```

The API must not return the encrypted CDN URL under a successful response.
Supporting such videos requires a separately designed decryptor capability,
not an API contract adjustment.

## 11. Cache Reporting

The cache decorator returns both the value and whether it was a cache hit. The
route response sets:

```text
cached=false  first successful computation
cached=true   value returned from an existing cache entry
```

Cache keys include every parameter that can change output:

- Search: query, cursor/page state, page size.
- Latest: genre, today flag, cursor/page state, page size.
- Rank: board, cursor/page state, page size.
- Detail: series ID.
- Video: video ID, quality, and `fast`.

Failures are not cached.

## 12. Validation and Errors

FastAPI validation returns HTTP 422 for malformed public parameters.

Stable business errors remain:

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `invalid_cursor` | Cursor is malformed or incompatible |
| 401 | `session_expired` | App session is expired |
| 404 | `book_not_found` | Series does not exist |
| 404 | `video_not_found` | Video does not exist |
| 422 | `encrypted_stream_unsupported` | Only encrypted streams exist |
| 429 | `risk_controlled` | Upstream risk control |
| 502 | `upstream_invalid_response` | Upstream schema is invalid |
| 503 | `session_missing` | No captured App session |
| 503 | `signer_unavailable` | Signer Service unavailable |
| 504 | `upstream_timeout` | Upstream timeout |

Secrets, cookies, dynamic signatures, full signed URLs, and raw upstream bodies
must not be exposed in errors or logs.

## 13. Component Changes

### API layer

- Extend route query parameters.
- Add strict public enums and pagination validation.
- Report actual cache-hit state.

### Models and parsers

- Extend `DramaItem`, `DramaPage`, `SeriesDetail`, `Episode`, and `VideoResult`.
- Parse richer metadata without rejecting older response shapes.
- Introduce opaque cursor types for latest and rank.

### Upstream client

- Consume page state instead of discarding latest/rank cursors.
- Add the three rank selector mappings.
- Capture and implement the current App search request.
- Pass the `fast` strategy through video resolution.

### Cache

- Preserve transparent service composition while returning cache metadata.
- Ensure all output-affecting parameters are included in cache keys.

## 14. Testing Strategy

Implementation follows test-driven development.

Unit tests cover:

- Rich list-field parsing with missing-field defaults.
- Search/latest/rank cursor encoding and validation.
- Latest multi-page today-label collection.
- Rank selector mapping and rank numbering.
- Rich detail and episode parsing.
- Video `vid`, quality whitelist, `fast`, fallback, expiry parsing, and
  encrypted-only rejection.
- Cache-hit reporting and cache-key separation.

Integration tests cover:

- Every public route's query validation.
- Additive response schemas.
- Conflict between cursor and explicit page pagination.
- 404 versus 502 error mapping.
- Actual `cached` values across repeated requests.

Live tests remain opt-in and verify:

- Search returns data after the new App request is captured.
- Latest all and today-only behavior.
- All six rank boards.
- Detail and episode consistency.
- Video behavior for encrypted and, when available, unencrypted samples.

## 15. Delivery Order

1. Extend models and parser fixtures.
2. Add pagination contracts and cache metadata.
3. Implement latest pagination.
4. Add rank boards and pagination.
5. Enrich detail and episode data.
6. Enrich video request and response metadata.
7. Capture and repair the current search request.
8. Update README and live-test documentation.

Each stage must keep existing paths usable and the complete test suite passing.
