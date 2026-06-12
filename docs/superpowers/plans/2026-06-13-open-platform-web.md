# DramaFlux Open Platform Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build responsive Home, API Documentation, and Pricing pages in React and serve the production bundle from the existing FastAPI API Server.

**Architecture:** A Vite React TypeScript application lives in `services/api-server/web` and compiles into `src/hongguo_api/web_dist`. Shared typed endpoint metadata drives both documentation and live same-origin requests. FastAPI keeps `/api/*` authoritative, moves Swagger to `/internal/docs`, and serves only the three known web routes plus hashed assets.

**Tech Stack:** React 19, TypeScript, Vite, React Router, Vitest, Testing Library, CSS, FastAPI, Hatchling, pytest

---

## File Map

### Frontend configuration

- Create `services/api-server/web/package.json`: scripts and frontend dependencies.
- Create `services/api-server/web/package-lock.json`: reproducible npm dependency lock.
- Create `services/api-server/web/tsconfig.json`: strict TypeScript settings.
- Create `services/api-server/web/vite.config.ts`: build output, API proxy, and Vitest setup.
- Create `services/api-server/web/index.html`: Vite entry document.
- Create `services/api-server/web/src/vite-env.d.ts`: Vite type declarations.
- Create `services/api-server/web/src/test/setup.ts`: DOM matcher and test cleanup setup.

### Shared application

- Create `services/api-server/web/src/main.tsx`: browser bootstrap.
- Create `services/api-server/web/src/App.tsx`: route table and shared shell.
- Create `services/api-server/web/src/styles.css`: tokens, layout, responsive styling, and motion rules.
- Create `services/api-server/web/src/components/AppShell.tsx`: navigation, mobile menu, footer, and background decoration.
- Create `services/api-server/web/src/components/CodeBlock.tsx`: accessible formatted code display.
- Create `services/api-server/web/src/components/Icon.tsx`: small inline SVG icon set.

### API documentation

- Create `services/api-server/web/src/api/catalog.ts`: endpoint groups, parameter definitions, examples, and errors.
- Create `services/api-server/web/src/api/client.ts`: validation, URL building, timeout, fetch, and response normalization.
- Create `services/api-server/web/src/api/client.test.ts`: request construction and error tests.
- Create `services/api-server/web/src/pages/DocsPage.tsx`: responsive documentation workspace.
- Create `services/api-server/web/src/pages/DocsPage.test.tsx`: endpoint selection and live request states.

### Marketing and pricing

- Create `services/api-server/web/src/pages/HomePage.tsx`: hero, capabilities, endpoint links, and pricing CTA.
- Create `services/api-server/web/src/pages/HomePage.test.tsx`: page navigation coverage.
- Create `services/api-server/web/src/pricing/plans.ts`: typed plans and total calculation.
- Create `services/api-server/web/src/pricing/plans.test.ts`: pricing calculation and bounds tests.
- Create `services/api-server/web/src/pages/PricingPage.tsx`: plans, quantity, total, and simulated purchase.
- Create `services/api-server/web/src/pages/PricingPage.test.tsx`: interactive pricing tests.
- Create `services/api-server/web/src/App.test.tsx`: top-level route and mobile navigation tests.

### FastAPI integration

- Create `services/api-server/src/hongguo_api/web.py`: static bundle discovery and route installation.
- Create `services/api-server/src/hongguo_api/web_dist/.gitkeep`: preserve the build target directory.
- Modify `services/api-server/src/hongguo_api/main.py`: documentation paths and web route installation.
- Modify `services/api-server/pyproject.toml`: include built web assets in wheels.
- Create `services/api-server/tests/integration/test_web.py`: web entry, assets, docs, fallback, and API precedence tests.
- Modify `services/api-server/README.md`: frontend install, test, build, and run commands.
- Modify `.gitignore`: ignore generated web bundle contents while retaining `.gitkeep`.

### Visual verification

- Browser-check `/`, `/docs`, and `/pricing` at desktop, tablet, and mobile sizes.
- Keep generated screenshots outside tracked source files.

---

