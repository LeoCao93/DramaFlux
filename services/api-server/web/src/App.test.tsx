import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "./App";

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

test.each([
  ["/", "DramaFlux 开放平台"],
  ["/docs", "接口文档 - DramaFlux"],
  ["/pricing", "定价购买 - DramaFlux"],
])("为 %s 设置路由标题", (path, expectedTitle) => {
  renderRoute(path);

  expect(document.title).toBe(expectedTitle);
});

test("立即接入指向定价页并在定价页隐藏", () => {
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

test("首页展示稳定、清爽、易接入的开放平台文案", () => {
  renderRoute("/");

  expect(
    screen.getByRole("heading", { name: /稳定、清爽、易接入/ }),
  ).toBeInTheDocument();
});

test("文档页展示接口文档标题", () => {
  renderRoute("/docs");

  expect(
    screen.getByRole("heading", { name: "接口文档" }),
  ).toBeInTheDocument();
});

test("定价页展示灵活透明的定价标题", () => {
  renderRoute("/pricing");

  expect(
    screen.getByRole("heading", { name: "灵活透明的定价" }),
  ).toBeInTheDocument();
});

test("未知路径展示 404 和返回首页链接", () => {
  renderRoute("/missing");

  expect(screen.getByRole("heading", { name: "404" })).toBeInTheDocument();
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(screen.getByRole("link", { name: "返回首页" })).toHaveAttribute(
    "href",
    "/",
  );
});

test("共享外壳提供品牌入口和主导航链接", () => {
  renderRoute("/");

  expect(
    screen.getByRole("link", { name: "DramaFlux 开放平台首页" }),
  ).toHaveAttribute("href", "/");
  expect(screen.getByTestId("brand-logo").tagName).toBe("svg");
  const navigation = screen.getByRole("navigation", { name: "主导航" });

  expect(within(navigation).getByRole("link", { name: "首页" })).toHaveAttribute(
    "href",
    "/",
  );
  expect(
    within(navigation).getByRole("link", { name: "接口文档" }),
  ).toHaveAttribute("href", "/docs");
  expect(within(navigation).getByRole("link", { name: "定价" })).toHaveAttribute(
    "href",
    "/pricing",
  );
  expect(screen.getByRole("navigation", { name: "页脚导航" })).toBeInTheDocument();
});

test("文档路由使用紧凑工作台外壳", () => {
  renderRoute("/docs");

  expect(screen.getByTestId("app-shell")).toHaveClass("is-docs");
});

test.each([
  ["/", "is-home"],
  ["/docs", "is-docs"],
  ["/pricing", "is-pricing"],
])("adds the route layout class for %s", (path, className) => {
  renderRoute(path);

  expect(screen.getByTestId("app-shell")).toHaveClass(className);
});

test("移动导航按钮随展开状态更新名称并可以关闭", () => {
  renderRoute("/");

  const openButton = screen.getByRole("button", { name: "打开导航菜单" });

  expect(openButton).toHaveAttribute("aria-expanded", "false");

  fireEvent.click(openButton);

  const closeButton = screen.getByRole("button", { name: "关闭导航菜单" });
  expect(closeButton).toHaveAttribute("aria-expanded", "true");

  fireEvent.click(closeButton);
  expect(
    screen.getByRole("button", { name: "打开导航菜单" }),
  ).toHaveAttribute("aria-expanded", "false");
});

test("菜单展开后点击导航链接会切换路由并关闭菜单", () => {
  renderRoute("/");

  fireEvent.click(screen.getByRole("button", { name: "打开导航菜单" }));
  fireEvent.click(
    within(screen.getByRole("navigation", { name: "主导航" })).getByRole(
      "link",
      { name: "接口文档" },
    ),
  );

  expect(screen.getByRole("heading", { name: "接口文档" })).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "打开导航菜单" }),
  ).toHaveAttribute("aria-expanded", "false");
});

test("菜单展开后点击立即接入会切换到定价页并关闭菜单", () => {
  renderRoute("/");

  fireEvent.click(screen.getByRole("button", { name: "打开导航菜单" }));
  fireEvent.click(screen.getByRole("link", { name: "立即接入" }));

  expect(
    screen.getByRole("heading", { name: "灵活透明的定价" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "打开导航菜单" }),
  ).toHaveAttribute("aria-expanded", "false");
});

test("按 Escape 关闭已展开的移动导航菜单", () => {
  renderRoute("/");

  fireEvent.click(screen.getByRole("button", { name: "打开导航菜单" }));
  fireEvent.keyDown(document, { key: "Escape" });

  expect(
    screen.getByRole("button", { name: "打开导航菜单" }),
  ).toHaveAttribute("aria-expanded", "false");
});
