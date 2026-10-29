import { tr } from "../i18n";
import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import {
  LocateFixed,
  Minus,
  Plus,
  Maximize,
  MapPin,
  MousePointer2,
  Check,
  X,
} from "lucide-react";
import type { Lead, RadarTerritory, RadarViewport } from "../types";
import { stageLabel } from "../types";

maplibregl.setWorkerUrl(workerUrl);
maplibregl.setWorkerCount(1);

function openStreetMapStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      osm: {
        type: "raster",
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        tileSize: 256,
        attribution:
          '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
      },
    },
    layers: [
      {
        id: "base",
        type: "raster",
        source: "osm",
        paint: { "raster-saturation": -1 },
      },
    ],
  };
}

function mapTilerStyleUrl(apiKey: string, styleId: string) {
  const safeStyle = styleId.trim() || "dataviz-v4-dark";
  return `https://api.maptiler.com/maps/${encodeURIComponent(safeStyle)}/style.json?key=${encodeURIComponent(apiKey)}`;
}

function normalizePlace(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR")
    .trim();
}

function focusLeads(leads: Lead[], focusCity?: string) {
  if (leads.length <= 1) return leads;

  const preferred = normalizePlace(focusCity ?? "");
  if (preferred) {
    const cityMatches = leads.filter(
      (lead) => normalizePlace(lead.city) === preferred,
    );
    if (cityMatches.length) return cityMatches;
  }

  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLng = Infinity;
  let maxLng = -Infinity;
  for (const lead of leads) {
    minLat = Math.min(minLat, lead.latitude);
    maxLat = Math.max(maxLat, lead.latitude);
    minLng = Math.min(minLng, lead.longitude);
    maxLng = Math.max(maxLng, lead.longitude);
  }

  // A Radar is a local discovery tool. When the local database contains
  // records from distant cities, fitting every point makes the map jump to a
  // country/continent view. Keep all points only when they form one region.
  if (maxLat - minLat <= 1.35 && maxLng - minLng <= 1.35) return leads;

  const groups = new Map<string, Lead[]>();
  for (const lead of leads) {
    const key =
      normalizePlace(lead.city) ||
      `${lead.latitude.toFixed(2)}:${lead.longitude.toFixed(2)}`;
    const group = groups.get(key) ?? [];
    group.push(lead);
    groups.set(key, group);
  }
  const dominant = [...groups.values()].sort((a, b) => b.length - a.length)[0];
  return dominant?.length ? dominant : [leads[0]];
}

function viewportRadiusKm(
  center: maplibregl.LngLat,
  northEast: maplibregl.LngLat,
) {
  const radius = 6371.0088;
  const lat1 = (center.lat * Math.PI) / 180;
  const lat2 = (northEast.lat * Math.PI) / 180;
  const dlat = lat2 - lat1;
  const dlng = ((northEast.lng - center.lng) * Math.PI) / 180;
  const h =
    Math.sin(dlat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlng / 2) ** 2;
  return radius * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
}

