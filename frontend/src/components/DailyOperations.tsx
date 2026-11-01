import './daily-operations.css';
export type DailySnapshot = {
  day:string; timezone:string; incorporated:number; plan_incorporated:number; other_incorporated:number;
  discarded:number; investigating:number; investigated:number; qualified:number; ready:number; plan_ready:number; needs_data:number; index_pending:number;
  plan:{state:string; target:number; reason:string; operations:number}|null;
  searches:{id:string;status:string;new:number;reencounters:number;reason:string;batch_id:string|null;run_id:string|null;plan:boolean}[];
  searches_truncated:boolean; decisions:{action:string;reason:string;at:number}[];
  operations:{id:string;action:string;status:string;failures:{status:string;reason:string}[]}[]; operations_truncated:boolean;
};
const statuses:Record<string,string>={pending:'Aguardando executor',running:'Descobrindo empresas',investigating:'Investigação em andamento',paused:'Pausada',completed:'Concluída',partial:'Parcial',cancelled:'Cancelada',active:'Ativo',disabled:'Desativado'};
export default function DailyOperations({data,onFilter,onInvestigation,onOperation,onDiscovery}:{data:DailySnapshot;onFilter:(cohort:string,focus:string,classification?:string)=>void;onInvestigation?:(id?:string)=>void;onOperation:(id:string)=>void;onDiscovery?:()=>void}){
  const state=data.plan;
  return <section className="daily-operations" aria-label="Resumo da operação diária">
    <header><div><h2>Operação do dia</h2><p>{data.day.split('-').reverse().join('/')} · {data.timezone}</p></div><a className="button compact" href="#automations">Gerir plano e rotinas</a></header>
    <div className="daily-goal"><strong>{data.incorporated}{state?` / ${state.target}`:''}</strong><span>Empresas novas{state?' · meta diária':' · sem meta configurada'}</span>{state&&<span>{statuses[state.state]||state.state}</span>}</div>
    {state&&<p className="daily-state">{state.reason||'Plano configurado; consulte as rotinas autorizadas.'}</p>}
    <dl className="daily-counts">
      <div><dt>Do plano</dt><dd><button aria-label={`Filtrar empresas do plano: ${data.plan_incorporated}`} onClick={()=>onFilter('plan','all')}>{data.plan_incorporated}</button></dd></div>
      <div><dt>Outras origens</dt><dd><button aria-label="Abrir empresas no Radar" onClick={onDiscovery} disabled={!onDiscovery}>{data.other_incorporated}</button></dd></div>
      <div><dt>Em investigação</dt><dd><button aria-label="Abrir fila de investigação" onClick={()=>onInvestigation?.()} disabled={!onInvestigation}>{data.investigating}</button></dd></div>
      <div><dt>Investigadas</dt><dd><button aria-label="Abrir fila de investigação" onClick={()=>onInvestigation?.()} disabled={!onInvestigation}>{data.investigated}</button></dd></div>
      <div><dt>Qualificadas</dt><dd><button aria-label={`Filtrar atenção de oportunidades qualificadas: ${data.qualified}`} onClick={()=>onFilter('today','all','priority')}>{data.qualified}</button></dd></div>
      <div><dt>Prontas para revisão</dt><dd><button aria-label={`Filtrar prontas para revisão: ${data.ready}`} onClick={()=>onFilter('today','ready')}>{data.ready}</button></dd></div>
    </dl>
    <p className="daily-context">{data.incorporated} empresas incorporadas hoje. Estados atuais. {data.plan_ready} prontas atribuídas ao plano. {data.discarded} descartadas fora da meta.</p>
    {data.index_pending>0&&<p role="status">Classificação parcial: {data.index_pending} empresas novas aguardam atualização local.</p>}
    <details><summary>Pesquisas e decisões do plano</summary>
      {!data.searches.length&&<p>Nenhuma pesquisa de hoje ou em aberto.</p>}
      <ul className="daily-searches">{data.searches.map((s,i)=><li key={s.id}><div><strong>Pesquisa {i+1} · {s.plan?'Plano diário':'Outra origem'}</strong><span>{statuses[s.status]||s.status}</span><p>{s.new} novas · {s.reencounters} reencontradas{ s.reason?` · ${s.reason}`:''}</p></div>{s.batch_id&&onInvestigation?<button className="button compact" onClick={()=>onInvestigation(s.batch_id!)}>Ver investigação</button>:<button className="button compact" onClick={onDiscovery} disabled={!onDiscovery}>Ver pesquisas</button>}</li>)}</ul>
      {data.searches_truncated&&<p>Exibindo as 20 pesquisas mais recentes ou abertas. Consulte o histórico de pesquisas.</p>}
      {data.decisions.length>0&&<ul>{data.decisions.map((d,i)=><li key={i}>{d.reason}</li>)}</ul>}
    </details>
    {data.operations.length>0&&<details><summary>Operações comerciais recentes do dia</summary><ul>{data.operations.map(o=><li key={o.id}><button className="button compact" onClick={()=>onOperation(o.id)}>{o.status==='preview'?'Retomar prévia':'Consultar resultado'}{o.failures.length?` · ${o.failures.length} pendências`:''}</button>{o.failures.map((f,i)=><p key={i}>{f.reason}</p>)}</li>)}</ul>{data.operations_truncated&&<p>Exibindo cinco operações. O histórico completo permanece em Operações recentes.</p>}</details>}
  </section>;
}
