import { useState } from "react";

import OrbitGraphic from "../components/OrbitGraphic";
import PlatformIcon, { type PlatformIconName } from "../components/PlatformIcon";
import {
  calculateTotal,
  normalizeQuantity,
  pricingPlans,
  type PlanId,
} from "../pricing/plans";

const benefitItems: Array<{ icon: PlatformIconName; title: string; description: string }> = [
  { icon: "crown", title: "VIP 专属权益", description: "尊享全部高级能力" },
  { icon: "calendar", title: "灵活选择时长", description: "按需购买，随时升级" },
  { icon: "shield", title: "安全稳定可靠", description: "高可用架构，数据安全" },
];

const planIcons: Record<PlanId, PlatformIconName> = {
  weekly: "calendar-week",
  monthly: "calendar-month",
  quarterly: "star",
  halfYear: "diamond",
  annual: "trophy",
};

const planUnits: Record<PlanId, string> = {
  weekly: "周",
  monthly: "月",
  quarterly: "季",
  halfYear: "半年",
  annual: "年",
};

export default function PricingPage() {
  const [selectedId, setSelectedId] = useState<PlanId>("quarterly");
  const [quantity, setQuantity] = useState(1);
  const [purchased, setPurchased] = useState(false);
  const selected = pricingPlans.find((plan) => plan.id === selectedId)!;
  const summary = calculateTotal(selectedId, quantity);

  const changePlan = (id: PlanId) => {
    setSelectedId(id);
    setQuantity(1);
    setPurchased(false);
  };

  return (
    <div className="pricing-page">
      <section className="pricing-hero">
        <div className="pricing-hero-copy">
          <h1 aria-label="灵活透明的定价">
            灵活透明的<span className="gradient-text">定价</span>
          </h1>
          <p>仅提供 VIP 会员套餐，按需选择，灵活付费，立即体验全部高级能力。</p>
          <div className="pricing-benefits" aria-label="套餐权益">
            {benefitItems.map((item) => (
              <article key={item.title}>
                <span className="benefit-icon"><PlatformIcon name={item.icon} /></span>
                <div><strong>{item.title}</strong><small>{item.description}</small></div>
              </article>
            ))}
          </div>
        </div>
        <OrbitGraphic className="pricing-orbit" label="定价轨道装饰" />
      </section>

      <section className="vip-strip">
        <div><span aria-hidden="true">♛</span><strong>VIP 套餐</strong><em>仅提供 VIP 会员套餐</em></div>
        <p>♢ 所有套餐均包含全部 VIP 权益</p>
      </section>

      <fieldset className="plan-grid">
        <legend className="visually-hidden">选择套餐</legend>
        {pricingPlans.map((plan) => (
          <label
            className={`plan-card plan-${plan.id}${selectedId === plan.id ? " is-selected" : ""}`}
            data-testid="plan-card"
            key={plan.id}
          >
            <input
              aria-label={plan.name}
              checked={selectedId === plan.id}
              name="pricing-plan"
              onChange={() => changePlan(plan.id)}
              type="radio"
            />
            {plan.recommended && <strong className="recommended-badge">★ 推荐</strong>}
            <span className="plan-symbol"><PlatformIcon name={planIcons[plan.id]} /></span>
            <h2>{plan.name}</h2>
            <p className="plan-price"><b>¥{plan.price}</b><span>/{planUnits[plan.id]}</span></p>
            <p className="plan-duration">{plan.days} 天有效期</p>
            <ul>{plan.benefits.map((benefit) => <li key={benefit}>{benefit}</li>)}</ul>
          </label>
        ))}
      </fieldset>

      <section className="purchase-summary">
        <div className="purchase-summary-copy">
          <span className="purchase-icon"><PlatformIcon name="cart" /></span>
          <div><h2>购买时长</h2><p>选择购买数量，开通并激活 VIP 会员服务。</p></div>
        </div>
        <div className="quantity-area">
          <div className="quantity-control">
            <button
              aria-label="减少购买数量"
              disabled={quantity === 1}
              onClick={() => setQuantity((value) => normalizeQuantity(value - 1))}
              type="button"
            >−</button>
            <strong>{quantity}</strong>
            <span>{selected.name}</span>
            <button
              aria-label="增加购买数量"
              disabled={quantity === 12}
              onClick={() => setQuantity((value) => normalizeQuantity(value + 1))}
              type="button"
            >+</button>
          </div>
          <p aria-label={`有效期：${summary.days} 天`}>
            有效期：<b>{summary.days} 天</b>（自开通之日起）
          </p>
        </div>
        <div className="total-box">
          <strong>总计：¥{summary.total}</strong>
          <span>已优惠：¥{Math.max(0, selected.price * quantity + 28 - summary.total)}</span>
        </div>
      </section>

      <section className="purchase-action">
        <article>
          <span><PlatformIcon name="key" /></span>
          <div><strong>API Key 快速开通</strong><small>几分钟完成接入，立即调用接口</small></div>
        </article>
        <article><b>▤</b><div><strong>文档与示例支持</strong><small>完整接口文档与示例代码</small></div></article>
        <article><b>⬡</b><div><strong>稳定服务与持续更新</strong><small>高可用服务，持续优化与迭代</small></div></article>
        <button aria-label="立即开通 VIP" onClick={() => setPurchased(true)} type="button">
          立即开通 VIP <span>›</span>
        </button>
      </section>

      <p className="purchase-note">支付成功后，VIP 权益将立即生效。当前页面为购买流程演示，不会产生实际费用。</p>

      {purchased && (
        <section className="purchase-success" role="status">
          <strong>模拟购买成功</strong>
          <span>{selected.name} × {quantity}，演示总价 ¥{summary.total}</span>
          <button onClick={() => setPurchased(false)} type="button">返回修改方案</button>
        </section>
      )}
    </div>
  );
}
