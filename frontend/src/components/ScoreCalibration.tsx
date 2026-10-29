import { useEffect, useState } from 'react';
import { api } from '../api';
import { SmartSelect } from './Primitives';

type Criteria = { weights: Record<string, number>; minimum_coverage: number; selection_threshold: number; need_threshold: number };
type Config = { version: number; engine_version: string; criteria: Criteria };
type Summary = { id: string; created_at: number; report: { parameters: { split: string; dataset: string } } };
type Metric = { tp: number; fp: number; fn: number; tn: number; sufficient_sample: boolean; labeled: number };
type Comparison = { sample: number; replayable: number; excluded: number; regressions: number; improvements: number;
  before: {metrics:Metric}; after: {metrics:Metric}; changes: { case_id: string; name: string; human: string; before: string; after: string;
    score_before: number; score_after: number; regression: boolean; improvement: boolean; justification: string; evidence: {statement: string; reference: string}[] }[] };
type Proposal = { id: string; created_at: number; base_version: number; report_hash: string; report: {
  reason: string; method: string; criteria: Criteria; previous: Config; development: Comparison; validation: Comparison; limitations: string[] } };
type Change = { id: string; config_version: number; created_at: number; reason: string; previous: Config; applied: Config };

const weights: Record<string,string> = { target_fit:'Adequação',need:'Necessidade',impact:'Impacto',viability:'Viabilidade',activity:'Atividade' };
const humanLabel: Record<string,string> = {suitable:'Adequada',unsuitable:'Inadequada',uncertain:'Inconclusiva'};
const decision: Record<string,string> = {selected:'Selecionada',rejected:'Rejeitada',abstained:'Abstenção'};

function Paired({ title, data }: { title: string; data: Comparison }) {
  return <section><h5>{title}</h5><p>{data.replayable} casos reproduzíveis de {data.sample} · {data.excluded} excluídos · {data.improvements} correções · {data.regressions} regressões</p>
    <p>FP: {data.before.metrics.fp} → {data.after.metrics.fp} · FN: {data.before.metrics.fn} → {data.after.metrics.fn}</p>
    {!data.after.metrics.sufficient_sample && <p>Amostra insuficiente para concluir melhoria comercial.</p>}
    <details><summary>Casos afetados</summary>{!data.changes.length && <p>Nenhuma decisão ou pontuação alterada nesta amostra.</p>}
      {data.changes.map(c => <div key={c.case_id}><strong>{c.name}{c.regression ? ' · Regressão' : c.improvement ? ' · Correção' : ''}</strong>
        <p>Avaliação humana: {humanLabel[c.human]} · {decision[c.before]} ({c.score_before}) → {decision[c.after]} ({c.score_after})</p><p>{c.justification}</p>
        {c.evidence.map((e,i) => <p key={i}>{e.statement} · {e.reference}</p>)}
      </div>)}</details>
  </section>;
}

