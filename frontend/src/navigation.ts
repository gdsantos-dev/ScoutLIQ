import {
  Radar,
  ScanLine,
  Bell,
  Target,
  ChartNoAxesCombined,
  Users,
  Globe,
  Wallet,
  Workflow,
  Settings,
  Info,
  PlugZap,
  ListTodo,
  History,
} from "lucide-react";
import type { Page } from "./types";
export type Environment = "operate" | "manage";
export const navigation = [
  { id: "radar", label: "Radar", icon: Radar, environment: "operate" },
  {
    id: "opportunities",
    label: "Oportunidades",
    icon: ScanLine,
    environment: "operate",
  },
  { id: "monitors", label: "Monitores", icon: Bell, environment: "operate" },
  { id: "campaigns", label: "Campanhas", icon: Target, environment: "operate" },
  { id: "actions", label: "Ações", mobileLabel: "Ações", icon: ListTodo, environment: "manage" },
  {
    id: "pipeline",
    label: "Negociações",
    mobileLabel: "Pipeline",
    icon: ChartNoAxesCombined,
    environment: "manage",
  },
  { id: "intelligence", label: "Histórico", mobileLabel: "Histórico", icon: History, environment: "manage" },
  { id: "clients", label: "Clientes", mobileLabel: "Clientes", icon: Users, environment: "manage" },
  {
    id: "sites",
    label: "Sites / Entregas",
    mobileLabel: "Entregas",
    icon: Globe,
    environment: "manage",
  },
  { id: "finance", label: "Financeiro", mobileLabel: "Financeiro", icon: Wallet, environment: "manage" },
] satisfies {
  id: Page;
  label: string;
  icon: typeof Radar;
  environment: Environment;
  mobileLabel?: string;
}[];
export const globalNavigation = [
  { id: "automations", label: "Automações", icon: Workflow },
  { id: "integrations", label: "Integrações", icon: PlugZap },
  { id: "settings", label: "Configurações", icon: Settings },
  { id: "about", label: "Sobre o ScoutLIQ", icon: Info },
] satisfies { id: Page; label: string; icon: typeof Radar }[];
export function pageFromHash(): Page {
  const key = location.hash.slice(1).split("?")[0];
  return (
    [...navigation, ...globalNavigation].find((item) => item.id === key)?.id ??
    "radar"
  );
}
export function environmentFor(page: Page): Environment | undefined {
  return navigation.find((item) => item.id === page)?.environment;
}
