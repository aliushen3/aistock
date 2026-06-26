import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { getSectors, type Sector } from "./api";

interface SectorContextValue {
  sectorId: string;
  setSectorId: (id: string) => void;
  sectors: Sector[];
  reloadSectors: () => void;
}

const SectorContext = createContext<SectorContextValue | null>(null);

const STORAGE_KEY = "aistock.activeSectorId";

export function SectorProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [sectorId, setSectorIdState] = useState<string>(
    () => searchParams.get("sector") || localStorage.getItem(STORAGE_KEY) || ""
  );

  const reloadSectors = () => {
    getSectors().then(setSectors);
  };

  useEffect(() => {
    reloadSectors();
  }, []);

  useEffect(() => {
    if (!sectors.length) return;
    const valid = sectors.some((s) => s.id === sectorId);
    if (!sectorId || !valid) {
      setSectorIdState(sectors[0].id);
    }
  }, [sectors, sectorId]);

  const setSectorId = (id: string) => {
    setSectorIdState(id);
    localStorage.setItem(STORAGE_KEY, id);
    const next = new URLSearchParams(searchParams);
    next.set("sector", id);
    setSearchParams(next, { replace: true });
  };

  useEffect(() => {
    if (!sectorId) return;
    localStorage.setItem(STORAGE_KEY, sectorId);
    if (searchParams.get("sector") !== sectorId) {
      const next = new URLSearchParams(searchParams);
      next.set("sector", sectorId);
      setSearchParams(next, { replace: true });
    }
  }, [sectorId]);

  const value = useMemo(
    () => ({ sectorId, setSectorId, sectors, reloadSectors }),
    [sectorId, sectors]
  );

  return <SectorContext.Provider value={value}>{children}</SectorContext.Provider>;
}

export function useSector(): SectorContextValue {
  const ctx = useContext(SectorContext);
  if (!ctx) {
    throw new Error("useSector 必须在 SectorProvider 内使用");
  }
  return ctx;
}
