import { afterEach, describe, expect, test, vi } from "vitest";

import { apiCatalog } from "./catalog";
import {
  buildRequest,
  executeRequest,
  validateCustomQueryParameters,
} from "./client";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("apiCatalog", () => {
  test("准确列出七个真实 GET 接口", () => {
    expect(apiCatalog.map(({ method, path }) => `${method} ${path}`)).toEqual([
      "GET /health",
      "GET /api/search",
      "GET /api/latest",
      "GET /api/rank",
      "GET /api/books/{series_id}",
      "GET /api/books/{series_id}/episodes",
      "GET /api/videos/{video_id}",
    ]);
  });
});

describe("buildRequest", () => {
  test("为搜索接口构建只包含有值参数的 URL", () => {
    const endpoint = apiCatalog.find(({ id }) => id === "search");

    expect(buildRequest(endpoint!, { q: "短剧 推荐", cursor: "" })).toEqual({
      method: "GET",
      url: "/api/search?q=%E7%9F%AD%E5%89%A7+%E6%8E%A8%E8%8D%90",
    });
  });

  test("可以追加自定义 query 参数", () => {
    const endpoint = apiCatalog.find(({ id }) => id === "search");

    expect(
      buildRequest(endpoint!, { q: "短剧", cursor: "" }, [
        { id: "custom-1", name: "source", type: "string", value: "portal" },
        { id: "custom-2", name: "preview", type: "boolean", value: "true" },
      ]),
    ).toEqual({
      method: "GET",
      url: "/api/search?q=%E7%9F%AD%E5%89%A7&source=portal&preview=true",
    });
  });

  test("自定义参数会忽略空值与冲突项", () => {
    const endpoint = apiCatalog.find(({ id }) => id === "search");

    expect(
      buildRequest(endpoint!, { q: "短剧", cursor: "" }, [
        { id: "a", name: "q", type: "string", value: "override" },
        { id: "b", name: "", type: "string", value: "skip" },
        { id: "c", name: "source", type: "string", value: "" },
      ]),
    ).toEqual({
      method: "GET",
      url: "/api/search?q=%E7%9F%AD%E5%89%A7",
    });
  });

  test("路径参数会逐段编码", () => {
    const endpoint = apiCatalog.find(({ id }) => id === "book-detail");

    expect(buildRequest(endpoint!, { series_id: "a/b" }).url).toBe(
      "/api/books/a%2Fb",
    );
  });

  test("必填参数为空时抛出清晰中文错误", () => {
    const endpoint = apiCatalog.find(({ id }) => id === "search");

    expect(() => buildRequest(endpoint!, { q: "   " })).toThrow(
      "缺少必填参数：q",
    );
  });
});

describe("validateCustomQueryParameters", () => {
  test("会标记与接口参数或其他自定义参数冲突的字段", () => {
    const endpoint = apiCatalog.find(({ id }) => id === "search");

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
  });
});

describe("executeRequest", () => {
  test("解析 JSON 成功响应并报告耗时", async () => {
    vi.spyOn(performance, "now")
      .mockReturnValueOnce(10)
      .mockReturnValueOnce(34.5);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: 200,
            message: "success",
            data: { items: [] },
          }),
          {
            status: 200,
            statusText: "OK",
            headers: { "content-type": "application/json; charset=utf-8" },
          },
        ),
      ),
    );

    await expect(
      executeRequest({ method: "GET", url: "/api/search?q=test" }),
    ).resolves.toEqual({
      status: 200,
      statusText: "OK",
      ok: true,
      elapsedMs: 24.5,
      body: {
        code: 200,
        message: "success",
        data: { items: [] },
      },
      contentType: "application/json; charset=utf-8",
    });
  });

  test("非 2xx JSON API 错误仍解析 body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            code: "invalid_cursor",
            message: "cursor is invalid",
            request_id: "request-1",
          }),
          {
            status: 400,
            statusText: "Bad Request",
            headers: { "content-type": "application/json" },
          },
        ),
      ),
    );

    const result = await executeRequest({
      method: "GET",
      url: "/api/search?q=test&cursor=bad",
    });

    expect(result.ok).toBe(false);
    expect(result.body).toEqual({
      code: "invalid_cursor",
      message: "cursor is invalid",
      request_id: "request-1",
    });
  });

  test("超时中止请求并规范化为中文错误", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      }),
    );

    const pending = executeRequest(
      { method: "GET", url: "/health" },
      { timeoutMs: 25 },
    );
    const rejection = expect(pending).rejects.toThrow("请求超时：25ms");
    await vi.advanceTimersByTimeAsync(25);

    await rejection;
  });

  test("默认 timeoutMs 在 15000ms 触发", async () => {
    vi.useFakeTimers();
    let fetchSignal: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        fetchSignal = init?.signal ?? undefined;
        return new Promise<Response>((_resolve, reject) => {
          fetchSignal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      }),
    );

    const pending = executeRequest({ method: "GET", url: "/health" });
    const rejection = expect(pending).rejects.toThrow("请求超时：15000ms");

    await vi.advanceTimersByTimeAsync(14_999);
    expect(fetchSignal?.aborted).toBe(false);

    await vi.advanceTimersByTimeAsync(1);
    expect(fetchSignal?.aborted).toBe(true);
    await rejection;
  });

  test("外部 AbortSignal 中止 fetch 并保留原始错误", async () => {
    vi.useFakeTimers();
    const externalController = new AbortController();
    let fetchSignal: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        fetchSignal = init?.signal ?? undefined;
        return new Promise<Response>((_resolve, reject) => {
          fetchSignal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      }),
    );

    const pending = executeRequest(
      { method: "GET", url: "/health" },
      { signal: externalController.signal },
    );
    const rejection = pending.catch((error: unknown) => error);

    externalController.abort();
    const error = await rejection;

    expect(fetchSignal?.aborted).toBe(true);
    expect(error).toBeInstanceOf(DOMException);
    expect((error as DOMException).name).toBe("AbortError");
    expect((error as Error).message).not.toContain("请求超时");
  });

  test("非 JSON 文本最多保留 20000 个字符", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("x".repeat(20_001), {
          status: 502,
          headers: { "content-type": "text/plain; charset=utf-8" },
        }),
      ),
    );

    const result = await executeRequest({
      method: "GET",
      url: "/upstream-error",
    });

    expect(result.body).toBe("x".repeat(20_000));
  });
});