### Task 1: Establish the React and Test Baseline

**Files:**
- Create: `services/api-server/web/package.json`
- Create: `services/api-server/web/package-lock.json`
- Create: `services/api-server/web/tsconfig.json`
- Create: `services/api-server/web/vite.config.ts`
- Create: `services/api-server/web/index.html`
- Create: `services/api-server/web/src/vite-env.d.ts`
- Create: `services/api-server/web/src/test/setup.ts`
- Create: `services/api-server/web/src/main.tsx`
- Create: `services/api-server/web/src/App.tsx`
- Test: `services/api-server/web/src/App.test.tsx`

- [ ] **Step 1: Create the package manifest and install locked dependencies**

Use these scripts and dependency groups:

```json
{
  "name": "dramaflux-open-platform",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc -b --pretty false"
  },
  "dependencies": {
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "react-router-dom": "^7.6.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^14.6.0",
    "@types/react": "^19.1.0",
    "@types/react-dom": "^19.1.0",
    "@vitejs/plugin-react": "^4.5.0",
    "jsdom": "^26.1.0",
    "typescript": "~5.8.0",
    "vite": "^6.3.0",
    "vitest": "^3.1.0"
  }
}
```

Run:

```powershell
Set-Location services/api-server/web
npm install
```

Expected: `package-lock.json` is created and `npm audit` reports no unresolved install failure.

- [ ] **Step 2: Write the failing route smoke test**

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "./App";

test("renders the home route", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: /稳定、清晰、易接入/ })).toBeInTheDocument();
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```powershell
npm test -- --run src/App.test.tsx
```

Expected: FAIL because `App` and the home page do not exist.

- [ ] **Step 4: Add strict TypeScript, Vite, test setup, and minimal route placeholders**

Configure Vite to:

```ts
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/hongguo_api/web_dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:18000",
      "/health": "http://127.0.0.1:18000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
```

Implement `App` with routes for `/`, `/docs`, and `/pricing`, using small temporary page components whose headings match the final page purposes. Bootstrap `BrowserRouter` in `main.tsx`.

- [ ] **Step 5: Run baseline tests and type checking**

Run:

```powershell
npm test
npm run typecheck
```

Expected: both commands PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/api-server/web
git commit -m "build: scaffold open platform web"
```

---

### Task 2: Build the Shared Visual Shell

**Files:**
- Create: `services/api-server/web/src/components/AppShell.tsx`
- Create: `services/api-server/web/src/components/CodeBlock.tsx`
- Create: `services/api-server/web/src/components/Icon.tsx`
- Create: `services/api-server/web/src/styles.css`
- Modify: `services/api-server/web/src/App.tsx`
- Modify: `services/api-server/web/src/main.tsx`
- Test: `services/api-server/web/src/App.test.tsx`

- [ ] **Step 1: Add failing navigation tests**

Test that:

```tsx
expect(screen.getByRole("link", { name: "首页" })).toHaveAttribute("href", "/");
expect(screen.getByRole("link", { name: "接口文档" })).toHaveAttribute("href", "/docs");
expect(screen.getByRole("link", { name: "定价" })).toHaveAttribute("href", "/pricing");
expect(screen.getByRole("button", { name: "打开导航菜单" })).toBeInTheDocument();
```

- [ ] **Step 2: Run the test to verify it fails**

Run `npm test -- --run src/App.test.tsx`.

Expected: FAIL because the shared shell does not exist.

- [ ] **Step 3: Implement the shell and visual tokens**

`AppShell` must render:

```tsx
<header>
  <Link to="/" aria-label="DramaFlux 开放平台首页">...</Link>
  <nav aria-label="主导航">...</nav>
  <Link to="/docs" className="primary-action">立即接入</Link>
  <button aria-label="打开导航菜单" aria-expanded={menuOpen}>...</button>
