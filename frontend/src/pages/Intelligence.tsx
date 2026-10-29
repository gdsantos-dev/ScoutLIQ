import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '../api';
import { PageHead } from '../components/UI';
import CommercialLearning from '../components/CommercialLearning';
import CommercialHistory from '../components/CommercialHistory';
import type { HistoryIntelligence } from '../historyIntelligence';
import type { OutcomeInsights } from '../types';
import { displayNumber, displayDuration, type OperationalMetric } from '../operationalIntelligence';
import './intelligence.css';

type Report = {
  generated_at:number; window:{period:string;origin:string;from_at:number;to_at:number;timezone:string};
  coverage:{companies:number;classified:number;multi_source:number;origin_unknown:number;demo_excluded:boolean};
  metrics:OperationalMetric[];
  rates:{key:string;label:string;numerator:number;denominator:number;value:number|null;population:string}[];
  times:{key:string;label:string;samples:number;seconds:number|null;population:string}[];
  providers:{provider:string;operations:number;failed:number;reserved:number;own_today:number;configured_daily_limit:number|null}[];
  averages:{key:string;label:string;total:number;samples:number;value:number|null}[];
  budgets:{configured_daily_operations:number;scope:string;monetary:null};
  diagnostics:{key:string;count:number;observation:string;consequence:string;action:string;href:string;population:string}[];
  cohorts:{dimension:string;group:string;companies:number;classified:number;opportunities:number;selected:number;known_outcomes:number;small_sample:boolean;groups_available:number}[];
  history:{intelligence:HistoryIntelligence;outcomes:OutcomeInsights}; limitations:string[];
};
const funnelKeys=['discovered','eligible','incorporated','investigations_started','investigations_completed','opportunities','reviewed','selected','drafts','contacts','replies','negotiating'];
const discoveryKeys=['unique','unlinked','duplicates','incomplete','qualification_coverage','insufficient_evidence'];
const efficiencyKeys=['companies_investigated','investigation_failures','investigation_cancelled','expired_attempts','investigation_queue','deepening','reuse','cache_avoided','empty_searches','provider_operations','provider_failures','source_limits','limit_or_configuration','monetary_cost','review_pending','drafts_unreviewed','followup_pending','tasks_completed','overdue','invalid_recipient'];
const qualityKeys=['deferred','not_priority','drafts_approved','contacts_declared','contacts_accepted','delivered','read','replies_provider','replies_declared','replies_uncertain','information_requests','meeting','proposal','won','lost','outcomes_undated','contact_blocked'];
const dimensions:Record<string,string>={origin:'Origem',strategy:'Estratégia',sector:'Setor',location:'Localização',level:'Nível de investigação',period:'Mês de entrada'};
const origins:Record<string,string>={search:'Busca',absorption:'Absorção',manual:'Entrada manual',unknown:'Origem desconhecida'};

function Metrics({rows,title}:{rows:OperationalMetric[];title:string}) {
  return <div className="intelligence-table" tabIndex={0} role="region" aria-label={title}><table>
    <caption>{title}</caption><thead><tr><th scope="col">Indicador</th><th scope="col">Quantidade</th><th scope="col">População e cobertura</th></tr></thead>
    <tbody>{rows.map(m=><tr key={m.key} data-metric={m.key}><th scope="row">{m.label}</th><td><strong>{displayNumber(m.value)}</strong><small>{m.unit}</small></td><td>{m.population}{m.status==='partial' && <small>Cobertura parcial</small>}{m.status==='unavailable' && <small>Não disponível</small>}</td></tr>)}</tbody>
  </table></div>;
}

