import type { UserOperator } from "./blockPermissions";

const STORAGE_KEY = "aistock_operator";

export function getStoredOperator(): UserOperator {
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === "fund_manager" || v === "risk" || v === "admin" || v === "data_admin") return v;
  return "analyst";
}

export function setStoredOperator(op: UserOperator) {
  localStorage.setItem(STORAGE_KEY, op);
}