</header>
<main>{children}</main>
<footer>...</footer>
```

Define CSS variables for background, panel, border, text, muted text, cyan,
violet, gradient, radius, and shadow. Add responsive breakpoints around
`1100px`, `820px`, and `600px`, `prefers-reduced-motion`, visible `:focus-visible`
styles, and body overflow protection.

- [ ] **Step 4: Run tests and type checking**

Run:

```powershell
npm test -- --run src/App.test.tsx
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/api-server/web/src
git commit -m "feat: add open platform application shell"
```

---

### Task 3: Define the API Catalog and Live Request Client

**Files:**
- Create: `services/api-server/web/src/api/catalog.ts`
- Create: `services/api-server/web/src/api/client.ts`
- Test: `services/api-server/web/src/api/client.test.ts`

- [ ] **Step 1: Write failing client tests**

Cover:

```ts
expect(buildRequest(searchEndpoint, { q: "测试", cursor: "next" }).url)
  .toBe("/api/search?q=%E6%B5%8B%E8%AF%95&cursor=next");

expect(buildRequest(detailEndpoint, { series_id: "a/b" }).url)
  .toBe("/api/books/a%2Fb");

expect(() => buildRequest(searchEndpoint, { q: "" }))
  .toThrow("请输入搜索关键词");
```

Mock `fetch` and fake timers to verify:

- JSON success returns status, elapsed time, and parsed body.
- JSON API failure still returns the public error body.
- abort timeout throws a normalized timeout error.
- text response is truncated and returned safely.

- [ ] **Step 2: Run the tests to verify they fail**

Run `npm test -- --run src/api/client.test.ts`.

Expected: FAIL because catalog and client modules do not exist.

- [ ] **Step 3: Implement typed endpoint metadata**

Define:

```ts
export type ApiParameter = {
  name: string;
  location: "path" | "query";
  type: "string" | "boolean";
  required: boolean;
  description: string;
  defaultValue?: string;
  example: string;
  validation?: { minLength?: number; maxLength?: number; pattern?: string };
};

export type ApiEndpoint = {
  id: string;
  group: "基础接口" | "内容接口" | "播放接口";
  title: string;
  method: "GET";
  path: string;
  description: string;
  parameters: ApiParameter[];
  successExample: unknown;
  errorCodes: Array<{ status: number; code: string; description: string }>;
};
```

Populate exactly seven endpoints from `hongguo_api/api/routes.py`: health,
search, latest, rank, detail, episodes, and video. Use real defaults and
constraints such as search length `1..100`, rank pattern
`recommend|hot|new`, and video quality pattern `^\d{3,4}p$`.

- [ ] **Step 4: Implement request construction and execution**

Expose:

```ts
export function buildRequest(
  endpoint: ApiEndpoint,
  values: Record<string, string>,
): { method: "GET"; url: string };