export default function ScoreCalibration({ evaluations }: { evaluations: Summary[] }) {
  const [config, setConfig] = useState<Config | null>(null), [proposals, setProposals] = useState<Proposal[]>([]), [changes, setChanges] = useState<Change[]>([]);
  const [proposal, setProposal] = useState<Proposal | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [dev, setDev] = useState(''), [validation, setValidation] = useState(''), [mode, setMode] = useState('suggest');
  const [criteria, setCriteria] = useState<Criteria | null>(null), [reason, setReason] = useState('');
  const [approved, setApproved] = useState(false), [acknowledged, setAcknowledged] = useState(false), [rollbackReason, setRollbackReason] = useState('');
  async function load() {
    const [c,p,h] = await Promise.all([api<Config>('/learning/calibrations/configuration'),
      api<{proposals:Proposal[]}>('/learning/calibrations/proposals'), api<{changes:Change[]}>('/learning/calibrations/changes')]);
    setConfig(c); setCriteria(c.criteria); setProposals(p.proposals); setChanges(h.changes);
  }
  useEffect(() => { void load().catch(e => setError(e.message)); }, []);
  async function run(fn: () => Promise<void>) { setBusy(true); setError(''); try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }
  const options = (split: string) => [{value:'',label:'Selecionar avaliação'},...evaluations.filter(e => e.report.parameters.split === split).map(e => ({value:e.id,label:`${e.report.parameters.dataset} · ${new Date(e.created_at*1000).toLocaleString()}`}))];
  return <details className="learning-calibration"><summary>Comparar e revisar critérios do Score</summary>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <button type="button" className="button compact" disabled={busy} onClick={() => void run(load)}>Atualizar critérios e histórico</button>
    {config && criteria && <><p>Critério ativo: {config.engine_version} · configuração {config.version}</p>
      <form className="learning-form" onSubmit={e => { e.preventDefault(); void run(async () => {
        const p = await api<Proposal>('/learning/calibrations/proposals','POST',{request_key:crypto.randomUUID(),development_id:dev,validation_id:validation,
          expected_version:config.version,criteria:mode === 'manual' ? criteria : null,reason});
        setProposal(p);setApproved(false);setAcknowledged(false); await load();
      }); }}>
        <SmartSelect ariaLabel="Amostra de desenvolvimento" value={dev} onChange={setDev} options={options('development')} />
        <SmartSelect ariaLabel="Amostra de validação" value={validation} onChange={setValidation} options={options('validation')} />
        <SmartSelect ariaLabel="Proposta de calibração" value={mode} onChange={setMode} options={[{value:'suggest',label:'Sugerir a partir dos casos de desenvolvimento'},{value:'manual',label:'Comparar critérios definidos pelo operador'}]} />
        {mode === 'manual' && <fieldset><legend>Critérios propostos</legend>{Object.entries(criteria.weights).map(([key,value]) => <label key={key}>Peso: {weights[key]}<input type="number" min={5} max={50} required value={value} onChange={e => setCriteria({...criteria,weights:{...criteria.weights,[key]:Number(e.target.value)}})} /></label>)}
          <label>Cobertura mínima<input type="number" min={80} max={100} required value={criteria.minimum_coverage} onChange={e => setCriteria({...criteria,minimum_coverage:Number(e.target.value)})} /></label>
          <label>Limiar de seleção<input type="number" min={60} max={95} required value={criteria.selection_threshold} onChange={e => setCriteria({...criteria,selection_threshold:Number(e.target.value)})} /></label>
          <label>Necessidade mínima<input type="number" min={65} max={95} required value={criteria.need_threshold} onChange={e => setCriteria({...criteria,need_threshold:Number(e.target.value)})} /></label>
        </fieldset>}
        <label>Problema e hipótese<textarea required minLength={15} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <button className="button" disabled={busy || !dev || !validation}>Comparar nos mesmos casos</button>
      </form>
      {!!proposals.length && <SmartSelect ariaLabel="Proposta registrada" value={proposal?.id || ''} onChange={id => { setProposal(proposals.find(p => p.id === id) || null); setApproved(false);setAcknowledged(false); }} options={[{value:'',label:'Selecionar proposta'},...proposals.map(p => ({value:p.id,label:`${p.report.reason} · ${new Date(p.created_at*1000).toLocaleString()}`}))]} />}
      {proposal && <section aria-label="Comparação de critérios"><h4>Comparação antes de aplicar</h4><p>{proposal.report.reason}</p>
        <details><summary>Configuração anterior e proposta</summary><h5>Anterior</h5><pre>{JSON.stringify(proposal.report.previous.criteria,null,2)}</pre><h5>Proposta</h5><pre>{JSON.stringify(proposal.report.criteria,null,2)}</pre></details>
        <Paired title="Desenvolvimento" data={proposal.report.development} /><Paired title="Validação independente declarada" data={proposal.report.validation} />
        {proposal.report.limitations.map(t => <p key={t}>{t}</p>)}
        <label className="op-check"><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} />Revisei amostras, limitações e possíveis regressões.</label>
        <label className="op-check"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />Autorizo alterar os critérios do Score nesta conta.</label>
        <button type="button" className="button primary" disabled={busy || !approved || !acknowledged || config.version !== proposal.base_version} onClick={() => void run(async () => {
          await api(`/learning/calibrations/proposals/${proposal.id}/apply`,'POST',{expected_version:config.version,report_hash:proposal.report_hash,approve_score_change:true,acknowledge_sample_limits:true});
          setApproved(false);setAcknowledged(false);setNotice('Critérios aplicados. Scores anteriores preservados no histórico.');await load();
        })}>Aplicar critérios aprovados</button>
      </section>}
      {!!changes.length && <details><summary>Histórico e reversão</summary>{changes.map(c => <div key={c.id}><h5>Configuração {c.config_version}</h5><p>{c.reason}</p><p>{c.previous.engine_version} → {c.applied.engine_version}</p>
        {c.config_version === config.version && <form className="learning-form" onSubmit={e => {e.preventDefault();void run(async () => {
          await api(`/learning/calibrations/changes/${c.id}/rollback`,'POST',{expected_version:config.version,reason:rollbackReason,approve_score_change:true});
          setNotice('Configuração anterior restaurada. Histórico preservado.');setRollbackReason('');await load();
        });}}><label>Motivo da reversão<textarea required minLength={15} maxLength={1000} value={rollbackReason} onChange={e => setRollbackReason(e.target.value)} /></label>
          <label className="op-check"><input type="checkbox" required />Autorizo restaurar os critérios anteriores nesta conta.</label><button className="button" disabled={busy}>Reverter alteração vigente</button></form>}
      </div>)}</details>}
    </>}
  </details>;
}
