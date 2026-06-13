# DramaFlux Browser-First Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the current high-fidelity mockup implementation into a unified browser-first three-page experience, while adding functional custom request parameters, highlighted live responses, route-aware CTA/title behavior, unique pricing icons, and a DramaFlux favicon.

**Architecture:** Keep the existing React Router application and current visual components. Move responsive sizing into shared CSS tokens, keep marketing pages in normal document flow, and retain a viewport-bound docs workbench. Extend `buildRequest` with a typed custom-query input so request behavior remains testable outside React, while `DocsPage` owns transient row state and reset behavior.

**Tech Stack:** React 19, React Router 7, TypeScript, Vite, Vitest, Testing Library, CSS, inline SVG.

---

## File Map

- `services/api-server/web/src/styles/tokens.css`: shared browser-first widths, spacing, radii, and responsive typography.
- `services/api-server/web/src/styles/shell.css`: unified Header/container/footer behavior and route-specific CTA visibility.
- `services/api-server/web/src/styles/home.css`: natural-flow homepage sections and responsive Hero sizing.
- `services/api-server/web/src/styles/docs.css`: viewport workbench, column scaling, parameter rows, and response code presentation.
- `services/api-server/web/src/styles/pricing.css`: natural-flow pricing layout and responsive plan grid.
- `services/api-server/web/src/components/AppShell.tsx`: route titles and Header CTA routing/visibility.
- `services/api-server/web/src/components/PlatformIcon.tsx`: distinct weekly and monthly plan icons.
- `services/api-server/web/src/components/SyntaxCodeBlock.tsx`: JSON-aware line tokenization for examples and live responses.
- `services/api-server/web/src/api/client.ts`: custom query parameter types, conflict detection, and URL merging.
- `services/api-server/web/src/pages/DocsPage.tsx`: add/delete/edit custom parameter rows and highlighted live response output.
- `services/api-server/web/src/pages/PricingPage.tsx`: assign a unique icon to every plan.
- `services/api-server/web/public/favicon.svg`: browser tab icon.

### Task 1: Route Metadata And Purchase CTA

**Files:**
- Create: `services/api-server/web/public/favicon.svg`
- Modify: `services/api-server/web/index.html`
- Modify: `services/api-server/web/src/components/AppShell.tsx`
- Modify: `services/api-server/web/src/App.test.tsx`

- [ ] **Step 1: Write failing route metadata and CTA tests**

Add tests that render each route independently and assert:

```tsx
test.each([
  ["/", "DramaFlux 开放平台"],
  ["/docs", "接口文档 - DramaFlux"],
  ["/pricing", "定价购买 - DramaFlux"],
])("sets the title for %s", (path, expectedTitle) => {
  renderRoute(path);
  expect(document.title).toBe(expectedTitle);
});

test("routes the header CTA to pricing and hides it on pricing", () => {
  const { unmount } = renderRoute("/");
  expect(screen.getByRole("link", { name: "立即接入" })).toHaveAttribute(
    "href",
    "/pricing",
  );
  unmount();

  renderRoute("/pricing");
  expect(
    screen.queryByRole("link", { name: "立即接入" }),
  ).not.toBeInTheDocument();
});
```

Make `renderRoute` return Testing Library's render result.

- [ ] **Step 2: Run the tests and verify the intended failures**

Run:

```powershell
npm test -- --run src/App.test.tsx
```

Expected: FAIL because all routes currently set the same title, the CTA points to `/docs`, and pricing still renders it.

- [ ] **Step 3: Implement route metadata and CTA behavior**

In `AppShell.tsx`, define route metadata once:

```tsx
const routeMetadata: Record<string, { title: string; showCta: boolean }> = {
  "/": { title: "DramaFlux 开放平台", showCta: true },
  "/docs": { title: "接口文档 - DramaFlux", showCta: true },
  "/pricing": { title: "定价购买 - DramaFlux", showCta: false },
};
```

Set `document.title` from the current path and render the Header action only when `showCta` is true:

```tsx
{metadata.showCta && (
  <Link className="primary-action" to="/pricing">
    立即接入
    <Icon name="arrow-right" size={16} />
  </Link>
)}
```

Create `public/favicon.svg` from the same cyan/blue/violet hexagonal geometry used by `BrandLogo`, with a square `64 64` view box. Add to `index.html`:

```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
```

- [ ] **Step 4: Run the metadata tests**

Run:

```powershell
npm test -- --run src/App.test.tsx
```

Expected: all `App.test.tsx` tests PASS.

- [ ] **Step 5: Commit the metadata change**

```powershell
git add services/api-server/web/public/favicon.svg services/api-server/web/index.html services/api-server/web/src/components/AppShell.tsx services/api-server/web/src/App.test.tsx
git commit -m "feat: add route-aware platform metadata"
```

### Task 2: Custom Query Parameter Request Model

**Files:**
- Modify: `services/api-server/web/src/api/client.ts`
- Modify: `services/api-server/web/src/api/client.test.ts`

- [ ] **Step 1: Write failing request builder tests**

Add the following public type and behavior expectations to the test:

```ts
const custom = [
  { id: "custom-1", name: "source", type: "string" as const, value: "portal" },
  { id: "custom-2", name: "preview", type: "boolean" as const, value: "true" },
];

expect(
  buildRequest(endpoint!, { q: "短剧", cursor: "" }, custom).url,
).toBe("/api/search?q=%E7%9F%AD%E5%89%A7&source=portal&preview=true");
```

Add separate tests for:

```ts
expect(
  validateCustomQueryParameters(endpoint!, [
    { id: "a", name: "q", type: "string", value: "override" },
    { id: "b", name: "tag", type: "string", value: "one" },
    { id: "c", name: "tag", type: "string", value: "two" },
  ]),
).toEqual({
  a: "参数名与接口参数重复",
  c: "参数名与其他自定义参数重复",
});
```

Also assert that blank names and blank values are omitted from the URL.

- [ ] **Step 2: Run the request tests and confirm RED**

Run:

```powershell
npm test -- --run src/api/client.test.ts
```

Expected: FAIL because `CustomQueryParameter`, `validateCustomQueryParameters`, and the third `buildRequest` argument do not exist.

- [ ] **Step 3: Implement custom query validation and merging**

Add:

```ts
export type CustomQueryParameterType = "string" | "boolean";

export interface CustomQueryParameter {
  id: string;
  name: string;
  type: CustomQueryParameterType;
  value: string;
}

export function validateCustomQueryParameters(
  endpoint: ApiEndpoint,
  parameters: CustomQueryParameter[],
): Record<string, string> {
  const errors: Record<string, string> = {};
  const reserved = new Set(endpoint.parameters.map(({ name }) => name));
  const accepted = new Set<string>();

  for (const parameter of parameters) {
    const name = parameter.name.trim();
    if (!name) continue;
    if (reserved.has(name)) {
      errors[parameter.id] = "参数名与接口参数重复";
    } else if (accepted.has(name)) {
      errors[parameter.id] = "参数名与其他自定义参数重复";
    } else {
      accepted.add(name);
    }
  }
  return errors;
}
```

Extend `buildRequest`:

```ts
export function buildRequest(
  endpoint: ApiEndpoint,
  values: Record<string, RequestValue>,
  customParameters: CustomQueryParameter[] = [],
): ApiRequest
```

After built-in parameters are processed, validate custom rows and append only rows with a nonblank name, nonblank value, and no conflict:

```ts
const customErrors = validateCustomQueryParameters(endpoint, customParameters);
for (const parameter of customParameters) {
  const name = parameter.name.trim();
  const value = parameter.value.trim();
  if (!name || !value || customErrors[parameter.id]) continue;
  query.set(name, value);
}
```

- [ ] **Step 4: Run the request tests and full API tests**

Run:

```powershell
npm test -- --run src/api/client.test.ts
```

Expected: PASS, including existing path replacement, required validation, timeout, and response parsing tests.

