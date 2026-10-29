import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Check, FilePenLine, RefreshCw, ShieldCheck } from 'lucide-react';
import { tr } from '../i18n';
import styles from './WorkflowSteps.module.css';
import { api, ApiError } from '../api';
import type { Lead } from '../types';
import { SmartSelect } from './Primitives';
import './opportunity-workflow.css';
import { LeadLearningReview } from './CommercialLearning';
import { OutreachExecution } from './Communication';

type Evidence = {
  id: string; statement: string; source_url: string; method: string;
  classification: string; observed_at: number; valid_until: number; version: number; stale: boolean;
  category: string; scope: string; verified_at: number | null; review_reason: string;
  relation: string; related_id: string | null; observation_key: string; translations: Record<string, string>;
};
type Draft = {
  id: string; channel: string; locale: string; recipient: string; subject: string; body: string;
  status: string; version: number; evidence_ids: string[]; review_blocker: string; approved_at: number | null;
  send_blocker: string; eligibility_state: string; strategy: string;
};
type Workflow = {
  lead_version: number; evidence: Evidence[]; drafts: Draft[]; next_action: string;
  coverage: { confirmed: number; total: number }; contact_blocked: boolean; contact_block_reason: string;
  recommendation: { id: string; label: string; reason: string; command: string; state: string; evidence_ids: string[]; blockers: string[] };
  insight: { diagnosis: string; priority: number; factors: string[]; services: { service: string; reason: string; evidence_ids: string[] }[];
    coverage: { investigated: string[]; required: string[]; missing: string[] }; reliability: { state: string; reason: string; expired: number; conflicts: number } };
};
const classifications = [
  { value: 'unverified', label: 'Não verificada' }, { value: 'probable', label: 'Provável' },
  { value: 'confirmed', label: 'Confirmada' }, { value: 'refuted', label: 'Refutada' },
];
const categories = [{ value: 'general', label: 'Geral' }, { value: 'content', label: 'Conteúdo e navegação' }, { value: 'security', label: 'Segurança' }, { value: 'mobile', label: 'Mobile' }, { value: 'discovery', label: 'SEO e descoberta' }, { value: 'contact', label: 'Contato' }, { value: 'performance', label: 'Desempenho' }];
const categoryLabel = (value: string) => categories.find(c => c.value === value)?.label || value;
const date = (timestamp: number) => new Date(timestamp * 1000).toLocaleDateString('pt-BR');

function EvidenceReview({ item, busy, save }: { item: Evidence; busy: boolean; save: (item: Evidence, status: string, reason: string, translations: Record<string, string>) => Promise<void> }) {
  const [status, setStatus] = useState(item.classification);
  const [reason, setReason] = useState('');
  const [english, setEnglish] = useState(item.translations['en-US'] || '');
  const [spanish, setSpanish] = useState(item.translations.es || '');
  return <details className="op-evidence">
    <summary><span><em>{categoryLabel(item.category)}</em>{item.statement}</span><small data-status={item.classification}>{item.relation === 'superseded' ? 'Substituída' : item.stale ? 'Vencida' : classifications.find(c => c.value === item.classification)?.label}</small></summary>
    <div className="op-evidence-detail">
      <a href={item.source_url} target="_blank" rel="noopener noreferrer">Consultar fonte <ArrowUpRight size={14} /></a>
      <p>{item.method === 'research_snapshot' ? 'Análise do HTML' : 'Observação do operador'} · {date(item.observed_at)} · válida até {date(item.valid_until)}</p>
      <p>{item.scope}</p>
      {item.related_id && <p>Há uma observação anterior com resultado diferente. A revisão está no histórico.</p>}
      {item.review_reason && <p>Última revisão: {item.review_reason}</p>}
      <form onSubmit={e => { e.preventDefault(); void save(item, status, reason, { ...(english ? { 'en-US': english } : {}), ...(spanish ? { es: spanish } : {}) }); }}>
        <SmartSelect ariaLabel="Classificação da evidência" value={status} onChange={setStatus} options={classifications} disabled={busy} />
        <label>Justificativa da revisão<textarea required minLength={15} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} placeholder="O que foi verificado, em qual página e com qual limite?" /></label>
        {!item.observation_key && <details><summary>Traduções revisadas</summary><label>English<textarea maxLength={600} value={english} onChange={e => setEnglish(e.target.value)} /></label><label>Español<textarea maxLength={600} value={spanish} onChange={e => setSpanish(e.target.value)} /></label><p>Preserve o significado e os limites da observação original.</p></details>}
        <button className="button compact" disabled={busy || item.relation !== 'current' || reason.trim().length < 15}><Check size={16} />Salvar revisão</button>
      </form>
    </div>
  </details>;
}

