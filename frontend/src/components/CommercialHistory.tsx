import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
} from "lucide-react";
import {
  type HistoryIntelligence,
  type HistoryPattern,
  type HistoryPatternKey,
} from "../historyIntelligence";
import { tr } from "../i18n";
import type { OutcomeInsights } from "../types";
import { activeLocale, stageLabel } from "../types";

const patternLabels: Record<HistoryPatternKey, string> = {
  proposal: "Proposta registrada",
  meeting: "Reunião registrada",
  reply: "Resposta registrada",
  follow_up: "Ao menos um follow-up",
  fast_first_contact: "Primeiro contato em até 1 dia",
};

function metric(value: number | null, unit = "") {
  if (value === null) return "—";
  return `${new Intl.NumberFormat(activeLocale(), { maximumFractionDigits: 1 }).format(value)}${unit}`;
}

function patternCopy(item: HistoryPattern) {
  const signal = item.deltaPp >= 0 ? "ganhos" : "perdas";
  return `${tr("Apareceu mais nos")} ${tr(signal)} · ${Math.abs(item.deltaPp)} p.p. ${tr("de diferença observada")}`;
}

export default function CommercialHistory({ intelligence, outcomes }: { intelligence: HistoryIntelligence; outcomes: OutcomeInsights }) {
  if (!intelligence.closedCount) return <p className="history-muted">Ainda não há desfechos datados neste período. As métricas de prospecção continuam disponíveis.</p>;
  const winRate = intelligence.closedCount
    ? Math.round((intelligence.wonCount / intelligence.closedCount) * 100)
    : 0;

  return (
    <div className="history-workspace">
      <section className="history-intro">
        <div>
          <span className="eyebrow">{tr("HISTÓRICO COMERCIAL")}</span>
          <h2>{tr("Padrões observados na sua operação")}</h2>
          <p>
            {tr(
              "O Scout compara comportamento e contexto de negociações já encerradas. Os números descrevem o seu histórico; não são previsão de fechamento nem alteram o Opportunity Score.",
            )}
          </p>
        </div>
        <span className="history-sample">
          {intelligence.closedCount} {tr("negociações fechadas")}
        </span>
      </section>


      <section className="history-summary" aria-label={tr("Resumo do histórico")}> 
        <div>
          <span>{tr("Desfechos")}</span>
          <strong>{intelligence.closedCount}</strong>
          <small>{intelligence.wonCount} {tr("ganhos")} · {intelligence.lostCount} {tr("perdas")}</small>
        </div>
        <div>
          <span>{tr("Taxa histórica observada")}</span>
          <strong>{winRate}%</strong>
          <small>{tr("sobre negociações encerradas")}</small>
        </div>
        <div>
          <span>{tr("Cobertura de atividades")}</span>
          <strong>{intelligence.activityCoverage}%</strong>
          <small>{tr("com atividades registradas")}</small>
        </div>
        <div>
          <span>{tr("Cobertura de snapshot")}</span>
          <strong>{outcomes?.snapshot_coverage ?? 0}%</strong>
          <small>{tr("contexto preservado no desfecho")}</small>
        </div>
      </section>

      {!intelligence.ready && (
        <section className="history-readiness">
          <Clock3 size={18} />
          <div>
            <strong>{tr("A amostra ainda é pequena para comparar comportamento com segurança")}</strong>
            <p>{tr("A comparação ganha força a partir de seis negociações encerradas, com pelo menos dois ganhos e duas perdas e atividades registradas.")}</p>
          </div>
        </section>
      )}

      <div className="history-grid">
        <section className="history-section">
          <div className="history-section-head">
            <div>
              <span className="eyebrow">{tr("CADÊNCIA")}</span>
              <h2>{tr("Como ganhos e perdas avançaram")}</h2>
            </div>
            <small>{tr("Medianas da amostra com atividades registradas")}</small>
          </div>
          <div className="history-comparison">
            <div className="history-comparison-head">
              <span>{tr("Métrica")}</span>
              <span>{tr("Ganhos")}</span>
              <span>{tr("Perdas")}</span>
            </div>
            {[
              ["Tempo até o primeiro contato", metric(intelligence.won.medianFirstContactDays, "d"), metric(intelligence.lost.medianFirstContactDays, "d")],
              ["Ciclo até o desfecho", metric(intelligence.won.medianCycleDays, "d"), metric(intelligence.lost.medianCycleDays, "d")],
              ["Interações antes do desfecho", metric(intelligence.won.medianInteractions), metric(intelligence.lost.medianInteractions)],
              ["Follow-ups antes do desfecho", metric(intelligence.won.medianFollowUps), metric(intelligence.lost.medianFollowUps)],
            ].map(([label, won, lost]) => (
              <div className="history-comparison-row" key={label}>
                <span>{tr(label)}</span>
                <strong>{won}</strong>
                <strong>{lost}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="history-section">
          <div className="history-section-head">
            <div>
              <span className="eyebrow">{tr("PERDAS")}</span>
              <h2>{tr("Etapa anterior ao encerramento")}</h2>
            </div>
            <small>{intelligence.lost.count} {tr("perdas com atividade registrada")}</small>
          </div>
          {intelligence.lossStages.length ? (
            <div className="history-loss-list">
              {intelligence.lossStages.map((item) => (
                <div className="history-loss-row" key={item.stage}>
                  <span>{item.stage === "unknown" ? tr("Etapa não identificada") : stageLabel(item.stage)}</span>
                  <div><i style={{ width: `${item.share}%` }} /></div>
                  <strong>{item.count}</strong>
                  <small>{item.share}%</small>
                </div>
              ))}
            </div>
          ) : (
            <p className="history-muted">{tr("Ainda não há transições suficientes para mostrar onde as perdas aconteceram.")}</p>
          )}
        </section>
      </div>

      <section className="history-section history-pattern-section">
        <div className="history-section-head">
          <div>
            <span className="eyebrow">{tr("COMPORTAMENTO")}</span>
            <h2>{tr("Diferenças que aparecem no histórico")}</h2>
          </div>
          <small>{tr("Correlação descritiva, não causalidade")}</small>
        </div>
        {intelligence.patterns.length ? (
          <div className="history-pattern-list">
            {intelligence.patterns.map((item) => (
              <article className="history-pattern-row" key={item.key}>
                <span className="history-pattern-icon" data-direction={item.deltaPp >= 0 ? "higher" : "lower"}>
                  {item.deltaPp >= 0 ? <ArrowUpRight size={17} /> : <ArrowDownRight size={17} />}
                </span>
                <div className="history-pattern-copy">
                  <strong>{tr(patternLabels[item.key])}</strong>
                  <p>{patternCopy(item)}</p>
                  <small>
                    {tr("Ganhos")}: {item.wonMatches}/{item.wonSample} · {tr("Perdas")}: {item.lostMatches}/{item.lostSample}
                  </small>
                </div>
                <div className="history-pattern-rates">
                  <span><small>{tr("Ganhos")}</small><b>{item.wonRate}%</b></span>
                  <span><small>{tr("Perdas")}</small><b>{item.lostRate}%</b></span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="history-muted">{tr("Registre mais ganhos, perdas e atividades para comparar padrões de abordagem.")}</p>
        )}
      </section>

      <section className="history-section">
        <div className="history-section-head">
          <div>
            <span className="eyebrow">{tr("PERFIL DAS OPORTUNIDADES")}</span>
            <h2>{tr("Contextos associados aos desfechos")}</h2>
          </div>
          <small>{tr("Snapshot do momento em que cada negociação foi encerrada")}</small>
        </div>
        {outcomes?.status === "ready" && outcomes.insights.length ? (
          <div className="history-context-list">
            {outcomes.insights.map((item) => (
              <article className="history-context-row" key={item.key}>
                <CheckCircle2 size={17} />
                <div>
                  <small>{tr(item.dimension)}</small>
                  <strong>{tr(item.value)}</strong>
                  <p>{tr(item.explanation)}</p>
                </div>
                <span>
                  <b>{item.win_rate}%</b>
                  <small>{item.delta_pp > 0 ? "+" : ""}{item.delta_pp} p.p. · n={item.sample}</small>
                </span>
              </article>
            ))}
          </div>
        ) : (
          <p className="history-muted">{tr("Ainda não há snapshots suficientes para comparar o perfil das oportunidades encerradas.")}</p>
        )}
        <p className="field-hint history-footnote">
          {tr("Use estes padrões para revisar processo e hipóteses comerciais. Eles não classificam pessoas, não garantem resultado e não mudam o score automaticamente.")}
        </p>
      </section>
    </div>
  );
}
