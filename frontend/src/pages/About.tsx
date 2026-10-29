import { tr } from "../i18n";
import {
  Activity,
  Building2,
  Database,
  ExternalLink,
  Globe2,
  Mail,
  MapPinned,
  Search,
  Radar,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import type { User } from "../types";
import { Brand, Mark, PageHead } from "../components/UI";

const VERSION = "1.38.7-dev";

function runtimeEnvironment() {
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1")
    return tr("Desenvolvimento");
  return tr("Produção");
}

export default function About({ user }: { user: User }) {
  const origin = window.location.origin;
  const environment = runtimeEnvironment();

  return (
    <>
      <PageHead title={tr("Sobre o ScoutLIQ")} eyebrow="ORLIQ" />

      <section className="about-hero" aria-labelledby="about-product-title">
        <div className="about-hero-copy">
          <span className="about-product-mark" aria-hidden="true">
            <Mark />
          </span>
          <div>
            <p className="eyebrow">{tr("UM PRODUTO ORLIQ")}</p>
            <h2 id="about-product-title">
              <Brand />
            </h2>
            <p>
              {tr(
                "Ferramenta operacional para descobrir estabelecimentos, qualificar oportunidades, acompanhar negociações, clientes, sites e resultados financeiros.",
              )}
            </p>
          </div>
        </div>
        <div className="about-release" aria-label={tr("Informações da versão")}>
          <div>
            <span>{tr("Versão")}</span>
            <strong>{VERSION}</strong>
          </div>
          <div>
            <span>{tr("Ambiente")}</span>
            <strong>{environment}</strong>
          </div>
          <div>
            <span>{tr("Domínio")}</span>
            <a href={origin} target="_blank" rel="noopener noreferrer">
              {window.location.host}
              <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </section>

      <div className="about-layout">
        <section className="about-section" aria-labelledby="about-does-title">
          <div className="about-section-head">
            <Radar size={19} />
            <div>
              <p className="eyebrow">{tr("Produto").toUpperCase()}</p>
              <h2 id="about-does-title">{tr("O que o ScoutLIQ faz")}</h2>
            </div>
          </div>
          <div className="about-capabilities">
            <div>
              <strong>{tr("Radar")}</strong>
              <p>
                {tr(
                  "Descobre estabelecimentos em toda a região selecionada, por localização e nicho.",
                )}
              </p>
            </div>
            <div>
              <strong>{tr("Ações")}</strong>
              <p>
                {tr(
                  "Organiza o que precisa ser feito agora, com prioridade explicável e ações comerciais rápidas.",
                )}
              </p>
            </div>
            <div>
              <strong>{tr("Pipeline")}</strong>
              <p>
                {tr(
                  "Acompanha cada oportunidade desde a descoberta até o fechamento.",
                )}
              </p>
            </div>
            <div>
              <strong>{tr("Histórico")}</strong>
              <p>
                {tr(
                  "Compara cadência, atividades e contexto de ganhos e perdas sem criar previsões opacas.",
                )}
              </p>
            </div>
            <div>
              <strong>{tr("Clientes e Sites")}</strong>
              <p>
                {tr(
                  "Organiza vendas, entregas, recebimentos e projetos vinculados.",
                )}
              </p>
            </div>
            <div>
              <strong>{tr("Financeiro")}</strong>
              <p>
                {tr(
                  "Consolida vendas, despesas, recebimentos e indicadores da operação.",
                )}
              </p>
            </div>
          </div>
        </section>

        <section className="about-section" aria-labelledby="about-stack-title">
          <div className="about-section-head">
            <Workflow size={19} />
            <div>
              <p className="eyebrow">{tr("Infraestrutura").toUpperCase()}</p>
              <h2 id="about-stack-title">{tr("Serviços da versão atual")}</h2>
            </div>
          </div>
          <dl className="about-facts">
            <div>
              <dt>
                <MapPinned size={16} />
                {tr("Mapa")}
              </dt>
              <dd>MapTiler + MapLibre</dd>
            </div>
            <div>
              <dt>
                <Globe2 size={16} />
                {tr("Estabelecimentos")}
              </dt>
              <dd>Geoapify</dd>
            </div>
            <div>
              <dt>
                <Search size={16} />
                {tr("Pesquisa web")}
              </dt>
              <dd>{tr("Validação direta + Brave opcional")}</dd>
            </div>
            <div>
              <dt>
                <Mail size={16} />
                {tr("E-mails transacionais")}
              </dt>
              <dd>Brevo</dd>
            </div>
            <div>
              <dt>
                <Database size={16} />
                {tr("Dados")}
              </dt>
              <dd>{tr("Workspace isolado por conta")}</dd>
            </div>
          </dl>
        </section>

        <section
          className="about-section about-wide"
          aria-labelledby="about-workspace-title"
        >
          <div className="about-section-head">
            <Building2 size={19} />
            <div>
              <p className="eyebrow">{tr("SEU WORKSPACE")}</p>
              <h2 id="about-workspace-title">{tr("Operação atual")}</h2>
            </div>
          </div>
          <div className="about-workspace-row">
            <div>
              <span>{tr("Operação")}</span>
              <strong>{user.name}</strong>
            </div>
            <div>
              <span>{tr("Conta")}</span>
              <strong>{user.email}</strong>
            </div>
            <div>
              <span>{tr("Fuso horário")}</span>
              <strong>{user.timezone}</strong>
            </div>
            <div>
              <span>{tr("Idioma")}</span>
              <strong>{user.locale}</strong>
            </div>
            <div>
              <span>{tr("Moeda padrão")}</span>
              <strong>{user.default_currency}</strong>
            </div>
          </div>
        </section>

        <section
          className="about-section about-principles"
          aria-labelledby="about-principles-title"
        >
          <div className="about-section-head">
            <ShieldCheck size={19} />
            <div>
              <p className="eyebrow">{tr("PRINCÍPIOS")}</p>
              <h2 id="about-principles-title">
                {tr("Como o produto trata seus dados")}
              </h2>
            </div>
          </div>
          <p>
            {tr(
              "Os dados da sua operação permanecem vinculados ao seu workspace. O ScoutLIQ evita inventar informações de estabelecimentos: quando uma fonte não confirma um dado, o sistema o mantém como desconhecido até nova verificação.",
            )}
          </p>
        </section>

        <section
          className="about-section about-status"
          aria-labelledby="about-status-title"
        >
          <div className="about-section-head">
            <Activity size={19} />
            <div>
              <p className="eyebrow">{tr("ESTADO DO PRODUTO")}</p>
              <h2 id="about-status-title">ScoutLIQ v1</h2>
            </div>
          </div>
          <p>
            {tr(
              "Radar, Pipeline, Clientes, Sites, Financeiro, autenticação e exportação de dados compõem a versão operacional atual.",
            )}
          </p>
          <span className="about-orliq-signature">ORLIQ · 2026</span>
        </section>
      </div>
    </>
  );
}
