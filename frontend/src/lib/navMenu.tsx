import { Link } from "react-router-dom";
import type { ReactNode } from "react";

/** 导航项 — 后续按 role 过滤 key 即可 */
export type NavItemKey =
  | "/"
  | "/knowledge"
  | "/graph"
  | "/research"
  | "/report"
  | "/candidates"
  | "/dashboard"
  | "/audit"
  | "/data-ops";

export interface NavMenuItem {
  key: NavItemKey;
  label: ReactNode;
  /** 预留：允许访问的角色，空表示全员可见 */
  roles?: string[];
  children?: NavMenuItem[];
}

/**
 * 按投研语义组织：工作台 → 产业研究（图谱 + 证据校准）→ 标的论证 → 研究报告 → 组合跟踪。
 * 审计与系统数据为支撑功能。
 */
export const NAV_MENU_ITEMS: NavMenuItem[] = [
  { key: "/", label: <Link to="/">工作台</Link> },
  {
    key: "/research",
    label: "产业研究",
    children: [
      { key: "/graph", label: <Link to="/graph">产业图谱</Link> },
      { key: "/knowledge", label: <Link to="/knowledge">证据与校准</Link> },
    ],
  },
  { key: "/candidates", label: <Link to="/candidates">标的论证</Link> },
  { key: "/report", label: <Link to="/report">研究报告</Link> },
  { key: "/dashboard", label: <Link to="/dashboard">组合跟踪</Link> },
  { key: "/audit", label: <Link to="/audit">审计</Link> },
  {
    key: "/data-ops",
    label: <Link to="/data-ops">系统与数据</Link>,
    roles: ["admin", "data_admin"],
  },
];

/**
 * 按角色过滤导航（当前未接登录，返回全部）。
 */
export function filterNavByRole(items: NavMenuItem[], role?: string | null): NavMenuItem[] {
  if (!role) {
    return items;
  }
  return items
    .filter((item) => {
      if (!item.roles?.length) {
        return true;
      }
      return item.roles.includes(role);
    })
    .map((item) =>
      item.children ? { ...item, children: filterNavByRole(item.children, role) } : item
    );
}
