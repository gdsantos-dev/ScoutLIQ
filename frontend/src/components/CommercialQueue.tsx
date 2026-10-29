import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { Lead } from '../types';
import { Modal } from './UI';
import OpportunityWorkflow from './OpportunityWorkflow';
import './commercial-queue.css';

type Selection = { id: string; version: number; review_version: number; followup_version?: number };
type Followup = {code:string;title:string;reason:string;category:string;due_on:string;confidence:string;blocks:string[];unknown:string[];manual_action:string;manual_due_on:string|null;version:number;source:{type:string;id:string};communication:{state:string;delivery:string};response:{text:string}|null};
type Review = { state: string; version: number; needs_review: boolean; decided_at: number | null; reason: string };
type Entry = { id: string; version: number; name: string; city: string; category: string; source: string; stage: string;
  qualification: { class: string; score: number; confidence?: { value: number }; pending: string[] };
  review: Review; followup?:Followup; confirmed_count: number; evidence_count: number; draft_count: number;
  contact: { email: string; whatsapp: string; phone: string };
  summary: { attention: string; services: { name: string; basis: string; type: string }[];
    facts: { id: string; statement: string; source_url: string; scope: string }[]; unknown: string[]; recommended_action: string } };
type DraftPreview = { recipient: string; channel: string; locale: string; strategy: string; subject: string; body: string };
type Operation = { id: string; action: string; status: string; eligible: number; total: number;
  preview: { id: string; name?: string; eligible: boolean; reason?: string; effect?: string; draft?: DraftPreview;next_action_before?:string;next_action_after?:string;due_before?:string;due_after?:string }[];
  results: { id: string; name: string; status: string; reason?: string; draft_id?: string }[] };
const classes: Record<string,string> = { priority:'Prioritárias', promising:'Promissoras', pending:'Pendentes', low:'Baixa prioridade', unavailable:'Investigação indisponível' };
const states: Record<string,string> = { main:'A revisar', all:'Todas as decisões', unreviewed:'Não revisadas', reviewed:'Revisadas', selected:'Possível abordagem', deferred:'Adiadas', not_priority:'Não prioritárias' };
const actions: Record<string,string> = { reviewed:'Marcar como revisada', selected:'Selecionar para possível abordagem', deferred:'Adiar revisão', not_priority:'Marcar como não prioritária', reopen:'Reabrir revisão', investigate:'Solicitar investigação', prepare:'Preparar rascunhos' };
const followActions: Record<string,string> = {followup_set:'Definir próxima ação',followup_snooze:'Adiar acompanhamento',followup_complete:'Concluir tarefa atual',followup_review:'Solicitar revisão',followup_prepare:'Preparar follow-up ou resposta',followup_disable:'Desativar acompanhamento',followup_enable:'Retomar acompanhamento'};
const attentionLabels:Record<string,string>={all:'Todos os acompanhamentos',today:'Atenção hoje',overdue:'Atrasados',awaiting:'Aguardando retorno',response:'Respostas a revisar',review:'Conteúdo e condição de contato',execution:'Execução pendente',pending:'Outras pendências',blocked:'Bloqueados',closed:'Encerrados',paused:'Pausados',completed:'Tarefas concluídas'};

function restore(key: string): Selection[] {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(key) || '[]');
    if (!Array.isArray(value)) return [];
    return value.filter((v): v is Selection => v && typeof v.id==='string' && Number.isInteger(v.version) && Number.isInteger(v.review_version)).slice(0,50);
  } catch { return []; }
}

