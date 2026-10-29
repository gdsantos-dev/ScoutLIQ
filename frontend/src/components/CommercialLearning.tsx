import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { inputDate, type Lead } from '../types';
import { SmartSelect } from './Primitives';
import './commercial-learning.css';
import ScoreCalibration from './ScoreCalibration';

type Evidence = { statement: string; reference: string; evidence_id?: string | null };
type ReviewRecord = {
  source: string; external_id: string; lead_id?: string | null;
  company?: { name: string; country: string; city: string; region?: string; sector: string; address: string; phone?: string } | null;
  dataset: string; split: string; reviewed_on: string; reviewer: string; label_origin: string;
  classification: string; justification: string; services: string[]; operator_priority: string;
  review_status: string; evidence: Evidence[]; outcome: string; outcome_reference: string; outcome_on: string | null;
  system_observation?: unknown;
};
type System = { origin: string; score: number | null; decision: string; criteria_version: string | null; dimensions?: Record<string, { reason: string }> };
type Case = { id: string; version: number; lead_id: string | null; record: ReviewRecord; system: System; updated_at: number };
type Preview = { id: string; preview_hash: string; valid: boolean; committed_at: number | null; rows: {
  index: number; action: string; record?: ReviewRecord; system?: System; before?: Case | null;
  errors: { field: string; message: string }[];
}[] };
type Counts = { cases: number; labeled: number; decided: number; ranked: number; tp: number; fp: number; fn: number; tn: number;
  precision: number | null; recall: number | null; precision_at_k: number | null; ndcg_at_k: number | null;
  abstention_rate: number | null; label_coverage: number | null; effective_k: number; sufficient_sample: boolean; group?: string };
type Evaluation = { id: string; created_at: number; report: { metrics: Counts; parameters: { dataset: string; split: string };
  by_sector: Counts[]; by_region: Counts[]; by_criteria: Counts[]; outcomes: Record<string, number>; limitations: string[] } };

const labels = [{value:'suitable',label:'Adequada'}, {value:'unsuitable',label:'Inadequada'}, {value:'uncertain',label:'Inconclusiva'}];
const splits = [{value:'development',label:'Desenvolvimento'}, {value:'validation',label:'Validação'}];
const outcomes = [{value:'unknown',label:'Desconhecido'}, {value:'not_contacted',label:'Não contatada'}, {value:'no_reply',label:'Sem resposta'},
  {value:'reply',label:'Resposta'}, {value:'meeting',label:'Reunião'}, {value:'proposal',label:'Proposta'}, {value:'won',label:'Fechamento'},
  {value:'lost',label:'Perda'}, {value:'refused',label:'Recusa'}, {value:'opt_out',label:'Pedido de remoção'}];
const label = (value: string) => labels.find(o => o.value === value)?.label || value;
const decision = (value: string) => ({selected:'Selecionada',rejected:'Rejeitada',abstained:'Abstenção'}[value] || value);
const percent = (value: number | null) => value === null ? 'Sem base' : `${(value*100).toFixed(1)}%`;
const serviceOptions = [
  ['site_institucional','Site institucional'], ['landing_page','Landing page'], ['redesign','Redesign'],
  ['sistema_agendamento','Agendamento'], ['catalogo','Catálogo'], ['ecommerce','E-commerce'], ['site_sob_medida','Site sob medida'],
  ['seo_local','SEO local'], ['otimizacao','Otimização'], ['sistema_reservas','Reservas'], ['cardapio_digital','Cardápio digital'],
];

function usePreview() {
  const request = useRef({ payload: '', key: '' });
  return async (records: unknown[]) => {
    const payload = JSON.stringify(records);
    if (request.current.payload !== payload) request.current = { payload, key: crypto.randomUUID() };
    return api<Preview>('/learning/imports/preview', 'POST', { request_key: request.current.key, records });
  };
}

