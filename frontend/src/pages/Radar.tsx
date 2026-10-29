import type { RadarViewState } from "../types";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import type {
  FormEvent,
  KeyboardEvent,
  PointerEvent as ReactPointerEvent,
} from "react";
import {
  Search,
  Plus,
  SlidersHorizontal,
  Map as MapIcon,
  List,
  ArrowUpRight,
  ChevronUp,
  ChevronDown,
  MoreHorizontal,
  LoaderCircle,
  MapPin,
  Store,
  Check,
  BookmarkPlus,
  Trash2,
  Sparkles,
  Bell,
  BellOff,
} from "lucide-react";
import type {
  Lead,
  RadarLocation,
  RadarSearchInput,
  RadarSearchResponse,
  RadarSavedSearch,
  RadarSavedQuery,
  RadarNaturalPlan,
  RadarOpportunityKey,
  ResearchBatch,
  ResearchBatchResponse,
  RadarViewport,
  RadarTerritory,
  SimilarLeadsResponse,
} from "../types";
import { activeLocale, inputDate, stageLabel } from "../types";
import { tr } from "../i18n";
import { api } from "../api";
import { Empty, PageHead, Modal } from "../components/UI";
import type { CommercialIntent, SearchArea } from "../searchTypes";
import {
  SearchDialog,
  SearchProgress,
  SearchHistory,
} from "../components/UnifiedSearch";
import { SmartSelect } from "../components/Primitives";
import { getOpportunityPriority, getOpportunityBrief } from "../opportunity";
import CommercialQueue from "../components/CommercialQueue";
const OpportunityMap = lazy(() => import("../components/OpportunityMap"));

const normalizeSearch = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR")
    .trim();

function weekStartDate(today: string) {
  const [year, month, day] = today.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  const daysSinceMonday = (date.getUTCDay() + 6) % 7;
  date.setUTCDate(date.getUTCDate() - daysSinceMonday);
  return date.toISOString().slice(0, 10);
}

function timestampDate(timestamp: number, timezone: string) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(timestamp * 1000));
}

const RADAR_OPPORTUNITY_OPTIONS: Array<{
  value: RadarOpportunityKey | "";
  label: string;
}> = [
  { value: "", label: "Qualquer oportunidade" },
  { value: "no_site", label: "Sem site próprio" },
  { value: "website_issues", label: "Site com problemas" },
  { value: "booking_gap", label: "Sem agendamento ou reserva" },
  { value: "menu_gap", label: "Sem cardápio digital" },
  { value: "catalog_gap", label: "Sem catálogo" },
  { value: "ecommerce_gap", label: "Sem e-commerce" },
  { value: "weak_digital", label: "Presença digital fraca" },
  { value: "competitive_gap", label: "Abaixo dos concorrentes locais" },
];

const RADAR_SERVICE_OPTIONS = [
  { value: "", label: "Qualquer serviço" },
  { value: "site_institucional", label: "Site institucional" },
  { value: "landing_page", label: "Landing page" },
  { value: "redesign", label: "Redesign" },
  { value: "sistema_agendamento", label: "Agendamento" },
  { value: "sistema_reservas", label: "Reservas" },
  { value: "catalogo", label: "Catálogo" },
  { value: "cardapio_digital", label: "Cardápio digital" },
  { value: "ecommerce", label: "E-commerce" },
  { value: "seo_local", label: "SEO local" },
  { value: "otimizacao", label: "Otimização" },
  { value: "site_sob_medida", label: "Projeto sob medida" },
];

function matchesProblem(lead: Lead, key: RadarOpportunityKey) {
  const diagnosis = lead.score.diagnosis || [];
  const keys = new Set(diagnosis.map((item) => item.key));
  if (key === "no_site") {
    return (
      lead.website_status === "none" ||
      keys.has("no_website") ||
      keys.has("aggregator_website")
    );
  }
  if (key === "website_issues") {
    return (
      lead.website_status === "poor" ||
      diagnosis.some((item) =>
        [
          "mobile",
          "performance",
          "technical",
          "conversion",
          "accessibility",
          "discoverability",
        ].includes(item.area),
      )
    );
  }
  if (key === "booking_gap") return keys.has("niche_booking");
  if (key === "menu_gap")
    return keys.has("niche_catalog_or_menu") && lead.score.niche.key === "food";
  if (key === "catalog_gap")
    return keys.has("niche_catalog_or_menu") && lead.score.niche.key !== "food";
  if (key === "ecommerce_gap") return keys.has("niche_ecommerce");
  if (key === "weak_digital") {
    return (
      lead.website_status === "none" ||
      lead.website_status === "poor" ||
      lead.score.dimensions.digital_need.value >= 28
    );
  }
  if (key === "competitive_gap")
    return Boolean(lead.score.competitive?.site_gap);
  return true;
}

function matchesSavedQuery(lead: Lead, query: RadarSavedQuery) {
  if (
    query.problem_keys?.length &&
    !query.problem_keys.every((key) => matchesProblem(lead, key))
  )
    return false;
  if ((query.min_score || 0) > lead.score.value) return false;
  if (
    (query.min_rating || 0) > 0 &&
    (lead.rating === null || lead.rating < query.min_rating)
  )
    return false;
  if (
    (query.min_reviews || 0) > 0 &&
    (lead.reviews === null || lead.reviews < query.min_reviews)
  )
    return false;
  if ((query.min_confidence || 0) > lead.score.confidence.value) return false;
  if ((query.min_timing || 0) > lead.score.timing.value) return false;
  if (
    query.contact_filter === "any" &&
    !(lead.phone || lead.whatsapp || lead.instagram)
  )
    return false;
  if (query.contact_filter === "phone" && !lead.phone) return false;
  if (query.contact_filter === "whatsapp" && !lead.whatsapp) return false;
  if (query.contact_filter === "instagram" && !lead.instagram) return false;
  if (query.service_key) {
    const fit = lead.score.service_scores.find(
      (item) => item.key === query.service_key,
    );
    if (!fit || fit.value < (query.min_service_score || 60)) return false;
  }
  return true;
}

type PersistedRadarSearch = {
  version: 1;
  form: {
    location: string;
    niche: string;
    radius: string;
    scope?: RadarSearchInput["scope"];
    selectedLocation: RadarLocation | null;
  };
  result: {
    ids: string[];
    provider: string;
    location: string;
    count: number;
    created: number;
    complete?: boolean;
    scanned?: number;
    result_limit?: number | null;
    scope?: RadarSearchResponse["scope"];
    workspace_limit_reached?: boolean;
    query?: RadarSearchInput;
  };
};

function readPersistedRadarSearch(
  storageKey: string,
): PersistedRadarSearch | null {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PersistedRadarSearch>;
    if (
      parsed.version !== 1 ||
      !parsed.form ||
      !parsed.result ||
      !Array.isArray(parsed.result.ids) ||
      typeof parsed.form.location !== "string" ||
      typeof parsed.form.niche !== "string" ||
      typeof parsed.form.radius !== "string" ||
      typeof parsed.result.provider !== "string" ||
      typeof parsed.result.location !== "string" ||
      typeof parsed.result.count !== "number" ||
      typeof parsed.result.created !== "number"
    ) {
      return null;
    }
    return parsed as PersistedRadarSearch;
  } catch {
    return null;
  }
}

function persistRadarSearch(storageKey: string, value: PersistedRadarSearch) {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(value));
  } catch {
    // The Radar still works if browser storage is unavailable.
  }
}

function locationRank(item: RadarLocation, query: string) {
  const name = normalizeSearch(item.name);
  const state = normalizeSearch(item.state);
  const needle = normalizeSearch(query);
  if (name.startsWith(needle)) return 0;
  if (name.split(/\s+/).some((part) => part.startsWith(needle))) return 1;
  if (name.includes(needle)) return 2;
  if (`${state} ${item.uf.toLowerCase()}`.includes(needle)) return 3;
  return 99;
}