function DraftEditor({ draft, busy, blocked, save, approve, onDirty }: {
  draft: Draft; busy: boolean; blocked: boolean;
  save: (draft: Draft, subject: string, body: string) => Promise<void>;
  approve: (draft: Draft, authorization: string) => Promise<void>;
  onDirty: (dirty: boolean) => void;
}) {
  const [subject, setSubject] = useState(draft.subject);
  const [body, setBody] = useState(draft.body);
  const [authorization, setAuthorization] = useState('');
  const [baseline, setBaseline] = useState(draft);
  const dirty = subject !== baseline.subject || body !== baseline.body;
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    if (!dirty || (subject === draft.subject && body === draft.body)) {
      setSubject(draft.subject); setBody(draft.body); setBaseline(draft);
    }
  }, [draft, dirty, subject, body]);
  return <div className="op-draft-editor">
    <p className="op-recipient">{draft.channel === 'email' ? 'E-mail' : 'WhatsApp'} · {draft.recipient}</p>
    {dirty && <p role="status" className="op-unsaved">Alterações não salvas. A aprovação está indisponível até salvar.</p>}
    {baseline.version !== draft.version && dirty && <p role="alert">O rascunho mudou no servidor. Seu texto foi preservado; compare antes de salvar.</p>}
    {baseline.version !== draft.version && dirty && <button type="button" className="button compact" onClick={() => setBaseline(draft)}>Manter meu texto sobre a versão atual</button>}
    <form onSubmit={e => { e.preventDefault(); void save(baseline, subject, body); }}>
      {draft.channel === 'email' && <label>Assunto<input value={subject} maxLength={200} onChange={e => setSubject(e.target.value)} /></label>}
      <label>Mensagem<textarea aria-label="Mensagem" rows={9} minLength={10} maxLength={6000} required value={body} onChange={e => setBody(e.target.value)} /></label>
      <span className="op-muted">{body.length} caracteres · preparação determinística</span>
      <details><summary>Prévia e comparação</summary><div className="op-message-preview">{body}</div>{dirty && <><h4>Versão salva</h4><div className="op-message-preview">{draft.body}</div></>}</details>
      <button className="button" disabled={busy || !dirty || body.trim().length < 10}><FilePenLine size={16} />Salvar alterações</button>
    </form>
    {draft.status === 'approved' && !draft.review_blocker && !dirty ? <p className="op-approved"><ShieldCheck size={18} />Aprovada em {date(draft.approved_at!)}. Nenhum envio realizado.</p> : <form onSubmit={e => { e.preventDefault(); void approve(draft, authorization); }}>
      {draft.review_blocker && <p className="op-muted">{draft.review_blocker}</p>}
      <label>Nota da revisão (opcional)<input maxLength={500} value={authorization} onChange={e => setAuthorization(e.target.value)} /></label>
      <p className="op-muted">A aprovação revisa este conteúdo por 7 dias. Não comprova consentimento nem libera envio.</p>
      <button className="button primary" disabled={busy || dirty || blocked}><ShieldCheck size={16} />Aprovar conteúdo</button>
    </form>}
    <p className="op-provider">{draft.channel==='email'?'Use Envio e acompanhamento para revisar a elegibilidade e autorizar uma execução.':'Envio indisponível: o adapter oficial WhatsApp ainda não está implementado.'}</p>
    <p className="op-muted">{draft.send_blocker}</p>
  </div>;
}

