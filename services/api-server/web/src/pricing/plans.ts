export type PlanId = "weekly" | "monthly" | "quarterly" | "halfYear" | "annual";

export type PricingPlan = {
  id: PlanId;
  name: string;
  price: number;
  days: number;
  caption: string;
  benefits: string[];
  recommended?: boolean;
};

export const pricingPlans: PricingPlan[] = [
  { id: "weekly", name: "周付", price: 18, days: 7, caption: "低成本试用", benefits: ["适合短期评估", "全部 VIP 能力"] },
  { id: "monthly", name: "月付", price: 59, days: 30, caption: "弹性使用", benefits: ["适合日常开发", "随时调整周期"] },
  { id: "quarterly", name: "季付", price: 149, days: 90, caption: "均衡之选", benefits: ["相比月付更划算", "适合项目开发"], recommended: true },
  { id: "halfYear", name: "半年付", price: 279, days: 180, caption: "长期稳定", benefits: ["更低周期成本", "适合持续运营"] },
  { id: "annual", name: "年付", price: 519, days: 365, caption: "年度优选", benefits: ["年度最优价格", "省心持续接入"] },
];

export function normalizeQuantity(quantity: number) {
  return Math.min(12, Math.max(1, Math.round(quantity) || 1));
}

export function calculateTotal(planId: PlanId, quantity: number) {
  const plan = pricingPlans.find((item) => item.id === planId);
  if (!plan) throw new Error(`Unknown plan: ${planId}`);
  const normalized = normalizeQuantity(quantity);
  return { total: plan.price * normalized, days: plan.days * normalized };
}