export default function Radar({
  surface = "radar",
  intent,
  onIntentConsumed,
  searchId,
  onSearchConsumed,
  onOpenSearch,
  selectedId,
  leads,
  onSelect,
  onAdd,
  onDiscover,
  onLoadLocations,
  onLeadUpdated,
  onSaveOpportunity,
  busy,
  reduced,
  storageKey,
  timezone,
  remembered,
  onRemember,
}: {
  surface?: "radar" | "opportunities" | "monitors";
  intent?: string;
  onIntentConsumed?: () => void;
  searchId?: string;
  onSearchConsumed?: () => void;
  onOpenSearch: (id: string) => void;
  selectedId?: string;
  leads: Lead[];
  onSelect: (l: Lead) => void;
  onAdd: () => void;
  onDiscover: (input: RadarSearchInput) => Promise<RadarSearchResponse>;
  onLoadLocations: (
    query: string,
    country?: string,
  ) => Promise<RadarLocation[]>;
  onLeadUpdated: (lead: Lead) => void;
  onSaveOpportunity: (lead: Lead) => void;
  busy: boolean;
  reduced: boolean;
  storageKey: string;
  timezone: string;
  remembered?: RadarViewState;
  onRemember: (state: RadarViewState) => void;
}) {
  const [commercialMode, setCommercialMode] = useState(() => {
    try { return sessionStorage.getItem(storageKey+':commercial-mode') === 'true'; } catch { return false; }
  });
  function changeCommercialMode(value:boolean) {
    setCommercialMode(value);
    try { sessionStorage.setItem(storageKey+':commercial-mode',String(value)); } catch { /* Optional persistence. */ }
  }
  const [searchOpen, setSearchOpen] = useState(false);
  const [savedOpen, setSavedOpen] = useState(false);
  const [mobileSheet, setMobileSheet] = useState<"peek" | "mid" | "full">(
    "peek",
  );
  const sheetDragStart = useRef<number | null>(null);
  const [visibleLimit, setVisibleLimit] = useState(
    remembered?.visibleLimit ?? 60,
  );
  const [naturalOpen, setNaturalOpen] = useState(false);
  const [restoredSearch] = useState(() => readPersistedRadarSearch(storageKey));
  const [query, setQuery] = useState(remembered?.query ?? ""),
    [category, setCategory] = useState(remembered?.category ?? ""),
    [city, setCity] = useState(remembered?.city ?? ""),
    [country, setCountry] = useState(remembered?.country ?? ""),
    [site, setSite] = useState(remembered?.site ?? ""),
    [minScore, setMinScore] = useState(remembered?.minScore ?? "0"),
    [minRating, setMinRating] = useState(remembered?.minRating ?? "0"),
    [minReviews, setMinReviews] = useState(remembered?.minReviews ?? "0"),
    [contactFilter, setContactFilter] = useState(
      remembered?.contactFilter ?? "",
    ),
    [pipelineFilter, setPipelineFilter] = useState(
      remembered?.pipelineFilter ?? "",
    ),
    [opportunityFilter, setOpportunityFilter] = useState<
      RadarOpportunityKey | ""
    >(remembered?.opportunityFilter ?? ""),
    [extraProblemKeys, setExtraProblemKeys] = useState<RadarOpportunityKey[]>(
      remembered?.extraProblemKeys ?? [],
    ),
    [minConfidence, setMinConfidence] = useState(
      remembered?.minConfidence ?? "0",
    ),
    [minTiming, setMinTiming] = useState(remembered?.minTiming ?? "0"),
    [serviceFilter, setServiceFilter] = useState(
      remembered?.serviceFilter ?? "",
    ),
    [smartList, setSmartList] = useState(
      remembered?.smartList ?? (surface === "monitors" ? "watchlist" : ""),
    ),
    [sortBy, setSortBy] = useState(remembered?.sortBy ?? "score"),
    [filters, setFilters] = useState(false),
    [mode, setMode] = useState(remembered?.mode ?? "list"),
    [location, setLocation] = useState(restoredSearch?.form.location ?? ""),
    [selectedLocation, setSelectedLocation] = useState<RadarLocation | null>(
      restoredSearch?.form.selectedLocation ?? null,
    ),
    [locations, setLocations] = useState<RadarLocation[]>([]),
    [locationCatalogFailed, setLocationCatalogFailed] = useState(false),
    [suggestionsOpen, setSuggestionsOpen] = useState(false),
    [activeSuggestion, setActiveSuggestion] = useState(0),
    [niche, setNiche] = useState(restoredSearch?.form.niche ?? ""),
    [scopeMode, setScopeMode] = useState<"region" | "radius">(
      restoredSearch?.form.scope === "region" ? "region" : "radius",
    ),
    [radius, setRadius] = useState(restoredSearch?.form.radius ?? "10"),
    [searching, setSearching] = useState(false),
    [searchError, setSearchError] = useState(""),
    [searchIds, setSearchIds] = useState<string[] | null>(
      surface === "radar" ? (restoredSearch?.result.ids ?? null) : null,
    ),
    [searchMeta, setSearchMeta] = useState<RadarSearchResponse | null>(
      restoredSearch
        ? {
            provider: restoredSearch.result.provider,
            location: restoredSearch.result.location,
            count: restoredSearch.result.count,
            created: restoredSearch.result.created,
            complete: restoredSearch.result.complete,
            scanned: restoredSearch.result.scanned,
            result_limit: restoredSearch.result.result_limit,
            scope: restoredSearch.result.scope,
            workspace_limit_reached:
              restoredSearch.result.workspace_limit_reached,
            results: [],
          }
        : null,
    );
  const rememberRef = useRef(onRemember);
  rememberRef.current = onRemember;
  const viewRef = useRef<RadarViewState | null>(null);
  viewRef.current = {
    query,
    mode,
    sortBy,
    category,
    city,
    country,
    site,
    minScore,
    minRating,
    minReviews,
    contactFilter,
    pipelineFilter,
    minConfidence,
    minTiming,
    serviceFilter,
    opportunityFilter,
    extraProblemKeys,
    smartList,
    visibleLimit,
    scrollY: 0,
  };
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      if (remembered) window.scrollTo(0, remembered.scrollY);
    });
    return () => {
      cancelAnimationFrame(frame);
      if (viewRef.current)
        rememberRef.current({ ...viewRef.current, scrollY: window.scrollY });
    };
  }, []);
  const [launchOpen, setLaunchOpen] = useState(false);
  const [launchText, setLaunchText] = useState("");
  const [launchArea, setLaunchArea] = useState<SearchArea | undefined>();
  const [activeSearch, setActiveSearch] = useState<string | null>(() => {
    try {
      return localStorage.getItem(storageKey + ":active-search");
    } catch {
      return null;
    }
  });
  const [savedIntent, setSavedIntent] = useState<CommercialIntent | undefined>(
    undefined,
  );
  const [savedSearches, setSavedSearches] = useState<RadarSavedSearch[]>([]);
  const [savedSearchBusy, setSavedSearchBusy] = useState(false);
  const [monitorBusy, setMonitorBusy] = useState(false);
  const monitorRef = useRef(new Set<string>());
  const savedLaunchKeys = useRef(new Map<string, string>());
  const monitorRunsRef = useRef(0);
  const [savedSearchError, setSavedSearchError] = useState("");
  const [viewport, setViewport] = useState<RadarViewport | null>(null);
  const [territory, setTerritory] = useState<RadarTerritory | null>(null);
  const [similarBusyId, setSimilarBusyId] = useState("");
  const [similarSource, setSimilarSource] = useState("");
  const [similarityById, setSimilarityById] = useState<Record<string, number>>(
    {},
  );
  const [saveSearchOpen, setSaveSearchOpen] = useState(false);
  const [saveSearchName, setSaveSearchName] = useState("");
  const [naturalText, setNaturalText] = useState("");
  const [naturalPlan, setNaturalPlan] = useState<RadarNaturalPlan | null>(null);
  const [naturalBusy, setNaturalBusy] = useState(false);
  const [naturalError, setNaturalError] = useState("");
  const [lastSearchInput, setLastSearchInput] =
    useState<RadarSearchInput | null>(restoredSearch?.result.query ?? null);
  const [agentBatch, setAgentBatch] = useState<ResearchBatch | null>(null),
    [agentPaused, setAgentPaused] = useState(false),
    [agentBusy, setAgentBusy] = useState(false),
    [agentError, setAgentError] = useState("");
  const agentStepRef = useRef(false);

  useEffect(() => {
    let alive = true;
    const refresh = () =>
      void api<RadarSavedSearch[]>("/radar/saved-searches")
        .then((items) => {
          if (alive) setSavedSearches(items);
        })
        .catch((error) => {
          if (alive) setSavedSearchError((error as Error).message);
        });
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => {
      window.clearInterval(timer);
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    void api<ResearchBatchResponse>("/research/batches/active")
      .then((result) => {
        if (!alive) return;
        setAgentBatch(result.batch);
        setAgentPaused(result.batch?.status === "paused");
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (selectedLocation || normalizeSearch(location).length < 2) {
      setLocations([]);
      return;
    }
    let active = true;
    const timer = window.setTimeout(() => {
      void onLoadLocations(location)
        .then((items) => {
          if (!active) return;
          setLocations(items);
          setLocationCatalogFailed(false);
          setSuggestionsOpen(items.length > 0);
        })
        .catch(() => {
          if (active) setLocationCatalogFailed(true);
        });
    }, 220);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [location, selectedLocation, onLoadLocations]);

  const locationSuggestions = useMemo(() => {
    if (selectedLocation || normalizeSearch(location).length < 2) return [];
    return locations
      .map((item) => ({ item, rank: locationRank(item, location) }))
      .sort(
        (a, b) =>
          a.rank - b.rank ||
          a.item.name.length - b.item.name.length ||
          a.item.name.localeCompare(b.item.name, activeLocale()),
      )
      .slice(0, 8)
      .map(({ item }) => item);
  }, [location, locations, selectedLocation]);

  const baseLeads = useMemo(() => {
    if (searchIds === null)
      return surface === "opportunities"
        ? leads.filter((lead) => lead.stage !== "won" && lead.stage !== "lost")
        : leads;
    const byId = new Map(leads.map((lead) => [lead.id, lead]));
    return searchIds
      .map((id) => byId.get(id))
      .filter((lead): lead is Lead => Boolean(lead));
  }, [leads, searchIds, surface]);

  const visible = useMemo(() => {
    const filtered = baseLeads.filter((l) => {
      const normalizedQuery = normalizeSearch(query);
      const matchesQuery =
        !normalizedQuery ||
        normalizeSearch(
          `${l.name} ${l.category} ${l.city} ${l.address}`,
        ).includes(normalizedQuery);
      const matchesContact =
        !contactFilter ||
        (contactFilter === "any" &&
          Boolean(l.phone || l.whatsapp || l.instagram)) ||
        (contactFilter === "phone" && Boolean(l.phone)) ||
        (contactFilter === "whatsapp" && Boolean(l.whatsapp)) ||
        (contactFilter === "instagram" && Boolean(l.instagram));
      const matchesPipeline =
        !pipelineFilter ||
        (pipelineFilter === "radar" && !l.in_pipeline) ||
        (pipelineFilter === "pipeline" && l.in_pipeline);
      const activeProblems = [opportunityFilter, ...extraProblemKeys].filter(
        Boolean,
      ) as RadarOpportunityKey[];
      const matchesOpportunity =
        !activeProblems.length ||
        activeProblems.every((key) => matchesProblem(l, key));
      const matchesConfidence =
        l.score.confidence.value >= Number(minConfidence);
      const matchesTiming = l.score.timing.value >= Number(minTiming);
      const serviceFit = serviceFilter
        ? l.score.service_scores.find((item) => item.key === serviceFilter)
        : null;
      const matchesService =
        !serviceFilter || Boolean(serviceFit && serviceFit.value >= 60);
      const today = inputDate(timezone);
      const weekStart = weekStartDate(today);
      const weekAgo = Math.floor(Date.now() / 1000) - 7 * 24 * 60 * 60;
      const contactBaseline =
        l.last_contact_at || l.pipeline_added_at || l.created_at;
      const activePipeline =
        l.in_pipeline && !["won", "lost"].includes(l.stage);
      const matchesSmart =
        !smartList ||
        (smartList === "high" && l.score.value >= 70) ||
        (smartList === "no_site" && l.website_status === "none") ||
        (smartList === "radar" && !l.in_pipeline) ||
        (smartList === "pipeline" && activePipeline) ||
        (smartList === "action_today" &&
          activePipeline &&
          l.next_action_on === today) ||
        (smartList === "overdue" &&
          activePipeline &&
          Boolean(l.next_action_on) &&
          (l.next_action_on as string) < today) ||
        (smartList === "stale" &&
          activePipeline &&
          contactBaseline < weekAgo) ||
        (smartList === "new_week" &&
          timestampDate(l.created_at, timezone) >= weekStart) ||
        (smartList === "watchlist" && l.watchlisted);

      return (
        matchesQuery &&
        (!category || l.category === category) &&
        (!city || l.city === city) &&
        (!country || l.country === country) &&
        (!site || l.website_status === site) &&
        l.score.value >= Number(minScore) &&
        (Number(minRating) <= 0 ||
          (l.rating !== null && l.rating >= Number(minRating))) &&
        (Number(minReviews) <= 0 ||
          (l.reviews !== null && l.reviews >= Number(minReviews))) &&
        matchesContact &&
        matchesPipeline &&
        matchesOpportunity &&
        matchesConfidence &&
        matchesTiming &&
        matchesService &&
        matchesSmart
      );
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === "reviews") return (b.reviews ?? -1) - (a.reviews ?? -1);
      if (sortBy === "rating") return (b.rating ?? -1) - (a.rating ?? -1);
      if (sortBy === "name")
        return a.name.localeCompare(b.name, activeLocale());
      return b.score.value - a.score.value;
    });
  }, [
    baseLeads,
    query,
    category,
    city,
    country,
    site,
    minScore,
    minRating,
    minReviews,
    contactFilter,
    pipelineFilter,
    opportunityFilter,
    extraProblemKeys,
    minConfidence,
    minTiming,
    serviceFilter,
    smartList,
    sortBy,
    timezone,
  ]);

  useEffect(() => {
    if (!searchId) return;
    clearResultFilters();
    setSearchMeta(null);
    setSearchIds([]);
    setActiveSearch(searchId);
    try {
      localStorage.setItem(storageKey + ":active-search", searchId);
    } catch {
      /* Optional persistence. */
    }
    onSearchConsumed?.();
  }, [searchId, onSearchConsumed, storageKey]);

  useEffect(() => {
    if (intent) {
      setLaunchText(intent);
      setLaunchOpen(true);
      onIntentConsumed?.();
    }
  }, [intent, onIntentConsumed]);
  useEffect(() => {
    const shortcut = (event: globalThis.KeyboardEvent) => {
      if (
        event.key === "/" &&
        !event.ctrlKey &&
        !event.metaKey &&
        !document.querySelector("dialog[open]") &&
        !(
          event.target instanceof HTMLElement &&
          event.target.closest("input,textarea,[contenteditable=true]")
        )
      ) {
        event.preventDefault();
        setLaunchOpen(true);
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  const firstFilterRender = useRef(true);
  useEffect(() => {
    if (firstFilterRender.current) {
      firstFilterRender.current = false;
      return;
    }
    setVisibleLimit(60);
  }, [query, category, city, country, site, smartList, minScore]);
  const activeFilterCount = useMemo(
    () =>
      [
        category,
        city,
        country,
        site,
        minScore !== "0" ? minScore : "",
        minRating !== "0" ? minRating : "",
        minReviews !== "0" ? minReviews : "",
        contactFilter,
        pipelineFilter,
        opportunityFilter || extraProblemKeys.length ? "problems" : "",
        minConfidence !== "0" ? minConfidence : "",
        minTiming !== "0" ? minTiming : "",
        serviceFilter,
        smartList,
      ].filter(Boolean).length,
    [
      category,
      city,
      country,
      site,
      minScore,
      minRating,
      minReviews,
      contactFilter,
      pipelineFilter,
      opportunityFilter,
      extraProblemKeys,
      minConfidence,
      minTiming,
      serviceFilter,
      smartList,
    ],
  );

  function chooseLocation(item: RadarLocation) {
    setSelectedLocation(item);
    setLocation(
      item.formatted ||
        [item.name, item.state_code || item.uf, item.country]
          .filter(Boolean)
          .join(", "),
    );
    setSuggestionsOpen(false);
    setActiveSuggestion(0);
  }

  function locationKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!suggestionsOpen || !locationSuggestions.length) {
      if (event.key === "ArrowDown" && locationSuggestions.length) {
        event.preventDefault();
        setSuggestionsOpen(true);
      }
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveSuggestion((current) =>
        Math.min(current + 1, locationSuggestions.length - 1),
      );
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveSuggestion((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      chooseLocation(locationSuggestions[activeSuggestion]);
    } else if (event.key === "Escape") {
      setSuggestionsOpen(false);
    }
  }

  const [investigationSelection, setInvestigationSelection] = useState<
    string[]
  >([]);
  const [investigationQueue, setInvestigationQueue] = useState<ResearchBatch[]>(
    [],
  );
  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const response = await api<{ batches: ResearchBatch[] }>(
          "/investigation/queue",
        );
        if (!alive) return;
        setInvestigationQueue(response.batches);
      } catch (e) {
        if (alive) setAgentError((e as Error).message);
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);
  async function selectInvestigationBatch(identifier: string) {
    if (!identifier || agentBusy) return;
    setAgentBusy(true);
    try {
      const result = await api<ResearchBatchResponse>(
        `/research/batches/${identifier}`,
      );
      setAgentBatch(result.batch);
      setAgentPaused(result.batch?.status === "paused");
      result.leads?.forEach(onLeadUpdated);
      setAgentError("");
    } catch (error) {
      setAgentError((error as Error).message);
    } finally {
      setAgentBusy(false);
    }
  }
  async function startAgentResearch() {
    if (agentBusy) return;
    const candidates = investigationSelection.length
      ? leads.filter((lead) => investigationSelection.includes(lead.id))
      : visible;
    const ids = candidates
      .filter((lead) => !lead.demo)
      .slice(0, 100)
      .map((lead) => lead.id);
    if (!ids.length) return;
    setAgentBusy(true);
    setAgentError("");
    try {
      const result = await api<ResearchBatchResponse>(
        "/investigation/requests",
        "POST",
        { lead_ids: ids, request_key: crypto.randomUUID() },
        20000,
      );
      setAgentBatch(result.batch);
      setAgentPaused(result.batch?.status === "paused");
    } catch (error) {
      setAgentError((error as Error).message);
    } finally {
      setAgentBusy(false);
    }
  }

  async function pauseAgentResearch() {
    if (!agentBatch || agentBusy) return;
    setAgentBusy(true);
    try {
      const result = await api<ResearchBatchResponse>(
        `/research/batches/${agentBatch.id}/pause`,
        "POST",
      );
      setAgentBatch(result.batch);
      setAgentPaused(true);
    } catch (error) {
      setAgentError((error as Error).message);
    } finally {
      setAgentBusy(false);
    }
  }

  async function resumeAgentResearch() {
    if (!agentBatch || agentBusy) return;
    setAgentBusy(true);
    setAgentError("");
    try {
      const result = await api<ResearchBatchResponse>(
        `/research/batches/${agentBatch.id}/resume`,
        "POST",
      );
      setAgentBatch(result.batch);
      setAgentPaused(false);
    } catch (error) {
      setAgentError((error as Error).message);
    } finally {
      setAgentBusy(false);
    }
  }

  async function cancelAgentResearch() {
    if (!agentBatch || agentBusy) return;
    setAgentBusy(true);
    try {
      const result = await api<ResearchBatchResponse>(
        `/research/batches/${agentBatch.id}/cancel`,
        "POST",
      );
      setAgentBatch(result.batch);
      setAgentPaused(false);
    } catch (error) {
      setAgentError((error as Error).message);
    } finally {
      setAgentBusy(false);
    }
  }

  useEffect(() => {
    if (
      !agentBatch ||
      agentPaused ||
      !["pending", "running"].includes(agentBatch.status) ||
      agentStepRef.current
    )
      return;
    const timer = window.setTimeout(() => {
      if (agentStepRef.current) return;
      agentStepRef.current = true;
      setAgentBusy(true);
      void api<ResearchBatchResponse>(
        `/research/batches/${agentBatch.id}${agentBatch.execution_mode === "legacy" ? "/step" : ""}`,
        agentBatch.execution_mode === "legacy" ? "POST" : "GET",
        undefined,
        75000,
      )
        .then((result) => {
          setAgentBatch(result.batch);
          if (result.lead) onLeadUpdated(result.lead);
          result.leads?.forEach(onLeadUpdated);
          setAgentError("");
        })
        .catch((error) => {
          setAgentError((error as Error).message);
          setAgentPaused(true);
        })
        .finally(() => {
          agentStepRef.current = false;
          setAgentBusy(false);
        });
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [agentBatch, agentPaused, onLeadUpdated]);

  function clearResultFilters() {
    setQuery("");
    setCategory("");
    setCity("");
    setCountry("");
    setSite("");
    setMinScore("0");
    setMinRating("0");
    setMinReviews("0");
    setContactFilter("");
    setPipelineFilter("");
    setOpportunityFilter("");
    setExtraProblemKeys([]);
    setMinConfidence("0");
    setMinTiming("0");
    setServiceFilter("");
    setSmartList("");
    setSortBy("score");
  }

  function buildSavedQuery(input: RadarSearchInput): RadarSavedQuery {
    return {
      ...input,
      problem_keys: [opportunityFilter, ...extraProblemKeys].filter(
        Boolean,
      ) as RadarOpportunityKey[],
      min_score: Number(minScore),
      min_rating: Number(minRating),
      min_reviews: Number(minReviews),
      contact_filter: contactFilter as RadarSavedQuery["contact_filter"],
      min_confidence: Number(minConfidence),
      min_timing: Number(minTiming),
      service_key: serviceFilter,
      min_service_score: serviceFilter ? 60 : 0,
    };
  }

  function applySavedQueryFilters(saved: RadarSavedQuery) {
    setOpportunityFilter(saved.problem_keys?.[0] || "");
    setExtraProblemKeys((saved.problem_keys || []).slice(1));
    setMinScore(String(saved.min_score || 0));
    setMinRating(String(saved.min_rating || 0));
    setMinReviews(String(saved.min_reviews || 0));
    setContactFilter(saved.contact_filter || "");
    setMinConfidence(String(saved.min_confidence || 0));
    setMinTiming(String(saved.min_timing || 0));
    setServiceFilter(saved.service_key || "");
  }

  async function interpretNaturalSearch() {
    if (naturalBusy || naturalText.trim().length < 3) return;
    setNaturalBusy(true);
    setNaturalError("");
    try {
      const plan = await api<RadarNaturalPlan>("/radar/interpret", "POST", {
        text: naturalText.trim(),
        fallback_location: location.trim(),
        fallback_country: selectedLocation?.country_code || "",
      });
      setNaturalPlan(plan);
      if (plan.query.location) {
        setSelectedLocation(null);
        setLocation(plan.query.location);
      }
      setNiche(plan.query.category || "");
      setScopeMode(plan.query.scope === "region" ? "region" : "radius");
      setRadius(String(plan.query.radius_km));
      applySavedQueryFilters(plan.query);
    } catch (error) {
      setNaturalError((error as Error).message);
    } finally {
      setNaturalBusy(false);
    }
  }

  function applySearchResult(
    result: RadarSearchResponse,
    input: RadarSearchInput,
    formLocation: string,
    formNiche: string,
    resolvedLocation: RadarLocation | null,
  ) {
    const resultIds = result.results.map((lead) => lead.id);
    setSearchOpen(false);
    setSavedOpen(false);
    setMobileSheet("mid");
    setSearchIds(resultIds);
    setSearchMeta(result);
    setLastSearchInput(input);
    persistRadarSearch(storageKey, {
      version: 1,
      form: {
        location: formLocation,
        niche: formNiche,
        radius: String(input.radius_km),
        scope: input.scope,
        selectedLocation: resolvedLocation,
      },
      result: {
        ids: resultIds,
        provider: result.provider,
        location: result.location,
        count: result.count,
        created: result.created,
        complete: result.complete,
        scanned: result.scanned,
        result_limit: result.result_limit,
        scope: result.scope,
        workspace_limit_reached: result.workspace_limit_reached,
        query: input,
      },
    });
    return resultIds;
  }

  async function saveCurrentSearch() {
    if (
      !lastSearchInput ||
      searchIds === null ||
      !saveSearchName.trim() ||
      savedSearchBusy
    )
      return;
    setSavedSearchBusy(true);
    setSavedSearchError("");
    try {
      const savedQuery = buildSavedQuery(lastSearchInput);
      const resultIds = baseLeads
        .filter((lead) => matchesSavedQuery(lead, savedQuery))
        .map((lead) => lead.id);
      const saved = await api<RadarSavedSearch>(
        "/radar/saved-searches",
        "POST",
        {
          name: saveSearchName.trim(),
          query: savedQuery,
          result_ids: resultIds,
        },
      );
      setSavedSearches((current) => [saved, ...current]);
      setSaveSearchName("");
      setSaveSearchOpen(false);
    } catch (error) {
      setSavedSearchError((error as Error).message);
    } finally {
      setSavedSearchBusy(false);
    }
  }

  async function runSavedSearch(saved: RadarSavedSearch, background = false) {
    if (
      saved.query.commercial_intent &&
      !saved.query.commercial_intent.legacy &&
      !background &&
      !(saved.monitor_enabled && saved.execution_mode === "worker")
    ) {
      setSavedIntent(saved.query.commercial_intent);
      setLaunchOpen(true);
      setSearchOpen(false);
      setSavedOpen(false);
      return;
    }
    if (
      (!background && (searching || savedSearchBusy)) ||
      (background && monitorBusy)
    )
      return;
    if (background) setMonitorBusy(true);
    else {
      setSearching(true);
      setSavedSearchBusy(true);
      setSearchError("");
    }
    setSavedSearchError("");
    try {
      if (saved.monitor_enabled && saved.execution_mode === "worker") {
        const scheduled = await api<RadarSavedSearch>(
          `/radar/saved-searches/${saved.id}/schedule`,
          "POST",
        );
        setSavedSearches((items) =>
          items.map((item) => (item.id === saved.id ? scheduled : item)),
        );
        return;
      }
      const requestIdentity = `${saved.id}:${saved.version}`;
      const requestKey =
        savedLaunchKeys.current.get(requestIdentity) || crypto.randomUUID();
      savedLaunchKeys.current.set(requestIdentity, requestKey);
      const launched = await api<{ job: { id: string } }>(
        `/smart-searches/saved/${saved.id}/launch`,
        "POST",
        { request_key: requestKey, version: saved.version },
      );
      savedLaunchKeys.current.delete(requestIdentity);
      setActiveSearch(launched.job.id);
      clearResultFilters();
      setSearchIds([]);
      setSearchMeta(null);
      setSavedOpen(false);
      setSearchOpen(false);
      if (surface !== "radar") onOpenSearch(launched.job.id);
      try {
        localStorage.setItem(storageKey + ":active-search", launched.job.id);
      } catch {
        /* Optional persistence. */
      }
    } catch (error) {
      if (!background) setSearchError((error as Error).message);
      setSavedSearchError((error as Error).message);
      void api<RadarSavedSearch[]>("/radar/saved-searches")
        .then(setSavedSearches)
        .catch(() => undefined);
    } finally {
      if (background) setMonitorBusy(false);
      else {
        setSearching(false);
        setSavedSearchBusy(false);
      }
    }
  }

  async function updateSavedSearchMonitor(
    saved: RadarSavedSearch,
    enabled: boolean,
    interval = saved.monitor_interval || "daily",
  ) {
    if (savedSearchBusy) return;
    setSavedSearchBusy(true);
    setSavedSearchError("");
    try {
      const updated = await api<RadarSavedSearch>(
        `/radar/saved-searches/${saved.id}/monitor`,
        "PATCH",
        {
          enabled,
          interval,
          version: saved.version,
        },
      );
      setSavedSearches((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (error) {
      setSavedSearchError((error as Error).message);
      void api<RadarSavedSearch[]>("/radar/saved-searches")
        .then(setSavedSearches)
        .catch(() => undefined);
    } finally {
      setSavedSearchBusy(false);
    }
  }

  async function deleteSavedSearch(saved: RadarSavedSearch) {
    if (savedSearchBusy) return;
    setSavedSearchBusy(true);
    setSavedSearchError("");
    try {
      await api(`/radar/saved-searches/${saved.id}`, "DELETE");
      setSavedSearches((current) =>
        current.filter((item) => item.id !== saved.id),
      );
    } catch (error) {
      setSavedSearchError((error as Error).message);
    } finally {
      setSavedSearchBusy(false);
    }
  }

  useEffect(() => {
    if (
      monitorBusy ||
      searching ||
      savedSearchBusy ||
      monitorRunsRef.current >= 4 ||
      savedSearches.some((item) => item.execution_mode !== "legacy")
    )
      return;
    const now = Math.floor(Date.now() / 1000);
    const due = savedSearches.find(
      (item) =>
        item.monitor_enabled &&
        item.next_monitor_at !== null &&
        item.next_monitor_at <= now &&
        !monitorRef.current.has(item.id),
    );
    if (!due) return;
    monitorRef.current.add(due.id);
    monitorRunsRef.current += 1;
    void runSavedSearch(due, true).finally(() =>
      monitorRef.current.delete(due.id),
    );
  }, [savedSearches, monitorBusy, searching, savedSearchBusy]);

  async function discover(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (searching || location.trim().length < 2) return;
    const typed = normalizeSearch(location.replace(/·/g, " "));
    const exactMatches = locations.filter((item) =>
      [
        item.name,
        item.formatted,
        `${item.name} ${item.state_code || item.uf} ${item.country_code}`,
      ].some((value) => normalizeSearch(value || "") === typed),
    );
    const resolvedLocation =
      selectedLocation ?? (exactMatches.length === 1 ? exactMatches[0] : null);
    setSearching(true);
    setSuggestionsOpen(false);
    setSearchError("");
    try {
      const searchInput: RadarSearchInput = {
        location: resolvedLocation?.formatted || location.trim(),
        category: niche.trim(),
        radius_km: Number(radius),
        scope: scopeMode,
        country: resolvedLocation?.country_code ?? "",
        municipality_id:
          resolvedLocation?.country_code === "BR" &&
          /^\d+$/.test(resolvedLocation.id)
            ? resolvedLocation.id
            : "",
        city_name: resolvedLocation?.name ?? "",
        state: resolvedLocation?.state ?? "",
        state_code: (
          resolvedLocation?.state_code ||
          resolvedLocation?.uf ||
          ""
        ).slice(0, 12),
      };
      const result = await onDiscover(searchInput);
      setSimilarSource("");
      setSimilarityById({});
      applySearchResult(result, searchInput, location, niche, resolvedLocation);
    } catch (error) {
      setSearchError((error as Error).message);
    } finally {
      setSearching(false);
    }
  }

  function territoryQuery(points: [number, number][]) {
    const lngs = points.map((point) => point[0]);
    const lats = points.map((point) => point[1]);
    const west = Math.min(...lngs),
      east = Math.max(...lngs),
      south = Math.min(...lats),
      north = Math.max(...lats);
    const centerLng = (west + east) / 2;
    const centerLat = (south + north) / 2;
    const latKm = (north - south) * 111.32;
    const lngKm =
      (east - west) *
      111.32 *
      Math.max(0.2, Math.cos((centerLat * Math.PI) / 180));
    const radiusKm = Math.max(
      1,
      Math.ceil(Math.sqrt((latKm / 2) ** 2 + (lngKm / 2) ** 2)),
    );
    return { west, south, east, north, centerLng, centerLat, radiusKm };
  }

  function runMapAreaSearch(kind: "bounds" | "polygon") {
    if (searching) return;
    setSearchError("");
    let input: RadarSearchInput | null = null;
    if (kind === "polygon") {
      const points = territory?.points ?? [];
      if (points.length < 3) {
        setSearchError(tr("Desenhe uma área com pelo menos 3 pontos."));
        return;
      }
      const geometry = territoryQuery(points);
      if (geometry.radiusKm > 25) {
        setSearchError(
          tr(
            "O território está muito amplo. Reduza a área para até 25 km a partir do centro.",
          ),
        );
        return;
      }
      input = {
        location: tr("Território desenhado"),
        category: niche.trim(),
        radius_km: geometry.radiusKm,
        scope: "polygon",
        country: selectedLocation?.country_code || "",
        center_lat: geometry.centerLat,
        center_lng: geometry.centerLng,
        bounds: [geometry.west, geometry.south, geometry.east, geometry.north],
        polygon: points,
      };
    } else {
      if (!viewport) {
        setSearchError(tr("Mova o mapa para definir a área visível."));
        return;
      }
      const radiusKm = Math.max(1, Math.ceil(viewport.radius_km));
      if (radiusKm > 25) {
        setSearchError(
          tr(
            "A área visível está muito ampla. Aproxime o mapa antes de buscar.",
          ),
        );
        return;
      }
      input = {
        location: tr("Área visível do mapa"),
        category: niche.trim(),
        radius_km: radiusKm,
        scope: "bounds",
        country: selectedLocation?.country_code || "",
        center_lat: viewport.center_lat,
        center_lng: viewport.center_lng,
        bounds: [viewport.west, viewport.south, viewport.east, viewport.north],
        polygon: [],
      };
    }
    setSavedIntent(undefined);
    setLaunchArea({
      kind,
      bounds: input.bounds || [],
      polygon: input.polygon || [],
    });
    setLaunchText(niche.trim());
    setLaunchOpen(true);
  }

  async function findSimilar(lead: Lead) {
    if (similarBusyId) return;
    setSimilarBusyId(lead.id);
    setSearchError("");
    try {
      const result = await api<SimilarLeadsResponse>(
        `/leads/${lead.id}/similar`,
        "POST",
        undefined,
        90000,
      );
      result.results.forEach((item) => onLeadUpdated(item));
      setSearchIds(result.results.map((item) => item.id));
      setSearchMeta(null);
      setLastSearchInput(null);
      clearResultFilters();
      setSimilarSource(lead.name);
      setSimilarityById(
        Object.fromEntries(
          result.results.map((item) => [item.id, item.similarity]),
        ),
      );
    } catch (error) {
      setSearchError((error as Error).message);
    } finally {
      setSimilarBusyId("");
    }
  }

  const savedSearchesContent = (
    <section className="radar-saved-searches" aria-label={tr("Buscas salvas")}>
      <div className="radar-saved-searches-head">
        <div>
          <span className="eyebrow">{tr("BUSCAS SALVAS")}</span>
          {savedSearches.length > 0 && <small>{savedSearches.length}/30</small>}
        </div>
        {lastSearchInput && searchIds !== null && !saveSearchOpen && (
          <button
            className="text-link"
            type="button"
            onClick={() => setSaveSearchOpen(true)}
          >
            <BookmarkPlus size={14} />
            {tr("Salvar busca atual")}
          </button>
        )}
      </div>
      {saveSearchOpen && (
        <div className="radar-save-search-form">
          <input
            type="text"
            maxLength={80}
            value={saveSearchName}
            onChange={(event) => setSaveSearchName(event.target.value)}
            placeholder={tr("Nome da busca")}
            autoFocus
          />
          <button
            className="button"
            type="button"
            disabled={savedSearchBusy || saveSearchName.trim().length < 2}
            onClick={() => void saveCurrentSearch()}
          >
            {savedSearchBusy ? (
              <LoaderCircle size={14} className="spin" />
            ) : (
              <Check size={14} />
            )}
            {tr("Salvar")}
          </button>
          <button
            className="text-link"
            type="button"
            onClick={() => {
              setSaveSearchOpen(false);
              setSaveSearchName("");
            }}
          >
            {tr("Cancelar")}
          </button>
        </div>
      )}
      {savedSearches.length > 0 && (
        <div className="radar-saved-search-list">
          {savedSearches.map((saved) => (
            <div className="radar-saved-search-item" key={saved.id}>
              <button
                type="button"
                className="radar-saved-search-run"
                title={
                  saved.monitor_enabled && saved.execution_mode === "worker"
                    ? "Agendar execução no servidor"
                    : "Executar busca"
                }
                disabled={searching || savedSearchBusy}
                onClick={() => void runSavedSearch(saved)}
              >
                <span>{saved.name}</span>
                {saved.monitor_enabled && saved.execution_mode === "worker" && (
                  <small>Execução no servidor · requer worker ativo</small>
                )}
                {saved.worker_error && (
                  <small role="status">{saved.worker_error}</small>
                )}
                <small>
                  {saved.query.category || tr("Exploração geral")} ·{" "}
                  {saved.query.scope === "radius"
                    ? `${saved.query.radius_km} km`
                    : tr("Região inteira")}
                  {saved.query.problem_keys?.length
                    ? ` · ${tr("oportunidade filtrada")}`
                    : ""}
                </small>
                {saved.last_new_count > 0 && (
                  <b>
                    +{saved.last_new_count} {tr("novas")}
                  </b>
                )}
              </button>
              <div className="radar-saved-search-actions">
                {saved.monitor_enabled ? (
                  <>
                    <label className="radar-monitor-frequency">
                      <Bell size={13} aria-hidden="true" />
                      <SmartSelect
                        ariaLabel={`${tr("Frequência do monitoramento")} ${saved.name}`}
                        value={saved.monitor_interval}
                        disabled={savedSearchBusy}
                        onChange={(value) =>
                          void updateSavedSearchMonitor(
                            saved,
                            true,
                            value as "daily" | "weekly",
                          )
                        }
                        options={[
                          { value: "daily", label: tr("Diário") },
                          { value: "weekly", label: tr("Semanal") },
                        ]}
                      />
                    </label>
                    <button
                      className="icon-button"
                      type="button"
                      aria-label={`${tr("Desativar monitoramento")} ${saved.name}`}
                      disabled={savedSearchBusy}
                      onClick={() =>
                        void updateSavedSearchMonitor(saved, false)
                      }
                    >
                      <BellOff size={14} />
                    </button>
                  </>
                ) : (
                  <button
                    className="radar-monitor-enable"
                    type="button"
                    disabled={savedSearchBusy}
                    onClick={() =>
                      void updateSavedSearchMonitor(saved, true, "daily")
                    }
                  >
                    <Bell size={13} />
                    {tr("Monitorar")}
                  </button>
                )}
                <button
                  className="icon-button"
                  type="button"
                  aria-label={`${tr("Excluir busca")} ${saved.name}`}
                  disabled={savedSearchBusy}
                  onClick={() => void deleteSavedSearch(saved)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {!savedSearches.length && (
        <Empty
          title={tr("Nenhum monitor criado")}
          description={tr(
            "Salve uma pesquisa no Radar para acompanhar novos resultados.",
          )}
          action={
            <button
              className="button"
              onClick={() => {
                setSavedOpen(false);
                setLaunchOpen(true);
              }}
            >
              {tr("Nova pesquisa")}
            </button>
          }
        />
      )}
      {savedSearchError && <p className="research-error">{savedSearchError}</p>}
    </section>
  );

  const displayTitle =
    surface === "monitors"
      ? "Monitores"
      : surface === "opportunities"
        ? "Oportunidades"
        : "Radar";
  const changed = leads.filter(
    (lead) => lead.watchlisted && lead.watch_last_event_at,
  ).length;

  function stepMobileSheet(direction: "up" | "down") {
    setMobileSheet((current) => {
      const order: Array<"peek" | "mid" | "full"> = ["peek", "mid", "full"];
      const index = order.indexOf(current);
      const next =
        direction === "up"
          ? Math.min(order.length - 1, index + 1)
          : Math.max(0, index - 1);
      return order[next];
    });
  }

  function cycleMobileSheet() {
    setMobileSheet((current) =>
      current === "peek" ? "mid" : current === "mid" ? "full" : "peek",
    );
  }

  function finishSheetDrag(event: ReactPointerEvent<HTMLButtonElement>) {
    const start = sheetDragStart.current;
    sheetDragStart.current = null;
    if (start === null) {
      cycleMobileSheet();
      return;
    }
    const delta = start - event.clientY;
    if (Math.abs(delta) < 28) {
      cycleMobileSheet();
      return;
    }
    stepMobileSheet(delta > 0 ? "up" : "down");
  }

  if (surface === "radar" && commercialMode) return <div className="radar-surface ledger-mode">
    <div className="radar-canvas-heading"><div className="radar-title"><h1>Radar</h1><span>Revisão comercial</span></div></div>
    <div className="commercial-mode"><button className="button" onClick={()=>changeCommercialMode(false)}>Descoberta</button><button className="button" aria-pressed="true">Fila comercial</button></div>
    <CommercialQueue storageKey={storageKey} onOpenLead={onSelect} onLeadUpdated={onLeadUpdated}/>
  </div>;
  const sheetExpanded = mobileSheet === "full";
  return (
    <div
      className={`radar-surface surface-${surface} ${mode === "map" ? "canvas-mode" : "ledger-mode"} sheet-${mobileSheet} ${sheetExpanded ? "sheet-expanded" : ""}`}
    >
      {surface !== "radar" && (
        <PageHead title={tr(displayTitle)}>
          <button className="button" onClick={() => setLaunchOpen(true)}>
            <Search size={17} />
            {tr("Buscar empresas")}
          </button>
          <button className="button primary" onClick={onAdd}>
            <Plus size={17} />
            {tr("Adicionar estabelecimento")}
          </button>
        </PageHead>
      )}
      {surface === "radar" && (
        <div className="radar-canvas-heading">
          <div className="radar-title">
            <h1>Radar</h1>
            <span>{tr("Descoberta comercial")}</span>
          </div>
          <button
            className="button primary radar-smart-launch"
            onClick={() => setLaunchOpen(true)}
          >
            <Search size={19} />
            {tr("Buscar empresas")}
            <kbd aria-hidden="true">/</kbd>
          </button>
        </div>
      )}
      {surface === "radar" && <div className="commercial-mode"><button className="button" aria-pressed="true">Descoberta</button><button className="button" onClick={()=>changeCommercialMode(true)}>Fila comercial</button></div>}
      {launchOpen && (
        <SearchDialog
          storageKey={storageKey}
          initialText={launchText}
          initialIntent={savedIntent}
          initialArea={launchArea}
          onClose={() => {
            setLaunchOpen(false);
            setLaunchText("");
            setSavedIntent(undefined);
            setLaunchArea(undefined);
          }}
          onStarted={(job) => {
            if (surface !== "radar") onOpenSearch(job.id);
            setLaunchText("");
            setSavedIntent(undefined);
            setLaunchArea(undefined);
            setLaunchOpen(false);
            setActiveSearch(job.id);
            clearResultFilters();
            setSearchMeta(null);
            setSearchIds([]);
            try {
              localStorage.setItem(storageKey + ":active-search", job.id);
            } catch {
              /* Optional persistence. */
            }
          }}
        />
      )}
      {surface === "radar" && activeSearch && (
        <SearchProgress
          jobId={activeSearch}
          onSaved={() => {
            void api<RadarSavedSearch[]>("/radar/saved-searches")
              .then(setSavedSearches)
              .catch((e) => setSavedSearchError(e.message));
          }}
          onResults={(job, group) => {
            const rows = job.results.filter(
              (row) => group === "all" || row.group === group,
            );
            setSearchIds(rows.map((row) => row.id));
            for (const row of job.results)
              if (row.lead) onLeadUpdated(row.lead);
          }}
          onDismiss={() => {
            setActiveSearch(null);
            setSearchIds(null);
            setSearchMeta(null);
            try {
              localStorage.removeItem(storageKey + ":active-search");
            } catch {
              /* Optional persistence. */
            }
          }}
        />
      )}
      {surface === "radar" && (
        <SearchHistory
          current={activeSearch}
          onSelect={(id) => {
            clearResultFilters();
            setSearchMeta(null);
            setSearchIds([]);
            setActiveSearch(id);
            try {
              localStorage.setItem(storageKey + ":active-search", id);
            } catch {
              /* Optional persistence. */
            }
          }}
        />
      )}
      {surface === "monitors" && (
        <div className="monitor-overview">
          <div>
            <strong>
              {savedSearches.filter((item) => item.monitor_enabled).length}
            </strong>
            <span>{tr("Monitoramentos ativos")}</span>
          </div>
          <div>
            <strong>{leads.filter((lead) => lead.watchlisted).length}</strong>
            <span>{tr("Empresas acompanhadas")}</span>
          </div>
          <div>
            <strong>{changed}</strong>
            <span>{tr("Com mudanças registradas")}</span>
          </div>
        </div>
      )}
      {surface === "monitors" && (
        <div className="monitor-searches"> {savedSearchesContent}</div>
      )}
      <div className="radar-workbench-controls">
        <button
          className="button"
          aria-expanded={filters}
          onClick={() => setFilters(true)}
        >
          <SlidersHorizontal size={17} />
          {tr("Filtros")}
          {activeFilterCount > 0 && <b>{activeFilterCount}</b>}
        </button>
        {surface !== "monitors" && (
          <button
            className="button"
            aria-label={tr("Buscas salvas")}
            onClick={() => setSavedOpen(true)}
          >
            <BookmarkPlus size={17} />
            <span>{tr("Buscas salvas")}</span>
          </button>
        )}
        {surface === "radar" && (
          <div
            className="view-toggle"
            role="group"
            aria-label={tr("Visualização")}
          >
            <button
              aria-pressed={mode === "map"}
              className={mode === "map" ? "active" : ""}
              aria-label={tr("Ver mapa")}
              onClick={() => setMode("map")}
            >
              <MapIcon size={18} />
              <span>{tr("Mapa")}</span>
            </button>
            <button
              aria-pressed={mode === "list"}
              className={mode === "list" ? "active" : ""}
              aria-label={tr("Ver lista")}
              onClick={() => setMode("list")}
            >
              <List size={18} />
              <span>{tr("Lista")}</span>
            </button>
          </div>
        )}
        {surface === "opportunities" && (
          <SmartSelect
            ariaLabel={tr("Lista inteligente")}
            value={smartList}
            onChange={setSmartList}
            options={[
              { value: "", label: tr("Todas as oportunidades") },
              { value: "high", label: tr("Alta prioridade") },
              { value: "no_site", label: tr("Sem site") },
              { value: "watchlist", label: tr("Acompanhadas") },
              { value: "new_week", label: tr("Novos esta semana") },
            ]}
          />
        )}
      </div>
      {searchOpen && (
        <Modal
          title={tr("Nova pesquisa")}
          onClose={() => setSearchOpen(false)}
          wide
          className="radar-search-sheet"
        >
          <div className="search-methods">
            <button
              className="text-link"
              aria-expanded={naturalOpen}
              onClick={() => setNaturalOpen((value) => !value)}
            >
              <Sparkles size={16} />
              {tr("Descrever oportunidade")}
              {naturalOpen ? (
                <ChevronUp size={16} />
              ) : (
                <ChevronDown size={16} />
              )}
            </button>
          </div>
          {naturalOpen && (
            <div>
              {" "}
              <section
                className="radar-natural-search"
                aria-label={tr("Pesquisa em linguagem natural")}
              >
                <div className="radar-natural-copy">
                  <Sparkles size={16} aria-hidden="true" />
                  <div>
                    <strong>{tr("Descreva a oportunidade")}</strong>
                    <small>
                      {tr(
                        "O Scout converte o pedido em critérios visíveis antes de buscar.",
                      )}
                    </small>
                  </div>
                </div>
                <div className="radar-natural-input">
                  <input
                    type="text"
                    maxLength={280}
                    value={naturalText}
                    onChange={(event) => {
                      setNaturalText(event.target.value);
                      setNaturalPlan(null);
                      setNaturalError("");
                    }}
                    placeholder={tr(
                      "Ex.: dentistas em Recife sem site, 100+ avaliações e WhatsApp",
                    )}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void interpretNaturalSearch();
                      }
                    }}
                  />
                  <button
                    className="button"
                    type="button"
                    disabled={naturalBusy || naturalText.trim().length < 3}
                    onClick={() => void interpretNaturalSearch()}
                  >
                    {naturalBusy ? (
                      <LoaderCircle size={14} className="spin" />
                    ) : (
                      <Sparkles size={14} />
                    )}
                    {tr("Interpretar")}
                  </button>
                </div>
                {naturalPlan && (
                  <div className="radar-natural-plan">
                    <div className="radar-natural-chips">
                      {naturalPlan.detected.map((item) => (
                        <span key={item}>{item}</span>
                      ))}
                    </div>
                    {naturalPlan.unresolved.includes("location") && (
                      <small className="research-error">
                        {tr("Informe uma cidade ou região antes de buscar.")}
                      </small>
                    )}
                    {!naturalPlan.unresolved.length && (
                      <small>
                        {tr(
                          "Critérios aplicados ao formulário. Revise e execute a busca.",
                        )}
                      </small>
                    )}
                  </div>
                )}
                {naturalError && (
                  <small className="research-error">{naturalError}</small>
                )}
              </section>
            </div>
          )}
          <form
            className={`radar-discovery ${scopeMode === "radius" ? "has-radius" : ""}`}
            onSubmit={discover}
          >
            <div className="radar-search-field radar-location-field">
              <MapPin size={18} aria-hidden="true" />
              <input
                aria-label={tr("Região para buscar empresas")}
                aria-autocomplete="list"
                aria-controls="radar-location-suggestions"
                aria-expanded={
                  suggestionsOpen && locationSuggestions.length > 0
                }
                aria-activedescendant={
                  suggestionsOpen && locationSuggestions.length
                    ? `radar-location-${locationSuggestions[activeSuggestion]?.id}`
                    : undefined
                }
                role="combobox"
                placeholder={tr("Cidade ou região")}
                value={location}
                minLength={2}
                maxLength={160}
                required
                autoComplete="off"
                onFocus={() => {
                  if (locationSuggestions.length) setSuggestionsOpen(true);
                }}
                onBlur={() =>
                  window.setTimeout(() => setSuggestionsOpen(false), 120)
                }
                onKeyDown={locationKeyDown}
                onChange={(e) => {
                  setSelectedLocation(null);
                  setLocation(e.target.value);
                  setActiveSuggestion(0);
                  setSuggestionsOpen(true);
                }}
              />
              {selectedLocation && (
                <Check className="radar-location-check" size={16} />
              )}
              {suggestionsOpen && locationSuggestions.length > 0 && (
                <div
                  className="radar-location-suggestions"
                  id="radar-location-suggestions"
                  role="listbox"
                >
                  {locationSuggestions.map((item, index) => (
                    <button
                      className={`radar-location-suggestion ${index === activeSuggestion ? "active" : ""}`}
                      id={`radar-location-${item.id}`}
                      key={item.id}
                      type="button"
                      role="option"
                      aria-selected={index === activeSuggestion}
                      onMouseDown={(e) => e.preventDefault()}
                      onMouseEnter={() => setActiveSuggestion(index)}
                      onClick={() => chooseLocation(item)}
                    >
                      <span className="radar-location-suggestion-icon">
                        <MapPin size={15} />
                      </span>
                      <span>
                        <strong>{item.name}</strong>
                        <small>
                          {[
                            item.state || item.state_code || item.uf,
                            item.country,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </small>
                      </span>
                    </button>
                  ))}
                </div>
              )}
              {suggestionsOpen &&
                locationCatalogFailed &&
                normalizeSearch(location).length >= 2 && (
                  <div className="radar-location-suggestions radar-location-catalog-fallback">
                    {tr(
                      "Sugestões indisponíveis. A busca manual continua funcionando.",
                    )}
                  </div>
                )}
            </div>

            <div className="radar-search-field radar-niche-field">
              <Store size={18} aria-hidden="true" />
              <input
                aria-label={tr("Nicho da busca")}
                placeholder={tr("Nicho opcional")}
                value={niche}
                maxLength={80}
                onChange={(e) => setNiche(e.target.value)}
              />
            </div>

            <div className="radar-search-field radar-scope-field">
              <MapIcon size={17} aria-hidden="true" />
              <div className="radar-scope-control">
                <span className="radar-control-label">{tr("Área")}</span>
                <SmartSelect
                  ariaLabel={tr("Área da busca")}
                  value={scopeMode}
                  onChange={(value) =>
                    setScopeMode(value as "region" | "radius")
                  }
                  options={[
                    { value: "region", label: tr("Região inteira") },
                    { value: "radius", label: tr("Por raio") },
                  ]}
                />
              </div>
            </div>

            {scopeMode === "radius" && (
              <div className="radar-search-field radar-radius-field">
                <span className="radar-control-label">{tr("Raio")}</span>
                <SmartSelect
                  ariaLabel={tr("Raio da busca")}
                  value={radius}
                  onChange={setRadius}
                  options={[
                    { value: "2", label: "2 km" },
                    { value: "5", label: "5 km" },
                    { value: "10", label: "10 km" },
                    { value: "15", label: "15 km" },
                    { value: "25", label: "25 km" },
                  ]}
                />
              </div>
            )}

            <button
              className="button primary radar-search-submit"
              type="submit"
              disabled={searching}
            >
              {searching ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Search size={16} />
              )}
              {searching ? tr("Carregando") : tr("Buscar empresas")}
            </button>
          </form>

          {searchError && (
            <p className="research-error" role="alert">
              {searchError}
            </p>
          )}
        </Modal>
      )}
      {filters && (
        <Modal
          title={tr("Filtros")}
          onClose={() => setFilters(false)}
          wide
          className="radar-filter-sheet"
        >
          <div className="filter-primary-fields">
            {" "}
            <SmartSelect
              ariaLabel="Categoria"
              value={category}
              onChange={setCategory}
              options={[
                { value: "", label: "Todas as categorias" },
                ...Array.from(new Set(baseLeads.map((l) => l.category)))
                  .filter(Boolean)
                  .sort()
                  .map((value) => ({ value, label: value })),
              ]}
            />
            <SmartSelect
              ariaLabel={tr("Oportunidade")}
              value={opportunityFilter}
              onChange={(value) => {
                setOpportunityFilter(value as RadarOpportunityKey | "");
                setExtraProblemKeys([]);
              }}
              options={RADAR_OPPORTUNITY_OPTIONS.map((item) => ({
                value: item.value,
                label: tr(item.label),
              }))}
            />
            <SmartSelect
              ariaLabel={tr("Lista inteligente")}
              value={smartList}
              onChange={setSmartList}
              options={[
                { value: "", label: tr("Lista inteligente") },
                { value: "high", label: tr("Alta prioridade") },
                { value: "no_site", label: tr("Sem site") },
                { value: "radar", label: tr("Só no Radar") },
                { value: "pipeline", label: tr("Pipeline ativo") },
                { value: "action_today", label: tr("Ação para hoje") },
                { value: "overdue", label: tr("Ação atrasada") },
                { value: "stale", label: tr("Sem contato há 7 dias") },
                { value: "new_week", label: tr("Novos esta semana") },
                { value: "watchlist", label: tr("Acompanhadas") },
              ]}
            />
          </div>{" "}
          <div className="advanced-filters">
            <div className="field">
              <span>{tr("País")}</span>
              <SmartSelect
                ariaLabel={tr("País")}
                value={country}
                onChange={setCountry}
                options={[
                  { value: "", label: "Todos" },
                  ...Array.from(new Set(baseLeads.map((l) => l.country)))
                    .filter(Boolean)
                    .map((value) => ({ value, label: value })),
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Cidade")}</span>
              <SmartSelect
                ariaLabel={tr("Cidade")}
                value={city}
                onChange={setCity}
                options={[
                  { value: "", label: "Todas" },
                  ...Array.from(new Set(baseLeads.map((l) => l.city)))
                    .filter(Boolean)
                    .map((value) => ({ value, label: value })),
                ]}
              />
            </div>
            <div className="field">
              <span>Site</span>
              <SmartSelect
                ariaLabel={tr("Site")}
                value={site}
                onChange={setSite}
                options={[
                  { value: "", label: "Todos" },
                  { value: "none", label: "Sem site confirmado" },
                  { value: "poor", label: "Site com problemas" },
                  { value: "unknown", label: "Não verificado" },
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Score mínimo")}</span>
              <SmartSelect
                ariaLabel={tr("Score mínimo")}
                value={minScore}
                onChange={setMinScore}
                options={[
                  { value: "0", label: tr("Qualquer score") },
                  { value: "60", label: "60%" },
                  { value: "70", label: "70%" },
                  { value: "80", label: "80%" },
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Avaliação mínima")}</span>
              <SmartSelect
                ariaLabel={tr("Avaliação mínima")}
                value={minRating}
                onChange={setMinRating}
                options={[
                  { value: "0", label: tr("Qualquer avaliação") },
                  { value: "3.5", label: "3,5+" },
                  { value: "4", label: "4,0+" },
                  { value: "4.5", label: "4,5+" },
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Avaliações")}</span>
              <SmartSelect
                ariaLabel={tr("Avaliações")}
                value={minReviews}
                onChange={setMinReviews}
                options={[
                  { value: "0", label: tr("Qualquer quantidade") },
                  { value: "10", label: "10+" },
                  { value: "50", label: "50+" },
                  { value: "100", label: "100+" },
                  { value: "250", label: "250+" },
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Contato disponível")}</span>
              <SmartSelect
                ariaLabel={tr("Contato disponível")}
                value={contactFilter}
                onChange={setContactFilter}
                options={[
                  { value: "", label: tr("Qualquer contato") },
                  { value: "any", label: tr("Com algum contato") },
                  { value: "phone", label: tr("Com telefone") },
                  { value: "whatsapp", label: "WhatsApp" },
                  { value: "instagram", label: "Instagram" },
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Situação")}</span>
              <SmartSelect
                ariaLabel={tr("Situação")}
                value={pipelineFilter}
                onChange={setPipelineFilter}
                options={[
                  { value: "", label: tr("Todos") },
                  { value: "radar", label: tr("Só no Radar") },
                  { value: "pipeline", label: tr("No Pipeline") },
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Confiança mínima")}</span>
              <SmartSelect
                ariaLabel={tr("Confiança mínima")}
                value={minConfidence}
                onChange={setMinConfidence}
                options={[
                  { value: "0", label: tr("Qualquer confiança") },
                  { value: "55", label: "55+" },
                  { value: "70", label: "70+" },
                  { value: "80", label: "80+" },
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Timing mínimo")}</span>
              <SmartSelect
                ariaLabel={tr("Timing mínimo")}
                value={minTiming}
                onChange={setMinTiming}
                options={[
                  { value: "0", label: tr("Qualquer timing") },
                  { value: "55", label: "55+" },
                  { value: "70", label: "70+" },
                  { value: "80", label: "80+" },
                ]}
              />
            </div>
            <div className="field">
              <span>{tr("Fit por serviço")}</span>
              <SmartSelect
                ariaLabel={tr("Serviço recomendado")}
                value={serviceFilter}
                onChange={setServiceFilter}
                options={RADAR_SERVICE_OPTIONS.map((item) => ({
                  value: item.value,
                  label: tr(item.label),
                }))}
              />
            </div>
            <div className="field">
              <span>{tr("Ordenar por")}</span>
              <SmartSelect
                ariaLabel={tr("Ordenar resultados")}
                value={sortBy}
                onChange={setSortBy}
                options={[
                  { value: "score", label: tr("Maior score") },
                  { value: "reviews", label: tr("Mais avaliações") },
                  { value: "rating", label: tr("Melhor avaliação") },
                  { value: "name", label: tr("Nome") },
                ]}
              />
            </div>
            <button
              className="text-link"
              type="button"
              onClick={() => {
                setQuery("");
                setCategory("");
                setCity("");
                setCountry("");
                setSite("");
                setMinScore("0");
                setMinRating("0");
                setMinReviews("0");
                setContactFilter("");
                setPipelineFilter("");
                setOpportunityFilter("");
                setExtraProblemKeys([]);
                setMinConfidence("0");
                setMinTiming("0");
                setServiceFilter("");
                setSmartList("");
                setSortBy("score");
              }}
            >
              {tr("Limpar filtros")}
            </button>
          </div>
          <div className="form-actions">
            <span>
              {visible.length} {tr("resultados")}
            </span>
            <button
              className="button primary"
              onClick={() => setFilters(false)}
            >
              {tr("Ver resultados")}
            </button>
          </div>
        </Modal>
      )}
      {savedOpen && (
        <Modal
          title={tr("Buscas salvas")}
          onClose={() => setSavedOpen(false)}
          wide
          className="radar-saved-sheet"
        >
          {" "}
          {savedSearchesContent}
        </Modal>
      )}
      {searchMeta?.provider === "geoapify" && (
        <a
          className="search-attribution"
          href="https://www.geoapify.com/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Geoapify · OpenStreetMap
        </a>
      )}
      {searchError && !searchOpen && (
        <div className="radar-search-error" role="alert">
          {searchError}
        </div>
      )}
      <div className="radar-process-state">
        {investigationQueue.length > 0 && (
          <label className="field investigation-queue-selector">
            <span>Fila de investigação</span>
            <select
              value={agentBatch?.id || ""}
              disabled={agentBusy}
              onChange={(e) => void selectInvestigationBatch(e.target.value)}
            >
              <option value="">Selecionar lote e revisar resultados</option>
              {investigationQueue.map((batch, index) => (
                <option key={batch.id} value={batch.id}>
                  Lote {batch.ordinal || investigationQueue.length - index} ·{" "}
                  {batch.processed}/{batch.total} ·{" "}
                  {
                    {
                      pending: "Na fila",
                      running: "Em andamento",
                      paused: "Pausado",
                      completed: "Concluído",
                      cancelled: "Cancelado",
                    }[batch.status]
                  }
                </option>
              ))}
            </select>
          </label>
        )}{" "}
        {agentBatch && (
          <section
            className={`radar-agent ${agentBatch.status}`}
            aria-live="polite"
          >
            <div className="radar-agent-copy">
              <span className="eyebrow">SCOUT AGENT</span>
              <strong>
                {agentBatch.status === "completed"
                  ? tr("Investigação concluída")
                  : agentBatch.status === "cancelled"
                    ? tr("Investigação cancelada")
                    : agentPaused
                      ? tr("Investigação pausada")
                      : tr("Investigando oportunidades")}
              </strong>
              <small>
                {agentBatch.processed}/{agentBatch.total} · {agentBatch.done}{" "}
                {tr("concluídos")} · {agentBatch.pending} pendentes
                {agentBatch.errors
                  ? ` · ${agentBatch.errors} ${tr("erros")}`
                  : ""}
                {agentBatch.skipped_recent
                  ? ` · ${agentBatch.skipped_recent} ${tr("já atualizados")}`
                  : ""}
              </small>
            </div>
            <div
              className="radar-agent-progress"
              aria-label={tr("Progresso da investigação")}
            >
              <i
                style={{
                  width: `${agentBatch.total ? Math.min(100, (agentBatch.processed / agentBatch.total) * 100) : 100}%`,
                }}
              />
            </div>
            <div className="radar-agent-actions">
              {agentBatch.status === "completed" ||
              agentBatch.status === "cancelled" ? (
                <button
                  className="text-link"
                  type="button"
                  onClick={() => setAgentBatch(null)}
                >
                  {tr("Fechar")}
                </button>
              ) : agentPaused ? (
                <button
                  className="button radar-agent-control"
                  type="button"
                  disabled={agentBusy}
                  onClick={() => void resumeAgentResearch()}
                >
                  {tr("Continuar")}
                </button>
              ) : (
                <button
                  className="button radar-agent-control"
                  type="button"
                  disabled={agentBusy}
                  onClick={() => void pauseAgentResearch()}
                >
                  {tr("Pausar")}
                </button>
              )}
              {!agentBatch.completed_at &&
                agentBatch.status !== "cancelled" && (
                  <button
                    className="text-link"
                    type="button"
                    disabled={agentBusy}
                    onClick={() => void cancelAgentResearch()}
                  >
                    {tr("Cancelar")}
                  </button>
                )}
            </div>
          </section>
        )}
        {agentBatch?.mode === "progressive" && (
          <details className="investigation-results">
            <summary>Resultados e motivos de prioridade</summary>
            <ul>
              {agentBatch.items.map((item) => (
                <li key={item.lead_id}>
                  <strong>{item.name}</strong>
                  {item.qualification && (
                    <>
                      <p>
                        {
                          {
                            priority: "Prioritária",
                            promising: "Promissora",
                            pending: "Pendente",
                            low: "Baixa prioridade",
                            unavailable: "Investigação indisponível",
                          }[item.qualification.class]
                        }{" "}
                        · Score {item.qualification.score} · Cobertura{" "}
                        {item.qualification.coverage}% · Confiança{" "}
                        {item.qualification.confidence?.value ?? 0}/100
                      </p>
                      <p>
                        {item.qualification.decision ||
                          item.qualification.reasons.join(" ")}
                      </p>
                      {item.qualification.pending.length > 0 && (
                        <p>
                          Pendências: {item.qualification.pending.join(" ")}
                        </p>
                      )}
                    </>
                  )}
                  {item.error && <p>{item.error}</p>}
                  <button
                    className="text-link"
                    onClick={() => {
                      const lead = leads.find((l) => l.id === item.lead_id);
                      if (lead) onSelect(lead);
                    }}
                  >
                    Revisar {item.name}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        )}
        {agentError && (
          <div className="radar-search-error" role="alert">
            {agentError}
          </div>
        )}
        {similarSource && (
          <div className="radar-similar-context">
            <div>
              <span className="eyebrow">{tr("EMPRESAS SEMELHANTES")}</span>
              <strong>{similarSource}</strong>
              <small>
                {tr(
                  "Ordenadas por nicho, categoria, região, porte aparente e perfil digital.",
                )}
              </small>
            </div>
            <button
              className="text-link"
              type="button"
              onClick={() => {
                setSimilarSource("");
                setSimilarityById({});
                setSearchIds(null);
              }}
            >
              {tr("Voltar à base local")}
            </button>
          </div>
        )}
      </div>
      <div className={`radar-layout ${mode === "list" ? "list-only" : ""}`}>
        {mode === "map" && (
          <div className="radar-map">
            <div className="radar-map-area-actions">
              <button
                className="secondary-button"
                type="button"
                disabled={searching || !viewport}
                onClick={() => void runMapAreaSearch("bounds")}
              >
                <MapIcon size={14} />
                <span className="desktop-label">
                  {tr("Buscar nesta área visível")}
                </span>
                <span className="mobile-label">{tr("Nesta área")}</span>
              </button>
              <button
                className="secondary-button"
                type="button"
                disabled={searching || !territory?.points?.length}
                onClick={() => void runMapAreaSearch("polygon")}
              >
                <MapPin size={14} />
                <span className="desktop-label">
                  {tr("Buscar no território")}
                </span>
                <span className="mobile-label">{tr("Território")}</span>
              </button>
            </div>
            <Suspense fallback={<div className="skeleton map-skeleton" />}>
              <OpportunityMap
                leads={visible}
                selectedId={selectedId}
                onSelect={onSelect}
                reduced={reduced}
                focusCity={selectedLocation?.name}
                territory={territory}
                onTerritoryChange={setTerritory}
                onViewportChange={setViewport}
              />
            </Suspense>
          </div>
        )}

        <section className="radar-results" aria-label={tr("Resultados")}>
          <header className="radar-results-head">
            <button
              className="sheet-handle"
              onPointerDown={(event) => {
                sheetDragStart.current = event.clientY;
                event.currentTarget.setPointerCapture?.(event.pointerId);
              }}
              onPointerUp={finishSheetDrag}
              onPointerCancel={() => {
                sheetDragStart.current = null;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  cycleMobileSheet();
                }
              }}
              aria-expanded={sheetExpanded}
              aria-label={tr(
                mobileSheet === "full"
                  ? "Recolher resultados"
                  : "Expandir resultados",
              )}
            >
              <i />
            </button>
            <div>
              <h2>
                {surface === "monitors" ? tr("Watchlist") : tr("Resultados")}{" "}
                <span>{visible.length}</span>
              </h2>
              <button
                className="icon-button"
                onClick={onAdd}
                aria-label={tr("Adicionar estabelecimento")}
              >
                <Plus size={18} />
              </button>
            </div>
            <label className="search-input">
              <Search size={16} />
              <input
                aria-label={tr("Filtrar estabelecimentos encontrados")}
                placeholder={tr("Filtrar empresas…")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            {searchIds !== null && (
              <button
                className="text-link"
                onClick={() => {
                  setSearchIds(null);
                  setSearchMeta(null);
                  setSearchError("");
                }}
              >
                {tr("Ver base local")}
              </button>
            )}
          </header>
          <div className="radar-result-scroll">
            {visible.length ? (
              visible.slice(0, visibleLimit).map((lead) => {
                const priority = getOpportunityPriority(lead.score);
                const brief = getOpportunityBrief(lead);
                return (
                  <article
                    className={`opportunity-row ${lead.id === selectedId ? "selected" : ""}`}
                    key={lead.id}
                  >
                    {!lead.demo && (
                      <label className="investigation-selection">
                        <input
                          type="checkbox"
                          aria-label={`Selecionar ${lead.name} para investigação`}
                          disabled={
                            investigationSelection.length >= 100 &&
                            !investigationSelection.includes(lead.id)
                          }
                          checked={investigationSelection.includes(lead.id)}
                          onChange={(e) =>
                            setInvestigationSelection((current) =>
                              e.target.checked
                                ? [...current, lead.id]
                                : current.filter((id) => id !== lead.id),
                            )
                          }
                        />
                      </label>
                    )}
                    <button
                      className="opportunity-row-main"
                      onClick={() => onSelect(lead)}
                      aria-label={`${tr("Abrir")} ${lead.name}`}
                    >
                      <span
                        className="opportunity-index"
                        data-priority={priority.level}
                      >
                        {lead.score.value}
                        <span className="sr-only">
                          /100 · {tr(priority.label)}
                        </span>
                      </span>
                      <span className="opportunity-row-copy">
                        <strong>{lead.name}</strong>
                        <span>
                          {lead.category} · {lead.city}
                        </span>
                        <small>
                          {tr(
                            brief.signals[0]?.label ||
                              "Dados ainda incompletos",
                          )}
                        </small>
                      </span>
                      <span className="opportunity-decision">
                        <span>{tr(priority.label)}</span>
                        <small>
                          {lead.next_action || tr("Revisar oportunidade")}
                        </small>
                      </span>
                      <ArrowUpRight className="row-arrow" size={17} />
                    </button>
                    <details className="result-actions-menu">
                      <summary aria-label={`${tr("Ações para")} ${lead.name}`}>
                        <MoreHorizontal size={19} />
                      </summary>
                      <div>
                        <button onClick={() => onSelect(lead)}>
                          {tr("Abrir contexto")}
                        </button>
                        <button
                          disabled={!!similarBusyId || lead.demo}
                          onClick={() => void findSimilar(lead)}
                        >
                          {tr("Semelhantes")}
                        </button>
                        {!lead.in_pipeline && lead.stage !== "won" && (
                          <button
                            disabled={busy}
                            onClick={() => onSaveOpportunity(lead)}
                          >
                            {tr("Salvar oportunidade")}
                          </button>
                        )}
                        <a
                          href={`https://www.google.com/search?q=${encodeURIComponent([lead.name, lead.address, lead.city, lead.country].filter(Boolean).join(" "))}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {tr("Pesquisar no Google")}
                        </a>
                      </div>
                    </details>
                    {surface !== "radar" && (
                      <div className="opportunity-row-context">
                        <span>{tr(priority.label)}</span>
                        <span>
                          {lead.score.service_scores[0]
                            ? tr(lead.score.service_scores[0].label)
                            : "—"}
                        </span>
                        <span>
                          {lead.in_pipeline
                            ? stageLabel(lead.stage)
                            : lead.demo
                              ? tr("Exemplo")
                              : tr("Só no Radar")}
                        </span>
                        {surface === "monitors" && lead.watch_last_event_at && (
                          <span>
                            {new Date(
                              lead.watch_last_event_at * 1000,
                            ).toLocaleDateString(activeLocale())}
                          </span>
                        )}
                      </div>
                    )}
                    {similarityById[lead.id] !== undefined && (
                      <small className="similarity-label">
                        {tr("Semelhança")}: {similarityById[lead.id]}%
                      </small>
                    )}
                  </article>
                );
              })
            ) : (
              <Empty
                title={tr("Nenhum resultado")}
                description={
                  surface === "monitors"
                    ? tr("Acompanhe uma empresa pelo painel de contexto.")
                    : tr("Ajuste os filtros ou inicie uma nova pesquisa.")
                }
                action={
                  <button
                    className="button"
                    onClick={() => {
                      clearResultFilters();
                      setQuery("");
                    }}
                  >
                    {tr("Limpar filtros")}
                  </button>
                }
              />
            )}
            {visible.length > visibleLimit && (
              <button
                className="button more-results"
                onClick={() => setVisibleLimit((value) => value + 60)}
              >
                {tr("Mostrar mais")} · {visible.length - visibleLimit}
              </button>
            )}
          </div>
          <footer className="radar-results-footer">
            {investigationSelection.length > 0 && (
              <button
                className="text-link"
                onClick={() => setInvestigationSelection([])}
              >
                Limpar seleção
              </button>
            )}
            <button
              className="text-link"
              disabled={
                agentBusy ||
                (!investigationSelection.length &&
                  !visible.some((lead) => !lead.demo))
              }
              onClick={() => void startAgentResearch()}
            >
              <Search size={16} />
              {investigationSelection.length
                ? `Investigar selecionadas (${investigationSelection.length})`
                : tr("Investigar melhores")}
            </button>
            <small>
              {leads.some((lead) => lead.demo) && tr("Inclui exemplos")}
            </small>
          </footer>
        </section>
      </div>
    </div>
  );
}
