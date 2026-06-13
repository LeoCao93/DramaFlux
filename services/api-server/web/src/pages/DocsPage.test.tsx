import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import * as client from "../api/client";
import DocsPage from "./DocsPage";

test("切换接口、添加自定义参数并发送调试请求", async () => {
  vi.spyOn(client, "executeRequest").mockResolvedValue({
    status: 200,
    statusText: "OK",
    ok: true,
    elapsedMs: 18,
    body: {
      code: 200,
      message: "success",
      data: { items: [] },
      cached: false,
      request_id: "request-id-0001",
    },
    contentType: "application/json",
  });

  render(
    <MemoryRouter>
      <DocsPage />
    </MemoryRouter>,
  );

  expect(screen.getByLabelText("搜索API文档")).toHaveValue("");
  expect(screen.getByRole("tab", { name: "API文档" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  fireEvent.click(screen.getByRole("tab", { name: "在线调试" }));
  expect(screen.getByLabelText("q")).toHaveValue("都市甜宠");
  expect(screen.getByLabelText("page")).toHaveValue(1);
  expect(screen.getByLabelText("page_size")).toHaveValue(30);
  expect(screen.getByLabelText("cursor")).toHaveValue("");

  fireEvent.click(screen.getByRole("button", { name: /获取短剧详情/ }));
  fireEvent.click(screen.getByRole("tab", { name: "在线调试" }));
  expect(screen.getAllByText("/api/books/{series_id}")[0]).toBeInTheDocument();
  expect(screen.getByLabelText("series_id")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "＋ 添加参数" }));
  expect(screen.getByTestId("custom-parameter-row")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("自定义参数名 1"), {
    target: { value: "source" },
  });
  fireEvent.change(screen.getByLabelText("自定义参数类型 1"), {
    target: { value: "string" },
  });
  fireEvent.change(screen.getByLabelText("自定义参数值 1"), {
    target: { value: "portal" },
  });

  fireEvent.click(screen.getByRole("button", { name: "发送请求" }));
  await waitFor(() =>
    expect(client.executeRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        method: "GET",
        url: expect.stringContaining("/api/books/1001?source=portal"),
      }),
      expect.anything(),
    ),
  );

  expect(await screen.findByText("200 OK")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "响应结果" })).toBeInTheDocument();
  expect(screen.getByLabelText("真实接口响应")).toBeInTheDocument();
});
