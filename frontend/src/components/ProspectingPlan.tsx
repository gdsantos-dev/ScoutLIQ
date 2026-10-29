import { useEffect, useState } from 'react';
import { api } from '../api';
import './prospecting-plan.css';

type Member = {saved_search_id:string; priority:number};
type Config = {daily_target:number;members:Member[];locations:string[];weekdays:number[];window_start:string;window_end:string;daily_runs:number;companies_per_search:number;daily_investigations:number;daily_operations:number;cooldown_hours:number};
type Option = {id:string;name:string;location:string;reason:string;provider:string|null;limits:Record<string,number|string>|null;coverage:{sector:string;coverage:string}[]};
type Progress = {day:string;incorporated:number;plan_incorporated:number;other_incorporated:number;discarded_excluded:number;runs:number;completed:number;finished:number;running:number;deferred:number;investigations_started:number;investigations_pending:number;operations:number};
type Plan = {version:number;state:string;config:Config|null;timezone?:string;reason:string;next_at?:number;progress:Progress|null;historical_targets?:number[];history_truncated?:boolean;history:{at:number;action:string;reason:string;run_id:string|null;details:{target:number;saved_search_id?:string;searches?:{id:string;reason:string}[];skipped?:{id:string;reason:string}[]}}[]};
type Preview = {token:string;blockers:string[];members:Option[];restrictions:string[];global_limits:{tasks:number;operations:number;providers:Record<string,number>};timezone:string};
type Suggestion = {key:string;count:number;observation:string;action:string;population:string;from_at:number;to_at:number;href:string};
const defaults:Config = {daily_target:50,members:[],locations:[],weekdays:[0,1,2,3,4],window_start:'09:00',window_end:'18:00',daily_runs:4,companies_per_search:50,daily_investigations:15,daily_operations:100,cooldown_hours:24};
const states:Record<string,string>={disabled:'Desativado',active:'Ativo',paused:'Pausado'};
const days=['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'];

