import base64
import json
import time
from uuid import uuid4
from urllib.parse import urlsplit,parse_qs
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select,func
from backend.db import SessionLocal
from backend.models import User,Lead,ResearchExecutor,LeadActivity
from backend.opportunity_models import RecipientPolicy
from backend.communication_models import ChannelAccount,OutboxMessage,OAuthState,ReceivedMessage
from backend import gmail_adapter as gmail
from backend import research_worker as worker
from backend import communication as comm
from backend.communication_replies import ingest,collect,classify,text_body
from test_opportunity_workflow import setup_flow,approve


@pytest.fixture
def configured(monkeypatch):
    from backend import consumption
    monkeypatch.setitem(consumption.PROVIDER_LIMITS,'gmail',100)
    monkeypatch.setenv('GMAIL_ENABLED','true')
    monkeypatch.setenv('GMAIL_CLIENT_ID','controlled-client')
    monkeypatch.setenv('GMAIL_CLIENT_SECRET','controlled-secret')
    monkeypatch.setenv('GMAIL_REDIRECT_URI','http://localhost:8000/api/communication/gmail/callback')
    monkeypatch.setenv('COMMUNICATION_TOKEN_KEYS',Fernet.generate_key().decode())
    monkeypatch.setenv('OUTREACH_DAILY_SEND_LIMIT','3')
    monkeypatch.setenv('OUTREACH_ALLOWED_MARKETS','BR')
    return monkeypatch


def prepared(auth,lead_data):
    lead,base,evidence,payload,draft=setup_flow(auth,lead_data)
    policy={'channel':'email','recipient':draft['recipient'],'basis':'explicit_permission','reference':'Permissão documentada controlada 001',
        'reason':'Pessoa autorizou contato no canal indicado.','market':'BR'}
    assert auth.put(base+'/recipient-policy',json=policy).status_code==200
    p=auth.get(base+'/recipient-policy',params={'channel':'email','recipient':draft['recipient']}).json()['policy']
    fields={'policy_id':p['id'],'policy_version':p['version'],'contact_source':'Origem controlada da solicitação.',
        'permission_evidence':'Permissão explícita controlada recebida.', 'jurisdiction_reference':'Revisão de jurisdição controlada BR.',
        'provider_policy_reference':'Revisão controlada das políticas Google.', 'reviewed_permission':True,
        'reviewed_jurisdiction':True,'reviewed_channel_rules':True,'opt_out_supported':True}
    verified=auth.post('/api/communication/contact-verifications',json=fields)
    assert verified.status_code==200,verified.text
    draft=auth.get(base+'/workflow').json()['drafts'][0]
    draft=approve(auth,base,draft).json()
    with SessionLocal() as db:
        user=db.scalar(select(User));aid=str(uuid4())
        credentials={'access_token':'controlled-access','refresh_token':'controlled-refresh','expires_at':int(time.time())+3600,'scopes':sorted(gmail.SCOPES)}
        a=ChannelAccount(id=aid,user_id=user.id,identity='sender@example.org',cursor='100',credentials=gmail.seal(credentials,user.id+':'+aid))
        db.add(a);db.commit()
    data={'request_key':str(uuid4()),'draft_id':draft['id'],'draft_version':draft['version'],
        'account_id':aid,'account_version':1,'verification_id':verified.json()['id'],
        'authorize_external_send':True,'legitimate_sender_confirmed':True,'opt_out_in_message_confirmed':True,
        'sender_configuration_reference':'Remetente controlado confirmado para teste.','sender_dns_review':'SPF DKIM DMARC: revisão controlada, não externa.'}
    return lead,base,draft,data


def queued(auth,data):
    r=auth.post('/api/communication/outbox',json=data)
    assert r.status_code==201,r.text
    return r.json()


class Controlled:
    def __init__(self): self.sent=0;self.reconciled=0;self.timeout=False
    def send(self,snapshot,mid):
        self.sent+=1
        if self.timeout: raise TimeoutError('secret must never reach storage')
        return gmail.Acceptance('sent01','thread01')
    def reconcile(self,snapshot,mid):
        self.reconciled+=1;return gmail.Acceptance('sent01','thread01')


def run_controlled(adapter):
    task=worker.claim();assert task and task['kind']=='outreach',task
    worker.execute(task,provider=lambda account:adapter)
    return task