function RecipientCondition({ base, channel, recipient, market, onSaved }: { base: string; channel: string; recipient: string; market: string; onSaved: () => void }) {
  const [version, setVersion] = useState(0);
  const [basis, setBasis] = useState('unknown');
  const [reference, setReference] = useState('');
  const [reason, setReason] = useState('');
  const [blocked, setBlocked] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!recipient) return;
    let alive = true;
    api<{ policy: { version: number; basis: string; reference: string; blocked: number } | null }>(`${base}/recipient-policy?channel=${channel}&recipient=${encodeURIComponent(recipient)}`)
      .then(({ policy }) => { if (alive) { setVersion(policy?.version || 0); setBasis(policy?.basis || 'unknown'); setReference(policy?.reference || ''); setBlocked(Boolean(policy?.blocked)); setReady(true); } })
      .catch(e => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [base, channel, recipient]);
  if (!recipient) return <p className="op-muted">Informe um destinatário na abordagem para consultar ou registrar sua condição de contato.</p>;
  return <form onSubmit={async e => {
    e.preventDefault(); setSaving(true); setError('');
    try {
      const result = await api<{ version: number }>(`${base}/recipient-policy`, 'PUT', { version, channel, recipient, basis, reference, reason, market, blocked });
      setVersion(result.version);
      onSaved();
    } catch (e) { setError((e as Error).message); } finally { setSaving(false); }
  }}>
    <p>{channel === 'email' ? 'E-mail' : 'WhatsApp'} · {recipient}</p>
    <SmartSelect ariaLabel="Condição declarada" value={basis} onChange={setBasis} options={[{value:'unknown',label:'Não determinada'},{value:'inbound_request',label:'Solicitação recebida'},{value:'explicit_permission',label:'Permissão declarada'},{value:'existing_relationship',label:'Relacionamento existente'}]} />
    <label>Referência verificável<input value={reference} maxLength={1000} onChange={e => setReference(e.target.value)} /></label>
    <label>Justificativa da condição<textarea required minLength={15} maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
    <label className="op-check"><input type="checkbox" checked={blocked} onChange={e => setBlocked(e.target.checked)} />Não contatar este destinatário em nenhuma oportunidade</label>
    <p className="op-muted">Registro declarado para {market}, válido por 30 dias. Não comprova consentimento nem substitui validação do provedor. Alterações invalidam aprovações deste destinatário.</p>
    {error && <p role="alert">{error}</p>}
    <button className="button" disabled={!ready || saving}>Salvar condição de contato</button>
  </form>;
}

