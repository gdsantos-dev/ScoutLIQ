import { useCallback, useEffect, useState } from "react";
import type { Lead, RadarTerritory, RadarViewport } from "../types";
import { api } from "../api";
import OpenOpportunityMap from "./OpenOpportunityMap";

type MapConfig = {
  provider: "maptiler" | "open";
  api_key: string;
  style_id: string;
};

export default function OpportunityMap({
  leads,
  onSelect,
  selectedId,
  reduced = false,
  focusCity,
  territory,
  onTerritoryChange,
  onViewportChange,
}: {
  leads: Lead[];
  onSelect: (lead: Lead) => void;
  selectedId?: string;
  reduced?: boolean;
  focusCity?: string;
  territory?: RadarTerritory | null;
  onTerritoryChange?: (territory: RadarTerritory | null) => void;
  onViewportChange?: (viewport: RadarViewport) => void;
}) {
  const [config, setConfig] = useState<MapConfig | null>(null);
  const [mapTilerFailed, setMapTilerFailed] = useState(false);

  useEffect(() => {
    let active = true;
    void api<MapConfig>("/radar/map-config")
      .then((value) => {
        if (active) setConfig(value);
      })
      .catch(() => {
        if (active)
          setConfig({ provider: "open", api_key: "", style_id: "" });
      });
    return () => {
      active = false;
    };
  }, []);

  const useFallback = useCallback(() => setMapTilerFailed(true), []);

  if (!config) return <div className="skeleton map-skeleton" />;

  const useMapTiler =
    config.provider === "maptiler" && config.api_key && !mapTilerFailed;

  return (
    <OpenOpportunityMap
      leads={leads}
      onSelect={onSelect}
      selectedId={selectedId}
      reduced={reduced}
      mapTilerApiKey={useMapTiler ? config.api_key : undefined}
      mapTilerStyleId={useMapTiler ? config.style_id : undefined}
      onMapTilerUnavailable={useMapTiler ? useFallback : undefined}
      focusCity={focusCity}
      territory={territory}
      onTerritoryChange={onTerritoryChange}
      onViewportChange={onViewportChange}
    />
  );
}
