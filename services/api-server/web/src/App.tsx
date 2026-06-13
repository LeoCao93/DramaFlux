import { Link, Route, Routes } from "react-router-dom";

import AppShell from "./components/AppShell";
import DocsPage from "./pages/DocsPage";
import HomePage from "./pages/HomePage";
import PricingPage from "./pages/PricingPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/docs" element={<DocsPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route
          path="*"
          element={
            <section className="not-found">
              <h1>404</h1>
              <Link to="/">返回首页</Link>
            </section>
          }
        />
      </Routes>
    </AppShell>
  );
}