export default function ProspectingPlan() {
  const [plan,setPlan]=useState<Plan|null>(null), [options,setOptions]=useState<Option[]>([]);
  const [form,setForm]=useState<Config>(defaults),[editing,setEditing]=useState(false);
  const [preview,setPreview]=useState<Preview|null>(null),[consent,setConsent]=useState(false);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[day,setDay]=useState('');
  const [suggestions,setSuggestions]=useState<{suggestions:Suggestion[];small_sample:boolean;limitation:string}|null>(null);
  const [truncated,setTruncated]=useState(false);
  const stamp=(at:number)=>new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'short',timeZone:plan?.timezone||'America/Sao_Paulo'}).format(at*1000);
  async function load(chosen=day) {
    setError('');
    try {
      const [p,o]=await Promise.all([api<Plan>('/operations/plan'+(chosen?'?day='+chosen:'')),api<{items:Option[];truncated:boolean}>('/operations/plan/options')]);
      setPlan(p);setOptions(o.items);setTruncated(o.truncated);setForm(p.config||defaults);
    } catch(e) {setError((e as Error).message)} finally {setLoading(false)}
  }
  useEffect(()=>{void load('')},[]);
  useEffect(()=>{
    if(plan?.state!=='active'||day)return;
    let live=true;
    const timer=window.setInterval(()=>{
      if(document.visibilityState!=='visible')return;
      void api<Plan>('/operations/plan').then(p=>{if(live)setPlan(previous=>!previous||p.version>=previous.version?p:previous)}).catch(e=>{if(live)setError((e as Error).message)});
    },15000);
    return()=>{live=false;window.clearInterval(timer)};
  },[plan?.state,day]);
  async function perform(action:()=>Promise<void>) {
    if(busy)return; setBusy(true);setError('');
    try {await action()} catch(e) {setError((e as Error).message)} finally {setBusy(false)}
  }
  function patch(values:Partial<Config>) {setForm(f=>({...f,...values}));setPreview(null);setConsent(false)}
  function toggleMember(option:Option,checked:boolean) {
    patch({members:checked?[...form.members,{saved_search_id:option.id,priority:1}]:form.members.filter(m=>m.saved_search_id!==option.id)});
  }
  async function save() {
    const selectedLocations=new Set(form.members.map(m=>options.find(o=>o.id===m.saved_search_id)?.location));
    if(form.locations.some(l=>!selectedLocations.has(l))||!form.members.length) throw new Error('Selecione ao menos uma pesquisa para cada local.');
    const saved=await api<Plan>('/operations/plan','PUT',{version:plan?.version||0,config:form});
    setPlan(saved);setEditing(false);setPreview(null);setDay('');
  }
  async function control(action:string) {
    const saved=await api<Plan>('/operations/plan/control','POST',{version:plan?.version,action,confirm:consent,preview_token:preview?.token||''});
    setPlan(saved);setPreview(null);setConsent(false);setDay('');
  }
  const progress=plan?.progress;
  return <section className="panel prospecting-plan" aria-labelledby="prospecting-title">
    <header className="plan-heading"><div><h2 id="prospecting-title">Planejamento de prospecção</h2><span>{states[plan?.state||'disabled']}</span></div>
      <button className="button secondary" type="button" disabled={busy||loading} onClick={()=>void perform(()=>load())}>Atualizar plano</button>
    </header>
    {error&&<div role="alert" className="error-text">{error}</div>}
    {loading?<p role="status">Carregando planejamento…</p>:<>
      <p role="status">{plan?.reason}</p>
      {progress&&<>
        <div className="plan-progress"><strong>{progress.incorporated} / {day?(plan?.historical_targets?.join(' · ')||'meta sem registro'):plan?.config?.daily_target}</strong><span>empresas novas no Radar{day?' · '+progress.day:''}</span></div>
        <dl className="plan-totals">
          <div><dt>Incorporadas pelo plano</dt><dd>{progress.plan_incorporated}</dd></div>
          <div><dt>Outras incorporações</dt><dd>{progress.other_incorporated}</dd></div>
          <div><dt>Descartados fora da meta</dt><dd>{progress.discarded_excluded}</dd></div>
          <div><dt>Pesquisas encerradas / em execução</dt><dd>{progress.finished} / {progress.running}</dd></div>
          <div><dt>Pesquisas com meta própria concluída</dt><dd>{progress.completed}</dd></div>
          <div><dt>Decisões de adiamento</dt><dd>{progress.deferred}</dd></div>
          <div><dt>Investigações iniciadas pelo plano</dt><dd>{progress.investigations_started}</dd></div>
          <div><dt>Investigações pendentes na conta</dt><dd>{progress.investigations_pending}</dd></div>
          <div><dt>Operações do plano</dt><dd>{progress.operations}{!day&&` / ${plan?.config?.daily_operations}`}</dd></div>
        </dl>
        {plan?.next_at&&<p className="muted">Próxima avaliação prevista: {stamp(plan.next_at)}. Depende da janela, do executor e dos limites.</p>}
      </>}
      <div className="plan-actions">
        {plan?.state!=='active'&&<button type="button" className="button secondary" disabled={busy} onClick={()=>{setEditing(!editing);setPreview(null)}}>{plan?.config?'Editar plano':'Configurar plano'}</button>}
        {plan?.config&&plan.state!=='active'&&!editing&&<button type="button" className="button primary" disabled={busy} onClick={()=>void perform(async()=>{setPreview(await api<Preview>('/operations/plan/preview'));setConsent(false)})}>Revisar {plan.state==='paused'?'retomada':'ativação'}</button>}
        {plan?.state==='active'&&<><button type="button" className="button secondary" disabled={busy} onClick={()=>void perform(()=>control('run_now'))}>Solicitar um ciclo</button><button type="button" className="button secondary" disabled={busy} onClick={()=>void perform(()=>control('pause'))}>Pausar plano</button></>}
        {plan?.state==='paused'&&<button type="button" className="button secondary" disabled={busy} onClick={()=>void perform(()=>control('disable'))}>Desativar plano e liberar recorrências originais</button>}
      </div>
      {editing&&<form onSubmit={e=>{e.preventDefault();void perform(save)}} className="plan-form">
        <div className="plan-fields">
          <label>Meta diária<input type="number" list="plan-targets" min="1" max="500" required value={form.daily_target} onChange={e=>patch({daily_target:Number(e.target.value)})}/><datalist id="plan-targets">{[25,50,75,100].map(n=><option key={n} value={n}/>)}</datalist></label>
          <label>Execuções por dia<input type="number" min="1" max="20" required value={form.daily_runs} onChange={e=>patch({daily_runs:Number(e.target.value)})}/></label>
          <label>Empresas por pesquisa<input type="number" min="1" max="100" required value={form.companies_per_search} onChange={e=>patch({companies_per_search:Number(e.target.value)})}/></label>
          <label>Investigações por dia<input type="number" min="0" max="100" required value={form.daily_investigations} onChange={e=>patch({daily_investigations:Number(e.target.value)})}/></label>
          <label>Operações por dia<input type="number" min="1" max="1000" required value={form.daily_operations} onChange={e=>patch({daily_operations:Number(e.target.value)})}/></label>
          <label>Repetir após (horas)<input type="number" min="24" max="2160" required value={form.cooldown_hours} onChange={e=>patch({cooldown_hours:Number(e.target.value)})}/></label>
          <label>Início da janela<input type="time" required value={form.window_start} onChange={e=>patch({window_start:e.target.value})}/></label>
          <label>Fim da janela<input type="time" required value={form.window_end} onChange={e=>patch({window_end:e.target.value})}/></label>
        </div>
        <fieldset><legend>Dias de execução</legend><div className="plan-checks">{days.map((d,i)=><label key={d}><input type="checkbox" checked={form.weekdays.includes(i)} onChange={e=>patch({weekdays:e.target.checked?[...form.weekdays,i]:form.weekdays.filter(n=>n!==i)})}/>{d}</label>)}</div></fieldset>
        <fieldset><legend>Localizações autorizadas</legend><div className="plan-checks">{[...new Set(options.map(o=>o.location).filter(Boolean))].map(l=><label key={l}><input type="checkbox" checked={form.locations.includes(l)} onChange={e=>patch({locations:e.target.checked?[...form.locations,l]:form.locations.filter(x=>x!==l),members:e.target.checked?form.members:form.members.filter(m=>options.find(o=>o.id===m.saved_search_id)?.location!==l)})}/>{l}</label>)}</div></fieldset>
        <fieldset><legend>Pesquisas participantes</legend>
          {!options.length&&<p>Salve uma pesquisa na Busca Unificada e configure sua rotina abaixo.</p>}
          {truncated&&<p>Mostrando as primeiras 200 pesquisas por nome.</p>}
          {form.members.filter(m=>!options.some(o=>o.id===m.saved_search_id)).map(m=><div className="plan-actions" key={m.saved_search_id}><span>Uma pesquisa selecionada não está na lista disponível.</span><button type="button" className="button secondary" onClick={()=>patch({members:form.members.filter(item=>item.saved_search_id!==m.saved_search_id)})}>Remover pesquisa não listada</button></div>)}
          <div className="plan-searches">{options.map(o=><div key={o.id}>
            <label><input type="checkbox" checked={form.members.some(m=>m.saved_search_id===o.id)} disabled={!form.locations.includes(o.location)} onChange={e=>toggleMember(o,e.target.checked)}/><span>{o.name}<small>{o.location}{o.reason?' · '+o.reason:''}</small></span></label>
            {form.members.some(m=>m.saved_search_id===o.id)&&<label>Prioridade de {o.name}<select value={form.members.find(m=>m.saved_search_id===o.id)?.priority} onChange={e=>patch({members:form.members.map(m=>m.saved_search_id===o.id?{...m,priority:Number(e.target.value)}:m)})}>{[1,2,3,4,5].map(n=><option key={n} value={n}>{n}{n===5?' · maior':''}</option>)}</select></label>}
          </div>)}</div>
        </fieldset>
        <div className="plan-actions"><button className="button primary" disabled={busy||!form.members.length||!form.weekdays.length}>Salvar configuração</button><button type="button" className="button secondary" onClick={()=>{setEditing(false);setForm(plan?.config||defaults)}}>Cancelar edição</button></div>
      </form>}
      {preview&&<section className="plan-preview" aria-label="Prévia de autorização">
        <h3>Autorizar {plan?.state==='paused'?'retomada':'planejamento'}</h3>
        <p>Meta: {plan?.config?.daily_target} empresas novas por dia. Até {plan?.config?.daily_runs} execuções, {plan?.config?.daily_operations} operações e {plan?.config?.daily_investigations} investigações.</p>
        <p>{plan?.config?.weekdays.map(n=>days[n]).join(', ')} · {plan?.config?.window_start}–{plan?.config?.window_end} · {preview.timezone}. Cooldown mínimo: {plan?.config?.cooldown_hours} h.</p>
        <ul>{preview.members.map(m=><li key={m.id}><strong>{m.name||'Pesquisa indisponível'}</strong> · {m.location} · {m.provider||'Sem fonte'}{m.limits&&<span> · intervalo {m.limits.interval_hours} h; até {m.limits.operation_limit} operações/execução, {m.limits.daily_operation_limit}/dia e {m.limits.duration_minutes} min.</span>}{m.coverage?.map((c,i)=><small key={i}>{c.coverage}</small>)}</li>)}</ul>
        <p>Worker: até {preview.global_limits.tasks} tarefas e {preview.global_limits.operations} operações/dia UTC. Fontes: {Object.entries(preview.global_limits.providers).map(([k,v])=>`${k}: ${v}`).join('; ')}. Sem estimativa monetária.</p>
        <ul>{preview.restrictions.map(r=><li key={r}>{r}</li>)}</ul>
        {!!preview.blockers.length&&<div role="alert"><strong>Ativação bloqueada</strong><ul>{preview.blockers.map(b=><li key={b}>{b}</li>)}</ul></div>}
        <label className="plan-consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>Autorizo a execução recorrente destas pesquisas dentro dos limites apresentados.</label>
        <button type="button" className="button primary" disabled={busy||!consent||!!preview.blockers.length} onClick={()=>void perform(()=>control(plan?.state==='paused'?'resume':'activate'))}>Confirmar autorização</button>
      </section>}
      {plan?.config&&<details className="plan-history"><summary>Histórico e sugestões</summary>
        <div className="plan-actions"><label>Dia do histórico<input type="date" value={day} onChange={e=>{setDay(e.target.value);void perform(()=>load(e.target.value))}}/></label><button type="button" className="button secondary" disabled={busy} onClick={()=>{setDay('');void perform(()=>load(''))}}>Ver hoje</button></div>
        {!plan.history.length?<p>Nenhuma decisão registrada neste dia.</p>:<ol>{plan.history.map((h,i)=><li key={i}><time>{stamp(h.at)}</time>{h.details.saved_search_id&&<strong>{options.find(o=>o.id===h.details.saved_search_id)?.name||'Pesquisa não listada'} · </strong>}<span>{h.reason}</span>{[...(h.details.searches||[]),...(h.details.skipped||[])].map(s=><small key={s.id}>{options.find(o=>o.id===s.id)?.name||'Pesquisa removida'}: {s.reason}</small>)}</li>)}</ol>}
        {plan.history_truncated&&<p>Exibidas as 200 decisões mais recentes do dia.</p>}
        <button type="button" className="button secondary" disabled={busy} onClick={()=>void perform(async()=>setSuggestions(await api('/operations/plan/suggestions')))}>Consultar sugestões dos últimos 7 dias</button>
        {suggestions&&<><p>{suggestions.limitation}</p>{suggestions.small_sample&&<p>Amostra pequena: distribuição neutra, sem otimização automática.</p>}{!suggestions.suggestions.length&&<p>Sem evidências suficientes para sugerir ajustes.</p>}<ul>{suggestions.suggestions.map(s=><li key={s.key}>{s.count} · {s.observation}. {s.population}. {stamp(s.from_at)}–{stamp(s.to_at)}. <a href={s.href}>{s.action}</a></li>)}</ul></>}
      </details>}
    </>}
  </section>;
}