export default function Intelligence() {
  const [period,setPeriod]=useState('30'),[origin,setOrigin]=useState('all'),[group,setGroup]=useState('funnel');
  const [report,setReport]=useState<Report|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[refresh,setRefresh]=useState(0);
  const [dimension,setDimension]=useState('strategy');
  useEffect(()=>{
    let alive=true;setLoading(true);setError('');setReport(null);
    void api<Report>(`/insights/operations?period=${period}&origin=${origin}`).then(value=>{if(alive)setReport(value);})
      .catch(()=>{if(alive)setError('Não foi possível carregar os indicadores. Tente novamente.');}).finally(()=>{if(alive)setLoading(false);});
    return ()=>{alive=false;};
  },[period,origin,refresh]);
  const subset=(keys:string[])=>keys.flatMap(key=>report?.metrics.filter(m=>m.key===key)||[]);
  return <div className="history-workspace operational-intelligence">
    <PageHead title="Inteligência"><button className="button compact" disabled={loading} onClick={()=>setRefresh(v=>v+1)}><RefreshCw size={15} className={loading?'spin':''}/>Atualizar indicadores</button></PageHead>
    <div className="intelligence-filters"><label>Período<select value={period} onChange={e=>setPeriod(e.target.value)}><option value="7">Últimos 7 dias</option><option value="30">Últimos 30 dias</option><option value="90">Últimos 90 dias</option><option value="history">Histórico disponível</option></select></label>
      <label>Origem<select value={origin} onChange={e=>setOrigin(e.target.value)}><option value="all">Todas as origens</option><option value="search">Busca</option><option value="absorption">Absorção</option><option value="manual">Entrada manual</option></select></label>
    </div>
    <div className="intelligence-groups" role="group" aria-label="Conjuntos de indicadores">{[['funnel','Funil'],['efficiency','Eficiência'],['quality','Qualidade comercial']].map(([id,label])=><button key={id} type="button" className="button compact" aria-pressed={group===id} onClick={()=>setGroup(id)}>{label}</button>)}</div>
    {loading && <p role="status">Carregando indicadores…</p>}
    {error && <div role="alert" className="action-error"><p>{error}</p><button className="button" onClick={()=>setRefresh(v=>v+1)}>Tentar novamente</button></div>}
    {report && <>
      <p className="intelligence-coverage">{displayNumber(report.coverage.companies)} empresas na origem selecionada · {displayNumber(report.coverage.classified)} com classificação vigente · Fuso {report.window.timezone}</p>
      {!report.coverage.companies && <p role="status">Nenhuma empresa incorporada nesta origem. Registros recebidos ainda sem vínculo podem aparecer abaixo.</p>}
      {group==='funnel' && <section aria-label="Funil operacional"><p>As etapas podem ocorrer fora de ordem. Cada indicador informa sua população; pendências atuais incluem empresas anteriores ao período.</p>
        <Metrics title="Etapas observadas" rows={subset(funnelKeys)}/>
        <h2>Taxas observáveis</h2><div className="intelligence-rates">{report.rates.map(r=><div key={r.key}><h3>{r.label}</h3><strong>{r.value===null?'Sem base':displayNumber(r.value)+'%'}</strong><p>{r.numerator} / {r.denominator} · {r.population}</p></div>)}</div>
        <details><summary>Identidade, duplicação e cobertura</summary><p>{report.coverage.multi_source} empresas em mais de uma origem · {report.coverage.origin_unknown} sem origem classificável. A visão consolidada conta cada ID uma vez.</p><Metrics title="Cobertura da descoberta" rows={subset(discoveryKeys)}/></details>
      </section>}
      {group==='efficiency' && <section aria-label="Eficiência operacional"><h2>Tempos observados</h2><p>Medianas de tempo de calendário. Não medem trabalho humano nem minutos economizados.</p>
        <div className="intelligence-table" tabIndex={0} role="region" aria-label="Tempos observados"><table><thead><tr><th scope="col">Intervalo</th><th scope="col">Mediana</th><th scope="col">Amostra e cobertura</th></tr></thead><tbody>{report.times.map(t=><tr key={t.key}><th scope="row">{t.label}</th><td>{displayDuration(t.seconds)}</td><td>n={t.samples} · {t.population}</td></tr>)}</tbody></table></div>
        <h2>Consumo do worker</h2><p>{report.budgets.scope} Limite global configurado: {report.budgets.configured_daily_operations} operações/dia UTC.</p>
        <div className="intelligence-table" tabIndex={0} role="region" aria-label="Consumo por provedor"><table><thead><tr><th scope="col">Provedor</th><th scope="col">Operações no período</th><th scope="col">Falhas / sem conclusão</th><th scope="col">Conta hoje UTC / limite global</th></tr></thead><tbody>{report.providers.map(p=><tr key={p.provider}><th scope="row">{p.provider}</th><td>{p.operations}</td><td>{p.failed} / {p.reserved}</td><td>{p.own_today} / {p.configured_daily_limit??'Desconhecido'}</td></tr>)}</tbody></table></div>
        {report.averages.map(a=><p key={a.key}>{a.label}: <strong>{displayNumber(a.value)}</strong> · {a.total} operações / {a.samples} unidades observadas.</p>)}
        <Metrics title="Processamento e pendências" rows={subset(efficiencyKeys)}/>
      </section>}
      {group==='quality' && <section aria-label="Qualidade comercial"><Metrics title="Registros comerciais e proveniência" rows={subset(qualityKeys)}/>
        <h2>Comparação descritiva</h2><label className="intelligence-dimension">Agrupar empresas por<select value={dimension} onChange={e=>setDimension(e.target.value)}>{Object.entries(dimensions).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
        <p>Empresas incorporadas no período e estado atual; níveis usam investigações iniciadas. Grupos podem se sobrepor. Até 30 grupos por dimensão. Não há ranking causal.</p>
        <div className="intelligence-table" tabIndex={0} role="region" aria-label="Comparação de grupos"><table><thead><tr><th scope="col">Grupo</th><th scope="col">Empresas / classificadas</th><th scope="col">Prioritárias / selecionadas</th><th scope="col">Desfechos datados</th></tr></thead><tbody>{report.cohorts.filter(c=>c.dimension===dimension).map(c=><tr key={c.group}><th scope="row">{origins[c.group]||c.group}{c.small_sample&&<small>Amostra pequena</small>}</th><td>{c.companies} / {c.classified}</td><td>{c.opportunities} / {c.selected}</td><td>{c.known_outcomes}</td></tr>)}</tbody></table></div>
        {!report.cohorts.some(c=>c.dimension===dimension)&&<p>Sem amostra nesta dimensão e período.</p>}
        <h2>Gargalos observados</h2>{!report.diagnostics.length&&<p>Nenhuma pendência mensurável nesta consulta.</p>}
        <ul className="intelligence-diagnostics">{report.diagnostics.map(d=><li key={d.key}><h3>{d.count} · {d.observation}</h3><p>{d.consequence}</p><p>{d.population}</p><a href={d.href}>{d.action}</a></li>)}</ul>
        <details><summary>Comportamento de negociações encerradas</summary><CommercialHistory {...report.history}/></details>
        <CommercialLearning/>
      </section>}
      <details className="intelligence-limitations"><summary>Contratos e limites dos indicadores</summary><ul>{report.limitations.map(text=><li key={text}>{text}</li>)}</ul><p>Consulta em {new Date(report.generated_at*1000).toLocaleString('pt-BR',{timeZone:report.window.timezone})}. Demonstrações identificadas excluídas.</p></details>
    </>}
  </div>;
}
