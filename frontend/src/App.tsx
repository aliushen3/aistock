import { Alert, Layout, Menu, Typography } from "antd";
import { BrowserRouter, Route, Routes, Link, useLocation } from "react-router-dom";
import HomePage from "./pages/HomePage";
import GraphPage from "./pages/GraphPage";
import CandidatesPage from "./pages/CandidatesPage";
import ProductPage from "./pages/ProductPage";
import ReportPage from "./pages/ReportPage";
import DashboardPage from "./pages/DashboardPage";
import AuditPage from "./pages/AuditPage";
import DiagnosisPage from "./pages/DiagnosisPage";
import KnowledgePage from "./pages/KnowledgePage";
import DataOpsPage from "./pages/DataOpsPage";
import SectorSelect from "./components/SectorSelect";
import { SectorProvider } from "./lib/sectorContext";

const { Header, Content, Footer } = Layout;

function AppMenu() {
  const location = useLocation();
  const items = [
    { key: "/", label: <Link to="/">首页</Link> },
    { key: "/graph", label: <Link to="/graph">产业图谱</Link> },
    { key: "/dashboard", label: <Link to="/dashboard">产业看板</Link> },
    { key: "/candidates", label: <Link to="/candidates">候选池</Link> },
    { key: "/report", label: <Link to="/report">投研报告</Link> },
    { key: "/knowledge", label: <Link to="/knowledge">知识抽取</Link> },
    { key: "/diagnosis", label: <Link to="/diagnosis">智能诊断</Link> },
    { key: "/audit", label: <Link to="/audit">审计日志</Link> },
    { key: "/data-ops", label: <Link to="/data-ops">系统与数据</Link> },
  ];
  return (
    <Menu
      theme="dark"
      mode="horizontal"
      selectedKeys={[location.pathname]}
      items={items}
      style={{ flex: 1, minWidth: 0 }}
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <SectorProvider>
        <Layout style={{ minHeight: "100vh" }}>
          <Header style={{ display: "flex", alignItems: "center" }}>
            <Typography.Title level={4} style={{ color: "#fff", margin: 0, marginRight: 24 }}>
              AiStock
            </Typography.Title>
            <AppMenu />
            <SectorSelect />
          </Header>
          <Content style={{ padding: 24 }}>
            <Alert
              type="info"
              showIcon
              message="知识驱动的定性投研辅助系统"
              description="量化提示分仅作辅助排序，所有入池须经研究员人工确认。不构成投资建议。"
              style={{ marginBottom: 16 }}
            />
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/graph" element={<GraphPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/candidates" element={<CandidatesPage />} />
              <Route path="/products/:productId" element={<ProductPage />} />
              <Route path="/report" element={<ReportPage />} />
              <Route path="/knowledge" element={<KnowledgePage />} />
              <Route path="/diagnosis" element={<DiagnosisPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/data-ops" element={<DataOpsPage />} />
            </Routes>
          </Content>
          <Footer style={{ textAlign: "center" }}>
            AiStock © {new Date().getFullYear()} — 投研辅助工具，不构成投资建议
          </Footer>
        </Layout>
      </SectorProvider>
    </BrowserRouter>
  );
}