def test_authorization_isolated_idempotent_and_acceptance_not_delivery(auth,lead_data,configured):
    lead,base,draft,data=prepared(auth,lead_data)
    msg=queued(auth,data);assert queued(auth,data)['id']==msg['id']
    assert auth.post('/api/communication/outbox',json={**data,'validity_hours':2}).status_code==409
    assert auth.post('/api/communication/outbox',json={**data,'request_key':str(uuid4())}).status_code==409
    adapter=Controlled();run_controlled(adapter)
    result=auth.get('/api/communication/outbox/'+msg['id']).json()
    assert result['status']=='accepted' and result['delivery']=='unverified' and adapter.sent==1
    assert worker.claim() is None
    assert auth.get('/api/leads/'+lead['id']+'/activities').json()[-1] is not None
    events={e['event'] for e in result['events']};assert {'authorized','attempt_started','accepted'}<=events
    assert 'credentials' not in json.dumps(auth.get('/api/communication/accounts').json())


@pytest.mark.parametrize('mutation',['edit','evidence','optout','expired','account','lead','disabled'])
def test_revalidate_before_wire(auth,lead_data,configured,mutation):
    lead,base,draft,data=prepared(auth,lead_data);msg=queued(auth,data)
    if mutation=='edit': auth.put(base+'/outreach/drafts/'+draft['id'],json={'version':draft['version'],'subject':'Alterado','body':'Conteúdo novo não aprovado.'})
    elif mutation=='evidence':
        e=auth.get(base+'/workflow').json()['evidence'][0]
        auth.patch(base+'/evidence/'+e['id'],json={'version':e['version'],'classification':'refuted','reason':'Observação refutada após nova revisão.'})
    elif mutation=='disabled': configured.setenv('GMAIL_ENABLED','false')
    else:
        with SessionLocal() as db:
            if mutation=='optout': db.scalar(select(RecipientPolicy)).blocked=1
            elif mutation=='expired': db.get(OutboxMessage,msg['id']).expires_at=1
            elif mutation=='account': db.get(ChannelAccount,data['account_id']).version+=1
            elif mutation=='lead': db.get(Lead,lead['id']).stage='won'
            db.commit()
    adapter=Controlled();run_controlled(adapter)
    assert adapter.sent==0
    assert auth.get('/api/communication/outbox/'+msg['id']).json()['status']=='blocked'


def test_cancel_before_and_during_attempt_and_uncertain_reconcile(auth,lead_data,configured):
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data)
    adapter=Controlled();adapter.timeout=True;run_controlled(adapter)
    path='/api/communication/outbox/'+msg['id']
    result=auth.get(path).json();assert result['status']=='uncertain' and 'secret' not in json.dumps(result)
    assert auth.post(path+'/cancel').json()['status']=='uncertain'
    with SessionLocal() as db:
        row=db.get(OutboxMessage,msg['id']);row.reconcile_at=int(time.time())-1;db.commit()
    run_controlled(adapter)
    assert auth.get(path).json()['status']=='accepted' and adapter.sent==1 and adapter.reconciled==1


def test_worker_recovery_does_not_resend_after_persisted_wire_boundary(auth,lead_data,configured):
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data)
    task=worker.claim()
    with SessionLocal() as db:
        row=db.get(OutboxMessage,msg['id']);row.wire_started_at=int(time.time())-100;row.lease_until=1
        db.get(ResearchExecutor,1).lease_until=1;db.commit()
    assert worker.claim() is None
    with SessionLocal() as db:
        row=db.get(OutboxMessage,msg['id']);assert row.status=='uncertain';row.reconcile_at=1;db.commit()
    adapter=Controlled();run_controlled(adapter);assert adapter.sent==0 and adapter.reconciled==1
    assert worker.execute(task,provider=lambda _:adapter) is False


def test_cancel_claim_before_wire(auth,lead_data,configured):
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data);task=worker.claim()
    assert auth.post('/api/communication/outbox/'+msg['id']+'/cancel').json()['status']=='cancelled'
    a=Controlled();worker.execute(task,provider=lambda _:a)
    assert a.sent==0