function PreviewConfirmation({ preview, onSaved, onBack }: { preview: Preview; onSaved: () => void; onBack: () => void }) {
  const [confirmed, setConfirmed] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  return <section aria-label="Prévia da revisão" className="learning-preview">
    <h4>Prévia da revisão</h4>
    <ul>{preview.rows.map(row => <li key={row.index}>
      <strong>Registro {row.index+1} · {{create:'Novo caso',update:'Correção',unchanged:'Sem alteração',error:'Corrigir'}[row.action]}</strong>
      {row.record && <><p>{row.record.company?.name} · {row.record.company?.city} · {row.record.company?.country} · {row.record.company?.address || row.record.company?.phone}</p>
        <p>Avaliação humana: {label(row.record.classification)}{row.before && ` (antes: ${label(row.before.record.classification)})`}</p>
        <p>{row.record.justification}</p><p>ScoutLIQ: {row.system?.score ?? 'Sem score'} · {decision(row.system?.decision || '')} · critério {row.system?.criteria_version || 'indisponível'}</p>
        <p>Resultado comercial: {outcomes.find(o => o.value === row.record!.outcome)?.label} · {row.record.dataset} / {splits.find(o => o.value === row.record!.split)?.label}</p>
        <details><summary>Dados da revisão e evidências</summary><pre>{JSON.stringify(row.record, null, 2)}</pre>{row.before && <><h5>Versão anterior</h5><pre>{JSON.stringify(row.before.record, null, 2)}</pre></>}</details>
      </>}
      {row.errors.map((e,i) => <p role="alert" key={i}>{e.field && `${e.field}: `}{e.message}</p>)}
    </li>)}</ul>
    <label className="op-check"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />Confirmo que as classificações e justificativas foram revisadas por uma pessoa.</label>
    {error && <p role="alert">{error}</p>}
    <div className="learning-actions"><button type="button" className="button" disabled={busy} onClick={onBack}>Voltar à revisão</button>
      <button type="button" className="button primary" disabled={busy || !confirmed || !preview.valid} onClick={async () => {
        setBusy(true); setError('');
        try { await api(`/learning/imports/${preview.id}/commit`, 'POST', { preview_hash: preview.preview_hash, confirm_human_reviews: true }); onSaved(); }
        catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      }}>Confirmar revisão</button></div>
  </section>;
}

