import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";

import BrandLogo from "./BrandLogo";
import Icon from "./Icon";

type AppShellProps = {
  children: ReactNode;
};

const navigation = [
  { label: "首页", to: "/" },
  { label: "接口文档", to: "/docs" },
  { label: "定价", to: "/pricing" },
];

const routeMetadata: Record<string, { title: string; showCta: boolean }> = {
  "/": { title: "DramaFlux 开放平台", showCta: true },
  "/docs": { title: "接口文档 - DramaFlux", showCta: true },
  "/pricing": { title: "定价购买 - DramaFlux", showCta: false },
};

export default function AppShell({ children }: AppShellProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const metadata = routeMetadata[location.pathname] ?? routeMetadata["/"];
  const isDocs = location.pathname === "/docs";
  const routeClass =
    location.pathname === "/pricing"
      ? "is-pricing"
      : isDocs
        ? "is-docs"
        : "is-home";

  useEffect(() => {
    setMenuOpen(false);
    document.title = metadata.title;
  }, [location.pathname, metadata.title]);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };

    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  return (
    <div
      className={`app-shell ${routeClass}${isDocs ? "" : " is-marketing"}`}
      data-testid="app-shell"
    >
      <div className="background-decoration" aria-hidden="true">
        <span className="background-orb background-orb-cyan" />
        <span className="background-orb background-orb-violet" />
        <span className="background-grid" />
      </div>

      <header className="site-header">
        <div className="site-header-inner">
          <Link className="brand" to="/" aria-label="DramaFlux 开放平台首页">
            <BrandLogo />
            <span className="brand-copy">
              <strong>DramaFlux</strong>
              
            </span>
          </Link>

          <nav
            id="primary-navigation"
            className={`main-navigation${menuOpen ? " is-open" : ""}`}
            aria-label="主导航"
          >
            {navigation.map((item) => (
              <NavLink
                key={item.to}
                end={item.to === "/"}
                to={item.to}
                className={({ isActive }) =>
                  `navigation-link${isActive ? " is-active" : ""}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="header-actions">
            {metadata.showCta && (
              <Link className="primary-action" to="/pricing">
                立即接入
                <Icon name="arrow-right" size={16} />
              </Link>
            )}
            <button
              className="menu-button"
              type="button"
              aria-label={menuOpen ? "关闭导航菜单" : "打开导航菜单"}
              aria-controls="primary-navigation"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <Icon name={menuOpen ? "close" : "menu"} />
            </button>
          </div>
        </div>
      </header>

      <main className="site-main">{children}</main>

      <footer className="site-footer">
        <div className="site-footer-inner">
          <Link className="footer-brand" to="/">
            DramaFlux 开放平台
          </Link>
          <p>稳定、清爽、易接入的开放 API 服务。</p>
          <nav className="footer-links" aria-label="页脚导航">
            <Link to="/docs">接口文档</Link>
            <Link to="/pricing">定价</Link>
          </nav>
          <small>© {new Date().getFullYear()} DramaFlux</small>
        </div>
      </footer>
    </div>
  );
}
