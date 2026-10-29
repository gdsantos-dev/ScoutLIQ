import json
import time
from datetime import date, timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select, func, event
from backend.db import SessionLocal, engine
from backend.models import Lead, User, LeadActivity
from backend.communication_models import ChannelAccount, OutboxMessage, MessageEvent, ReceivedMessage
from backend.opportunity_models import OutreachDraft, RecipientPolicy
from backend.followup_models import FollowupPreference
from backend.commercial_review_models import CommercialOperation
from backend.followup import local_day
from test_commercial_review import create, preview, commit


def queue(auth, **params):
    r=auth.get('/api/commercial-review/queue',params={'view':'followup',**params})
    assert r.status_code==200,r.text
    return r.json()


def operation(auth, rows, action, **options):
    payload={'request_key':str(uuid4()),'action':action,'selection':[{'id':r['id'],'version':r['version'],
        'review_version':r['review']['version'],'followup_version':r['followup']['version']} for r in rows],**options}
    r=auth.post('/api/commercial-review/operations/preview',json=payload)
    assert r.status_code==201,r.text
    return r.json()


def manual(auth, lead, **data):
    r=auth.post('/api/leads/'+lead['id']+'/activities',json={'kind':'email','body':'Contato declarado em cenário controlado.',
        'occurred_on':(date.today()-timedelta(days=10)).isoformat(),'request_id':str(uuid4()),**data})
    assert r.status_code==201,r.text
    return r.json()


def provider(lead,status='accepted',receipt=True,days=10):
    now=int(time.time());stamp=now-days*86400
    with SessionLocal() as db:
        l=db.get(Lead,lead['id']);a=ChannelAccount(user_id=l.user_id,identity=str(uuid4())+'@example.org');db.add(a);db.flush()
        b=OutboxMessage(user_id=l.user_id,lead_id=l.id,account_id=a.id,request_key=str(uuid4()),input_hash='0'*64,
            draft_version=1,channel='email',recipient=l.contact,snapshot_json='{}',authorization_json='{}',status=status,
            due_at=stamp,expires_at=now+86400,created_at=stamp,updated_at=stamp,message_id='<controlled@example.org>',
            provider_id='provider01' if status=='accepted' else '',thread_id='thread01')
        db.add(b);db.flush()
        if receipt: db.add(MessageEvent(user_id=l.user_id,outbox_id=b.id,event='accepted',created_at=stamp))
        if status=='accepted': db.add(LeadActivity(user_id=l.user_id,lead_id=l.id,kind='email',body='Aceitação técnica controlada.',created_at=stamp,
            metadata_json=json.dumps({'event':'outreach_accepted','outbox_id':b.id})))
        db.commit();return b.id,a.id


def response(lead,classification,association='matched',thread='thread01'):
    bid,aid=provider(lead)
    with SessionLocal() as db:
        l=db.get(Lead,lead['id']);r=ReceivedMessage(user_id=l.user_id,lead_id=l.id,account_id=aid,provider_id=str(uuid4()),
            thread_id=thread,classification=classification,association=association,text='Texto controlado, requer revisão.',sent_at=int(time.time()))
        db.add(r);db.commit();return r.id


def test_discovery_never_creates_followup(auth,lead_data):
    create(auth,lead_data)
    row,=queue(auth)['items'];assert row['followup']['strategy'] is None
    op=operation(auth,[row],'followup_prepare');assert op['eligible']==0
    assert auth.get('/api/communication/outbox').json()['messages']==[]


def test_contact_missing_preserves_score(auth,lead_data):
    lead=create(auth,lead_data,contact='',whatsapp='')
    row,=queue(auth)['items'];assert row['followup']['code']=='verify_contact'
    assert row['qualification']['score']==lead['score']['value']


@pytest.mark.parametrize('status',['queued','executing','uncertain'])
def test_pending_is_never_sent(auth,lead_data,status):
    lead=create(auth,lead_data);provider(lead,status,False)
    row,=queue(auth)['items'];p=row['followup']
    assert p['code']=='check_execution' and p['communication']['accepted_at'] is None
    assert operation(auth,[row],'followup_prepare')['eligible']==0