def callback_url(auth):
    response=auth.post('/api/communication/gmail/connect',json={})
    assert response.status_code==200,response.text
    query=parse_qs(urlsplit(response.json()['authorization_url']).query)
    assert query['code_challenge_method']==['S256']
    return '/api/communication/gmail/callback?code=controlled-code&state='+query['state'][0],query


def test_oauth_state_once_cipher_scope_and_redirect(auth,configured):
    configured.setattr(gmail,'request',lambda method,url,**kw: {
        'access_token':'access','refresh_token':'refresh','token_type':'Bearer','expires_in':3600,'scope':' '.join(gmail.SCOPES)}
        if url==gmail.TOKEN else {'emailAddress':'sender@example.org','historyId':'123'})
    path,query=callback_url(auth)
    assert auth.get(path,follow_redirects=False).status_code==303
    assert auth.get(path,follow_redirects=False).status_code==400
    with SessionLocal() as db:
        account=db.scalar(select(ChannelAccount));assert 'refresh' not in account.credentials
        assert gmail.unseal(account.credentials,account.user_id+':'+account.id)['refresh_token']=='refresh'
        with pytest.raises(gmail.AuthenticationRequired): gmail.unseal(account.credentials,'different-owner')
        assert db.scalar(select(OAuthState)).verifier==''
    assert set(query['scope'][0].split())==gmail.SCOPES
    assert 'refresh' not in auth.get('/api/communication/accounts').text
    configured.setenv('GMAIL_REDIRECT_URI','https://attacker.example/callback')
    assert auth.post('/api/communication/gmail/connect',json={}).status_code==503


def test_invalid_or_expired_state_never_calls_provider(auth,configured):
    configured.setattr(gmail,'exchange',lambda *_:pytest.fail('provider should not be called'))
    assert auth.get('/api/communication/gmail/callback?state='+'a'*40+'&code=x').status_code==400
    path,_=callback_url(auth)
    with SessionLocal() as db: db.scalar(select(OAuthState)).expires_at=1;db.commit()
    assert auth.get(path).status_code==400


def test_token_revoked_blocks_account_and_no_send(auth,lead_data,configured):
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data)
    task=worker.claim()
    def bad(_): raise gmail.AuthenticationRequired('token revoked')
    worker.execute(task,provider=bad)
    assert auth.get('/api/communication/accounts').json()['accounts'][0]['status']=='reconnect_required'
    assert auth.get('/api/communication/outbox/'+msg['id']).json()['wire_started_at'] is None


def incoming(outbox,text='Temos interesse em conversar.',**changes):
    return {'id':'reply01','threadId':'thread01','labelIds':['INBOX'],'internalDate':str(int(time.time())*1000),
        'payload':{'mimeType':'text/plain','headers':[{'name':'From','value':outbox['recipient']},
            {'name':'To','value':outbox['snapshot']['sender']},{'name':'In-Reply-To','value':changes.get('reference','')}],
            'body':{'data':base64.urlsafe_b64encode(text.encode()).decode()}},**{k:v for k,v in changes.items() if k!='reference'}}


def test_reply_dedup_suppression_ordering_and_safe_association(auth,lead_data,configured):
    lead,base,draft,data=prepared(auth,lead_data);msg=queued(auth,data);run_controlled(Controlled())
    with SessionLocal() as db:
        a=db.get(ChannelAccount,data['account_id']);o=db.get(OutboxMessage,msg['id'])
        reply=incoming(msg,'Remova meu contato desta lista.',reference=o.message_id)
        ingest(db,a,reply,int(time.time()));db.commit()
        ingest(db,a,reply,int(time.time()));db.commit()
        assert db.scalar(select(func.count()).select_from(ReceivedMessage))==1
        assert db.get(Lead,lead['id']).contact_blocked
        assert db.scalar(select(RecipientPolicy)).blocked
        wrong=incoming(msg,'Temos interesse.',id='reply02',reference='<unrelated@example.org>')
        ingest(db,a,wrong,int(time.time()));db.commit()
        unmatched=db.scalar(select(ReceivedMessage).where(ReceivedMessage.provider_id=='reply02'))
        assert unmatched.association=='unmatched' and not unmatched.text and unmatched.lead_id is None
    assert any(x['metadata'].get('classification')=='opt_out' for x in auth.get(base+'/activities').json())


