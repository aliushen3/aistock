import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { type UserOperator, operatorNavRole, canInteract, INTERACTION_REQUIRED_ROLES } from "./blockPermissions";
import { getStoredOperator, setStoredOperator } from "./operatorStorage";
import { getAgentUiPermissions, type UiPermissionsApi } from "./api";

interface UserContextValue {
  operator: UserOperator;
  navRole: string;
  setOperator: (op: UserOperator) => void;
  permissions: UiPermissionsApi | null;
  can: (action: keyof typeof INTERACTION_REQUIRED_ROLES) => boolean;
}

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  const [operator, setOperatorState] = useState<UserOperator>(() => getStoredOperator());
  const [permissions, setPermissions] = useState<UiPermissionsApi | null>(null);

  const setOperator = useCallback((op: UserOperator) => {
    setStoredOperator(op);
    setOperatorState(op);
  }, []);

  useEffect(() => {
    getAgentUiPermissions()
      .then(setPermissions)
      .catch(() => setPermissions(null));
  }, [operator]);

  const navRole = operatorNavRole(operator);

  const can = useCallback(
    (action: keyof typeof INTERACTION_REQUIRED_ROLES) => {
      if (permissions?.interactions?.[action] !== undefined) {
        return permissions.interactions[action];
      }
      return canInteract(operator, action);
    },
    [operator, permissions]
  );

  const value = useMemo(
    () => ({ operator, navRole, setOperator, permissions, can }),
    [operator, navRole, setOperator, permissions, can]
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}

export type { UserOperator };
