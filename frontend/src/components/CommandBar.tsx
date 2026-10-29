import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Search, Plus, Workflow, X } from "lucide-react";
import { api } from "../api";
import { tr } from "../i18n";
import { globalNavigation, navigation } from "../navigation";
import type { Campaign, Lead, Page } from "../types";
import { normalizeSearch } from "../search";
import { useDialogLifecycle } from "./dialogLifecycle";

export default function CommandBar({
  leads,
  onClose,
  navigate,
  onSelect,
  onAdd,
  onSearch,
}: {
  leads: Lead[];
  onClose: () => void;
  navigate: (page: Page) => void;
  onSelect: (lead: Lead) => void;
  onAdd: () => void;
  onSearch: (query: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useDialogLifecycle(dialog, true);
  useEffect(() => {
    let alive = true;
    api<Campaign[]>("/campaigns")
      .then((items) => {
        if (alive) setCampaigns(items);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);
  const results = useMemo(() => {
    const needle = normalizeSearch(query);
    const items = [...navigation, ...globalNavigation].map((item) => ({
      id: item.id as string,
      label: tr(item.label),
      meta: tr("Navegar"),
      icon: item.icon,
      run: () => navigate(item.id),
    }));
    items.push({
      id: "new",
      label: tr("Adicionar estabelecimento"),
      meta: tr("Ação"),
      icon: Plus,
      run: onAdd,
    });
    const matching = items.filter((item) =>
      normalizeSearch(item.label).includes(needle),
    );
    if (needle) {
      const matchingLeads = leads
        .filter((lead) =>
          normalizeSearch(
            [lead.name, lead.city, lead.address, lead.phone].join(" "),
          ).includes(needle),
        )
        .slice(0, 12)
        .map((lead) => ({
          id: lead.id,
          label: lead.name,
          meta: [
            lead.city,
            lead.address || lead.phone,
            lead.stage === "won" ? tr("Cliente") : tr("Empresa"),
          ]
            .filter(Boolean)
            .join(" · "),
          icon: Search,
          run: () => onSelect(lead),
        }));
      const matchingCampaigns = campaigns
        .filter((campaign) => normalizeSearch(campaign.name).includes(needle))
        .slice(0, 4)
        .map((campaign) => ({
          id: campaign.id,
          label: campaign.name,
          meta: tr("Campanha"),
          icon: Workflow,
          run: () => {
            navigate("campaigns");
            location.hash = `campaigns?campaign=${encodeURIComponent(campaign.id)}`;
          },
        }));
      matching.unshift(...matchingLeads, ...matchingCampaigns);
      matching.push({
        id: "search",
        label: `${tr("Pesquisar no Radar")}: ${query}`,
        meta: tr("Revisar critérios antes de buscar"),
        icon: Search,
        run: () => onSearch(query),
      });
    }
    return matching;
  }, [query, leads, campaigns, navigate, onAdd, onSelect, onSearch]);
  const selectedIndex = Math.min(active, Math.max(0, results.length - 1));
  useEffect(() => {
    dialog.current
      ?.querySelector(`#command-${selectedIndex}`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);
  function run(index: number) {
    const result = results[index];
    if (!result) return;
    onClose();
    result.run();
  }
  return (
    <dialog
      ref={dialog}
      className="command-surface"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      aria-label={tr("Busca e comandos")}
      onClick={(event) => {
        if (event.target === dialog.current) {
          const bounds = dialog.current.getBoundingClientRect();
          if (
            event.clientX < bounds.left ||
            event.clientX > bounds.right ||
            event.clientY < bounds.top ||
            event.clientY > bounds.bottom
          )
            onClose();
        }
      }}
    >
      <div className="command-input">
        <Search size={22} />
        <input
          ref={input}
          role="combobox"
          aria-label={tr("Buscar empresas ou comandos")}
          aria-controls="command-results"
          aria-expanded="true"
          aria-activedescendant={
            results.length ? `command-${selectedIndex}` : undefined
          }
          value={query}
          placeholder={tr("Empresa, cidade ou comando…")}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              setActive(
                (selectedIndex +
                  (event.key === "ArrowDown" ? 1 : -1) +
                  results.length) %
                  results.length,
              );
            }
            if (event.key === "Enter") {
              event.preventDefault();
              run(selectedIndex);
            }
          }}
        />
        <button
          className="icon-button"
          aria-label={tr("Fechar")}
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      <div
        className="command-results"
        id="command-results"
        role="listbox"
        aria-label={tr("Resultados")}
      >
        {results.map((item, index) => (
          <button
            id={`command-${index}`}
            role="option"
            aria-selected={index === selectedIndex}
            tabIndex={-1}
            className="command-result"
            key={item.id}
            onClick={() => run(index)}
            onPointerMove={() => setActive(index)}
          >
            <item.icon size={19} />
            <span>
              <b>{item.label}</b>
              <small>{item.meta}</small>
            </span>
            <ArrowUpRight size={16} />
          </button>
        ))}
      </div>
      <footer className="command-footer">
        <span>
          <kbd>↑ ↓</kbd> {tr("Selecionar")}
        </span>
        <span>
          <kbd>Enter</kbd> {tr("Abrir")}
        </span>
        <span>
          <kbd>Esc</kbd> {tr("Fechar")}
        </span>
      </footer>
    </dialog>
  );
}
