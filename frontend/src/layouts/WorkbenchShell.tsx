import {
  AppstoreOutlined,
  ApartmentOutlined,
  AlertOutlined,
  BarChartOutlined,
  BankOutlined,
  SettingOutlined,
  TeamOutlined,
  FundOutlined,
} from "@ant-design/icons";
import { Layout, Typography } from "antd";
import type { ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { workbenchNavigation } from "../mocks/navigation";

const { Sider, Header, Content } = Layout;

const iconMap: Record<string, ReactNode> = {
  dashboard: <AppstoreOutlined />,
  analysis: <BarChartOutlined />,
  risk: <AlertOutlined />,
  team: <TeamOutlined />,
  decision: <ApartmentOutlined />,
  bond: <BankOutlined />,
  settings: <SettingOutlined />,
  market: <FundOutlined />,
};

export function WorkbenchShell() {
  const location = useLocation();

  return (
    <Layout
      style={{
        minHeight: "100vh",
        background: "transparent",
      }}
    >
      <Sider
        width={264}
        breakpoint="lg"
        collapsedWidth={84}
        style={{
          margin: 18,
          border: "1px solid #d7dfea",
          borderRadius: 28,
          overflow: "hidden",
          boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "24px 24px 18px",
            borderBottom: "1px solid #e3e9f2",
          }}
        >
          <div
            style={{
              display: "grid",
              placeItems: "center",
              width: 34,
              height: 34,
              borderRadius: 12,
              background: "#162033",
              color: "#fbfcfe",
              fontWeight: 700,
            }}
          >
            M
          </div>
          <div>
            <Typography.Text
              style={{
                display: "block",
                color: "#162033",
                fontWeight: 600,
                fontSize: 18,
                letterSpacing: "-0.02em",
              }}
            >
              MOSS
            </Typography.Text>
            <Typography.Text
              style={{
                color: "#8090a8",
                fontSize: 12,
              }}
            >
              Workbench Shell
            </Typography.Text>
          </div>
        </div>

        <nav
          aria-label="主导航"
          style={{
            display: "grid",
            gap: 6,
            padding: 16,
          }}
        >
          {workbenchNavigation.map((item) => {
            const active = location.pathname === item.path;

            return (
              <NavLink
                key={item.key}
                to={item.path}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "14px 16px",
                  borderRadius: 16,
                  background: active ? "#e7efff" : "transparent",
                  color: active ? "#1f5eff" : "#485970",
                  fontWeight: active ? 600 : 500,
                  border: active
                    ? "1px solid #cddcff"
                    : "1px solid transparent",
                  transition: "background-color 160ms ease, color 160ms ease",
                }}
              >
                <span style={{ fontSize: 16 }}>{iconMap[item.icon]}</span>
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </Sider>

      <Layout
        style={{
          background: "transparent",
          padding: "18px 18px 18px 0",
        }}
      >
        <Header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 24px",
            height: 84,
            background: "#fbfcfe",
            border: "1px solid #d7dfea",
            borderRadius: 28,
            boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
          }}
        >
          <div>
            <Typography.Text
              style={{
                display: "block",
                color: "#8090a8",
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              management workspace
            </Typography.Text>
            <Typography.Title
              level={4}
              style={{
                margin: "6px 0 0",
                fontSize: 22,
                fontWeight: 600,
              }}
            >
              前端壳层阶段
            </Typography.Title>
          </div>
          <div style={{ textAlign: "right" }}>
            <Typography.Text
              style={{
                display: "block",
                color: "#162033",
                fontWeight: 600,
              }}
            >
              数据日期 2026-04-09
            </Typography.Text>
            <Typography.Text
              style={{
                color: "#5c6b82",
              }}
            >
              health / result_meta 协议对接预留
            </Typography.Text>
          </div>
        </Header>

        <Content
          style={{
            marginTop: 18,
            padding: 28,
            background: "#fbfcfe",
            border: "1px solid #d7dfea",
            borderRadius: 28,
            boxShadow: "0 18px 40px rgba(19, 37, 70, 0.08)",
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