export default function CommercialQueue({ storageKey, onOpenLead, onLeadUpdated, initialFollowup=false }: {
  storageKey: string; onOpenLead: (lead: Lead) => void; onLeadUpdated: (lead: Lead) => void; initialFollowup?:boolean;
}) {
  const [following,setFollowing]=useState(initialFollowup), [attention,setAttention]=useState('all');
  const [nextAction,setNextAction]=useState(''),[dueOn,setDueOn]=useState(''),[overwrite,setOverwrite]=useState(false);
  const [settings,setSettings]=useState({interval_days:7,version:0,timezone:''});
  const [manual,setManual]=useState<Entry|null>(null),[manualKind,setManualKind]=useState('email'),[manualResult,setManualResult]=useState('recorded'),[manualDate,setManualDate]=useState(''),[manualBody,setManualBody]=useState('');
  const manualRequest=useRef(crypto.randomUUID());
  const actionLabels={...actions,...followActions};
  const key = storageKey+':commercial-selection';
  const [selection,setSelection] = useState<Selection[]>(()=>restore(key));
  const [rows,setRows] = useState<Entry[]>([]), [total,setTotal] = useState(0), [pending,setPending] = useState(0);
  const [classification,setClassification] = useState(''), [state,setState] = useState('main'), [search,setSearch] = useState(''), [source,setSource] = useState('');
  const [offset,setOffset] = useState(0), [loading,setLoading] = useState(true), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const [action,setAction] = useState(initialFollowup?'followup_set':'reviewed'), [reason,setReason] = useState(''), [channel,setChannel] = useState('email'), [locale,setLocale] = useState('pt-BR'), [strategy,setStrategy] = useState('auto');
  const [operation,setOperation] = useState<Operation|null>(null), [confirmed,setConfirmed] = useState(false);
  const [history,setHistory] = useState<{id:string;action:string;status:string;created_at:number}[]>([]);
  const [detail,setDetail] = useState<Lead|null>(null), [dirty,setDirty] = useState(false);
  const request = useRef(0);
  const load = useCallback(async()=>{
    const id=++request.current; setLoading(true);
    try {
      const query=new URLSearchParams({state,offset:String(offset),limit:'25',search,source});
      if(following){query.set('view','followup');query.set('attention',attention);}
      if(classification) query.set('classification',classification);
      const result=await api<{items:Entry[];total:number;index_pending:number}>('/commercial-review/queue?'+query);
      if(id!==request.current) return;
      setRows(result.items);setTotal(result.total);setPending(result.index_pending);setError('');
    } catch(e) { if(id===request.current)setError((e as Error).message); }
    finally { if(id===request.current)setLoading(false); }
  },[classification,state,offset,search,source,following,attention]);
  useEffect(()=>{if(following)void api<typeof settings>('/followup/settings').then(setSettings).catch(e=>setError(e.message));},[following]);
  useEffect(()=>{const timer=setTimeout(()=>void load(),200);return()=>{clearTimeout(timer);request.current++;};},[load]);
  useEffect(()=>{if(!pending)return;const timer=setTimeout(()=>void load(),1000);return()=>clearTimeout(timer);},[pending,load,rows]);
  useEffect(()=>{try{sessionStorage.setItem(key,JSON.stringify(selection));}catch{/* Storage optional. */}},[selection,key]);
  const loadHistory=useCallback(async()=>{
    const result=await api<{operations:typeof history}>('/commercial-review/operations');setHistory(result.operations);
  },[]);
  useEffect(()=>{void loadHistory().catch(e=>setError(e.message));},[loadHistory]);
  async function showOperation(id:string) {
    try {setOperation(await api<Operation>('/commercial-review/operations/'+id));setConfirmed(false);}
    catch(e){setError((e as Error).message);}
  }
  async function openDetail(id:string) {
    setBusy(true);
    try {const result=await api<{lead:Lead}>('/commercial-review/leads/'+id);setDetail(result.lead);setDirty(false);}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  function toggle(row:Entry) {
    setSelection(current=>current.some(s=>s.id===row.id)?current.filter(s=>s.id!==row.id):current.length<50?[...current,{id:row.id,version:row.version,review_version:row.review.version,followup_version:row.followup?.version}]:current);
  }
  async function prepare() {
    setBusy(true);setError('');
    try {
      const result=await api<Operation>('/commercial-review/operations/preview','POST',{request_key:crypto.randomUUID(),action,selection,reason,channel,locale,strategy,next_action:nextAction,due_on:dueOn||null,overwrite_manual:overwrite},60000);
      setOperation(result);setConfirmed(false);await loadHistory();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function execute() {
    if(!operation||!confirmed)return;setBusy(true);setError('');
    try {
      const result=await api<Operation>('/commercial-review/operations/'+operation.id+'/confirm','POST',{confirm:true},60000);
      setOperation(result);setSelection([]);await load();await loadHistory();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <section className="commercial-queue" aria-label="Fila comercial">
    <div className="commercial-view" role="group" aria-label="Visão comercial">
      <button className="button compact" aria-pressed={!following} onClick={()=>{setFollowing(false);setAction('reviewed');setOffset(0);setSelection([]);}}>Triagem</button>
      <button className="button compact" aria-pressed={following} onClick={()=>{setFollowing(true);setAction('followup_set');setOffset(0);setSelection([]);}}>Acompanhamento</button>
    </div>
    {following&&<details><summary>Intervalo de acompanhamento</summary><form className="commercial-filters" onSubmit={e=>{e.preventDefault();setBusy(true);void api<typeof settings>('/followup/settings','PUT',settings.timezone?{interval_days:settings.interval_days,version:settings.version}:{interval_days:settings.interval_days,version:0}).then(s=>{setSettings(s);void load();}).catch(e=>setError(e.message)).finally(()=>setBusy(false));}}><label>Dias após contato<input type="number" min={1} max={90} value={settings.interval_days} onChange={e=>setSettings({...settings,interval_days:Number(e.target.value)})}/></label><p>Fuso: {settings.timezone}. Intervalo para revisão, sem envio automático.</p><button className="button" disabled={busy}>Salvar intervalo</button></form></details>}
    <div className="commercial-filters">
      {following?<label>Acompanhamento<select value={attention} onChange={e=>{setAttention(e.target.value);setOffset(0);}}>{Object.entries(attentionLabels).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>:<label>Revisão<select value={state} onChange={e=>{setState(e.target.value);setOffset(0);}}>{Object.entries(states).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>}
      <label>Classificação<select value={classification} onChange={e=>{setClassification(e.target.value);setOffset(0);}}><option value="">Todas as classificações</option>{Object.entries(classes).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
      <label>Empresa, cidade ou setor<input value={search} maxLength={100} onChange={e=>{setSearch(e.target.value);setOffset(0);}} /></label>
      <label>Origem<input value={source} maxLength={50} placeholder="Todas" onChange={e=>{setSource(e.target.value);setOffset(0);}} /></label>
    </div>
    {error&&<div role="alert"><p>{error}</p><button className="button" onClick={()=>void load()}>Atualizar fila</button></div>}
    {pending>0&&<p role="status">Atualizando avaliações locais: {pending} empresas restantes.</p>}
    <div className="commercial-list-heading"><span>{total} empresas · {following?'Urgência, data e Score':'Score decrescente'}</span><button className="button compact" disabled={loading} onClick={()=>void load()}>Atualizar</button></div>
    {loading&&<p role="status">Carregando fila…</p>}
    {!loading&&!rows.length&&<p>Nenhuma empresa neste filtro.</p>}
    <ul className="commercial-list">{rows.map(row=><li key={row.id}>
      <label className="commercial-select"><input type="checkbox" aria-label={`Selecionar ${row.name}`} checked={selection.some(s=>s.id===row.id)} disabled={busy||selection.length>=50&&!selection.some(s=>s.id===row.id)} onChange={()=>toggle(row)} /></label>
      <div className="commercial-company"><strong>{row.name}</strong><span>{row.city} · {row.category}</span><small>Origem: {row.source} · {states[row.review.state]}</small></div>
      <div className="commercial-priority"><strong>Score {row.qualification.score}</strong><span>{classes[row.qualification.class]}</span><small>Confiança {row.qualification.confidence?.value ?? '—'}/100</small></div>
      <div className="commercial-reason"><p>{following&&row.followup?<><strong>{row.followup.title}</strong><br/>{row.followup.reason}{row.followup.due_on&&<small>Data: {row.followup.due_on.split('-').reverse().join('/')}</small>}</>:row.summary.attention}</p><small>{row.confirmed_count}/{row.evidence_count} evidências confirmadas · {row.draft_count} rascunhos</small><span>{row.contact.email||row.contact.whatsapp||row.contact.phone||'Contato pendente'}</span>
        {row.review.needs_review&&<p className="commercial-recheck">Novos dados: reavaliar decisão anterior.</p>}
      </div>
      <details className="commercial-summary"><summary>Resumo de {row.name}</summary>
        {following&&row.followup&&<><p>Ação registrada: {row.followup.manual_action||'Nenhuma'}{row.followup.manual_due_on?' · '+row.followup.manual_due_on:''}</p><p>Base: {row.followup.source.type==='operator_declared'?'declaração do operador':row.followup.source.type==='provider_reply'?'resposta associada pelo sincronizador':row.followup.source.type==='provider_accepted'?'aceitação pelo provedor':'registro interno'} · {row.followup.confidence==='needs_human_review'?'Classificação a revisar':row.followup.confidence==='limited'?'Informação limitada':'Evento registrado'}</p>{row.followup.response&&<blockquote>{row.followup.response.text}</blockquote>}{[...row.followup.blocks,...row.followup.unknown].map((s,i)=><p key={i}>{s}</p>)}<button className="button compact" disabled={busy} onClick={()=>{setManual(row);setManualBody('');setManualDate('');manualRequest.current=crypto.randomUUID();}}>Registrar atividade de {row.name}</button></>}
        {row.summary.services.map(s=><p key={s.name}><strong>{s.name}</strong> · Sugestão a validar: {s.basis}</p>)}
        {row.summary.facts.map(f=><p key={f.id}><a href={f.source_url} target="_blank" rel="noopener noreferrer">{f.statement}</a><br/><small>{f.scope}</small></p>)}
        <p><strong>A confirmar:</strong> {row.summary.unknown.join(' ')||'Revisar atualidade e condição de contato.'}</p><p>{row.summary.recommended_action}</p>
        {row.review.decided_at&&<p>Decisão em {new Date(row.review.decided_at*1000).toLocaleString('pt-BR')}. {row.review.reason}</p>}
        <button className="button compact" disabled={busy} onClick={()=>void openDetail(row.id)}>Evidências e rascunhos de {row.name}</button>
      </details>
    </li>)}</ul>
    <nav className="commercial-pagination" aria-label="Páginas da fila comercial"><button className="button compact" disabled={!offset||loading} onClick={()=>setOffset(Math.max(0,offset-25))}>Anterior</button><span>Página {Math.floor(offset/25)+1}</span><button className="button compact" disabled={offset+25>=total||loading} onClick={()=>setOffset(offset+25)}>Próxima</button></nav>
    <form className="commercial-actions" onSubmit={e=>{e.preventDefault();void prepare();}}>
      <div className="commercial-selection-count"><strong>{selection.length}/50 selecionadas</strong><button type="button" className="button compact" disabled={!selection.length||busy} onClick={()=>setSelection([])}>Limpar seleção</button><button type="button" className="button compact" disabled={busy||loading||!rows.length} onClick={()=>setSelection(current=>{
        const selected=new Map(current.map(s=>[s.id,s]));rows.forEach(r=>{if(selected.size<50||selected.has(r.id))selected.set(r.id,{id:r.id,version:r.version,review_version:r.review.version,followup_version:r.followup?.version});});return [...selected.values()];
      })}>Selecionar página</button></div>
      <label>Ação em lote<select value={action} onChange={e=>setAction(e.target.value)}>{Object.entries(following?{...followActions,investigate:actions.investigate}:actions).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
      {action==='followup_set'&&<label>Próxima ação<input value={nextAction} required maxLength={180} onChange={e=>setNextAction(e.target.value)}/></label>}
      {['followup_set','followup_snooze'].includes(action)&&<label>Data da ação<input type="date" required value={dueOn} onChange={e=>setDueOn(e.target.value)}/></label>}
      {['followup_set','followup_snooze','followup_complete'].includes(action)&&<label className="commercial-consent"><input type="checkbox" checked={overwrite} onChange={e=>setOverwrite(e.target.checked)}/>Permitir substituir ou concluir ações manuais existentes, conforme a prévia.</label>}
      <label>Motivo da decisão<input value={reason} maxLength={500} minLength={['deferred','not_priority'].includes(action)?5:undefined} required={['deferred','not_priority'].includes(action)} onChange={e=>setReason(e.target.value)} /></label>
      {['prepare','followup_prepare'].includes(action)&&<div className="commercial-filters">
        <label>Canal<select value={channel} onChange={e=>setChannel(e.target.value)}><option value="email">E-mail</option><option value="whatsapp">WhatsApp</option></select></label>
        <label>Idioma<select value={locale} onChange={e=>setLocale(e.target.value)}><option value="pt-BR">Português (Brasil)</option><option value="en-US">English (US)</option><option value="es">Español</option></select></label>
        {action==='prepare'&&<label>Estratégia<select value={strategy} onChange={e=>setStrategy(e.target.value)}><option value="auto">Conforme evidências revisadas</option><option value="initial">Apresentação inicial</option><option value="verified_opportunity">Oportunidade verificada</option><option value="follow_up">Retomada de contato</option><option value="reply">Resposta a interesse</option></select></label>}
      </div>}
      <button className="button primary" disabled={!selection.length||busy}>{busy?'Processando…':'Revisar operação'}</button>
    </form>
    <details className="commercial-history"><summary>Operações recentes</summary>{history.length?history.map(o=><button key={o.id} className="commercial-history-row" onClick={()=>void showOperation(o.id)}>{actionLabels[o.action]} · {o.status==='committed'?'Concluída':'Prévia'} · {new Date(o.created_at*1000).toLocaleString('pt-BR')}</button>):<p>Nenhuma operação registrada.</p>}</details>
    {operation&&<Modal title="Prévia da operação comercial" wide onClose={()=>{if(!busy||operation.status==='committed')setOperation(null);}} className="commercial-preview">
      <h3>{actionLabels[operation.action]}</h3><p>{operation.eligible} elegíveis de {operation.total}. Estágios do CRM preservados. Nenhuma mensagem será enviada.</p>
      {error&&<p role="alert">{error}</p>}
      <ul>{operation.preview.map(row=><li key={row.id}><strong>{row.name||'Empresa indisponível'}</strong><p>{row.eligible?row.effect:row.reason}</p>
        {operation.action.startsWith('followup_')&&row.eligible&&<p>Ação anterior: {row.next_action_before||'Nenhuma'} {row.due_before||''}<br/>Ação após confirmação: {row.next_action_after||'Nenhuma'} {row.due_after||''}</p>}
        {row.draft&&<details><summary>Conferir rascunho para {row.draft.recipient}</summary><p>{row.draft.channel} · {row.draft.locale} · {row.draft.strategy==='verified_opportunity'?'Oportunidade verificada':'Abordagem sem alegação técnica não verificada'}</p><strong>{row.draft.subject}</strong><pre>{row.draft.body}</pre></details>}
      </li>)}</ul>
      {operation.status==='committed'?<div role="status"><h3>Resultado da operação</h3>{operation.results.map(r=><p key={r.id}>{r.name||'Empresa indisponível'}: {r.status==='success'?'Concluída':r.status==='skipped'?'Ignorada':'Não executada'}{r.reason?` — ${r.reason}`:''}{r.draft_id&&<button className="button compact" onClick={()=>{setOperation(null);void openDetail(r.id);}}>Revisar rascunho de {r.name}</button>}</p>)}</div>:<>
        <label className="commercial-consent"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} />Confirmo os efeitos apresentados para as empresas elegíveis.</label>
        <button className="button primary" disabled={!confirmed||!operation.eligible||busy} onClick={()=>void execute()}>{busy?'Executando…':'Confirmar operação'}</button>
      </>}
    </Modal>}
    {manual&&<Modal title={`Registrar atividade — ${manual.name}`} onClose={()=>{if(!busy)setManual(null);}}><form className="commercial-actions" onSubmit={e=>{e.preventDefault();setBusy(true);void api('/leads/'+manual.id+'/activities','POST',{kind:manualKind,body:manualBody,result:manualResult,occurred_on:manualDate||null,request_id:manualRequest.current}).then(()=>{setManual(null);void load();}).catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>
      <p>Registro declarado pelo operador. Não comprova envio ou entrega pelo provedor.</p>{error&&<p role="alert">{error}</p>}
      <label>Atividade<select value={manualKind} onChange={e=>setManualKind(e.target.value)}>{Object.entries({email:'E-mail manual',whatsapp:'WhatsApp manual',call:'Ligação',meeting:'Reunião',proposal:'Proposta apresentada',reply:'Resposta recebida',note:'Nota de revisão'}).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
      <label>Data do ocorrido<input type="date" value={manualDate} onChange={e=>setManualDate(e.target.value)}/></label>
      <label>Resultado<select value={manualResult} onChange={e=>setManualResult(e.target.value)}>{Object.entries({recorded:'Registrado',contacted:'Contato realizado',not_reached:'Contato não alcançado',interest:'Interesse declarado',information_request:'Pedido de informações',objection:'Objeção',refusal:'Recusa',opt_out:'Pedido de remoção',automatic_reply:'Resposta automática',insufficient:'Intenção incerta',delivery_failure:'Falha de entrega'}).map(([v,n])=><option key={v} value={v}>{n}</option>)}</select></label>
      <label>Observações<textarea maxLength={1200} value={manualBody} onChange={e=>setManualBody(e.target.value)}/></label><button className="button primary" disabled={busy}>Salvar atividade</button>
    </form></Modal>}
    {detail&&<Modal title={`Revisão — ${detail.name}`} wide onClose={()=>{if(!dirty||window.confirm('Descartar alterações não salvas do rascunho?')){setDetail(null);void load();}}}>
      <OpportunityWorkflow lead={detail} onInvestigate={()=>{setDetail(null);setAction('investigate');setError('Selecione a empresa na fila e revise a solicitação de investigação.');}} onHistory={()=>{onOpenLead(detail);setDetail(null);}} onLeadUpdated={lead=>{setDetail(lead);onLeadUpdated(lead);}} onDirty={setDirty}/>
    </Modal>}
  </section>;
}
