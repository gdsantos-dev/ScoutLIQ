"""Synthetic canonical histories. No providers, messages or production databases."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, event, insert
from backend.db import SessionLocal, engine
from backend.models import Lead, User, LeadActivity, SmartSearch, ResearchBatch, ResearchBatchItem
from backend.autonomy_models import WorkAttempt, ProviderOperation
from backend.absorption_models import AbsorptionBatch, AbsorptionItem
from backend.commercial_review_models import CommercialReview
from backend.opportunity_models import OutreachDraft
from backend.communication_models import ChannelAccount, OutboxMessage, MessageEvent, ReceivedMessage
from backend.operational_intelligence import report, window


def uid(): return str(uuid4())


def company(db,user,**changes):
    lead=Lead(user_id=user.id,name='Empresa sintética',category='Cafeteria',city='Recife',latitude=-8,longitude=-34,
              **changes)
    db.add(lead);db.flush();return lead


def actor(db): return db.scalar(select(User).where(User.email=='test@example.com'))


def read(auth,**params):
    response=auth.get('/api/insights/operations',params=params)
    assert response.status_code==200,response.text
    data=response.json()
    assert 'credentials' not in response.text and 'message_body' not in response.text
    return data


def metrics(data): return {m['key']:m['value'] for m in data['metrics']}
def rates(data): return {r['key']:r for r in data['rates']}


def search(db,user,leads,duplicates=(),**kwargs):
    now=int(time.time())
    s=SmartSearch(user_id=user.id,request_key=uid(),intent_json='{"search_mode":"general"}',
        state_json=json.dumps({'candidates':[{'id':l.id,'origin':'new','group':'qualified'} for l in leads],
                              'duplicate_records':[{'id':l.id,'origin':'duplicate'} for l in duplicates]}),
        deadline=now+100,created_at=kwargs.pop('created_at',now-60),**kwargs)
    db.add(s);db.flush();return s


def absorb(db,user,status='imported',lead=None,**kwargs):
    batch=AbsorptionBatch(user_id=user.id,request_key=uid(),source='external',payload_hash='a'*64)
    db.add(batch);db.flush()
    item=AbsorptionItem(user_id=user.id,batch_id=batch.id,position=0,status=status,lead_id=lead.id if lead else None,
        payload_json=kwargs.pop('payload_json','{}'),**kwargs)
    db.add(item);db.flush();return item


def accepted(db,user,lead,now=None):
    now=now or int(time.time())-100
    account=ChannelAccount(user_id=user.id,identity=uid()+'@example.test');db.add(account);db.flush()
    box=OutboxMessage(user_id=user.id,lead_id=lead.id,account_id=account.id,request_key=uid(),input_hash='0'*64,
        draft_version=1,channel='email',recipient='synthetic@example.test',snapshot_json='{}',authorization_json='{}',
        status='accepted',due_at=now,expires_at=now+86400,created_at=now,updated_at=now,message_id=uid(),provider_id=uid(),thread_id=uid())
    db.add(box);db.flush()
    db.add(MessageEvent(user_id=user.id,outbox_id=box.id,event='accepted',created_at=now))
    db.add(LeadActivity(user_id=user.id,lead_id=lead.id,kind='email',created_at=now,
        metadata_json=json.dumps({'event':'outreach_accepted','outbox_id':box.id})))
    return box


def test_empty_data_has_unknown_rates_and_no_fabricated_alerts(auth):
    data=read(auth);m=metrics(data)
    assert data['coverage']['companies']==0 and data['diagnostics']==[]
    assert m['contacts']==m['unique']==m['won']==0
    assert all(r['value'] is None for r in data['rates'])
    assert all(t['seconds'] is None for t in data['times'])
    assert m['monetary_cost'] is None and m['cache_avoided'] is None


def test_sources_deduplicate_same_company_without_merging_homonyms(auth):
    with SessionLocal() as db:
        u=actor(db);a=company(db,u,source='manual');b=company(db,u,source='external',source_id='absorption:test')
        search(db,u,[a],[a]);search(db,u,[a]);absorb(db,u,lead=a);absorb(db,u,lead=b);absorb(db,u,status='duplicate')
        db.commit()
    all_data=read(auth);m=metrics(all_data)
    assert m['unique']==2 and m['discovered']==7 and m['duplicates']==2
    assert all_data['coverage']['multi_source']==1
    assert read(auth,origin='search')['coverage']['companies']==1
    assert read(auth,origin='manual')['coverage']['companies']==1
    assert read(auth,origin='absorption')['coverage']['companies']==2
    assert rates(all_data)['eligibility']['numerator']==2 and rates(all_data)['eligibility']['denominator']==3
    assert all(c['small_sample'] for c in all_data['cohorts'])


def test_demo_is_excluded_from_every_linked_relation(auth):
    with SessionLocal() as db:
        u=actor(db);l=company(db,u,demo=True);search(db,u,[l],[l]);absorb(db,u,lead=l);accepted(db,u,l);db.commit()
    d=read(auth);m=metrics(d)
    assert d['coverage']['companies']==0 and m['unique']==m['contacts']==m['discovered']==0


def test_missing_identity_and_partial_legacy_history_are_not_invented(auth):
    with SessionLocal() as db:
        u=actor(db);company(db,u,source='legacy',stage='won');absorb(db,u,status='pending');db.commit()
    d=read(auth);m=metrics(d)
    assert d['coverage']['origin_unknown']==1
    assert m['won']==0 and m['outcomes_undated']==1 and m['unlinked']==1 and m['unique']==0
    assert m['opportunities']==0 and d['history']['intelligence']['closedCount']==0
    assert {a['key'] for a in d['diagnostics']} >= {'coordinates','outcomes_undated'}


def test_interrupted_resumed_item_counted_once_and_time_not_overwritten(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u)
        b=ResearchBatch(user_id=u.id,created_at=now-600,status='completed');db.add(b);db.flush()
        i=ResearchBatchItem(batch_id=b.id,lead_id=l.id,status='done',started_at=now-100,finished_at=now-50,phase='deep');db.add(i);db.flush()
        for t,start,end,status in [(uid(),now-500,now-450,'expired'),(uid(),now-100,now-50,'committed')]:
            db.add(WorkAttempt(token=t,user_id=u.id,kind='batch',item_id=i.id,started_at=start,finished_at=end,status=status))
        db.commit()
    d=read(auth);m=metrics(d);times={t['key']:t for t in d['times']}
    assert m['investigations_started']==m['investigations_completed']==m['expired_attempts']==m['deepening']==1
    assert times['queue']['seconds']==100 and times['processing']['seconds']==50 and times['processing']['samples']==1
    assert rates(d)['completion']['value']==100


def test_completion_events_do_not_corrupt_started_cohort_denominator(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u);b=ResearchBatch(user_id=u.id,created_at=now-100*86400);db.add(b);db.flush()
        db.add(ResearchBatchItem(batch_id=b.id,lead_id=l.id,status='done',started_at=now-99*86400,finished_at=now-10))
        db.commit()
    d=read(auth);m=metrics(d)
    assert m['investigations_started']==0 and m['investigations_completed']==1
    assert rates(d)['completion']['value'] is None


def test_provider_calls_failures_reserved_and_costs_remain_distinct(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u);s=search(db,u,[l],status='completed');t=uid()
        db.add(WorkAttempt(token=t,user_id=u.id,kind='smart',item_id=s.id,started_at=now-50,finished_at=now-5,status='committed'));db.flush()
        for status in ('completed','failed','reserved'): db.add(ProviderOperation(token=t,provider='website',started_at=now-40,status=status))
        db.commit()
    d=read(auth);m=metrics(d);provider=next(p for p in d['providers'] if p['provider']=='website')
    assert m['provider_operations']==3 and m['provider_failures']==1 and m['monetary_cost'] is None
    assert provider['reserved']==1 and d['averages'][0]['value']==3


@pytest.mark.parametrize('zone,iso,start_iso',[
    ('America/Sao_Paulo','2026-10-26T01:00:00+00:00','2026-10-19T03:00:00+00:00'),
    ('UTC','2026-10-26T01:00:00+00:00','2026-10-20T00:00:00+00:00'),
    ('America/New_York','2026-03-10T15:00:00+00:00','2026-03-04T05:00:00+00:00')])
def test_calendar_window_obeys_user_zone_and_dst(zone,iso,start_iso):
    start,end,today=window('7',zone,int(datetime.fromisoformat(iso).timestamp()))
    assert start==int(datetime.fromisoformat(start_iso).timestamp()) and end>start


def test_fresh_canonical_classification_only_and_selection_denominator(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db)
        for state,dirty,expiry in [('selected',0,now+300),('deferred',1,now+300),('unreviewed',0,now-1)]:
            l=company(db,u);db.add(CommercialReview(lead_id=l.id,user_id=u.id,state=state,decided_at=now-10,
                classification='priority',dirty=dirty,refresh_at=expiry))
        db.commit()
    d=read(auth);m=metrics(d)
    assert m['opportunities']==1 and m['qualification_coverage']==1
    assert m['reviewed']==2 and m['selected']==1 and rates(d)['selection']['value']==50


def test_approved_draft_and_queued_attempt_are_not_contact(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u);b=accepted(db,u,l);b.status='queued'
        db.add(OutreachDraft(user_id=u.id,lead_id=l.id,request_id=uid(),channel='email',locale='pt-BR',recipient='test@example.test',body='message_body secret',evidence_json='[]',status='approved',approved_at=now))
        db.commit()
    m=metrics(read(auth));assert m['drafts']==m['drafts_approved']==1 and m['contacts']==m['delivered']==m['read']==0


def test_manual_accepted_receipts_and_activity_mirrors_are_distinct(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u);box=accepted(db,u,l)
        for result in ('recorded','not_reached','delivery_failure'):
            db.add(LeadActivity(user_id=u.id,lead_id=l.id,kind='email',metadata_json=json.dumps({'event':'manual_activity','result':result,'occurred_at':now-60})))
        db.add(MessageEvent(user_id=u.id,outbox_id=box.id,event='accepted',created_at=now-50))
        db.add(MessageEvent(user_id=u.id,outbox_id=box.id,event='delivered',created_at=now-20))
        db.commit()
    m=metrics(read(auth));assert m['contacts']==2 and m['contacts_declared']==m['contacts_accepted']==m['delivered']==1 and m['read']==0


@pytest.mark.parametrize('association,classification,thread_match,expected',[
    ('matched','interest',True,1),('matched','information_request',True,1),('ambiguous','interest',True,0),
    ('matched','interest',False,0),('matched','automatic_reply',True,0),('matched','insufficient',True,0),
    ('matched','delivery_failure',True,0),('matched','refusal',True,1)])
def test_reply_requires_traceable_account_thread_and_commercial_classification(auth,association,classification,thread_match,expected):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u);b=accepted(db,u,l)
        db.add(ReceivedMessage(user_id=u.id,lead_id=l.id,account_id=b.account_id,provider_id=uid(),thread_id=b.thread_id if thread_match else uid(),
            association=association,classification=classification,sent_at=now-10,text='message_body secret'))
        db.commit()
    d=read(auth);m=metrics(d)
    assert m['replies']==expected and rates(d)['response']['numerator']==expected and rates(d)['response']['denominator']==1
    assert m['replies_uncertain']==1-expected and m['lost']==0


def test_declared_reply_does_not_create_conversion_without_trace(auth):
    with SessionLocal() as db:
        u=actor(db);l=company(db,u);db.add(LeadActivity(user_id=u.id,lead_id=l.id,kind='reply',metadata_json='{"event":"manual_activity"}'));db.commit()
    d=read(auth);assert metrics(d)['replies_declared']==1 and rates(d)['response']['value'] is None


def test_unassociated_message_is_unknown_and_never_attributed_to_an_origin(auth):
    with SessionLocal() as db:
        u=actor(db);a=ChannelAccount(user_id=u.id,identity='synthetic@example.test');db.add(a);db.flush()
        db.add(ReceivedMessage(user_id=u.id,lead_id=None,account_id=a.id,provider_id=uid(),thread_id='unmatched',
            classification='insufficient',association='ambiguous',sent_at=int(time.time())))
        db.commit()
    assert metrics(read(auth))['replies_uncertain']==1
    assert metrics(read(auth,origin='manual'))['replies_uncertain']==0
    assert metrics(read(auth))['replies']==0


def test_reply_before_new_acceptance_does_not_convert_current_contact_cohort(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u);old=accepted(db,u,l,now-100*86400);new=accepted(db,u,l,now-10)
        new.account_id=old.account_id;new.thread_id=old.thread_id
        db.add(ReceivedMessage(user_id=u.id,lead_id=l.id,account_id=old.account_id,provider_id=uid(),thread_id=old.thread_id,
            classification='interest',association='matched',sent_at=now-50))
        db.commit()
    d=read(auth);assert metrics(d)['replies']==1
    assert rates(d)['response']['numerator']==0 and rates(d)['response']['denominator']==1


def test_behavior_never_synthesizes_missing_close_or_pipeline_time(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u,stage='won',outcome_recorded_at=now-10,pipeline_added_at=None)
        db.add(LeadActivity(user_id=u.id,lead_id=l.id,kind='email',created_at=now-100))
        company(db,u,stage='lost',outcome_recorded_at=None);db.commit()
    h=read(auth)['history']['intelligence']
    assert h['closedCount']==1 and h['won']['medianCycleDays'] is None and h['won']['medianFirstContactDays'] is None


def test_rate_limiter_does_not_trigger_work(auth):
    from backend.security import limiter
    with SessionLocal() as db: user_id=actor(db).id
    for _ in range(30): limiter.check('operational-intelligence:'+user_id,30,60)
    assert auth.get('/api/insights/operations').status_code==429


def test_observed_diagnostics_and_dates_do_not_include_future_events(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);l=company(db,u,in_pipeline=True,next_action='Revisar acordo',next_action_on='2020-01-01',contact='valid@example.test')
        db.add(LeadActivity(user_id=u.id,lead_id=l.id,kind='email',metadata_json=json.dumps({'event':'manual_activity','occurred_at':now+86400})))
        db.commit()
    d=read(auth);assert metrics(d)['contacts']==0
    diag={x['key']:x for x in d['diagnostics']};assert diag['overdue']['count']==1 and 'invalid_recipient' not in diag
    assert all(x['population'] and x['action'] and x['consequence'] for x in d['diagnostics'])


def test_ownership_on_every_join_and_no_private_fields(auth):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);other=User(email='other@example.test',password_hash='not-used');db.add(other);db.flush()
        a=company(db,u);b=company(db,other);foreign=accepted(db,other,b)
        # Invalid historical links must not grant access just because their owner matches.
        db.add(ReceivedMessage(user_id=u.id,lead_id=a.id,account_id=foreign.account_id,provider_id=uid(),thread_id=foreign.thread_id,
                              classification='interest',association='matched',sent_at=now))
        search(db,u,[b]);absorb(db,u,lead=b);db.commit()
    d=read(auth);assert d['coverage']['companies']==1
    assert metrics(d)['contacts']==metrics(d)['replies']==0
    assert 'other@example.test' not in json.dumps(d)


@pytest.mark.parametrize('params',[{'period':'1'},{'period':'0'},{'origin':'other'},{'origin':"' OR 1=1 --"}])
def test_filters_are_closed(auth,params):
    assert auth.get('/api/insights/operations',params=params).status_code==422


def test_authentication_required(client):
    assert client.get('/api/insights/operations').status_code==401


def test_concurrent_read_is_idempotent_read_only_and_preserves_score(auth,monkeypatch):
    from backend import scoring, commercial_fit
    with SessionLocal() as db:
        u=actor(db);l=company(db,u,contact='valid@example.test');identifier=l.id;db.commit()
        before=(l.version,l.score_criteria_json,l.qualification_json,l.stage)
    def prohibited(*args,**kwargs): raise AssertionError('Report must not invoke score or external work')
    monkeypatch.setattr(scoring,'score',prohibited);monkeypatch.setattr(commercial_fit,'assess',prohibited)
    statements=[]
    def capture(*args): statements.append(args[2].strip().upper())
    event.listen(engine,'before_cursor_execute',capture)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool: data=list(pool.map(lambda _: read(auth),range(3)))
    finally: event.remove(engine,'before_cursor_execute',capture)
    assert all(d['metrics']==data[0]['metrics'] for d in data)
    assert not any(s.startswith(('INSERT','UPDATE','DELETE')) for s in statements)
    with SessionLocal() as db:
        l=db.get(Lead,identifier);assert (l.version,l.score_criteria_json,l.qualification_json,l.stage)==before


def test_safety_ceiling_refuses_partial_report(auth,monkeypatch):
    import backend.operational_intelligence as module
    with SessionLocal() as db:
        u=actor(db);company(db,u);company(db,u);db.commit()
    monkeypatch.setattr(module,'MAX_ROWS',1)
    assert auth.get('/api/insights/operations').status_code==422


@pytest.mark.parametrize('size',[1000,10000])
def test_volume_bounded_queries_and_aggregate_payload(auth,size):
    now=int(time.time())
    with SessionLocal() as db:
        u=actor(db);ids=[uid() for _ in range(size)]
        db.execute(insert(Lead),[dict(id=i,user_id=u.id,name='Volume sintético',category='Cafeteria',city='Recife',latitude=-8,longitude=-34,source='manual',created_at=now-100) for i in ids])
        db.execute(insert(LeadActivity),[dict(id=uid(),user_id=u.id,lead_id=i,kind='email',metadata_json='{"event":"manual_activity"}',created_at=now-50) for i in ids])
        db.execute(insert(CommercialReview),[dict(lead_id=i,user_id=u.id,state='selected',decided_at=now-30,classification='priority',dirty=0,refresh_at=now+3600) for i in ids])
        db.commit()
    statements=[]
    def capture(*args): statements.append(args[2])
    event.listen(engine,'before_cursor_execute',capture)
    try:
        start=time.perf_counter();d=read(auth);elapsed=time.perf_counter()-start
    finally: event.remove(engine,'before_cursor_execute',capture)
    assert metrics(d)['contacts']==size and d['coverage']['companies']==size
    assert len(statements)<=18 and len(json.dumps(d))<65000
    path=Path(f'artifacts/operational-volume-{size}.json');path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(dict(companies=size,activities=size,reviews=size,queries=len(statements),seconds=round(elapsed,4),
        response_bytes=len(json.dumps(d).encode()),providers=0,scope='SQLite sintético local; não é SLA de produção'),indent=2),encoding='utf-8')