def test_provider_acceptance_without_delivery_and_dedup_across_operations(auth,lead_data):
    lead=create(auth,lead_data);bid,_=provider(lead)
    row,=queue(auth)['items'];p=row['followup']
    assert p['code']=='review_followup' and p['communication']['delivery']=='unknown'
    assert p['source']['id']==bid and p['communication']['accepted_at']
    op=operation(auth,[row],'followup_prepare');assert op['eligible']==1
    assert op['preview'][0]['draft']['strategy']=='follow_up'
    result=commit(auth,op);assert result['results'][0]['status']=='success'
    assert commit(auth,op)==result
    row,=queue(auth)['items'];assert row['followup']['code']=='review_draft'
    assert operation(auth,[row],'followup_prepare')['eligible']==0
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OutreachDraft))==1
        assert db.scalar(select(func.count()).select_from(OutboxMessage))==1


@pytest.mark.parametrize('classification,code,strategy',[
    ('interest','review_response','reply'),('information_request','prepare_reply','reply'),('objection','review_proposal','reply'),
    ('refusal','stop_contact',None),('opt_out','stop_contact',None),('delivery_failure','stop_contact',None),
    ('automatic_reply','wait_human',None),('insufficient','review_response',None)])
def test_reply_classifications_are_conservative(auth,lead_data,classification,code,strategy):
    lead=create(auth,lead_data);rid=response(lead,classification)
    row,=queue(auth)['items'];p=row['followup']
    assert p['code']==code and p['strategy']==strategy
    assert p['response']['id']==rid
    if code=='stop_contact': assert p['rank']>=90


@pytest.mark.parametrize('association,thread',[('unmatched','thread01'),('ambiguous','thread01'),('matched','otherthread')])
def test_wrong_association_is_not_used(auth,lead_data,association,thread):
    lead=create(auth,lead_data);response(lead,'interest',association,thread)
    row,=queue(auth)['items'];assert row['followup']['response'] is None


def test_manual_provenance_date_and_idempotency(auth,lead_data):
    lead=create(auth,lead_data)
    data={'kind':'whatsapp','result':'contacted','occurred_on':(date.today()-timedelta(days=10)).isoformat(),'request_id':str(uuid4())}
    url='/api/leads/'+lead['id']+'/activities'
    first=auth.post(url,json=data);assert first.status_code==201,first.text
    assert auth.post(url,json=data).json()['activity']['id']==first.json()['activity']['id']
    assert auth.post(url,json={**data,'body':'Mudou'}).status_code==409
    meta=first.json()['activity']['metadata'];assert meta['provenance']=='operator_declared' and not meta['provider_verified']
    row,=queue(auth)['items'];assert row['followup']['source']['type']=='operator_declared'
    assert row['followup']['communication']['accepted_at'] is None
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(OutboxMessage))==0


def test_manual_refusal_never_unlocks_contact(auth,lead_data):
    lead=create(auth,lead_data);manual(auth,lead,kind='reply',result='opt_out')
    row,=queue(auth)['items'];assert row['followup']['code']=='stop_contact'
    assert auth.post('/api/leads/'+lead['id']+'/activities',json={'kind':'email'}).status_code==409
    op=operation(auth,[row],'followup_enable');commit(auth,op)
    assert queue(auth)['items'][0]['followup']['code']=='stop_contact'


def test_preserve_manual_action_with_explicit_consent_and_partial_results(auth,lead_data):
    a=create(auth,lead_data);b=create(auth,lead_data)
    with SessionLocal() as db:
        l=db.get(Lead,a['id']);l.in_pipeline=True;l.next_action='Decisão humana';l.next_action_on='2020-01-01'
        db.get(Lead,b['id']).in_pipeline=True;db.commit()
    rows=queue(auth)['items'];assert rows[0]['id']==a['id'] and rows[0]['followup']['category']=='overdue'
    due=(date.today()+timedelta(days=10)).isoformat()
    op=operation(auth,rows,'followup_set',next_action='Revisar proposta',due_on=due)
    assert op['eligible']==1;result=commit(auth,op)
    assert {r['status'] for r in result['results']}=={'skipped','success'}
    rows=queue(auth)['items'];op=operation(auth,rows,'followup_set',next_action='Consentimento revisado',due_on=due,overwrite_manual=True)
    assert op['eligible']==2;commit(auth,op)
    with SessionLocal() as db:
        assert db.get(Lead,a['id']).next_action=='Consentimento revisado'
        assert db.get(Lead,a['id']).stage==a['stage']


def test_pause_resume_complete_and_recovery(auth,lead_data):
    lead=create(auth,lead_data);manual(auth,lead)
    row,=queue(auth)['items'];op=operation(auth,[row],'followup_snooze',due_on=(date.today()+timedelta(days=2)).isoformat())
    commit(auth,op);assert queue(auth)['items'][0]['followup']['category']=='paused'
    row,=queue(auth)['items'];commit(auth,operation(auth,[row],'followup_review'))
    row,=queue(auth)['items'];commit(auth,operation(auth,[row],'followup_complete'))
    engine.dispose();row,=queue(auth)['items'];assert row['followup']['category']=='completed'
    commit(auth,operation(auth,[row],'followup_disable'))
    row,=queue(auth)['items'];assert row['followup']['code']=='disabled'
    commit(auth,operation(auth,[row],'followup_enable'))
    assert queue(auth)['items'][0]['followup']['code']=='review_followup'


