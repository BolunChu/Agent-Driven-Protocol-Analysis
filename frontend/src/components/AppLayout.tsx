import { useState, useEffect } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Select } from "antd";
import {
  DashboardOutlined,
  ApartmentOutlined,
  MessageOutlined,
  LinkOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { Project } from "../api/client";
import { useProjectContext } from "../context/ProjectContext";

const { Sider, Content, Header } = Layout;

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
  const [projects, setProjects] = useState<Project[]>([]);
  const { projectId, setProjectId } = useProjectContext();

  useEffect(() => {
    api.listProjects().then((p) => {
      // Sort projects by ID descending (newest batch first)
      const sorted = p.sort((a, b) => b.id - a.id);
      setProjects(sorted);
      // We only want to set the default project ID initially if one isn't selected
      // or if the currently selected one is not in the fetched list.
      setProjectId((currentId) => {
        if (sorted.length > 0 && (!currentId || !sorted.some((item) => item.id === currentId))) {
          return sorted[0].id;
        }
        return currentId;
      });
    }).catch(() => {});
  }, [setProjectId]);

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
        <Header style={{ 
          background: "var(--bg-card)", 
          padding: "0 32px", 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "flex-end",
          borderBottom: "1px solid var(--border-color)",
          height: 64,
          position: "sticky",
          top: 0,
          zIndex: 99
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ color: "var(--text-secondary)", fontSize: 14 }}>Batch Select:</span>
            <Select
              value={projectId}
              onChange={setProjectId}
              style={{ width: 320 }}
              placeholder="Select Project Batch"
              options={projects.map((p) => ({ 
                label: `[#${p.id}] ${p.name}`, 
                value: p.id 
              }))}
              showSearch
              optionFilterProp="label"
            />
          </div>
        </Header>
        <Content style={{ padding: 32, minHeight: "calc(100vh - 64px)" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
