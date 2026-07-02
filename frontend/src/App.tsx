import { Alert, Layout, Menu, Typography } from "antd";

import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import HomePage from "./pages/HomePage";

import GraphPage from "./pages/GraphPage";

import CandidatesPage from "./pages/CandidatesPage";

import ProductPage from "./pages/ProductPage";

import ReportPage from "./pages/ReportPage";

import DashboardPage from "./pages/DashboardPage";

import AuditPage from "./pages/AuditPage";

import KnowledgePage from "./pages/KnowledgePage";

import DataOpsPage from "./pages/DataOpsPage";

import SectorSelect from "./components/SectorSelect";
import OperatorSelect from "./components/OperatorSelect";

import { SectorProvider } from "./lib/sectorContext";
import { UserProvider, useUser } from "./lib/userContext";

import { NAV_MENU_ITEMS, filterNavByRole } from "./lib/navMenu";



const { Header, Content, Footer } = Layout;



function AppMenu() {
  const location = useLocation();
  const { navRole } = useUser();
  const items = filterNavByRole(NAV_MENU_ITEMS, navRole).map(({ key, label, children }) => ({
    key,
    label,
    children: children?.map((c) => ({ key: c.key, label: c.label })),
  }));



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



function DiagnosisRedirect() {

  return <Navigate to="/candidates?tab=diagnosis" replace />;

}



export default function App() {
  return (
    <BrowserRouter>
      <UserProvider>
        <SectorProvider>
          <Layout style={{ minHeight: "100vh" }}>
            <Header style={{ display: "flex", alignItems: "center" }}>
              <Typography.Title level={4} style={{ color: "#fff", margin: 0, marginRight: 24 }}>
                AiStock
              </Typography.Title>
              <AppMenu />
              <OperatorSelect />
              <SectorSelect />
            </Header>

          <Content style={{ padding: 24 }}>

            <Alert

              type="info"

              showIcon

              message="Agent 驱动的定性投研辅助系统"

              description="五阶段投研流程（赛道→产业链→环节→标的→跟踪），Agent 自动推进、人工门控裁决。量化提示分仅作辅助排序，不构成投资建议。"

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

              <Route path="/diagnosis" element={<DiagnosisRedirect />} />

              <Route path="/audit" element={<AuditPage />} />

              <Route path="/data-ops" element={<DataOpsPage />} />

            </Routes>

          </Content>

          <Footer style={{ textAlign: "center" }}>

            AiStock © {new Date().getFullYear()} — 投研辅助工具，不构成投资建议

          </Footer>

        </Layout>
        </SectorProvider>
      </UserProvider>
    </BrowserRouter>
  );
}