export async function executeRequest(
  request: { method: "GET"; url: string },
  options?: { timeoutMs?: number; signal?: AbortSignal },
): Promise<ApiExecutionResult>;
```

Use `encodeURIComponent` for path values, `URLSearchParams` for present query
values, `AbortController` for a default 15-second timeout, `performance.now()`
for elapsed time, and a 20,000-character limit for non-JSON text.

- [ ] **Step 5: Run tests and type checking**

Run:

```powershell
npm test -- --run src/api/client.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/api-server/web/src/api
git commit -m "feat: define API catalog and live client"
```

---

### Task 4: Implement the Home Page

**Files:**
- Create: `services/api-server/web/src/pages/HomePage.tsx`
- Test: `services/api-server/web/src/pages/HomePage.test.tsx`
- Modify: `services/api-server/web/src/App.tsx`
- Modify: `services/api-server/web/src/styles.css`

- [ ] **Step 1: Write the failing home page test**

Verify the hero heading, `/api/search` code example, three capability cards,
links to docs endpoint anchors, and the pricing CTA:

```tsx
expect(screen.getByText("/api/search")).toBeInTheDocument();
expect(screen.getByRole("link", { name: "查看接口文档" })).toHaveAttribute("href", "/docs");
expect(screen.getByRole("link", { name: "查看定价方案" })).toHaveAttribute("href", "/pricing");
expect(screen.getAllByTestId("capability-card")).toHaveLength(3);
```

- [ ] **Step 2: Run the test to verify it fails**

Run `npm test -- --run src/pages/HomePage.test.tsx`.

Expected: FAIL because the full home page is missing.

- [ ] **Step 3: Implement the home sections**

Build:

- Hero copy and two actions.
- Syntax-colored cURL example using `/api/search?q=热播短剧`.
- Availability, simple integration, and fast response cards.
- Search, series detail, and video resolution cards sourced from `apiCatalog`.
- Pricing CTA and shared footer through `AppShell`.

Use semantic sections and headings. Decorative shapes must be
`aria-hidden="true"`.

- [ ] **Step 4: Run the focused and full frontend tests**

Run:

```powershell
npm test -- --run src/pages/HomePage.test.tsx
npm test
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/api-server/web/src
git commit -m "feat: build open platform home page"
```

---

### Task 5: Implement API Documentation and Real Online Debugging

**Files:**
- Create: `services/api-server/web/src/pages/DocsPage.tsx`
- Test: `services/api-server/web/src/pages/DocsPage.test.tsx`
- Modify: `services/api-server/web/src/App.tsx`
- Modify: `services/api-server/web/src/styles.css`

- [ ] **Step 1: Write failing endpoint navigation tests**

Render `/docs` and verify:

```tsx
expect(screen.getByRole("button", { name: /搜索接口/ })).toHaveAttribute("aria-pressed", "true");
expect(screen.getByText("GET")).toBeInTheDocument();
expect(screen.getByText("/api/search")).toBeInTheDocument();
expect(screen.getByLabelText("q")).toHaveValue("短剧");
```

Click Series Detail and verify the path and `series_id` editor replace the
search documentation.

- [ ] **Step 2: Write failing live request tests**

Mock `executeRequest` and verify:

```tsx
await user.click(screen.getByRole("button", { name: "发送请求" }));
expect(executeRequest).toHaveBeenCalledWith(
  expect.objectContaining({ url: expect.stringContaining("/api/search?q=") }),
  expect.anything(),
);
expect(await screen.findByText("200 OK")).toBeInTheDocument();
```

Also verify required-field errors, backend error code display, clear response,
and disabled duplicate submit while pending.

- [ ] **Step 3: Run the tests to verify they fail**

Run `npm test -- --run src/pages/DocsPage.test.tsx`.

Expected: FAIL because `DocsPage` is not implemented.

- [ ] **Step 4: Implement the responsive docs workspace**

Implement:

- Searchable grouped endpoint list.
- Selected endpoint method, path, description, and metadata summary.
- Parameter table and example success/error tabs.
- Parameter inputs generated from endpoint metadata.
- Request submission using `buildRequest` and `executeRequest`.
- Response status, elapsed time, formatted JSON/text, copy, and clear controls.
- Abort the current request when selection changes or the component unmounts.
- Mobile endpoint selector and section tabs below `820px`.

Use `aria-pressed` for endpoint choices, `role="status"` for request state, and
`aria-live="polite"` for response summary.

- [ ] **Step 5: Run docs tests, all tests, and type checking**

Run:

```powershell
npm test -- --run src/pages/DocsPage.test.tsx
npm test
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/api-server/web/src
git commit -m "feat: add interactive API documentation"
```

---

### Task 6: Implement Pricing and Simulated Purchase

**Files:**
- Create: `services/api-server/web/src/pricing/plans.ts`
- Create: `services/api-server/web/src/pricing/plans.test.ts`
- Create: `services/api-server/web/src/pages/PricingPage.tsx`
- Create: `services/api-server/web/src/pages/PricingPage.test.tsx`
- Modify: `services/api-server/web/src/App.tsx`
- Modify: `services/api-server/web/src/styles.css`

- [ ] **Step 1: Write failing pricing model tests**

Define expected demonstration prices:

```ts
expect(calculateTotal("quarterly", 1)).toEqual({ total: 149, days: 90 });
expect(calculateTotal("monthly", 2)).toEqual({ total: 118, days: 60 });
expect(normalizeQuantity(0)).toBe(1);
expect(normalizeQuantity(13)).toBe(12);
```

- [ ] **Step 2: Write failing pricing page tests**

Verify the quarterly plan is initially selected, changing to annual updates the
summary, incrementing quantity updates total and validity, and clicking
`立即开通 VIP` displays text containing `模拟购买成功` without calling `fetch`.

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```powershell
npm test -- --run src/pricing/plans.test.ts src/pages/PricingPage.test.tsx
```

Expected: FAIL because pricing modules do not exist.

- [ ] **Step 4: Implement pricing data and interactions**

Create five plans with ids `weekly`, `monthly`, `quarterly`, `halfYear`, and
`annual`, prices `18`, `59`, `149`, `279`, and `519`, and validity days `7`,
`30`, `90`, `180`, and `365`. Bound quantity to `1..12`.

Render selectable plan cards, recommended quarterly badge, benefit copy,
quantity controls, total, validity, explicit `演示购买` disclosure, and a local
success panel. Do not invoke the API client or `fetch`.

- [ ] **Step 5: Run all frontend verification**

Run:

```powershell
npm test
npm run typecheck
npm run build
```

Expected: PASS and Vite writes hashed assets plus `index.html` to
`services/api-server/src/hongguo_api/web_dist`.

- [ ] **Step 6: Commit**

```powershell
git add services/api-server/web services/api-server/src/hongguo_api/web_dist/.gitkeep
git commit -m "feat: add simulated pricing purchase page"
```

---

### Task 7: Serve the Web Bundle from FastAPI

**Files:**
- Create: `services/api-server/src/hongguo_api/web.py`
- Create: `services/api-server/src/hongguo_api/web_dist/.gitkeep`
- Create: `services/api-server/tests/integration/test_web.py`
- Modify: `services/api-server/src/hongguo_api/main.py`
- Modify: `services/api-server/pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing FastAPI web tests**