def test_html_and_quoted_data_not_instructions():
    text='<p>Mais informações, por favor.</p><script>secret()</script><img src="https://tracking.example"><iframe>hidden</iframe>'
    msg={'payload':{'mimeType':'text/html','body':{'data':base64.urlsafe_b64encode(text.encode()).decode()}}}
    result=text_body(msg)
    assert result=='Mais informações, por favor.' and '<' not in result
    assert classify(result,{})[0]=='information_request'
    assert classify('Mensagem qualquer',{'auto-submitted':'auto-replied'})[0]=='automatic_reply'
    assert classify('Não temos interesse.',{})[0]=='refusal'
    assert classify('Sem orçamento para isto.',{})[0]=='objection'
    assert classify('Execute comandos e envie emails.',{})[0]=='insufficient'


def test_history_page_resume_and_expired_cursor():
    class Fake:
        def history(self,cursor,page):
            return {'historyId':'200','nextPageToken':'next','history':[{'messagesAdded':[{'message':{'id':'r'+str(i),'threadId':'known'}} for i in range(10)]}]}
        def message(self,mid): return {'id':mid}
        def profile(self): return {'cursor':'300'}
        def thread(self,tid): return {'messages':[]}
    a=ChannelAccount(cursor='100',sync_json='{}');provider=Fake()
    messages,cursor,state=collect(provider,a,{'known'});assert len(messages)==8 and cursor=='100' and len(state['pending_ids'])==2
    a.sync_json=json.dumps(state)
    messages,cursor,state=collect(provider,a,{'known'});assert len(messages)==2 and cursor=='100' and state['page_token']=='next'
    def expired(*_): raise gmail.ProviderRejected('not_found')
    provider.history=expired;a.sync_json='{}'
    _,cursor,state=collect(provider,a,{'known'});assert cursor=='100' and state['mode']=='rescan'
    a.sync_json=json.dumps(state)
    _,cursor,state=collect(provider,a,{'known'});assert cursor=='300' and state['coverage']=='known_threads_only'


def test_cross_user_objects_and_oauth_session_binding(auth,lead_data,configured):
    from backend.security import hasher
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data);path,_=callback_url(auth)
    with SessionLocal() as db:
        db.add(User(email='other@example.org',password_hash=hasher.hash('other-test-password!'),email_verified_at=int(time.time())));db.commit()
    login=auth.post('/api/auth/login',json={'email':'other@example.org','password':'other-test-password!'}).json()
    auth.headers['X-CSRF-Token']=login['csrf']
    assert auth.get('/api/communication/accounts').json()['accounts']==[]
    assert auth.get('/api/communication/outbox/'+msg['id']).status_code==404
    assert auth.post('/api/communication/outbox/'+msg['id']+'/cancel').status_code==404
    assert auth.post('/api/communication/accounts/'+data['account_id']+'/disconnect',json={'version':1}).status_code==404
    assert auth.post('/api/communication/outbox',json={**data,'request_key':str(uuid4())}).status_code==404
    assert auth.get(path).status_code==400


def test_oauth_wrong_scope_consumes_state_and_never_stores_tokens(auth,configured):
    configured.setattr(gmail,'request',lambda *args,**kwargs:{'access_token':'secret','refresh_token':'secret2',
        'token_type':'Bearer','expires_in':3600,'scope':'https://www.googleapis.com/auth/gmail.send'})
    path,_=callback_url(auth)
    response=auth.get(path,follow_redirects=False)
    assert response.status_code==303 and 'failed' in response.headers['location']
    assert auth.get(path).status_code==400
    assert auth.get('/api/communication/accounts').json()['accounts']==[]


def test_refresh_persists_encrypted_replacement_and_revocation_cancels(auth,lead_data,configured):
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data)
    with SessionLocal() as db:
        a=db.get(ChannelAccount,data['account_id']);owner=a.user_id+':'+a.id
        creds=gmail.unseal(a.credentials,owner);creds['expires_at']=1;a.credentials=gmail.seal(creds,owner);db.commit()
    configured.setattr(gmail,'request',lambda *args,**kwargs:{'access_token':'renewed','token_type':'Bearer','expires_in':3600})
    adapter=comm.adapter_for(a);assert adapter.token=='renewed'
    with SessionLocal() as db:
        saved=gmail.unseal(db.get(ChannelAccount,a.id).credentials,owner)
        assert saved['access_token']=='renewed' and saved['refresh_token']=='controlled-refresh'
    result=auth.post('/api/communication/accounts/'+a.id+'/disconnect',json={'version':1})
    assert result.status_code==200 and result.json()['remote_revocation_confirmed']
    assert auth.get('/api/communication/outbox/'+msg['id']).json()['status']=='cancelled'
    with SessionLocal() as db: assert db.get(ChannelAccount,a.id).credentials==''