function ReviewEditor({ initial, existing, onSaved }: { initial: ReviewRecord; existing?: Case; onSaved: () => void }) {
  const [record, setRecord] = useState(initial), [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const makePreview = usePreview();
  function field<K extends keyof ReviewRecord>(key: K, value: ReviewRecord[K]) { setRecord(r => ({...r, [key]: value})); }
  if (preview) return <PreviewConfirmation preview={preview} onSaved={onSaved} onBack={() => setPreview(null)} />;
  return <form className="learning-form" onSubmit={async e => {
    e.preventDefault(); setError(''); setBusy(true);
    try {
      const payload = { ...record, expected_version: existing?.version || 0 };
      if (payload.lead_id) { delete payload.company; delete payload.system_observation; }
      setPreview(await makePreview([payload]));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }}>
    {existing && <p>Versão {existing.version} · Score registrado: {existing.system.score ?? 'indisponível'} · {decision(existing.system.decision)}</p>}
    {existing && existing.record.review_status === 'reviewed' && existing.record.classification !== 'uncertain' && existing.system.decision !== 'abstained' &&
      (existing.record.classification === 'suitable') !== (existing.system.decision === 'selected') && <p role="status">Divergência registrada entre a revisão humana e a decisão do Score.</p>}
    {existing?.system.dimensions && <details><summary>Motivos do Score registrado</summary>{Object.entries(existing.system.dimensions).map(([key,d]) => <p key={key}>{d.reason}</p>)}</details>}
    <div className="learning-fields"><label>Conjunto de casos<input required minLength={2} maxLength={80} value={record.dataset} onChange={e => field('dataset', e.target.value)} /></label>
      <SmartSelect ariaLabel="Divisão da amostra" value={record.split} onChange={v => field('split',v)} options={splits} /></div>
    <div className="learning-fields"><label>Revisor<input required minLength={2} maxLength={100} value={record.reviewer} onChange={e => field('reviewer', e.target.value)} /></label>
      <label>Data da revisão<input required type="date" max={inputDate()} value={record.reviewed_on} onChange={e => field('reviewed_on',e.target.value)} /></label></div>
    <SmartSelect ariaLabel="Avaliação humana" value={record.classification} onChange={v => field('classification',v)} options={labels} />
    <label>Justificativa comercial<textarea required minLength={15} maxLength={1500} value={record.justification} onChange={e => field('justification',e.target.value)} /></label>
    <SmartSelect ariaLabel="Estado da revisão" value={record.review_status} onChange={v => field('review_status',v)} options={[{value:'reviewed',label:'Revisada'},{value:'needs_review',label:'Requer nova revisão'}]} />
    <SmartSelect ariaLabel="Prioridade do operador" value={record.operator_priority} onChange={v => field('operator_priority',v)} options={[{value:'unknown',label:'Não definida'},{value:'low',label:'Baixa'},{value:'medium',label:'Média'},{value:'high',label:'Alta'}]} />
    <details><summary>Serviços adequados</summary>{serviceOptions.map(([value,name]) => <label className="op-check" key={value}><input type="checkbox" checked={record.services.includes(value)} onChange={e => field('services',e.target.checked ? [...record.services,value] : record.services.filter(s => s !== value))} />{name}</label>)}</details>
    {record.evidence.map((evidence,index) => <fieldset key={index}><legend>Evidência {index+1}</legend>
      <label>Observação revisada<textarea required minLength={5} maxLength={600} value={evidence.statement} onChange={e => field('evidence',record.evidence.map((item,i) => i === index ? {...item,statement:e.target.value} : item))} /></label>
      <label>Referência da evidência<input required minLength={5} maxLength={1000} value={evidence.reference} onChange={e => field('evidence',record.evidence.map((item,i) => i === index ? {...item,reference:e.target.value} : item))} /></label>
    </fieldset>)}
    <SmartSelect ariaLabel="Resultado comercial conhecido" value={record.outcome} onChange={v => field('outcome',v)} options={outcomes} />
    {!['unknown','not_contacted'].includes(record.outcome) && <><label>Data do resultado<input required type="date" max={inputDate()} value={record.outcome_on || ''} onChange={e => field('outcome_on',e.target.value || null)} /></label>
      <label>Referência do resultado<input required minLength={5} maxLength={1000} value={record.outcome_reference} onChange={e => field('outcome_reference',e.target.value)} /></label></>}
    <p>O resultado comercial não altera a avaliação humana nem os pesos do Score.</p>
    {error && <p role="alert">{error}</p>}
    <button className="button" disabled={busy}>Revisar antes de salvar</button>
  </form>;
}

function CaseHistory({ item }: { item: Case }) {
  const [history, setHistory] = useState<Case[] | null>(null), [error, setError] = useState('');
  return <details onToggle={async e => {
    if (!e.currentTarget.open || history) return;
    try { setHistory((await api<{revisions: Case[]}>(`/learning/cases/${item.id}/history`)).revisions); setError(''); }
    catch (e) { setError((e as Error).message); }
  }}><summary>Histórico das revisões</summary>{error && <p role="alert">{error}</p>}
    {history?.map(h => <div key={h.version}><strong>Versão {h.version} · {label(h.record.classification)}</strong><p>{h.record.reviewer} · {h.record.reviewed_on}</p><p>{h.record.justification}</p><p>Score {h.system.score ?? 'indisponível'} · {decision(h.system.decision)}</p></div>)}
  </details>;
}

export function LeadLearningReview({ lead }: { lead: Lead }) {
  const [item, setItem] = useState<Case | null>(null), [loaded, setLoaded] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  async function load() {
    try { setItem((await api<{cases: Case[]}>(`/learning/cases?lead_id=${lead.id}`)).cases[0] || null); setLoaded(true); setError(''); }
    catch (e) { setError((e as Error).message); }
  }
  const initial: ReviewRecord = { source:'orliq_manual',external_id:`lead-${lead.id}`,lead_id:lead.id,dataset:'ORLIQ manual',split:'development',
    reviewed_on:inputDate(),reviewer:'',label_origin:'human',classification:'uncertain',justification:'',
    services:[],operator_priority:'unknown',review_status:'reviewed',evidence:[{statement:'',reference:''}],outcome:'unknown',outcome_on:null,outcome_reference:'' };
  return <details className="learning-section" onToggle={e => { if (e.currentTarget.open && !loaded) void load(); }}>
    <summary>Revisão comercial supervisionada</summary>
    {error && <p role="alert">{error}<button type="button" className="button" onClick={() => void load()}>Tentar novamente</button></p>}
    {notice && <p role="status">{notice}</p>}
    {loaded && !lead.demo && <ReviewEditor key={item ? `${item.id}:${item.version}` : lead.id} initial={item?.record || initial} existing={item || undefined} onSaved={() => { setNotice('Revisão registrada. Score preservado.'); void load(); }} />}
    {lead.demo && <p>Exemplos de demonstração não compõem a amostra humana.</p>}
    {item && <CaseHistory key={item.version} item={item} />}
  </details>;
}

function Metrics({ evaluation }: { evaluation: Evaluation }) {
  const report = evaluation.report, m = report.metrics;
  return <section className="learning-metrics" aria-label="Avaliação de oportunidades">
    <h4>{report.parameters.dataset} · {splits.find(o => o.value === report.parameters.split)?.label}</h4>
    <p>{m.cases} casos · {m.labeled} rótulos conclusivos · {m.decided} decisões do sistema</p>
    {!m.sufficient_sample && <p role="status">Amostra insuficiente para concluir qualidade comercial. Valores descritivos.</p>}
    <dl><dt>Verdadeiros positivos / negativos</dt><dd>{m.tp} / {m.tn}</dd><dt>Falsos positivos / negativos</dt><dd>{m.fp} / {m.fn}</dd>
      <dt>Precisão / recall</dt><dd>{percent(m.precision)} / {percent(m.recall)}</dd><dt>Precisão nos primeiros {m.effective_k}</dt><dd>{percent(m.precision_at_k)}</dd>
      <dt>NDCG da ordenação</dt><dd>{m.ndcg_at_k?.toFixed(3) ?? 'Sem base'}</dd><dt>Cobertura humana / abstenção</dt><dd>{percent(m.label_coverage)} / {percent(m.abstention_rate)}</dd></dl>
    <details><summary>Setores, regiões e critérios</summary>{[['Setor',report.by_sector],['Região',report.by_region],['Critério',report.by_criteria]].map(([name,rows]) => <div key={String(name)}><h5>{String(name)}</h5>{(rows as Counts[]).map(row => <p key={row.group}>{row.group} · {row.cases} casos · FP {row.fp} / FN {row.fn} · precisão {percent(row.precision)}</p>)}</div>)}</details>
    <details><summary>Resultados comerciais registrados</summary>{Object.entries(report.outcomes).map(([key,n]) => <p key={key}>{outcomes.find(o => o.value === key)?.label}: {n}</p>)}</details>
    <details><summary>Limites da avaliação</summary>{report.limitations.map(text => <p key={text}>{text}</p>)}</details>
  </section>;
}

export default function CommercialLearning() {
  const [text, setText] = useState(''), [preview, setPreview] = useState<Preview | null>(null), [busy, setBusy] = useState(false);
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [dataset, setDataset] = useState('ORLIQ manual'), [split, setSplit] = useState('development');
  const [cases, setCases] = useState<Case[]>([]), [evaluations, setEvaluations] = useState<Evaluation[]>([]), [selected, setSelected] = useState<Case | null>(null);
  const [loaded, setLoaded] = useState(false), [offset, setOffset] = useState(0), [hasMore, setHasMore] = useState(false);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const makePreview = usePreview();
  useEffect(() => { setSelected(null); }, [dataset]);
  async function load() {
    const [a,b] = await Promise.all([api<{cases: Case[]}>('/learning/cases'),api<{evaluations: Evaluation[]}>('/learning/evaluations')]);
    setCases(a.cases); setOffset(0); setHasMore(a.cases.length === 50); setEvaluations(b.evaluations); setLoaded(true);
  }
  async function run(work: () => Promise<void>) { setError(''); setBusy(true); try { await work(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }
  return <details className="learning-section op-workflow" onToggle={e => { if (e.currentTarget.open && !loaded) void run(load); }}>
    <summary>Casos revisados e qualidade da seleção</summary>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <button type="button" className="button compact" disabled={busy} onClick={() => void run(load)}>Atualizar casos e avaliações</button>
    <details><summary>Importar casos em JSON</summary><p>Até 50 registros e 64 KB por arquivo. Use uma lista de casos revisados; a prévia identifica erros antes de salvar.</p>
      <label>Arquivo de casos<input type="file" accept=".json,application/json" onChange={async e => {
        const file = e.target.files?.[0]; if (!file) return;
        if (file.size > 64000 || !file.name.toLowerCase().endsWith('.json')) { setError('Use um arquivo JSON de até 64 KB.'); return; }
        try { setText(await file.text()); setPreview(null); } catch { setError('Não foi possível ler o arquivo.'); }
      }} /></label>
      <label>JSON dos casos<textarea rows={7} maxLength={64000} value={text} onChange={e => { setText(e.target.value); setPreview(null); }} /></label>
      <button type="button" className="button" disabled={busy || !text} onClick={() => void run(async () => {
        let records: unknown; try { records = JSON.parse(text); } catch { throw new Error('JSON inválido. Confira o arquivo.'); }
        if (!Array.isArray(records)) throw new Error('Informe uma lista JSON de casos.');
        setPreview(await makePreview(records));
      })}>Gerar prévia da importação</button>
      {preview && <PreviewConfirmation key={preview.id} preview={preview} onBack={() => setPreview(null)} onSaved={() => { setNotice('Importação confirmada.'); setPreview(null); void run(load); }} />}
    </details>
    <details><summary>Consultar e corrigir casos ({cases.length})</summary>
      {!cases.length && <p>Nenhum caso revisado nesta conta.</p>}
      <ul className="learning-case-list">{cases.map(item => <li key={item.id}><button type="button" className="button compact" onClick={() => setSelected(item)}>{item.record.company?.name} · {label(item.record.classification)} · v{item.version}</button></li>)}</ul>
      {hasMore && <button type="button" className="button" disabled={busy} onClick={() => void run(async () => {
        const result = await api<{cases:Case[]}>(`/learning/cases?offset=${offset+50}`); setOffset(offset+50); setHasMore(result.cases.length === 50); setCases(items => [...items,...result.cases]);
      })}>Carregar mais casos</button>}
      {selected && <><h4>{selected.record.company?.name}</h4><ReviewEditor key={`${selected.id}:${selected.version}`} initial={selected.record} existing={selected} onSaved={() => { setSelected(null); setNotice('Correção registrada.'); void run(load); }} /><CaseHistory key={`${selected.id}:${selected.version}`} item={selected} /></>}
    </details>
    <form className="learning-form" onSubmit={e => { e.preventDefault(); void run(async () => {
      const value = await api<Evaluation>('/learning/evaluations','POST',{request_key:crypto.randomUUID(),dataset,split,k:10});
      setEvaluation(value); await load();
    }); }}><div className="learning-fields"><label>Conjunto para avaliação<input required minLength={2} maxLength={80} value={dataset} onChange={e => setDataset(e.target.value)} /></label>
      <SmartSelect ariaLabel="Divisão para avaliação" value={split} onChange={setSplit} options={splits} /></div>
      <button className="button" disabled={busy}>Registrar avaliação da seleção</button></form>
    {!!evaluations.length && <SmartSelect ariaLabel="Avaliação registrada" value={evaluation?.id || ''} onChange={id => setEvaluation(evaluations.find(e => e.id === id) || null)} options={[{value:'',label:'Selecionar avaliação'},...evaluations.map(e => ({value:e.id,label:`${e.report.parameters.dataset} · ${splits.find(o => o.value === e.report.parameters.split)?.label} · ${new Date(e.created_at*1000).toLocaleString()}`}))]} />}
    {evaluation && <Metrics evaluation={evaluation} />}
    {loaded && <ScoreCalibration evaluations={evaluations} />}
  </details>;
}
