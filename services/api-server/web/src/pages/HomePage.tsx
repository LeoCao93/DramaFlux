import { Link } from "react-router-dom";

import { apiCatalog } from "../api/catalog";
import Icon from "../components/Icon";
import OrbitGraphic from "../components/OrbitGraphic";
import PlatformIcon, { type PlatformIconName } from "../components/PlatformIcon";
import SyntaxCodeBlock from "../components/SyntaxCodeBlock";

const capabilities: Array<{
  title: string;
  description: string;
  icon: PlatformIconName;
  tone: string;
}> = [
  {
    title: "高可用服务",
    description: "多机房分布式部署，智能监控与弹性扩展，保障 99.9% 服务可用性。",
    icon: "layers",
    tone: "blue",
  },
  {
    title: "简单认证",
    description: "通过 API Key 轻松认证，快速接入，无需复杂流程。",
    icon: "shield",
    tone: "violet",
  },
  {
    title: "快速响应",
    description: "全球加速，毫秒级响应，为业务提供强大支持。",
    icon: "lightning",
    tone: "cyan",
  },
];

const endpointCards: Array<{
  id: string;
  title: string;
  description: string;
  icon: PlatformIconName;
  tone: string;
}> = [
  { id: "search", title: "搜索接口", description: "关键词搜索，快速获取结果。", icon: "search", tone: "blue" },
  { id: "book-detail", title: "详情接口", description: "获取资源详细信息。", icon: "document", tone: "violet" },
  { id: "video", title: "解析接口", description: "结构化解析，返回关键信息。", icon: "code", tone: "cyan" },
];

const heroCode = [
  "curl -X GET 'https://api.dramaflux.com/v1/search' \\",
  "  -H \"Authorization: Bearer YOUR_API_KEY\" \\",
  "  -H \"Content-Type: application/json\" \\",
  "  -d '{",
  "    \"keyword\": \"流浪地球2\",",
  "    \"page\": 1,",
  "    \"page_size\": 10",
  "  }'",
  "",
  "# 响应示例",
  "{ \"code\": 0, \"message\": \"success\", \"data\": { ... } }",
];

export default function HomePage() {
  return (
    <div className="home-page">
      <section className="hero-section">
        <div className="hero-copy">
          <h1>
            稳定、清爽、易接入的
            <span className="gradient-text">开放平台</span>
          </h1>
          <p className="hero-description">
            DramaFlux 提供稳定可靠的开放 API 服务，拥有清晰完整的文档
            <br />
            和简洁的接入流程，助力开发者快速构建精彩应用。
          </p>
          <div className="hero-actions">
            <Link className="primary-action hero-action" to="/docs">
              <PlatformIcon name="book" />
              查看接口文档
            </Link>
            <Link className="secondary-action hero-key-action" to="/docs#search">
              <PlatformIcon name="key" />
              获取 API Key
            </Link>
          </div>
        </div>

        <div className="hero-visual">
          <OrbitGraphic className="home-orbit" label="首页轨道装饰" />
          <div className="hero-code" data-testid="hero-code-window">
            <div className="code-window-header">
              <span className="terminal-dots" aria-hidden="true">
                <i /><i /><i />
              </span>
              <strong>cURL</strong>
              <span className="code-chevron">⌄</span>
            </div>
            <SyntaxCodeBlock lines={heroCode} label="搜索接口 cURL 示例" />
          </div>
        </div>
      </section>

      <section className="capability-grid" aria-label="平台优势">
        {capabilities.map((item) => (
          <article className="feature-card" data-testid="capability-card" key={item.title}>
            <span className={`feature-icon icon-tone-${item.tone}`}>
              <PlatformIcon name={item.icon} />
            </span>
            <div>
              <h2>{item.title}</h2>
              <p>{item.description}</p>
            </div>
          </article>
        ))}
      </section>

      <section className="endpoint-grid" aria-label="核心接口">
        {endpointCards.map((item) => {
          const endpoint = apiCatalog.find((candidate) => candidate.id === item.id)!;
          return (
            <Link
              className="endpoint-card"
              data-testid="endpoint-card"
              key={item.id}
              to={`/docs#${item.id}`}
            >
              <span className={`endpoint-icon icon-tone-${item.tone}`}>
                <PlatformIcon name={item.icon} />
              </span>
              <span className="endpoint-copy">
                <strong>{item.title}</strong>
                <small>{item.description}</small>
                <code>{endpoint.path}</code>
              </span>
              <Icon name="arrow-right" />
            </Link>
          );
        })}
      </section>

      <section className="pricing-banner">
        <span className="pricing-banner-icon" aria-hidden="true">
          ◇
        </span>
        <div>
          <h2>透明的定价，灵活可控</h2>
          <p>灵活的计费方式，满足不同规模项目需求，免费额度可用，按需付费，成本可控。</p>
        </div>
        <Link className="secondary-action" to="/pricing">
          查看定价方案 <Icon name="arrow-right" size={17} />
        </Link>
      </section>
    </div>
  );
}