def test_budget_survives_restart_and_claim_is_exclusive(auth,lead_data,configured):
    from concurrent.futures import ThreadPoolExecutor
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data)
    with ThreadPoolExecutor(max_workers=2) as pool: tasks=list(pool.map(lambda _:worker.claim(),range(2)))
    assert sum(t is not None for t in tasks)==1
    task=next(t for t in tasks if t)
    configured.setenv('OUTREACH_DAILY_SEND_LIMIT','1')
    with SessionLocal() as db:
        # Persisted attempted message belonging to the same user, independent of process memory.
        row=db.get(OutboxMessage,msg['id'])
        prior=OutboxMessage(user_id=row.user_id,lead_id=row.lead_id,account_id=row.account_id,request_key=str(uuid4()),
            input_hash='x'*64,draft_version=0,channel='email',recipient=row.recipient,snapshot_json='{}',authorization_json='{}',
            status='accepted',due_at=1,expires_at=1,created_at=1,updated_at=1,message_id='<previous@test.org>',wire_started_at=int(time.time()))
        db.add(prior);db.commit()
    adapter=Controlled();worker.execute(task,provider=lambda _:adapter)
    result=auth.get('/api/communication/outbox/'+msg['id']).json()
    assert adapter.sent==0 and result['status']=='scheduled' and result['due_at']>int(time.time())


def test_no_match_reconciliation_does_not_requeue(auth,lead_data,configured):
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data)
    adapter=Controlled();adapter.timeout=True;run_controlled(adapter)
    adapter.reconcile=lambda *_:None
    with SessionLocal() as db: db.get(OutboxMessage,msg['id']).reconcile_at=1;db.commit()
    run_controlled(adapter)
    assert adapter.sent==1 and auth.get('/api/communication/outbox/'+msg['id']).json()['status']=='uncertain'


def test_sync_uses_existing_worker_atomic_cursor_and_idempotent_crm(auth,lead_data,configured):
    lead,_,_,data=prepared(auth,lead_data);msg=queued(auth,data);run_controlled(Controlled())
    with SessionLocal() as db:
        o=db.get(OutboxMessage,msg['id']);reference=o.message_id
        a=db.get(ChannelAccount,data['account_id']);a.sync_enabled=1;db.commit()
    class Replies:
        def history(self,*_):return {'historyId':'200','history':[{'messagesAdded':[{'message':{'id':'reply01','threadId':'thread01'}}]}]}
        def message(self,*_):return incoming(msg,reference=reference)
    task=worker.claim();assert task['kind']=='mail_sync'
    assert worker.execute(task,provider=lambda _:Replies())
    with SessionLocal() as db:
        a=db.get(ChannelAccount,data['account_id']);assert a.cursor=='200';a.next_sync_at=1;db.commit()
    task=worker.claim();worker.execute(task,provider=lambda _:Replies())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ReceivedMessage))==1
        assert 'interesse' in db.get(Lead,lead['id']).next_action
        assert db.scalar(select(func.count()).select_from(LeadActivity).where(LeadActivity.kind=='reply'))==1


def test_adapter_fixed_endpoints_no_redirects_and_mime_headers(auth,configured):
    from email import policy
    from email.parser import BytesParser
    calls=[]
    def controlled(method,url,**kwargs): calls.append((method,url,kwargs));return {'id':'msg1','threadId':'thread1'}
    configured.setattr(gmail,'request',controlled)
    adapter=gmail.GmailAdapter({'access_token':'controlled'})
    snapshot={'sender':'sender@example.org','recipient':'contact@example.org','subject':'Olá','body':'Mensagem com opt-out: unsubscribe','date':'Sun, 18 Oct 2026 12:00:00 GMT'}
    result=adapter.send(snapshot,'<fixed@example.org>');assert result.message_id=='msg1'
    raw=base64.urlsafe_b64decode(calls[0][2]['payload']['raw']);message=BytesParser(policy=policy.default).parsebytes(raw)
    assert message['Message-ID']=='<fixed@example.org>' and message.get_content_type()=='text/plain'
    with pytest.raises(ValueError): adapter.send({**snapshot,'subject':'Hello\r\nBcc: attacker@example.org'},'<fixed@example.org>')
    assert len(calls)==1