Create a temporary web directory containing `index.html` and `assets/app.js`.
Pass it to `create_app(FakeHongguo(), web_dist=tmp_path)`, then assert:

```python
assert client.get("/").text == "<div id='root'></div>"
assert client.get("/docs").status_code == 200
assert client.get("/pricing").status_code == 200
assert client.get("/assets/app.js").text == "console.log('ok')"
assert client.get("/internal/docs").status_code == 200
assert client.get("/openapi.json").status_code == 200
assert client.get("/api/search", params={"q": "test"}).headers["content-type"].startswith(
    "application/json"
)
```

For a missing build, assert `/` returns `503` JSON with code
`web_build_missing`, while `/health` still returns `200`.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
uv run pytest services/api-server/tests/integration/test_web.py -q
```

Expected: FAIL because web route installation does not exist.

- [ ] **Step 3: Implement explicit web route installation**

In `web.py`, define:

```python
WEB_DIST = Path(__file__).with_name("web_dist")

def install_web(app: FastAPI, web_dist: Path) -> None:
    index_file = web_dist / "index.html"
    assets_dir = web_dist / "assets"

    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")

    async def web_entry() -> Response:
        if not index_file.is_file():
            return JSONResponse(
                status_code=503,
                content={
                    "code": "web_build_missing",
                    "message": "Run npm install and npm run build in services/api-server/web",
                },
            )
        return FileResponse(index_file)

    app.add_api_route("/", web_entry, methods=["GET"], include_in_schema=False)
    app.add_api_route("/docs", web_entry, methods=["GET"], include_in_schema=False)
    app.add_api_route("/pricing", web_entry, methods=["GET"], include_in_schema=False)