export default function OpportunityWorkflow({ lead, onInvestigate, onHistory, onLeadUpdated, onDirty }: {
  lead: Lead; onInvestigate: () => void; onHistory: () => void; onLeadUpdated: (lead: Lead) => void;
  onDirty: (dirty: boolean) => void;
}) {
  const [data, setData] = useState<Workflow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [statement, setStatement] = useState('');
  const [source, setSource] = useState(lead.website || '');
  const [channel, setChannel] = useState('email');
  const [locale, setLocale] = useState(['US', 'GB', 'CA', 'AU'].includes(lead.country) ? 'en-US' : ['ES', 'MX', 'AR'].includes(lead.country) ? 'es' : 'pt-BR');
  const [category, setCategory] = useState('general');
  const [scope, setScope] = useState('');
  const [workSection, setWorkSection] = useState('evidence');
  const sectionInitialized = useRef(false);
  useEffect(() => { if (data && !sectionInitialized.current) { sectionInitialized.current = true; if (data.drafts.length) setWorkSection('outreach'); } }, [data]);
  const [strategy, setStrategy] = useState('verified_opportunity');
  const [recipient, setRecipient] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [draftId, setDraftId] = useState('');
  const [policyReason, setPolicyReason] = useState('');
  const [retry, setRetry] = useState(0);
  const [editorDirty, setEditorDirty] = useState(false);
  const handleDirty = useCallback((dirty: boolean) => { setEditorDirty(dirty); onDirty(dirty); }, [onDirty]);
  const pendingRequest = useRef<{ signature: string; id: string } | null>(null);
  const evidenceSection = useRef<HTMLDivElement>(null);
  const prepareSection = useRef<HTMLDetailsElement>(null);
  const draftSection = useRef<HTMLDivElement>(null);
  const policySection = useRef<HTMLDetailsElement>(null);
  const base = `/leads/${lead.id}`;
  useEffect(() => {
    let alive = true;
    setLoading(true); setError('');
    api<Workflow>(`${base}/workflow`).then(result => { if (alive) setData(result); })
      .catch(e => { if (alive) setError(e.message); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [base, retry]);
  useEffect(() => {
    if (data?.recommendation.state !== 'pending') return;
    const timer = window.setTimeout(() => setRetry(value => value + 1), 3000);
    return () => window.clearTimeout(timer);
  }, [data]);

  async function mutate(action: () => Promise<unknown>, message: string) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await action();
      const fresh = await api<Workflow>(`${base}/workflow`);
      setData(fresh);
      onLeadUpdated({ ...lead, version: fresh.lead_version, contact_blocked: fresh.contact_blocked });
      setNotice(message);
    } catch (e) {
      setError((e as Error).message);
      if (e instanceof ApiError && e.status === 409) {
        try { setData(await api<Workflow>(`${base}/workflow`)); } catch { /* Keep the editable local draft if refresh also fails. */ }
      }
    }
    finally { setBusy(false); }
  }
  async function prepare() {
    if (editorDirty && !window.confirm('Descartar alterações não salvas e preparar outro rascunho?')) return;
    const payload = { channel, locale, recipient, evidence_ids: selected, strategy };
    const signature = JSON.stringify(payload);
    if (pendingRequest.current?.signature !== signature) pendingRequest.current = { signature, id: crypto.randomUUID() };
    await mutate(async () => {
      const result = await api<Draft>(`${base}/outreach/drafts`, 'POST', { ...payload, request_id: pendingRequest.current!.id });
      handleDirty(false);
      setDraftId(result.id);
      setWorkSection('outreach');
    }, 'Rascunho salvo no servidor.');
  }
  const draft = data?.drafts.find(d => d.id === draftId) || data?.drafts[0];
  const inactive = lead.demo || ['won', 'lost'].includes(lead.stage);
  function runNextAction() {
    if (!data) return;
    const command = data.recommendation.command;
    if (command === 'refresh') return setRetry(value => value + 1);
    if (command === 'investigate') return void mutate(async () => {
      const result = await api<{ batch: { items: { lead_id: string }[] } }>('/research/batches', 'POST', { lead_ids: [lead.id], mode: 'web', stale_days: 0 });
      if (!result.batch.items.some(i => i.lead_id === lead.id)) throw new Error('Já existe outro lote ativo. Termine ou cancele esse lote no Radar antes de iniciar esta investigação.');
    }, 'Investigação adicionada à fila do servidor. O worker precisa estar ativo.');
    if (command === 'research') return onInvestigate();
    if (['history', 'activity'].includes(command)) return onHistory();
    setWorkSection(command === 'evidence' ? 'evidence' : 'outreach');
    requestAnimationFrame(() => {
    if (command === 'prepare' && prepareSection.current) prepareSection.current.open = true;
    if (command === 'policy' && policySection.current) policySection.current.open = true;
    const target = command === 'evidence' ? evidenceSection.current : command === 'prepare' ? prepareSection.current : command === 'policy' ? policySection.current : draftSection.current;
    target?.scrollIntoView({ block: 'start', behavior: 'instant' });
    target?.focus();
    });
  }
  if (loading && !data) return <p className="op-muted" role="status">Carregando ficha operacional…</p>;
  if (!data) return <div className="op-workflow"><p role="alert">{error}</p><button className="button" onClick={() => setRetry(v => v + 1)}>Tentar novamente</button></div>;
  return <section className="op-workflow" aria-label="Ficha operacional" aria-busy={busy}>
    <div className="op-identity"><span>{lead.source} · {lead.country}</span>{lead.website && <a href={lead.website} target="_blank" rel="noopener noreferrer">Website <ArrowUpRight size={14} /></a>}{lead.phone && <span>{lead.phone}</span>}</div>
    <header className="op-diagnosis"><span>Diagnóstico</span><h3>{data.insight.diagnosis}</h3>
      {data.insight.services.slice(0, 2).map((s, i) => <p key={i}>{s.service}<small>{s.reason}</small></p>)}
    </header>
    <div className="op-confidence"><div><strong>{data.insight.priority}<small>/100</small></strong><span>{tr("Prioridade comercial")}</span></div><div><b>{data.insight.coverage.investigated.length}/{data.insight.coverage.required.length} áreas investigadas</b><span>{data.insight.reliability.state === 'reviewed' ? 'Informação revisada' : data.insight.reliability.state === 'divergent' ? 'Resultados divergentes' : 'Confiabilidade indeterminada'}</span></div></div>
    <details className="op-method"><summary>Fundamentos e limites</summary><p>{data.insight.reliability.reason}</p><p>Áreas sem investigação: {data.insight.coverage.missing.map(categoryLabel).join(', ') || 'nenhuma'}.</p>{data.insight.factors.map((factor, i) => <p key={i}>{factor}</p>)}</details>
    <header className="op-next"><span>Próxima ação</span><h3>{data.recommendation.label}</h3><p>{data.recommendation.reason}</p>
      <button className="button primary" disabled={busy || inactive} onClick={runNextAction}>{data.recommendation.label}</button>
    </header>
    {error && <div role="alert" className="op-error">{error}<button className="button compact" onClick={() => setRetry(v => v + 1)}>Atualizar ficha</button></div>}
    {notice && <p role="status" className="op-muted">{notice}</p>}
    {inactive && <p className="op-muted">Ações disponíveis somente para oportunidades reais e ativas.</p>}
    {data.contact_blocked && <p role="status" className={styles.blocker}>{tr('Contato suspenso')}: {data.contact_block_reason}</p>}
    <div className={styles.steps} role="group" aria-label={tr('Trabalho da oportunidade')}>
      {([['evidence','Evidências'],['outreach','Abordagem'],['review','Revisão humana']] as const).map(([id,label]) => <button type="button" key={id} aria-pressed={workSection===id} aria-controls={`workflow-${id}`} onClick={()=>setWorkSection(id)}>{tr(label)}</button>)}
    </div>
    <div id="workflow-evidence" hidden={workSection!=='evidence'}>
    <div className="op-section-heading" ref={evidenceSection} tabIndex={-1}><h3>Evidências</h3><span>{data.coverage.confirmed}/{data.coverage.total} confirmadas e válidas</span></div>
    {!data.evidence.length && <p className="op-muted">Nenhuma evidência registrada. Importe a pesquisa ou registre uma observação com fonte.</p>}
    {data.evidence.map(item => <EvidenceReview key={`${item.id}:${item.version}`} item={item} busy={busy || inactive} save={(e, classification, reason, translations) => mutate(() => api(`${base}/evidence/${e.id}`, 'PATCH', { version: e.version, classification, reason, translations }), 'Revisão registrada no histórico.')} />)}
    <button className="button compact" disabled={busy || inactive} onClick={() => void mutate(() => api(`${base}/evidence/capture`, 'POST'), 'Observações da pesquisa incorporadas.')}><RefreshCw size={16} />Importar pesquisa existente</button>
    <details className="op-add-evidence"><summary>Registrar observação com fonte</summary><form onSubmit={e => { e.preventDefault(); void mutate(async () => { await api(`${base}/evidence`, 'POST', { statement, source_url: source, category, scope }); setStatement(''); }, 'Evidência registrada como não verificada.'); }}>
      <SmartSelect ariaLabel="Categoria da evidência" value={category} onChange={setCategory} options={categories} />
      <label>Observação<textarea required minLength={5} maxLength={600} rows={3} value={statement} onChange={e => setStatement(e.target.value)} /></label>
      <label>URL da fonte<input required type="url" maxLength={1000} value={source} onChange={e => setSource(e.target.value)} /></label>
      <label>Escopo da observação<input required minLength={5} maxLength={500} placeholder="Página, data e limites do que foi observado" value={scope} onChange={e => setScope(e.target.value)} /></label>
      <button className="button" disabled={busy || inactive}>Registrar evidência</button>
    </form></details>
    </div>
    <div id="workflow-outreach" hidden={workSection!=='outreach'}>
    <div className="op-section-heading"><h3>Abordagem</h3><span>{data.drafts.length} rascunhos</span></div>
    <details className="op-prepare" ref={prepareSection} tabIndex={-1}><summary>Preparar nova abordagem</summary><form onSubmit={e => { e.preventDefault(); void prepare(); }}>
      <SmartSelect ariaLabel="Estratégia da abordagem" value={strategy} onChange={setStrategy} options={[{value:'verified_opportunity',label:'Oportunidade verificada'},{value:'initial',label:'Apresentação inicial'},{value:'follow_up',label:'Retomada de contato'},{value:'reply',label:'Responder ao retorno'}]} />
      <div className="op-fields"><SmartSelect ariaLabel="Canal da abordagem" value={channel} onChange={value => { setChannel(value); setRecipient(value === 'whatsapp' ? lead.whatsapp || '' : ''); }} options={[{ value: 'email', label: 'E-mail' }, { value: 'whatsapp', label: 'WhatsApp' }]} />
        <SmartSelect ariaLabel="Idioma da abordagem" value={locale} onChange={setLocale} options={[{ value: 'pt-BR', label: 'Português' }, { value: 'en-US', label: 'English' }, { value: 'es', label: 'Español' }]} /></div>
      <label>Destinatário<input required type={channel === 'email' ? 'email' : 'tel'} maxLength={254} value={recipient} onChange={e => setRecipient(e.target.value)} /></label>
      <fieldset><legend>Evidências para a mensagem</legend>{data.evidence.filter(e => e.classification === 'confirmed' && !e.stale && e.relation === 'current').map(e => <label className="op-check" key={e.id}><input type="checkbox" checked={selected.includes(e.id)} onChange={event => setSelected(ids => event.target.checked ? [...ids, e.id].slice(0, 8) : ids.filter(id => id !== e.id))} />{e.statement}</label>)}
        {!data.coverage.confirmed && <p className="op-muted">Confirme pelo menos uma evidência válida.</p>}</fieldset>
      <button className="button primary" disabled={busy || inactive || data.contact_blocked || (strategy === 'verified_opportunity' && !selected.length)}>Preparar rascunho</button>
    </form></details>
    {data.drafts.length > 1 && <SmartSelect ariaLabel="Rascunho salvo" value={draft?.id} onChange={id => { if (!editorDirty || window.confirm('Descartar alterações não salvas e abrir outro rascunho?')) { handleDirty(false); setDraftId(id); } }} options={data.drafts.map(d => ({ value: d.id, label: `${d.recipient} · ${d.status === 'approved' ? 'aprovado' : d.status === 'paused' ? 'pausado' : 'rascunho'}` }))} />}
    {draft && <div ref={draftSection} tabIndex={-1}><DraftEditor key={draft.id} draft={draft} busy={busy || inactive} blocked={data.contact_blocked} onDirty={handleDirty}
      save={(d, subject, body) => mutate(() => api(`${base}/outreach/drafts/${d.id}`, 'PUT', { version: d.version, subject, body }), 'Alterações salvas. Revise antes de aprovar.')}
      approve={(d, authorization_ref) => mutate(() => api(`${base}/outreach/drafts/${d.id}/approve`, 'POST', { version: d.version, authorization_ref }), 'Conteúdo aprovado. Nenhuma mensagem enviada.')} /></div>}
    {draft&&<OutreachExecution leadId={lead.id} draft={draft} disabled={busy||inactive||editorDirty||data.contact_blocked}/>}
    <details className="op-contact-policy" ref={policySection} tabIndex={-1}><summary>{data.contact_blocked ? 'Contato suspenso' : 'Condição de contato e remoção'}</summary>
      <RecipientCondition key={draft?.recipient || recipient} base={base} channel={draft?.channel || channel} recipient={draft?.recipient || recipient} market={lead.country} onSaved={() => setRetry(v => v + 1)} />
      {data.contact_block_reason && <p>{data.contact_block_reason}</p>}
      <form onSubmit={e => { e.preventDefault(); void mutate(() => api(`${base}/contact-policy`, 'PATCH', { version: data.lead_version, blocked: !data.contact_blocked, reason: policyReason }), 'Preferência registrada no histórico.'); }}>
        <label>Motivo<input required minLength={5} maxLength={500} value={policyReason} onChange={e => setPolicyReason(e.target.value)} /></label>
        <button className="button" disabled={busy}>{data.contact_blocked ? 'Reabrir revisão de contato' : 'Suspender contato em todos os canais'}</button>
      </form>
    </details>
    </div>
    <button className="button compact" onClick={onHistory}>Ver histórico da oportunidade</button>
    <div id="workflow-review" hidden={workSection!=='review'}><LeadLearningReview key={lead.id} lead={lead} /></div>
  </section>;
}
