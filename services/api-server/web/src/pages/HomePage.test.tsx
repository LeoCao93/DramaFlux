import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import HomePage from "./HomePage";

test("presents the platform capabilities and primary routes", () => {
  render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );

  expect(
    screen.getByRole("heading", { name: /稳定、清爽、易接入/ }),
  ).toBeInTheDocument();
  expect(screen.getByText("/api/search")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看接口文档" })).toHaveAttribute(
    "href",
    "/docs",
  );
  expect(screen.getByRole("link", { name: "查看定价方案" })).toHaveAttribute(
    "href",
    "/pricing",
  );
  expect(screen.getAllByTestId("capability-card")).toHaveLength(3);
  expect(screen.getAllByTestId("endpoint-card")).toHaveLength(3);
  expect(screen.getByTestId("hero-code-window")).toBeInTheDocument();
  expect(screen.getByLabelText("首页轨道装饰")).toBeInTheDocument();
  expect(screen.getAllByTestId("platform-icon")).toHaveLength(8);
});
