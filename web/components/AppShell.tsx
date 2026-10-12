"use client";

import { Button, Layout, Menu, Typography } from "antd";
import type { MenuProps } from "antd";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import type { ReactNode } from "react";

const { Header, Content } = Layout;

const navigationItems: MenuProps["items"] = [
  {
    key: "/workspace",
    label: <Link href="/workspace">工作台</Link>,
  },
  {
    key: "diagnosis-application",
    label: "诊断应用",
    children: [
      { key: "/incidents", label: <Link href="/incidents">Incident 诊断</Link> },
    ],
  },
  {
    key: "ai-platform",
    label: "AI 中台",
    children: [
      {
        key: "/ai/datasets",
        label: <Link href="/ai/datasets">治理数据</Link>,
      },
      {
        key: "/ai/knowledge",
        label: <Link href="/ai/knowledge">企业知识</Link>,
      },
      {
        key: "/ai/knowledge/search",
        label: <Link href="/ai/knowledge/search">企业搜索</Link>,
      },
      {
        key: "/ai/knowledge/external",
        label: <Link href="/ai/knowledge/external">外部参考</Link>,
      },
      {
        key: "/ai/experiments",
        label: <Link href="/ai/experiments">训练评测</Link>,
      },
      {
        key: "/ai/releases",
        label: <Link href="/ai/releases">模型发布</Link>,
      },
      {
        key: "/ai/enterprise-assets",
        label: <Link href="/ai/enterprise-assets">企业资产</Link>,
      },
      {
        key: "/ai/prompts",
        label: <Link href="/ai/prompts">Prompt 治理</Link>,
      },
      {
        key: "/ai/memories",
        label: <Link href="/ai/memories">Memory 治理</Link>,
      },
    ],
  },
  {
    key: "collaborative-intelligence",
    label: "协作智能",
    children: [
      {
        key: "/maintenance-planning",
        label: <Link href="/maintenance-planning">多 Agent 会审</Link>,
      },
      {
        key: "/device-families",
        label: <Link href="/device-families">设备族准入</Link>,
      },
    ],
  },
  {
    key: "platform-governance",
    label: "平台治理",
    children: [
      { key: "/ops", label: <Link href="/ops">运行运维</Link> },
      { key: "/ops/gpu", label: <Link href="/ops/gpu">GPU 运维</Link> },
      { key: "/ops/cost", label: <Link href="/ops/cost">成本治理</Link> },
      {
        key: "/ops/traces",
        label: <Link href="/ops/traces">链路观测</Link>,
      },
      { key: "/ops/tools", label: <Link href="/ops/tools">工具治理</Link> },
      {
        key: "/security",
        label: <Link href="/security">安全审计</Link>,
      },
      { key: "/tenant", label: <Link href="/tenant">租户治理</Link> },
    ],
  },
];

const navigationPaths = [
  "/workspace",
  "/incidents",
  "/ai/datasets",
  "/ai/knowledge/search",
  "/ai/knowledge/external",
  "/ai/knowledge",
  "/ai/experiments",
  "/ai/releases",
  "/ai/enterprise-assets",
  "/ai/prompts",
  "/ai/memories",
  "/maintenance-planning",
  "/device-families",
  "/ops/gpu",
  "/ops/cost",
  "/ops/traces",
  "/ops/tools",
  "/ops",
  "/security",
  "/tenant",
] as const;

function selectedNavigationPath(pathname: string) {
  return (
    navigationPaths.find(
      (path) => pathname === path || pathname.startsWith(`${path}/`),
    ) ?? "/workspace"
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <Layout className="app-shell">
      <Header className="app-header">
        <Typography.Text className="app-brand">
          <span className="app-brand-full">
            Multimodal Operations Agent
          </span>
          <span className="app-brand-short">Operations Agent</span>
        </Typography.Text>
        <Menu
          aria-label="主导航"
          className="app-navigation"
          items={navigationItems}
          mode="horizontal"
          overflowedIndicator="更多"
          selectedKeys={[selectedNavigationPath(pathname)]}
          theme="dark"
          triggerSubMenuAction="click"
        />
        <Button
          aria-label="退出当前企业账号"
          className="app-signout"
          type="text"
          onClick={() => void signOut({ callbackUrl: "/login" })}
        >
          退出登录
        </Button>
      </Header>
      <Content className="app-content">{children}</Content>
    </Layout>
  );
}