- [ ] **Step 5: Commit the request model**

```powershell
git add services/api-server/web/src/api/client.ts services/api-server/web/src/api/client.test.ts
git commit -m "feat: support custom debug query parameters"
```

### Task 3: Functional Add And Delete Parameter Rows

**Files:**
- Modify: `services/api-server/web/src/pages/DocsPage.tsx`
- Modify: `services/api-server/web/src/pages/DocsPage.test.tsx`
- Modify: `services/api-server/web/src/styles/docs.css`

- [ ] **Step 1: Write failing interaction tests**

Add tests that:

1. Click `添加参数`.
2. Find a new row by `data-testid="custom-parameter-row"`.
3. Fill `自定义参数名 1` with `source`.
4. Select `自定义参数类型 1` as `string`.
5. Fill `自定义参数值 1` with `portal`.
6. Send the request and expect `executeRequest` to receive a URL containing `source=portal`.
7. Delete the row and verify it disappears.

Add another test:

```tsx
fireEvent.click(screen.getByRole("button", { name: "移除 q" }));
fireEvent.click(screen.getByRole("button", { name: "发送请求" }));
expect(await screen.findByRole("alert")).toHaveTextContent("缺少必填参数：q");
```

Add a reset test that creates a custom row, switches to `获取短剧详情`, and expects no custom rows.

- [ ] **Step 2: Run the docs tests and confirm RED**

Run:

```powershell
npm test -- --run src/pages/DocsPage.test.tsx
```

Expected: FAIL because add/delete buttons do not mutate parameter state and requests do not receive custom rows.

- [ ] **Step 3: Add explicit parameter state**

In `DocsPage.tsx`, add:

```ts
const [activeParameterNames, setActiveParameterNames] = useState(
  () => firstEndpoint.parameters.map(({ name }) => name),
);
const [customParameters, setCustomParameters] = useState<CustomQueryParameter[]>([]);
const nextCustomId = useRef(1);
```

When switching endpoints:

```ts
setActiveParameterNames(endpoint.parameters.map(({ name }) => name));
setCustomParameters([]);
```

When deleting a built-in parameter, remove its key from both state objects:

```ts
const removeBuiltInParameter = (name: string) => {
  setActiveParameterNames((names) => names.filter((item) => item !== name));
  setValues(({ [name]: _removed, ...remaining }) => remaining);
};
```

Render built-in rows from:

```ts
selected.parameters.filter(({ name }) => activeParameterNames.includes(name))
```

- [ ] **Step 4: Implement custom rows and conflict feedback**

Create rows with:

```ts
const addCustomParameter = () => {
  const id = `custom-${nextCustomId.current++}`;
  setCustomParameters((rows) => [
    ...rows,
    { id, name: "", type: "string", value: "" },
  ]);
};
```

Each row must expose:

```tsx
<label data-testid="custom-parameter-row">
  <input aria-label={`自定义参数名 ${index + 1}`} />
  <select aria-label={`自定义参数类型 ${index + 1}`}>
    <option value="string">string</option>
    <option value="boolean">boolean</option>
  </select>
  <input aria-label={`自定义参数值 ${index + 1}`} />
  <button aria-label={`删除自定义参数 ${index + 1}`} type="button">×</button>
</label>
```

Compute conflicts with `validateCustomQueryParameters`. Render each error with `role="alert"` next to its row. Pass custom rows into:

```ts
const request = buildRequest(selected, values, customParameters);
```

- [ ] **Step 5: Run docs tests**

Run:

```powershell
npm test -- --run src/pages/DocsPage.test.tsx
```

Expected: PASS for existing endpoint switching/live request behavior and all new parameter interactions.

- [ ] **Step 6: Commit functional parameter controls**

```powershell
git add services/api-server/web/src/pages/DocsPage.tsx services/api-server/web/src/pages/DocsPage.test.tsx services/api-server/web/src/styles/docs.css
git commit -m "feat: make debug parameters editable"
```

### Task 4: Highlight Live JSON Responses