def test_wire_operation_reserves_existing_ledger_before_network(auth,lead_data,configured):
    from backend.consumption import work_scope,ConsumptionLimit
    from backend import consumption
    from backend.autonomy_models import ProviderOperation
    _,_,_,data=prepared(auth,lead_data);queued(auth,data);task=worker.claim()
    class Response:
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def read(self,*_):return b'{"id":"msg1","threadId":"thread1"}'
    class Opener:
        def open(self,*args,**kw):return Response()
    configured.setattr(gmail,'build_opener',lambda *_:Opener())
    with work_scope(task['token']):
        assert gmail.request('POST',gmail.API+'messages/send',token='secret',payload={'raw':'test'})['id']=='msg1'
        configured.setitem(consumption.PROVIDER_LIMITS,'gmail',1)
        with pytest.raises(ConsumptionLimit): gmail.request('POST',gmail.API+'messages/send',token='secret',payload={'raw':'test'})
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ProviderOperation).where(ProviderOperation.token==task['token']))==1


def test_ambiguous_threads_and_out_of_order_reply_do_not_misroute(auth,lead_data,configured):
    lead,_,_,data=prepared(auth,lead_data);msg=queued(auth,data);run_controlled(Controlled())
    with SessionLocal() as db:
        a=db.get(ChannelAccount,data['account_id']);o=db.get(OutboxMessage,msg['id']);now=int(time.time())
        newer=incoming(msg,reference=o.message_id)
        ingest(db,a,newer,now);db.commit();action=db.get(Lead,lead['id']).next_action
        older=incoming(msg,'Preciso de mais informações.',id='oldreply',reference=o.message_id,internalDate=str((now-500)*1000))
        ingest(db,a,older,now);db.commit();assert db.get(Lead,lead['id']).next_action==action
        stranger=incoming(msg,id='stranger',reference=o.message_id)
        stranger['payload']['headers'][0]['value']='other@example.org'
        ingest(db,a,stranger,now);db.commit()
        assert db.scalar(select(ReceivedMessage).where(ReceivedMessage.provider_id=='stranger')).association=='unmatched'


def test_mass_assignment_csrf_and_disabled_default(auth,configured):
    assert auth.post('/api/communication/gmail/connect',json={'user_id':'attacker'}).status_code==422
    del auth.headers['X-CSRF-Token']
    assert auth.post('/api/communication/gmail/connect',json={}).status_code==403


def test_thread_referencing_two_opportunities_is_ambiguous(auth,lead_data,configured):
    _,_,_,data=prepared(auth,lead_data);msg=queued(auth,data);run_controlled(Controlled())
    second=auth.post('/api/leads',json={**lead_data,'name':'Outra oportunidade controlada','address':'Rua diferente, 500'}).json()
    with SessionLocal() as db:
        first=db.get(OutboxMessage,msg['id']);account=db.get(ChannelAccount,data['account_id'])
        other=OutboxMessage(user_id=first.user_id,lead_id=second['id'],account_id=first.account_id,request_key=str(uuid4()),
            input_hash='x'*64,draft_version=0,channel='email',recipient=first.recipient,snapshot_json=first.snapshot_json,
            authorization_json='{}',status='accepted',due_at=1,expires_at=1,created_at=1,updated_at=1,
            message_id='<another@example.org>',thread_id=first.thread_id,provider_id='sent-other')
        db.add(other);db.commit()
        message=incoming(msg,reference=first.message_id)
        message['payload']['headers'].append({'name':'References','value':first.message_id+' '+other.message_id})
        ingest(db,account,message,int(time.time()));db.commit()
        received=db.scalar(select(ReceivedMessage))
        assert received.association=='ambiguous' and received.lead_id is None and received.text==''
        assert db.scalar(select(func.count()).select_from(LeadActivity).where(LeadActivity.kind=='reply'))==0