```

Construct FastAPI with:

```python
FastAPI(
    title="DramaFlux API",
    version="1.0",
    docs_url="/internal/docs",
    redoc_url="/redoc",
)
```

Change the application factory signature to:

```python
def create_app(
    service: HongguoService,
    web_dist: Path | None = None,
) -> FastAPI:
```

Call `install_web(app, WEB_DIST if web_dist is None else web_dist)` only after
API routes and exception handlers are installed. Existing callers remain
compatible, while tests can supply an isolated bundle directory.

- [ ] **Step 4: Configure generated files and wheel inclusion**

Ignore:

```gitignore
services/api-server/src/hongguo_api/web_dist/*
!services/api-server/src/hongguo_api/web_dist/.gitkeep
```

Configure Hatchling shared data:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/hongguo_api"]

[tool.hatch.build.targets.wheel.force-include]
"src/hongguo_api/web_dist" = "hongguo_api/web_dist"
```

The production build must be run before wheel creation. Do not commit hashed
bundle output.

- [ ] **Step 5: Run backend and packaging tests**

Run:

```powershell
uv run pytest services/api-server/tests/integration/test_web.py -q
uv run pytest services/api-server/tests -q
uv run ruff check services/api-server
uv build --package hongguo-api-server
```

Expected: all tests and Ruff PASS, and the wheel contains
`hongguo_api/web_dist/index.html` plus `assets/*` after a frontend build.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore services/api-server/src/hongguo_api services/api-server/tests/integration/test_web.py services/api-server/pyproject.toml
git commit -m "feat: serve open platform web from FastAPI"
```

---

### Task 8: Document, Run Full Verification, and Perform Browser QA

**Files:**
- Modify: `services/api-server/README.md`

- [ ] **Step 1: Document frontend commands and route ownership**

Add:

```powershell
Set-Location services/api-server/web
npm install
npm test
npm run typecheck
npm run build
Set-Location ../../..
.\services\api-server\scripts\start.ps1
```

Document:

- `/`, `/docs`, and `/pricing` are React pages.
- `/internal/docs`, `/redoc`, and `/openapi.json` are framework documentation.
- Live docs requests use the current origin and require the local API session
  and Signer Service for successful business responses.
- Pricing purchase is a UI simulation only.

- [ ] **Step 2: Run the complete automated verification**

Run:

```powershell
Set-Location services/api-server/web
npm ci
npm test
npm run typecheck
npm run build
Set-Location ../../..
uv run pytest services/api-server/tests -q
uv run ruff check services/api-server
git diff --check
```

Expected: every command PASS with no whitespace errors.

- [ ] **Step 3: Start the API Server for browser testing**

Run:

```powershell
.\services\api-server\scripts\start.ps1
```

Expected: Uvicorn listens on `http://127.0.0.1:18000`.

- [ ] **Step 4: Verify the three routes in the in-app browser**

Inspect:

- Desktop `1440x900`
- Tablet `820x1180`
- Mobile `390x844`

For each viewport verify:

- Navigation and active state.
- No page-level horizontal overflow.
- Readable hero, cards, and code blocks.
- Docs endpoint selection, parameter editing, real request error/success display,
  and responsive section switching.
- Pricing plan selection, quantity controls, total calculation, and simulation
  success feedback.
- Keyboard focus visibility and reduced-motion behavior.

- [ ] **Step 5: Fix any visual defects and rerun focused tests**

For each defect, add or tighten a relevant component test when behavior is
involved, then rerun `npm test`, `npm run typecheck`, and `npm run build`.

- [ ] **Step 6: Commit**

```powershell
git add services/api-server/README.md services/api-server/web
git commit -m "docs: add open platform web workflow"
```

---

## Final Verification Checklist

- [ ] `npm ci` succeeds from a clean dependency state.
- [ ] `npm test` passes all frontend tests.
- [ ] `npm run typecheck` passes with strict TypeScript.
- [ ] `npm run build` emits the production bundle.
- [ ] `uv run pytest services/api-server/tests -q` passes.
- [ ] `uv run ruff check services/api-server` passes.
- [ ] `uv build --package hongguo-api-server` includes web assets.
- [ ] `/api/*` behavior is unchanged.
- [ ] `/`, `/docs`, and `/pricing` work from the FastAPI origin.
- [ ] `/internal/docs`, `/redoc`, and `/openapi.json` remain available.
- [ ] Browser QA passes at desktop, tablet, and mobile sizes.
- [ ] Pricing is visibly identified as a simulation.
- [ ] No Signer token, session credential, generated bundle, or local screenshot is committed.