def test_settings_local_timezone_and_interval(auth,lead_data):
    lead=create(auth,lead_data)
    with SessionLocal() as db:
        user=db.scalar(select(User));user.timezone='Pacific/Kiritimati';db.commit()
        from datetime import datetime, timezone
        stamp=datetime(2026,10,26,12,tzinfo=timezone.utc).timestamp()
        assert local_day(user,stamp).isoformat()=='2026-10-27'
        user.timezone='America/Sao_Paulo';assert local_day(user,stamp).isoformat()=='2026-10-26'
        user.timezone='Pacific/Kiritimati';db.commit()
    provider(lead,days=3)
    assert queue(auth)['items'][0]['followup']['code']=='await_response'
    settings=auth.get('/api/followup/settings').json()
    r=auth.put('/api/followup/settings',json={'version':settings['version'],'interval_days':2});assert r.status_code==200,r.text
    assert auth.put('/api/followup/settings',json={'version':0,'interval_days':1}).status_code==409
    row,=queue(auth)['items'];assert row['followup']['code']=='review_followup'
    assert row['followup']['timezone']=='Pacific/Kiritimati'


def test_concurrent_context_change_refuses_confirmation(auth,lead_data):
    lead=create(auth,lead_data);manual(auth,lead)
    row,=queue(auth)['items'];op=operation(auth,[row],'followup_prepare')
    manual(auth,lead,kind='reply',result='refusal')
    r=commit(auth,op);assert r['results'][0]['status']=='failed'
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(OutreachDraft))==0


def test_positive_reply_before_higher_score_and_blocked_last(auth,lead_data):
    high=create(auth,lead_data,reviews=5000);low=create(auth,lead_data,reviews=0,rating=1);blocked=create(auth,lead_data)
    response(low,'interest');response(blocked,'opt_out')
    rows=queue(auth)['items'];assert rows[0]['id']==low['id'] and rows[-1]['id']==blocked['id']
    assert queue(auth,attention='response')['total']==1 and queue(auth,attention='blocked')['total']==1


def test_owned_dto_csrf_and_manual_future(auth,lead_data):
    lead=create(auth,lead_data)
    assert auth.post('/api/leads/'+lead['id']+'/activities',json={'kind':'email','occurred_on':'2099-01-01'}).status_code==422
    assert auth.post('/api/leads/'+lead['id']+'/activities',json={'kind':'email','channel':'whatsapp'}).status_code==422
    assert auth.put('/api/followup/settings',json={'version':0,'interval_days':0,'user_id':str(uuid4())}).status_code==422
    with SessionLocal() as db:
        other=User(email='other@example.org',password_hash='controlled');db.add(other);db.flush()
        l=db.get(Lead,lead['id']);l.user_id=other.id;db.commit()
    assert queue(auth)['total']==0
    assert auth.post('/api/leads/'+lead['id']+'/activities',json={'kind':'email'}).status_code==404


def test_sync_does_not_replace_manual_action(auth,lead_data):
    from backend.communication_replies import ingest
    import base64
    lead=create(auth,lead_data);bid,aid=provider(lead)
    with SessionLocal() as db:
        l=db.get(Lead,lead['id']);l.next_action='Ligar no horário combinado';l.next_action_on='2030-01-02'
        account=db.get(ChannelAccount,aid)
        ingest(db,account,{'id':'replyControlled','threadId':'thread01','internalDate':str(int(time.time())*1000),'payload':{
            'mimeType':'text/plain','headers':[{'name':'From','value':l.contact},{'name':'To','value':account.identity},{'name':'In-Reply-To','value':'<controlled@example.org>'}],
            'body':{'data':base64.urlsafe_b64encode(b'Temos interesse').decode()}}},int(time.time()))
        db.commit();assert l.next_action=='Ligar no horário combinado' and l.next_action_on=='2030-01-02'


def test_drafts_approval_is_not_sending(auth,lead_data):
    create(auth,lead_data)
    row,=queue(auth)['items'];op,_=preview(auth,[row],'prepare');commit(auth,op)
    assert queue(auth)['items'][0]['followup']['code']=='review_draft'
    with SessionLocal() as db:
        draft=db.scalar(select(OutreachDraft));draft.status='approved';db.commit()
    p=queue(auth)['items'][0]['followup'];assert p['code']=='review_contact_condition' and p['communication']['accepted_at'] is None