**Files:**
- Modify: `services/api-server/web/src/components/SyntaxCodeBlock.tsx`
- Create: `services/api-server/web/src/components/SyntaxCodeBlock.test.tsx`
- Modify: `services/api-server/web/src/pages/DocsPage.tsx`
- Modify: `services/api-server/web/src/pages/DocsPage.test.tsx`
- Modify: `services/api-server/web/src/styles/tokens.css`
- Modify: `services/api-server/web/src/styles/docs.css`

- [ ] **Step 1: Write failing token and live-response tests**

Render:

```tsx
render(
  <SyntaxCodeBlock
    label="JSON"
    lines={[
      '  "message": "success",',
      '  "count": 2,',
      '  "cached": false,',
      '  "next": null',
    ]}
  />,
);
```

Assert `.syntax-key`, `.syntax-string`, `.syntax-number`, `.syntax-boolean`, and `.syntax-null` all exist and that four line numbers render.

In `DocsPage.test.tsx`, after the mocked request resolves, assert the live response region named `真实接口响应` contains syntax-token elements rather than a plain `<pre>`.

- [ ] **Step 2: Run component and docs tests to verify RED**

Run:

```powershell
npm test -- --run src/components/SyntaxCodeBlock.test.tsx src/pages/DocsPage.test.tsx
```

Expected: FAIL because the current tokenizer does not distinguish all JSON token types and the live response uses `CodeBlock`.

- [ ] **Step 3: Implement JSON-aware line tokenization**

Replace the generic split with a tokenizer that classifies:

```ts
type SyntaxToken =
  | "key"
  | "string"
  | "number"
  | "boolean"
  | "null"
  | "plain";
```

For JSON lines, match keys before values:

```ts
const jsonTokenPattern =
  /("(?:[^"\\]|\\.)*")(?=\s*:)|("(?:[^"\\]|\\.)*")|(-?\d+(?:\.\d+)?)|\b(true|false)\b|\b(null)\b/g;
```

Map matches to `syntax-key`, `syntax-string`, `syntax-number`, `syntax-boolean`, and `syntax-null`. Preserve unmatched punctuation and whitespace as plain text.

- [ ] **Step 4: Use SyntaxCodeBlock for real responses**

In `DocsPage.tsx`, replace:

```tsx
<CodeBlock language="json" label="真实接口响应">
  {pretty(result.body)}
</CodeBlock>
```

with:

```tsx
<SyntaxCodeBlock
  compact
  label="真实接口响应"
  lines={codeLines(result.body)}
/>
```

Keep plain-text non-JSON bodies readable by passing `pretty(result.body).split("\n")`; unmatched text remains `syntax-plain`.

- [ ] **Step 5: Add token colors and response scrolling**

Define distinct but accessible colors:

```css
.syntax-key { color: #ffab69; }
.syntax-string { color: #77e86c; }
.syntax-number { color: #54d6ff; }
.syntax-boolean { color: #b68cff; }
.syntax-null { color: #8792aa; }
```

Ensure the response code region, not the entire right column, owns overflow.

- [ ] **Step 6: Run token and docs tests**

Run:

```powershell
npm test -- --run src/components/SyntaxCodeBlock.test.tsx src/pages/DocsPage.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit response highlighting**

```powershell
git add services/api-server/web/src/components/SyntaxCodeBlock.tsx services/api-server/web/src/components/SyntaxCodeBlock.test.tsx services/api-server/web/src/pages/DocsPage.tsx services/api-server/web/src/pages/DocsPage.test.tsx services/api-server/web/src/styles/tokens.css services/api-server/web/src/styles/docs.css
git commit -m "feat: highlight live debug responses"
```

### Task 5: Distinct Pricing Plan Icons

**Files:**
- Modify: `services/api-server/web/src/components/PlatformIcon.tsx`
- Modify: `services/api-server/web/src/pages/PricingPage.tsx`
- Modify: `services/api-server/web/src/pages/PricingPage.test.tsx`

- [ ] **Step 1: Write a failing icon assignment test**

Add `data-icon={name}` to `PlatformIcon` in the intended API, then assert:

```tsx
const planCards = screen.getAllByTestId("plan-card");
expect(planCards.map((card) =>
  within(card).getByTestId("platform-icon").getAttribute("data-icon"),
)).toEqual([
  "calendar-week",
  "calendar-month",
  "star",
  "diamond",
  "trophy",
]);
```

- [ ] **Step 2: Run pricing tests and confirm RED**

Run:

```powershell
npm test -- --run src/pages/PricingPage.test.tsx
```

Expected: FAIL because weekly/monthly both use `calendar` and icons do not expose their identity.

- [ ] **Step 3: Add separate weekly and monthly drawings**

Extend `PlatformIconName` with:

```ts
| "calendar-week"
| "calendar-month"
```

Use visibly different geometry:

- `calendar-week`: compact tear-off calendar with a large `7`.
- `calendar-month`: grid calendar with binding rings and four date cells.

Add `data-icon={name}` to the root SVG.

Update `planIcons`:

```ts
weekly: "calendar-week",
monthly: "calendar-month",
quarterly: "star",
halfYear: "diamond",
annual: "trophy",
```

Add `data-testid="plan-card"` to each pricing label.

- [ ] **Step 4: Run pricing tests**

Run:

```powershell
npm test -- --run src/pages/PricingPage.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit distinct plan icons**

```powershell
git add services/api-server/web/src/components/PlatformIcon.tsx services/api-server/web/src/pages/PricingPage.tsx services/api-server/web/src/pages/PricingPage.test.tsx
git commit -m "feat: differentiate pricing plan icons"
```

### Task 6: Unified Browser-First Layout

**Files:**
- Modify: `services/api-server/web/src/styles/tokens.css`
- Modify: `services/api-server/web/src/styles/shell.css`
- Modify: `services/api-server/web/src/styles/home.css`
- Modify: `services/api-server/web/src/styles/docs.css`
- Modify: `services/api-server/web/src/styles/pricing.css`
- Modify: `services/api-server/web/src/App.test.tsx`

- [ ] **Step 1: Add structural layout assertions**

Add route-class tests:

```tsx
test.each([
  ["/", "is-home"],
  ["/docs", "is-docs"],
  ["/pricing", "is-pricing"],
])("adds the route layout class for %s", (path, className) => {
  renderRoute(path);
  expect(screen.getByTestId("app-shell")).toHaveClass(className);
});
```

Keep visual dimensions in browser checks rather than brittle JSDOM pixel assertions.

- [ ] **Step 2: Run App tests**

Run:

```powershell
npm test -- --run src/App.test.tsx
```

Expected: PASS if route classes already exist; this test becomes the regression contract before CSS changes.

- [ ] **Step 3: Establish shared responsive tokens**

In `tokens.css`, define:

```css
:root {
  --content-max: 1440px;
  --content-gutter: clamp(20px, 4vw, 64px);
  --section-gap: clamp(20px, 2.2vw, 34px);
  --panel-radius: clamp(10px, 1vw, 16px);
  --heading-xl: clamp(40px, 3.2vw, 54px);
  --heading-lg: clamp(34px, 2.7vw, 46px);
}
```

Use one font, border, panel, radius, and muted-color hierarchy across all pages.

- [ ] **Step 4: Normalize shell and marketing flow**

In `shell.css`:

- Give marketing pages `width: min(calc(100% - 2 * var(--content-gutter)), var(--content-max))`.
- Keep a common desktop Header height and allow a compact mobile Header.
- Remove page-height assumptions from marketing routes.
- Keep the footer in normal flow.
- Hide Header CTA on `.is-pricing` through conditional rendering, not CSS.

- [ ] **Step 5: Convert homepage fixed dimensions to content flow**

In `home.css`:

- Remove fixed/minimum page heights used only to fill 945px.
- Use `grid-template-columns: minmax(0, 1fr) minmax(480px, .95fr)`.
- Size Hero gaps and section margins from `--section-gap`.
- Use `clamp()` for title and code-window height.
- Keep code overflow internal.
- At approximately `1120px`, stack Hero; at `760px`, switch all card grids to one column.

