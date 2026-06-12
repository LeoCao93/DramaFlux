# DramaFlux Open Platform Web Design

## Overview

Add a three-page React web experience to the existing
`services/api-server` FastAPI service:

- Home page at `/`
- API documentation at `/docs`
- Pricing and simulated purchase page at `/pricing`

The web application uses the supplied dark blue and violet reference images
as its visual direction. It is built as part of the API Server and served by
the same FastAPI process and origin. This is not a separately deployed
frontend.

The repository does not contain a directory named `api-service`; the existing
service is `services/api-server`, which is the target of this work.

## Goals

- Present DramaFlux as a polished open API platform.
- Document every current public API Server route accurately.
- Let users issue real same-origin requests from the documentation page.
- Provide a responsive experience for desktop, tablet, and mobile.
- Demonstrate pricing selection and purchase feedback without implementing
  orders or payment processing.
- Preserve all existing API behavior and tests.

## Non-Goals

- User registration, login, account management, or API key issuance.
- Real payments, orders, invoices, entitlements, or subscription persistence.
- Exposing the Signer Service token or upstream credentials to the browser.
- Replacing FastAPI's OpenAPI schema.
- Creating a separately deployed frontend service.

## Technical Approach

Create a Vite-powered React application under:

```text
services/api-server/web/
```

The production build is emitted into a static directory packaged with
`hongguo_api`. FastAPI serves hashed assets and the React entry document from
the same process that serves `/api/*`.

The Python application keeps these backend routes authoritative:

```text
GET /health
GET /api/search
GET /api/latest
GET /api/rank
GET /api/books/{series_id}
GET /api/books/{series_id}/episodes
GET /api/videos/{video_id}
```

FastAPI continues to expose `/openapi.json`. Its default Swagger route moves
away from `/docs` so the custom React documentation page can own that path.
The framework documentation remains available at a clearly named auxiliary
path such as `/internal/docs`, and ReDoc remains available at `/redoc`.

FastAPI serves the React entry document only for the known application routes
`/`, `/docs`, and `/pricing`. Unknown API paths must continue returning API
errors instead of being converted into HTML.

During frontend development, Vite may run as a local build tool with a proxy
to the API Server. Production and normal application use require only the
FastAPI process after the frontend has been built.

## Frontend Architecture

Use React with TypeScript and React Router. Keep runtime dependencies small.
Use CSS variables and locally maintained styles rather than a large component
framework so the reference visual language can be reproduced precisely.

Primary units:

- `AppShell`: shared header, navigation, responsive menu, background effects,
  page container, and footer.
- `HomePage`: platform introduction, code sample, capability cards, API entry
  cards, and pricing call to action.
- `DocsPage`: API navigation, endpoint documentation, parameter editor, live
  request execution, and response viewer.
- `PricingPage`: duration plans, quantity selection, total calculation, and
  simulated purchase confirmation.
- `apiCatalog`: typed endpoint metadata shared by the home page and docs page.
- `apiClient`: same-origin request construction, timeout handling, JSON parsing,
  and normalized errors.

Components remain focused and reusable. Large page sections such as the docs
sidebar, endpoint overview, parameter table, request panel, response panel,
pricing card, and purchase summary are separate components.

## Visual System

The interface follows the supplied references without copying their product
content:

- Near-black navy base with layered blue and violet radial glows.
- Blue-to-violet gradients for primary actions and selected states.
- Cyan and green for HTTP methods, healthy states, and successful responses.
- Translucent panels with restrained blur, fine borders, and subtle shadows.
- Clear Chinese typography with monospace code and response blocks.
- Small, purposeful transitions for hover, selection, tabs, and mobile menus.
- Decorative orbit and grid effects implemented in CSS or lightweight SVG.

The product name is `DramaFlux 开放平台`.

Accessibility requirements:

- Semantic landmarks and heading order.
- Keyboard-operable navigation, tabs, endpoint selection, and controls.
- Visible focus states.
- Sufficient contrast for normal text and status labels.
- Reduced-motion support.
- Status feedback not communicated by color alone.

## Page Design

### Home

The home page contains:

1. Shared navigation with Home selected.
2. Hero copy describing a stable, clear, easy-to-integrate API platform.
3. Primary link to `/docs` and secondary integration action.
4. A code sample based on the real `/api/search` endpoint.
5. Capability cards for availability, simple integration, and fast response.
6. Cards linking to Search, Detail, and Video Resolution documentation.
7. A pricing strip linking to `/pricing`.
8. Shared footer.

The layout is two-column on wide screens and stacked on smaller screens.

### API Documentation

The docs page is data-driven from `apiCatalog` and covers:

- Health check
- Search
- Latest releases
- Ranking
- Series detail
- Episode list
- Video resolution

Desktop layout:

- Left: searchable endpoint navigation grouped by domain.
- Center: method, path, description, metadata, parameters, examples, response
  shapes, and stable error information.