def test_operational_index_is_bounded_and_paged(auth,lead_data):
    lead=create(auth,lead_data)
    with SessionLocal() as db:
        owner=db.get(Lead,lead['id']).user_id
        db.add_all([Lead(user_id=owner,name=f'Controlada {i}',category='Cafeteria',city='Recife',latitude=0,longitude=0) for i in range(300)]);db.commit()
    first=queue(auth);assert first['index_pending']==51
    second=queue(auth);assert second['index_pending']==0 and second['total']==301
    statements=[]
    def capture(*args): statements.append(args[2])
    event.listen(engine,'before_cursor_execute',capture)
    try: page=queue(auth,limit=50)
    finally: event.remove(engine,'before_cursor_execute',capture)
    assert len(page['items'])==50 and len(statements)<20
    other=queue(auth,limit=50,offset=50)
    assert not {r['id'] for r in page['items']}&{r['id'] for r in other['items']}


def test_missing_acceptance_receipt_cannot_schedule_contact(auth,lead_data):
    lead=create(auth,lead_data);provider(lead,receipt=False)
    p=queue(auth)['items'][0]['followup'];assert p['code']=='verify_acceptance' and p['strategy'] is None


def test_provider_delivery_event_is_distinct(auth,lead_data):
    lead=create(auth,lead_data);bid,_=provider(lead)
    with SessionLocal() as db:
        box=db.get(OutboxMessage,bid);db.add(MessageEvent(user_id=box.user_id,outbox_id=bid,event='delivered'));db.commit()
    assert queue(auth)['items'][0]['followup']['communication']['delivery']=='confirmed'


def test_failed_transaction_can_resume_without_duplicates(auth,lead_data,monkeypatch):
    from backend import commercial_review
    lead=create(auth,lead_data);manual(auth,lead);row,=queue(auth)['items']
    op=operation(auth,[row],'followup_prepare');original=commercial_review.create_draft
    def interrupted(*args,**kwargs): original(*args,**kwargs);raise RuntimeError('controlled interruption')
    monkeypatch.setattr(commercial_review,'create_draft',interrupted)
    with pytest.raises(RuntimeError): commit(auth,op)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OutreachDraft))==0
        assert db.get(CommercialOperation,op['id']).status=='preview'
    monkeypatch.setattr(commercial_review,'create_draft',original)
    assert commit(auth,op)['results'][0]['status']=='success'


def test_two_previews_cannot_overwrite_followup_decision(auth,lead_data):
    create(auth,lead_data);row,=queue(auth)['items']
    a=operation(auth,[row],'followup_disable');b=operation(auth,[row],'followup_review')
    assert commit(auth,a)['results'][0]['status']=='success'
    assert commit(auth,b)['results'][0]['status']=='failed'


def test_settings_change_invalidates_preview_and_closed_stays_closed(auth,lead_data):
    lead=create(auth,lead_data);manual(auth,lead);row,=queue(auth)['items']
    op=operation(auth,[row],'followup_prepare')
    assert auth.put('/api/followup/settings',json={'version':0,'interval_days':30}).status_code==200
    assert commit(auth,op)['results'][0]['status']=='failed'
    with SessionLocal() as db: db.get(Lead,lead['id']).stage='lost';db.commit()
    row,=queue(auth)['items'];assert row['followup']['code']=='closed' and row['followup']['strategy'] is None


def test_complete_manual_action_does_not_reappear(auth,lead_data):
    lead=create(auth,lead_data);manual(auth,lead)
    with SessionLocal() as db:
        l=db.get(Lead,lead['id']);l.in_pipeline=True;l.next_action='Conferir contato';l.next_action_on='2020-01-01';db.commit()
    row,=queue(auth)['items'];commit(auth,operation(auth,[row],'followup_complete',overwrite_manual=True))
    row,=queue(auth)['items'];assert row['followup']['category']=='completed' and not row['followup']['manual_action']


def test_future_manual_action_is_not_due_today(auth,lead_data):
    lead=create(auth,lead_data);manual(auth,lead)
    with SessionLocal() as db:
        l=db.get(Lead,lead['id']);l.next_action='Retomar na data combinada';l.next_action_on='2099-01-01';db.commit()
    p=queue(auth)['items'][0]['followup'];assert p['category']=='awaiting' and p['strategy'] is None
    assert queue(auth,attention='today')['total']==0
