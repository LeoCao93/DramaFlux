import { expect, test } from "vitest";

import { calculateTotal, normalizeQuantity } from "./plans";

test("calculates plan totals and bounds quantity", () => {
  expect(calculateTotal("quarterly", 1)).toEqual({ total: 149, days: 90 });
  expect(calculateTotal("monthly", 2)).toEqual({ total: 118, days: 60 });
  expect(normalizeQuantity(0)).toBe(1);
  expect(normalizeQuantity(13)).toBe(12);
});
