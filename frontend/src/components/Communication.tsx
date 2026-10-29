import { tr, currentLocale } from "../i18n";
import {useCallback, useEffect, useRef, useState} from 'react';
import {api} from '../api';
import {SmartSelect} from './Primitives';
import './commercial-learning.css';

type Account = {id:string; identity:string; status:string; version:number; sync_enabled:number; error:string; sync:{coverage?:string;truncated?:boolean}};
type Accounts = {configured:boolean; send_limit:number; allowed_markets:string[]; accounts:Account[]};
type Draft = {id:string; version:number; channel:string; recipient:string; status:string; review_blocker:string};
type Message = {id:string; status:string; recipient:string; created_at:number; error:string; cancel_requested:number;
  snapshot:{sender:string; subject:string; body:string}; authorization:{authorized_at:number;expires_at:number};
  events?:{event:string; detail:string; created_at:number}[]};
const labels:Record<string,string>={queued:'Na fila',scheduled:'Agendada',executing:'Em execução',accepted:'Aceita pelo provedor',
  uncertain:'Resultado incerto',failed:'Falhou',cancelled:'Cancelada',blocked:'Bloqueada',connected:'Conectada',disconnected:'Desconectada',reconnect_required:'Reconexão necessária'};
const errorText=(e:unknown)=>e instanceof Error?e.message:'Não foi possível concluir a operação.';
const when=(t:number)=>new Date(t*1000).toLocaleString(currentLocale());

export function GmailConnection() {
  const [data,setData]=useState<Accounts|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const load=useCallback(async()=>setData(await api<Accounts>('/communication/accounts')),[]);
  useEffect(()=>{void load().catch(e=>setError(errorText(e)));},[load]);
  async function action(fn:()=>Promise<unknown>) {setBusy(true);setError('');try{await fn();await load();}catch(e){setError(errorText(e));try{await load();}catch{/* Preserve the error and last known state. */}}finally{setBusy(false);}}
  function toggleSync(a:Account,enabled:boolean) {
    setData(current=>current?{...current,accounts:current.accounts.map(row=>row.id===a.id?{...row,sync_enabled:Number(enabled)}:row)}:current);
    void action(()=>api(`/communication/accounts/${a.id}/sync`,'POST',{version:a.version,enabled}));
  }
  async function connect(account?:Account) {
    const result=await api<{authorization_url:string}>('/communication/gmail/connect','POST',{account_id:account?.id??null});
    const url=new URL(result.authorization_url);
    if(url.origin!=='https://accounts.google.com')throw new Error('Destino OAuth inválido.');
    window.location.assign(url.href);
  }
  const returned=new URLSearchParams(location.hash.split('?')[1]||'').get('gmail');
  return <section className="learning-section" aria-label="Conexão Gmail">
    <h2>Gmail</h2>
    {returned==='failed'&&<p role="alert">Conexão não concluída. Confira o cliente OAuth, os escopos e a conta selecionada.</p>}
    {returned==='denied'&&<p role="status">Permissão não concedida. Nenhuma conta foi conectada.</p>}
    {error&&<p role="alert">{error}</p>}
    {!data?<button className="button" onClick={()=>void action(load)}>Consultar conexão</button>:<>
      {!data.configured&&<p>Gmail ainda não configurado no servidor. Consulte o guia de integrações para cadastrar o cliente OAuth e a chave de cifra.</p>}
      <p>Permissões: enviar mensagens autorizadas e ler respostas das conversas acompanhadas. Limite configurado: {data.send_limit} tentativas de envio por usuário/dia.</p>
      <button className="button" disabled={busy||!data.configured||data.accounts.length>=3} onClick={()=>void action(()=>connect())}>Conectar Gmail</button>
      {data.accounts.map(a=><div key={a.id} className="op-evidence-detail">
        <p><strong>{a.identity}</strong> · {labels[a.status]||a.status}</p>{a.error&&<p role="status">{a.error}</p>}
        <div className="op-fields"><button className="button compact" disabled={busy||!data.configured} onClick={()=>void action(()=>connect(a))}>Reconectar conta</button>
          {a.status!=='disconnected'&&<button className="button compact" disabled={busy} onClick={()=>void action(()=>api(`/communication/accounts/${a.id}/disconnect`,'POST',{version:a.version}))}>Desconectar e revogar</button>}</div>
        <label className="op-check"><input type="checkbox" checked={!!a.sync_enabled} disabled={busy||a.status!=='connected'} onChange={e=>toggleSync(a,e.target.checked)}/>Acompanhar respostas das conversas autorizadas</label>
        {a.sync.coverage&&<p>Sincronização limitada às threads conhecidas. O histórico completo da caixa não é importado.</p>}
        {a.sync.truncated&&<p role="status">A recuperação atingiu o limite de histórico. Consulte a caixa Gmail para revisar conversas antigas que podem ter ficado fora da importação.</p>}
      </div>)}
    </>}
  </section>;
}

