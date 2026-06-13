import { fireEvent, render, screen, within } from "@testing-library/react";

import PricingPage from "./PricingPage";

test("selects plans, updates quantity, and simulates purchase", () => {
  render(<PricingPage />);

  expect(screen.getByRole("heading", { level: 1, name: "灵活透明的定价" })).toBeInTheDocument();
  expect(screen.getByText("VIP 套餐")).toBeInTheDocument();
  expect(screen.getAllByTestId("platform-icon")).toHaveLength(10);
  expect(
    screen
      .getAllByTestId("plan-card")
      .map((card) => within(card).getByTestId("platform-icon").getAttribute("data-icon")),
  ).toEqual(["calendar-week", "calendar-month", "star", "diamond", "trophy"]);
  expect(screen.getByRole("radio", { name: "季付" })).toBeChecked();
  expect(screen.getByText("总计：¥149")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("radio", { name: "年付" }));
  fireEvent.click(screen.getByRole("button", { name: "增加购买数量" }));
  expect(screen.getByText("总计：¥1038")).toBeInTheDocument();
  expect(screen.getByLabelText("有效期：730 天")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "立即开通 VIP" }));
  expect(screen.getByText(/模拟购买成功/)).toBeInTheDocument();
});