- Right: live request editor and response result.

Tablet and mobile layouts collapse these regions into accessible sections or
tabs. No page-level horizontal overflow is permitted. Code blocks may scroll
within their own containers.

Each endpoint definition contains:

- Display name and group.
- HTTP method and path template.
- Description.
- Path and query parameters, types, requirements, constraints, and defaults.
- Example parameter values.
- Example success response.
- Relevant stable error responses.

The endpoint catalog reflects the implementation in
`hongguo_api/api/routes.py`. It is maintained explicitly rather than attempting
to generate the entire presentation from OpenAPI at runtime, which keeps
examples and product copy predictable.

### Pricing

The pricing page presents five duration plans inspired by the reference:

- Weekly
- Monthly
- Quarterly
- Half-year
- Annual

Prices and savings are demonstration content, not a billing contract. The UI
must label the purchase flow as a simulation.

Users can select one plan, adjust quantity within a bounded positive range,
review validity and calculated total, and trigger a simulated purchase.
Success feedback is local UI state only. Refreshing the page resets it. No
order or payment request is sent.

## Live API Request Flow

The documentation page sends requests to the current browser origin.

1. User selects an endpoint.
2. Endpoint metadata initializes editable parameters.
3. Client validation checks required values and basic constraints.
4. Path parameters are URI encoded and substituted.
5. Defined query parameters are encoded with `URLSearchParams`.
6. `fetch` issues the request with an abort timeout.
7. The response panel displays HTTP status, elapsed time, and formatted body.

The browser never receives or stores the Signer Service bearer token. The
FastAPI service remains responsible for all downstream signing and session
handling.

Expected live errors include missing or expired session, unavailable signer,
upstream timeout, risk control, missing resources, invalid cursors, and
unsupported encrypted streams. The UI displays the HTTP status and public
error payload without exposing private request details.

Non-JSON responses are shown as a short escaped text preview. Requests disable
duplicate submission while active and can be cleared by the user. Navigating
between endpoints cancels or supersedes stale requests.

## Backend Integration

Update FastAPI application construction to:

- Configure custom framework documentation paths.
- Mount the built asset directory when it exists.
- Return the React entry document for `/`, `/docs`, and `/pricing`.
- Keep API and OpenAPI paths registered before web routes.
- Produce an explicit, understandable response when frontend assets have not
  been built rather than failing application startup.

Frontend files must be included in the Python wheel configuration so packaged
deployments behave like source checkouts.

Development and build commands are documented in the API Server README.
The existing PowerShell API start script remains the normal production-style
entry point.

## Error and Empty States

- Missing required parameters: inline field message and no request.
- Network failure: clear connection message with retry action.
- Timeout: distinct timeout state.
- Backend JSON error: formatted stable code, message, and request ID.
- Empty successful data: valid empty-state presentation, not an error.
- Missing frontend build: FastAPI returns a developer-facing build instruction.
- Simulated purchase: visible confirmation and a way to return to plan editing.

## Responsive Behavior

Breakpoints are content-driven, with these target modes:

- Wide desktop: full hero split, three-column docs, five pricing cards.
- Tablet: reduced navigation density, two-column or stacked content, docs
  request panel below endpoint content where needed.
- Mobile: collapsible top navigation, single-column sections, horizontally
  scrollable code blocks, compact pricing cards, and full-width actions.

Touch targets remain at least 44 CSS pixels where practical. The docs sidebar
becomes a drawer or endpoint selector rather than consuming permanent width.

## Testing

### Frontend

Automated tests cover:

- Application route rendering and navigation.
- API path substitution and query serialization.
- Required parameter validation.
- Successful, failed, and timed-out live request states.
- Endpoint selection and catalog rendering.
- Pricing plan selection, quantity bounds, total calculation, and simulated
  purchase confirmation.

### Backend

Integration tests cover:

- `/`, `/docs`, and `/pricing` serving the web entry document.
- Static assets being reachable.
- `/openapi.json` and auxiliary framework documentation remaining reachable.
- Existing `/api/*` routes retaining their behavior.
- A missing web build returning the documented fallback response.

### Verification

- Build the React production bundle.
- Run frontend unit tests and type checking.
- Run existing API Server tests.
- Run Ruff against `services/api-server`.
- Use a browser to inspect desktop, tablet, and mobile viewport behavior.
- Exercise at least one successful mocked/test request and representative
  backend error states.

## Acceptance Criteria

- All three pages are available from the FastAPI service and share consistent
  navigation and visual styling.
- The visual result closely follows the dark blue and violet reference
  direction while remaining responsive and accessible.
- Documentation accurately represents all current public routes.
- Live requests call the current FastAPI origin and render success or public
  error responses clearly.
- Pricing calculations work and the purchase flow is explicitly simulated.
- Existing API tests continue to pass.
- The production frontend build is included in packaged API Server artifacts.
- Running the built application does not require a separate frontend server.