export default function OpenOpportunityMap({
  leads,
  onSelect,
  selectedId,
  reduced = false,
  mapTilerApiKey,
  mapTilerStyleId = "dataviz-v4-dark",
  onMapTilerUnavailable,
  focusCity,
  territory,
  onTerritoryChange,
  onViewportChange,
}: {
  leads: Lead[];
  onSelect: (lead: Lead) => void;
  selectedId?: string;
  reduced?: boolean;
  mapTilerApiKey?: string;
  mapTilerStyleId?: string;
  onMapTilerUnavailable?: () => void;
  focusCity?: string;
  territory?: RadarTerritory | null;
  onTerritoryChange?: (territory: RadarTerritory | null) => void;
  onViewportChange?: (viewport: RadarViewport) => void;
}) {
  const container = useRef<HTMLDivElement>(null),
    map = useRef<maplibregl.Map | null>(null),
    callback = useRef(onSelect);
  const markers = useRef<maplibregl.Marker[]>([]),
    lastFitKey = useRef("");
  const territoryCallback = useRef(onTerritoryChange);
  const viewportCallback = useRef(onViewportChange);
  const drawingRef = useRef(false);
  const draftRef = useRef<[number, number][]>(territory?.points ?? []);
  const [error, setError] = useState(""),
    [ready, setReady] = useState(false),
    [drawing, setDrawing] = useState(false),
    [draftPoints, setDraftPoints] = useState<[number, number][]>(
      territory?.points ?? [],
    );
  callback.current = onSelect;
  territoryCallback.current = onTerritoryChange;
  viewportCallback.current = onViewportChange;
  drawingRef.current = drawing;
  draftRef.current = draftPoints;
  const isMapTiler = Boolean(mapTilerApiKey);

  useEffect(() => {
    if (drawing) return;
    const next = territory?.points ?? [];
    setDraftPoints(next);
    draftRef.current = next;
  }, [territory, drawing]);

  const fit = () => {
    if (!map.current || !leads.length) return;
    const compact = map.current.getContainer().clientWidth <= 760;
    const padding = compact
      ? { top: 120, right: 30, bottom: 220, left: 30 }
      : { top: 100, right: 100, bottom: 60, left: 410 };
    const targets = focusLeads(leads, focusCity);
    if (targets.length === 1) {
      map.current.easeTo({
        center: [targets[0].longitude, targets[0].latitude],
        zoom: 13.2,
        padding,
        duration: reduced ? 0 : 420,
      });
      return;
    }
    const bounds = new maplibregl.LngLatBounds();
    targets.forEach((lead) => bounds.extend([lead.longitude, lead.latitude]));
    map.current.fitBounds(bounds, {
      padding,
      maxZoom: 13.8,
      duration: reduced ? 0 : 500,
    });
  };

  useEffect(() => {
    if (!container.current) return;
    let m: maplibregl.Map;
    let loaded = false;
    let fallbackSent = false;
    try {
      m = new maplibregl.Map({
        container: container.current,
        center: [-34.9, -8.055],
        zoom: 12.4,
        attributionControl: false,
        style: mapTilerApiKey
          ? mapTilerStyleUrl(mapTilerApiKey, mapTilerStyleId)
          : openStreetMapStyle(),
        maxZoom: 18,
        minZoom: 3,
        scrollZoom: false,
        pitchWithRotate: false,
        dragRotate: false,
      });
      map.current = m;
      // Normal page scrolling must never zoom the map. Zoom stays explicit via
      // the map controls, which prevents the viewport from flying out to a
      // country/continent view while the user scrolls the page.
      m.scrollZoom.disable();
      m.touchZoomRotate.disableRotation();
      const startupTimer = window.setTimeout(() => {
        if (
          mapTilerApiKey &&
          !loaded &&
          !fallbackSent &&
          onMapTilerUnavailable
        ) {
          fallbackSent = true;
          onMapTilerUnavailable();
        }
      }, 4000);
      m.addControl(
        new maplibregl.AttributionControl({ compact: true }),
        "bottom-right",
      );
      const emitViewport = () => {
        const bounds = m.getBounds();
        const center = m.getCenter();
        const radiusKm = viewportRadiusKm(center, bounds.getNorthEast());
        viewportCallback.current?.({
          west: bounds.getWest(),
          south: bounds.getSouth(),
          east: bounds.getEast(),
          north: bounds.getNorth(),
          center_lat: center.lat,
          center_lng: center.lng,
          radius_km: radiusKm,
        });
      };
      m.on("load", () => {
        loaded = true;
        window.clearTimeout(startupTimer);
        m.resize();
        window.requestAnimationFrame(() => m.resize());
        window.setTimeout(() => m.resize(), 120);
        setReady(true);
        setError("");
        emitViewport();
      });
      m.on("click", (event) => {
        if (!drawingRef.current) return;
        const next = [
          ...draftRef.current,
          [event.lngLat.lng, event.lngLat.lat] as [number, number],
        ].slice(0, 32);
        draftRef.current = next;
        setDraftPoints(next);
      });
      m.on("moveend", emitViewport);
      m.on("error", () => {
        if (
          mapTilerApiKey &&
          !loaded &&
          !fallbackSent &&
          onMapTilerUnavailable
        ) {
          fallbackSent = true;
          onMapTilerUnavailable();
          return;
        }
        if (loaded) {
          setError(
            "Alguns elementos do mapa não puderam ser carregados. As oportunidades continuam disponíveis.",
          );
        }
      });
      const observer = new ResizeObserver(() => m.resize());
      observer.observe(container.current);
      return () => {
        window.clearTimeout(startupTimer);
        observer.disconnect();
        markers.current.forEach((marker) => marker.remove());
        markers.current = [];
        m.remove();
        map.current = null;
        lastFitKey.current = "";
      };
    } catch {
      if (mapTilerApiKey && onMapTilerUnavailable) {
        onMapTilerUnavailable();
        return;
      }
      setError(
        "Seu navegador não pôde iniciar o mapa. Use a lista de oportunidades.",
      );
    }
  }, [mapTilerApiKey, mapTilerStyleId, onMapTilerUnavailable]);

  useEffect(() => {
    if (!map.current || !ready) return;
    const currentMap = map.current;
    const renderMarkers = () => {
      markers.current.forEach((marker) => marker.remove());
      markers.current = [];
      // Cluster only the visible viewport. DOM size scales with screen area,
      // not the database. The complete, keyboard-accessible list stays available.
      const groups = new Map<string, Lead[]>();
      const bounds = currentMap.getBounds();
      leads.forEach((lead) => {
        if (!bounds.contains([lead.longitude, lead.latitude])) return;
        const point = currentMap.project([lead.longitude, lead.latitude]);
        const key =
          currentMap.getZoom() >= 17 || lead.id === selectedId
            ? lead.id
            : `${Math.floor(point.x / 52)}:${Math.floor(point.y / 52)}`;
        const group = groups.get(key) ?? [];
        group.push(lead);
        groups.set(key, group);
      });
      groups.forEach((group) => {
        if (group.length > 1) {
          const element = document.createElement("button");
          element.type = "button";
          element.className = "map-marker map-cluster";
          element.textContent = String(group.length);
          element.setAttribute(
            "aria-label",
            `${group.length} ${tr("empresas nesta área")}. ${tr("Ampliar mapa")}`,
          );
          const lng =
            group.reduce((sum, lead) => sum + lead.longitude, 0) / group.length;
          const lat =
            group.reduce((sum, lead) => sum + lead.latitude, 0) / group.length;
          element.addEventListener("click", (event) => {
            event.stopPropagation();
            currentMap.easeTo({
              center: [lng, lat],
              zoom: Math.min(18, currentMap.getZoom() + 2),
              duration: reduced ? 0 : 300,
            });
          });
          markers.current.push(
            new maplibregl.Marker({ element })
              .setLngLat([lng, lat])
              .addTo(currentMap),
          );
          return;
        }
        const lead = group[0];
        const el = document.createElement("button");
        el.type = "button";
        const symbol =
          lead.stage === "won"
            ? "✓"
            : lead.stage === "lost"
              ? "−"
              : lead.stage === "contacted"
                ? "↗"
                : lead.stage === "replied"
                  ? "↔"
                  : lead.stage === "negotiating"
                    ? "◐"
                    : lead.score.value >= 80
                      ? "✦"
                      : lead.score.value >= 60
                        ? "◆"
                        : "○";
        el.className = `map-marker stage-${lead.stage} ${lead.score.value >= 80 ? "exceptional" : ""} ${lead.id === selectedId ? "selected" : ""}`;
        el.textContent = symbol;
        el.setAttribute(
          "aria-label",
          `${lead.name}, ${tr("Índice")} ${lead.score.value}/100, ${stageLabel(lead.stage)}`,
        );
        el.addEventListener("click", (event) => {
          event.stopPropagation();
          callback.current(lead);
        });
        markers.current.push(
          new maplibregl.Marker({ element: el })
            .setLngLat([lead.longitude, lead.latitude])
            .addTo(map.current!),
        );
      });
    };
    renderMarkers();
    currentMap.on("moveend", renderMarkers);
    currentMap.on("resize", renderMarkers);
    const fitKey = `${normalizePlace(focusCity ?? "")}::${leads
      .map(
        (lead) =>
          `${lead.id}:${lead.latitude.toFixed(5)}:${lead.longitude.toFixed(5)}`,
      )
      .sort()
      .join("|")}`;
    if (leads.length && fitKey !== lastFitKey.current) {
      fit();
      lastFitKey.current = fitKey;
    } else if (!leads.length) {
      lastFitKey.current = "";
    }
    return () => {
      currentMap.off("moveend", renderMarkers);
      currentMap.off("resize", renderMarkers);
    };
  }, [leads, ready, selectedId, focusCity, reduced]);

  useEffect(() => {
    if (!map.current || !ready) return;
    const id = "radar-territory";
    const features: Array<Record<string, unknown>> = [];
    if (draftPoints.length >= 3) {
      features.push({
        type: "Feature",
        properties: { role: "boundary" },
        geometry: {
          type: "Polygon",
          coordinates: [[...draftPoints, draftPoints[0]]],
        },
      });
    } else if (draftPoints.length >= 2) {
      features.push({
        type: "Feature",
        properties: { role: "boundary" },
        geometry: { type: "LineString", coordinates: draftPoints },
      });
    }
    draftPoints.forEach((point, index) => {
      features.push({
        type: "Feature",
        properties: { role: "vertex", index },
        geometry: { type: "Point", coordinates: point },
      });
    });
    const data = { type: "FeatureCollection", features } as any;
    const source = map.current.getSource(id) as
      maplibregl.GeoJSONSource | undefined;
    if (!source) {
      map.current.addSource(id, { type: "geojson", data });
      map.current.addLayer({
        id: `${id}-fill`,
        type: "fill",
        source: id,
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": "#ffffff", "fill-opacity": 0.07 },
      });
      map.current.addLayer({
        id: `${id}-line`,
        type: "line",
        source: id,
        paint: {
          "line-color": "#ffffff",
          "line-width": 1.6,
          "line-opacity": 0.78,
        },
      });
      map.current.addLayer({
        id: `${id}-vertices`,
        type: "circle",
        source: id,
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": 3.5,
          "circle-color": "#d8d8d8",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#111111",
        },
      });
    } else {
      source.setData(data);
    }
  }, [draftPoints, ready]);

  useEffect(() => {
    const lead = leads.find((item) => item.id === selectedId);
    if (lead)
      map.current?.easeTo({
        center: [lead.longitude, lead.latitude],
        zoom: Math.max(map.current.getZoom(), 14),
        duration: reduced ? 0 : 450,
      });
  }, [selectedId, reduced, leads]);

  return (
    <div
      className="map-shell"
      data-ready={ready}
      data-provider={isMapTiler ? "maptiler" : "open"}
    >
      <div
        ref={container}
        className="map-canvas"
        aria-label={tr("Mapa de oportunidades")}
      />
      {error && (
        <div className="map-error" role="status">
          <MapPin size={18} />
          {tr(error)}
          <button
            className="text-link"
            onClick={() => {
              setError("");
              map.current?.triggerRepaint();
            }}
          >
            {tr("Tentar novamente")}
          </button>
        </div>
      )}
      <div className="map-location">
        <MapPin size={15} />
        <span>
          {drawing
            ? `${tr("Desenhando território")} · ${draftPoints.length} ${tr("pontos")}`
            : leads.length
              ? Array.from(new Set(leads.map((lead) => lead.city)))
                  .slice(0, 2)
                  .join(" · ")
              : tr("Explore sua região")}
        </span>
      </div>
      <div className="map-territory-controls">
        {!drawing ? (
          <button
            type="button"
            className={territory?.points?.length ? "active" : ""}
            onClick={() => {
              const seed = territory?.points ?? [];
              setDraftPoints(seed);
              draftRef.current = seed;
              setDrawing(true);
            }}
          >
            <MousePointer2 size={15} />
            {territory?.points?.length
              ? tr("Editar território")
              : tr("Desenhar território")}
          </button>
        ) : (
          <>
            <button
              type="button"
              disabled={draftPoints.length < 3}
              onClick={() => {
                if (draftPoints.length < 3) return;
                territoryCallback.current?.({ points: draftPoints });
                setDrawing(false);
              }}
            >
              <Check size={15} />
              {tr("Concluir área")}
            </button>
            <button
              type="button"
              onClick={() => {
                setDraftPoints([]);
                draftRef.current = [];
                territoryCallback.current?.(null);
                setDrawing(false);
              }}
              aria-label={tr("Limpar território")}
            >
              <X size={15} />
            </button>
          </>
        )}
      </div>
      <div className="map-controls">
        <button
          aria-label={tr("Ampliar mapa")}
          data-tooltip="Ampliar"
          onClick={() => map.current?.zoomIn({ duration: reduced ? 0 : 200 })}
        >
          <Plus size={18} />
        </button>
        <button
          aria-label={tr("Reduzir mapa")}
          data-tooltip="Reduzir"
          onClick={() => map.current?.zoomOut({ duration: reduced ? 0 : 200 })}
        >
          <Minus size={18} />
        </button>
        <button
          aria-label={tr("Centralizar oportunidades")}
          data-tooltip="Centralizar oportunidades"
          onClick={fit}
        >
          <LocateFixed size={18} />
        </button>
        <button
          aria-label={tr("Mapa em tela cheia")}
          data-tooltip="Tela cheia"
          onClick={() => {
            const shell = container.current?.parentElement;
            if (document.fullscreenElement) void document.exitFullscreen();
            else
              void shell
                ?.requestFullscreen()
                .catch(() =>
                  setError("Tela cheia não disponível neste navegador."),
                );
          }}
        >
          <Maximize size={17} />
        </button>
      </div>
      <div className="map-legend">
        <span>
          <i className="legend-diamond" />
          {tr("Oportunidade")}
        </span>
        <span>
          <i className="legend-client">✓</i>
          {tr("Cliente")}
        </span>
      </div>
    </div>
  );
}