export function OutreachExecution({leadId,draft,disabled=false}:{leadId:string;draft:Draft;disabled?:boolean}) {
  const [accounts,setAccounts]=useState<Accounts|null>(null),[accountId,setAccountId]=useState('');
  const [messages,setMessages]=useState<Message[]>([]),[detail,setDetail]=useState<Message|null>(null);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
  const [verification,setVerification]=useState(''),[review,setReview]=useState<Record<string,string>>({}),[checks,setChecks]=useState<Record<string,boolean>>({});
  const [senderRef,setSenderRef]=useState(''),[dns,setDns]=useState(''),[authorized,setAuthorized]=useState(false),[sender,setSender]=useState(false),[optout,setOptout]=useState(false),[due,setDue]=useState('');
  const key=useRef({fingerprint:'',value:''});
  const load=useCallback(async()=>{const [a,m]=await Promise.all([api<Accounts>('/communication/accounts'),api<{messages:Message[]}>(`/communication/outbox?lead_id=${encodeURIComponent(leadId)}`)]);setAccounts(a);setMessages(m.messages);},[leadId]);
  useEffect(()=>{void load().catch(e=>setError(errorText(e)));},[load,draft.version]);
  useEffect(()=>{setAuthorized(false);setVerification('');},[draft.id,draft.version]);
  async function action(fn:()=>Promise<unknown>,message='') {setBusy(true);setError('');setNotice('');try{await fn();await load();setNotice(message);}catch(e){setError(errorText(e));}finally{setBusy(false);}}
  const reviewFields=[['contact_source','Origem do contato'],['permission_evidence','Evidência da permissão ou solicitação'],['jurisdiction_reference','Referência da revisão de jurisdição'],['provider_policy_reference','Referência das regras do canal']];
  const checkFields=[['reviewed_permission','Verifiquei a evidência da permissão ou solicitação.'],['reviewed_jurisdiction','Revisei as condições aplicáveis à jurisdição.'],['reviewed_channel_rules','Revisei as regras do provedor.'],['opt_out_supported','O destinatário pode solicitar remoção e será suprimido.']];
  async function verify() {
    const {policy}=await api<{policy:null|{id:string;version:number}}>(`/leads/${leadId}/recipient-policy?channel=${draft.channel}&recipient=${encodeURIComponent(draft.recipient)}`);
    if(!policy)throw new Error('Registre primeiro a condição de contato abaixo.');
    const result=await api<{id:string}>('/communication/contact-verifications','POST',{policy_id:policy.id,policy_version:policy.version,...review,...checks});
    setVerification(result.id);
  }
  async function send() {
    const a=accounts?.accounts.find(x=>x.id===accountId);if(!a)throw new Error('Selecione a conta remetente.');
    const payload={draft_id:draft.id,draft_version:draft.version,account_id:a.id,account_version:a.version,verification_id:verification,
      due_at:due?Math.floor(new Date(due).getTime()/1000):0,authorize_external_send:authorized,legitimate_sender_confirmed:sender,
      opt_out_in_message_confirmed:optout,sender_configuration_reference:senderRef,sender_dns_review:dns};
    const fingerprint=JSON.stringify(payload);
    if(key.current.fingerprint!==fingerprint)key.current={fingerprint,value:crypto.randomUUID()};
    await api('/communication/outbox','POST',{request_key:key.current.value,...payload});setAuthorized(false);
  }
  return <details className="learning-section" aria-label="Execução da comunicação"><summary>Envio e acompanhamento</summary>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    <button type="button" className="button compact" disabled={busy} onClick={()=>void action(load)}>Atualizar fila</button>
    {draft.channel!=='email'?<p>WhatsApp possui contrato compartilhado; o adapter oficial ainda não está disponível.</p>:<>
      {!accounts?.configured&&<p role="status">{tr("Configure Gmail em Integrações para habilitar esta operação.")}</p>}
      {accounts?.configured && !accounts.accounts.some(a=>a.status==='connected') && <p role="status">{tr("Conecte uma conta Gmail em Integrações antes de autorizar o envio.")}</p>}
      {accounts?.configured && accounts.accounts.some(a=>a.status==='connected') && <>
      <details><summary>Revisar condição de contato</summary><form className="learning-form" onSubmit={e=>{e.preventDefault();void action(verify,'Revisão de contato registrada. Nenhum envio autorizado.');}}>
        <p>A revisão é responsabilidade do operador. Um endereço público ou a aprovação do texto não comprovam permissão para contato.</p>
        {reviewFields.map(([name,label])=><label key={name}>{label}<textarea required minLength={15} maxLength={1000} value={review[name]||''} onChange={e=>{setReview({...review,[name]:e.target.value});setVerification('');}}/></label>)}
        {checkFields.map(([name,label])=><label className="op-check" key={name}><input type="checkbox" required checked={!!checks[name]} onChange={e=>{setChecks({...checks,[name]:e.target.checked});setVerification('');}}/>{label}</label>)}
        <button className="button" disabled={busy||disabled}>Registrar verificação do contato</button>
      </form></details>
      <details><summary>{tr("Autorizar execução")}</summary>
      <form className="learning-form" onSubmit={e=>{e.preventDefault();void action(send,'Autorização registrada na fila. Consulte o estado antes de repetir.');}}>
        <SmartSelect ariaLabel="Conta remetente" value={accountId} onChange={id=>{setAccountId(id);setAuthorized(false);}} options={[{value:'',label:'Selecionar conta'},...(accounts?.accounts.filter(a=>a.status==='connected').map(a=>({value:a.id,label:a.identity}))||[])]}/>
        <label>Referência da identidade remetente<input required minLength={15} maxLength={1000} value={senderRef} onChange={e=>{setSenderRef(e.target.value);setAuthorized(false);}}/></label>
        <label>Revisão SPF, DKIM e DMARC<textarea required minLength={15} maxLength={1000} value={dns} onChange={e=>{setDns(e.target.value);setAuthorized(false);}}/></label>
        <p>Registre os resultados e limites da sua verificação. Este registro não executa diagnóstico DNS automático.</p>
        <label>Agendar envio (opcional, horário local)<input type="datetime-local" value={due} onChange={e=>{setDue(e.target.value);setAuthorized(false);}}/></label>
        <label className="op-check"><input required type="checkbox" checked={sender} onChange={e=>setSender(e.target.checked)}/>Confirmo que a conta identifica legitimamente o remetente.</label>
        <label className="op-check"><input required type="checkbox" checked={optout} onChange={e=>setOptout(e.target.checked)}/>Revisei a identificação e a opção de remoção no texto aprovado.</label>
        <label className="op-check"><input required type="checkbox" checked={authorized} onChange={e=>setAuthorized(e.target.checked)}/>Autorizo este envio externo para {draft.recipient}, com a conta e a versão selecionadas.</label>
        <p>A autorização vence em até 24 horas. Aceitação pela API não confirma entrega ou leitura.</p>
        <button className="button primary" disabled={busy||disabled||!!draft.review_blocker||draft.status!=='approved'||!verification||!accountId||!authorized||!accounts?.configured}>Autorizar e colocar na fila</button>
      </form></details></>}
    </>}
    {!messages.length&&<p>Nenhuma execução registrada nesta oportunidade.</p>}
    {messages.map(m=><div className="op-evidence-detail" key={m.id}>
      <p><strong>{labels[m.status]||m.status}</strong> · {m.recipient} · {when(m.created_at)}</p>
      {m.error&&<p>{m.error}</p>}{m.status==='accepted'&&<p>Entrega e leitura não confirmadas.</p>}
      {!!m.cancel_requested&&m.status!=='cancelled'&&<p>Cancelamento solicitado após o início da tentativa; aguarde reconciliação.</p>}
      <button className="button compact" disabled={busy} onClick={()=>void action(async()=>setDetail(await api<Message>(`/communication/outbox/${m.id}`)))}>Consultar autorização e histórico</button>
      {['queued','scheduled','executing','uncertain'].includes(m.status)&&<button className="button compact" disabled={busy} onClick={()=>void action(()=>api(`/communication/outbox/${m.id}/cancel`,'POST'))}>Cancelar pendência</button>}
      {m.status==='uncertain'&&<button className="button compact" disabled={busy} onClick={()=>void action(()=>api(`/communication/outbox/${m.id}/reconcile`,'POST'),'Reconciliação solicitada. Não há reenvio automático.')}>Solicitar reconciliação</button>}
    </div>)}
    {detail&&<section aria-label="Autorização e histórico da mensagem"><h4>{labels[detail.status]||detail.status}</h4>
      <p>De {detail.snapshot.sender} para {detail.recipient}</p><p>{detail.snapshot.subject}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{detail.snapshot.body}</pre>
      <p>Autorizada em {when(detail.authorization.authorized_at)}; válida até {when(detail.authorization.expires_at)}.</p>
      {detail.events?.map((e,i)=><p key={i}>{when(e.created_at)} · {e.event} · {e.detail}</p>)}</section>}
  </details>;
}