- [ ] **Step 6: Keep docs as a bounded workbench**

In `docs.css`:

```css
.is-docs {
  height: 100dvh;
  overflow: hidden;
}

.is-docs .site-main {
  height: calc(100dvh - var(--header-height));
  padding: clamp(12px, 1.4vw, 20px) var(--content-gutter);
}

.docs-page {
  width: min(100%, var(--content-max));
  height: 100%;
  margin: 0 auto;
  grid-template-columns:
    clamp(230px, 18vw, 285px)
    minmax(520px, 1fr)
    clamp(340px, 27vw, 420px);
}
```

Left and right columns remain stable; `.docs-content` owns vertical scrolling. Below the existing workbench breakpoint, return to normal page flow and allow the document to scroll.

- [ ] **Step 7: Convert pricing to natural flow**

In `pricing.css`:

- Remove fixed Hero and card heights used only for single-screen fit.
- Give cards a shared `min-height` and let content determine final height.
- Use five columns only when each card can remain at least about 220px wide.
- Move to three columns, then two, then one at content-driven breakpoints.
- Keep the selected quarterly glow and recommendation badge.
- Keep purchase summary and action strip in normal flow.

- [ ] **Step 8: Run component tests and build**

Run:

```powershell
npm test
npm run typecheck
npm run build
```

Expected: 0 failures and a successful Vite production build.

- [ ] **Step 9: Commit browser-first layout**

```powershell
git add services/api-server/web/src/styles services/api-server/web/src/styles.css services/api-server/web/src/App.test.tsx
git commit -m "feat: unify browser-first page layouts"
```

### Task 7: Browser Verification And Regression Cleanup

**Files:**
- Modify only files required by observed verification failures.

- [ ] **Step 1: Build the production assets**

Run:

```powershell
npm run build
```

Expected: the API server's static `web_dist` is refreshed successfully.

- [ ] **Step 2: Verify desktop layouts**

Using the in-app Browser, inspect `/`, `/docs`, and `/pricing` at:

- `1366×768`
- `1440×900`
- `1680×945`

For every route, record:

```js
{
  title: document.title,
  innerWidth,
  scrollWidth: document.documentElement.scrollWidth,
  scrollHeight: document.documentElement.scrollHeight
}
```

Acceptance:

- No horizontal overflow.
- Homepage and pricing content use normal vertical flow without large empty blocks.
- The three pages share aligned content boundaries and comparable visual scale.
- Docs stays at one viewport height on desktop, with the middle column independently scrollable.

- [ ] **Step 3: Verify tablet and mobile layouts**

Inspect all routes at `820×1180` and `390×844`.

Acceptance:

- No horizontal overflow.
- Header navigation remains usable.
- Docs converts to page flow.
- Pricing cards and homepage cards stack without clipped text or controls.

- [ ] **Step 4: Verify live request controls**

On `/docs`:

1. Add `source=portal`.
2. Send the request and verify the requested URL contains `source=portal`.
3. Verify response metadata appears.
4. Verify the response includes colored JSON tokens and line numbers.
5. Delete the custom row.
6. Delete required `q`, send, and verify `缺少必填参数：q`.
7. Switch endpoints and verify custom rows reset.

- [ ] **Step 5: Verify navigation and metadata**

Acceptance:

- Homepage title: `DramaFlux 开放平台`.
- Docs title: `接口文档 - DramaFlux`.
- Pricing title: `定价购买 - DramaFlux`.
- The favicon appears on all routes.
- Header `立即接入` opens `/pricing` from home/docs.
- Pricing has no Header CTA.

- [ ] **Step 6: Run final verification**

Run:

```powershell
npm test
npm run typecheck
npm run build
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 7: Commit verification fixes, if any**

If browser verification required changes:

```powershell
git add services/api-server/web
git commit -m "fix: polish responsive platform behavior"
```

If no changes were required, do not create an empty commit.
