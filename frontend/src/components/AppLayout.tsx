import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu } from "antd";
import {
  DashboardOutlined,
  ApartmentOutlined,
  MessageOutlined,
  LinkOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";

const { Sider, Content } = Layout;

const menuItems = [
  { key: "/dashboard", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/state-machine", icon: <ApartmentOutlined />, label: "State Machine" },
  { key: "/messages", icon: <MessageOutlined />, label: "Messages" },
  { key: "/evidence", icon: <LinkOutlined />, label: "Evidence Chain" },
  { key: "/probes", icon: <ExperimentOutlined />, label: "Probe History" },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={240}
        theme="light"
        style={{
          position: "fixed",
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
      >
        <div className="brand-logo">
          <div className="logo-icon">P</div>
          {!collapsed && (
            <div>
              <div className="logo-text">ProtoAnalyzer</div>
              <div className="logo-sub">Protocol Analysis</div>
            </div>
          )}
        </div>
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ marginTop: 12 }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 240, transition: "margin-left 0.2s" }}>
        <Content style={{ padding: 32, minHeight: "100vh" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
