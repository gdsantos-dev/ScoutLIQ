import json
import time
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select, func, event
from backend.db import SessionLocal, engine
from backend.models import Lead, User, LeadActivity, ResearchBatchItem
from backend.opportunity_models import OpportunityEvidence, OutreachDraft, RecipientPolicy
from backend.commercial_review_models import CommercialReview, CommercialOperation
from backend.communication_models import OutboxMessage


def create(auth, lead_data, **changes):
    result = auth.post('/api/leads', json={**lead_data, 'name': 'Café '+str(uuid4())[:8], 'contact': 'equipe@example.org', **changes})
    assert result.status_code == 201, result.text
    return result.json()


def queue(auth, **params):
    response = auth.get('/api/commercial-review/queue', params=params)
    assert response.status_code == 200, response.text
    return response.json()


def preview(auth, rows, action='reviewed', **options):
    body = {'request_key': str(uuid4()), 'action': action, 'selection': [
        {'id': r['id'], 'version': r['version'], 'review_version': r['review']['version']} for r in rows], **options}
    response = auth.post('/api/commercial-review/operations/preview', json=body)
    assert response.status_code == 201, response.text
    return response.json(), body


def commit(auth, op):
    response = auth.post('/api/commercial-review/operations/'+op['id']+'/confirm', json={'confirm': True})
    assert response.status_code == 200, response.text
    return response.json()


def evidence(lead, **changes):
    with SessionLocal() as db:
        l = db.get(Lead, lead['id'])
        e = OpportunityEvidence(user_id=l.user_id, lead_id=l.id, source_key=str(uuid4()), statement='Cardápio não disponível nas páginas revisadas.',
            source_url='https://example.org/menu', method='operator_observation', classification='confirmed', category='content',
            scope='Apenas a página de cardápio.', observed_at=int(time.time()), valid_until=int(time.time())+86400,
            verified_at=int(time.time()), translations_json=json.dumps({'en-US':'Menu unavailable on the reviewed page.', 'es':'Menú no disponible en la página revisada.'}))
        for k,v in changes.items(): setattr(e,k,v)
        db.add(e); db.commit(); return e.id


def test_queue_uses_canonical_projection_and_bounded_evidence(auth, lead_data):
    lead = create(auth, lead_data)
    for _ in range(6): evidence(lead)
    result = queue(auth)
    row, = result['items']
    assert row['qualification']['score'] == lead['score']['value']
    assert row['source'] == lead['source'] and row['confirmed_count'] == 6
    assert len(row['summary']['facts']) == 3
    assert row['summary']['services'][0]['name'] == 'Desenvolvimento Web'
    assert row['summary']['services'][0]['type'] == 'inference'
    assert row['summary']['attention'] == row['summary']['facts'][0]['statement']
    assert row['review']['state'] == 'unreviewed'


def test_missing_evidence_does_not_invent_service_or_absent_site(auth, lead_data):
    create(auth, lead_data, website_status='unknown', contact='', whatsapp='')
    row, = queue(auth)['items']
    assert row['summary']['services'] == row['summary']['facts'] == []
    assert row['summary']['unknown']
    assert row['qualification']['class'] in ('promising','pending')
    op,_ = preview(auth,[row],action='prepare')
    assert op['eligible'] == 0 and 'Destinatário' in op['preview'][0]['reason']


@pytest.mark.parametrize('action',['reviewed','selected','deferred','not_priority'])
def test_triage_is_persistent_without_crm_or_score_change(auth, lead_data, action):
    leads = [create(auth, lead_data) for _ in range(2)]
    rows = queue(auth)['items']; op,_ = preview(auth,rows,action,reason='Decisão humana de teste.')
    assert op['eligible'] == 2 and not op['stage_changes'] and not op['external_send']
    result = commit(auth,op); assert all(r['status']=='success' for r in result['results'])
    assert queue(auth)['total'] == 0
    reviewed = queue(auth,state=action)['items']; assert len(reviewed)==2
    with SessionLocal() as db:
        for l in leads:
            saved = db.get(Lead,l['id']); assert saved.stage==l['stage'] and saved.version==l['version']
            r = db.get(CommercialReview,l['id']); assert r.author_id==saved.user_id and r.decided_at and r.reason
        assert db.scalar(select(func.count()).select_from(LeadActivity).where(LeadActivity.body=='Decisão humana de teste.')) == 2


def test_partial_invalid_selection_does_not_lose_valid_rows(auth,lead_data):
    create(auth,lead_data); rows=queue(auth)['items']
    rows.append({'id':str(uuid4()),'version':1,'review':{'version':1}})
    op,_=preview(auth,rows); assert op['eligible']==1
    result=commit(auth,op); assert [r['status'] for r in result['results']]==['success','skipped']


def test_reopen_and_new_evidence_revalidation_keep_human_decision(auth,lead_data):
    lead=create(auth,lead_data); op,_=preview(auth,queue(auth)['items']); commit(auth,op)
    evidence(lead)
    row,=queue(auth)['items']; assert row['review']['needs_review'] and row['review']['state']=='reviewed'
    op,_=preview(auth,[row],action='reopen');commit(auth,op)
    row,=queue(auth)['items']; assert row['review']['state']=='unreviewed' and not row['review']['needs_review']


@pytest.mark.parametrize('channel,locale',[('email','pt-BR'),('email','en-US'),('whatsapp','es')])
def test_drafts_reuse_canonical_models_without_any_send(auth,lead_data,channel,locale,monkeypatch):
    lead=create(auth,lead_data); evidence(lead)
    from backend import communication
    def forbidden(*a,**k): raise AssertionError('No communication may be authorized')
    monkeypatch.setattr(communication,'authorize_send',forbidden)
    op,_=preview(auth,queue(auth)['items'],action='prepare',channel=channel,locale=locale)
    assert op['eligible']==1 and op['preview'][0]['draft']['strategy']=='verified_opportunity'
    result=commit(auth,op);assert result['results'][0]['status']=='success'
    again=commit(auth,op);assert again==result
    with SessionLocal() as db:
        draft,=db.scalars(select(OutreachDraft)).all()
        assert draft.status=='draft' and not draft.approval_hash and draft.approved_at is None
        assert draft.channel==channel and draft.locale==locale
        assert db.scalar(select(func.count()).select_from(OutboxMessage))==0
        assert db.scalar(select(func.count()).select_from(LeadActivity).where(LeadActivity.kind.in_(['email','whatsapp'])))==0


def test_initial_strategy_without_confirmed_evidence(auth,lead_data):
    create(auth,lead_data);rows=queue(auth)['items'];op,_=preview(auth,rows,action='prepare')
    assert op['preview'][0]['draft']['strategy']=='initial' and op['preview'][0]['draft']['evidence_ids']==[]
    assert commit(auth,op)['results'][0]['status']=='success'
    rejected,_=preview(auth,rows,action='prepare',strategy='verified_opportunity')
    assert rejected['eligible']==0


@pytest.mark.parametrize('change',[{'contact':'Ana Silva'},{'contact':''},{'whatsapp':'123'}])
def test_invalid_recipients_remain_commercially_reviewable(auth,lead_data,change):
    lead=create(auth,lead_data,**({} if 'whatsapp' in change else change))
    if 'whatsapp' in change:
        with SessionLocal() as db: db.get(Lead,lead['id']).whatsapp=change['whatsapp'];db.commit()
    rows=queue(auth)['items']
    op,_=preview(auth,rows,action='prepare',channel='whatsapp' if 'whatsapp' in change else 'email')
    assert op['eligible']==0
    review,_=preview(auth,rows);assert commit(auth,review)['results'][0]['status']=='success'


def test_policy_block_added_after_preview_is_rechecked(auth,lead_data):
    lead=create(auth,lead_data);op,_=preview(auth,queue(auth)['items'],action='prepare')
    with SessionLocal() as db:
        l=db.get(Lead,lead['id']);db.add(RecipientPolicy(user_id=l.user_id,channel='email',recipient='equipe@example.org',blocked=1,recorded_at=int(time.time())));db.commit()
    result=commit(auth,op);assert result['results'][0]['status']=='failed'
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(OutreachDraft))==0


@pytest.mark.parametrize('mutation',['lead','evidence'])
def test_changed_context_requires_new_preview(auth,lead_data,mutation):
    lead=create(auth,lead_data);eid=evidence(lead);op,_=preview(auth,queue(auth)['items'],action='prepare')
    with SessionLocal() as db:
        if mutation=='lead': db.get(Lead,lead['id']).name='Nome atualizado'
        else: db.get(OpportunityEvidence,eid).classification='refuted'
        db.commit()
    result=commit(auth,op);assert result['results'][0]['status']=='failed'


def test_request_replay_conflict_expiration_and_confirmation(auth,lead_data):
    create(auth,lead_data);op,body=preview(auth,queue(auth)['items'])
    assert auth.post('/api/commercial-review/operations/preview',json=body).json()['id']==op['id']
    assert auth.post('/api/commercial-review/operations/preview',json={**body,'action':'selected'}).status_code==409
    assert auth.post('/api/commercial-review/operations/'+op['id']+'/confirm',json={'confirm':False}).status_code==422
    with SessionLocal() as db: db.get(CommercialOperation,op['id']).created_at=1;db.commit()
    assert auth.post('/api/commercial-review/operations/'+op['id']+'/confirm',json={'confirm':True}).status_code==409


def test_concurrent_confirmation_commits_once(auth,lead_data):
    create(auth,lead_data);op,_=preview(auth,queue(auth)['items'],action='prepare')
    from backend.commercial_review import confirm,ConfirmInput
    def run():
        with SessionLocal() as db:
            user=db.scalar(select(User).where(User.email=='test@example.com'))
            return confirm(op['id'],ConfirmInput(confirm=True),user,db)
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:run(),range(2)))
    assert results[0]==results[1]
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(OutreachDraft))==1


def test_queue_pagination_filters_query_count_and_no_network(auth,lead_data,monkeypatch):
    for i in range(6): create(auth,lead_data,city='Recife' if i<4 else 'Olinda')
    queue(auth);statements=[]
    def capture(*args): statements.append(args[2])
    event.listen(engine,'before_cursor_execute',capture)
    try:
        page=queue(auth,limit=2,search='Recife');assert page['total']==4
        assert len(statements)<20
    finally:event.remove(engine,'before_cursor_execute',capture)
    next_page=queue(auth,limit=2,search='Recife',offset=2)
    assert not set(r['id'] for r in page['items'])&set(r['id'] for r in next_page['items'])
    assert sum(queue(auth,classification=c)['total'] for c in ('priority','promising','pending','low','unavailable'))==6
    assert queue(auth,search="%' OR 1=1 --")['total']==0


def test_isolation_dtos_csrf_and_history(auth,lead_data):
    create(auth,lead_data);op,body=preview(auth,queue(auth)['items'])
    assert auth.post('/api/commercial-review/operations/preview',json={**body,'owner_id':'evil'}).status_code==422
    assert auth.post('/api/commercial-review/operations/preview',json={**body,'selection':body['selection']*51}).status_code==422
    assert auth.get('/api/commercial-review/operations/'+str(uuid4())).status_code==404
    assert auth.get('/api/commercial-review/leads/'+str(uuid4())).status_code==404
    with SessionLocal() as db:
        other=User(email='other@example.org',password_hash='unused');db.add(other);db.flush()
        db.get(CommercialOperation,op['id']).user_id=other.id;db.commit()
    assert auth.get('/api/commercial-review/operations/'+op['id']).status_code==404
    assert auth.post('/api/commercial-review/operations/'+op['id']+'/confirm',json={'confirm':True}).status_code==404
    auth.headers['X-CSRF-Token']='invalid'
    assert auth.post('/api/commercial-review/operations/preview',json=body).status_code==403


def test_reinvestigate_uses_existing_queue_and_preserves_stage(auth,lead_data):
    create(auth,lead_data);op,_=preview(auth,queue(auth)['items'],action='investigate');result=commit(auth,op)
    assert result['results'][0]['batch_ids']
    commit(auth,op)
    with SessionLocal() as db: assert db.scalar(select(func.count()).select_from(ResearchBatchItem))==1


def test_draft_edit_after_approval_invalidates_content_approval(auth,lead_data):
    lead=create(auth,lead_data);op,_=preview(auth,queue(auth)['items'],action='prepare');result=commit(auth,op)
    draftid=result['results'][0]['draft_id'];url=f"/api/leads/{lead['id']}/outreach/drafts/{draftid}"
    approved=auth.post(url+'/approve',json={'version':1}).json();assert approved['status']=='approved'
    edited=auth.put(url,json={'version':approved['version'],'body':'Texto revisado pelo operador, sem envio.'}).json()
    assert edited['status']=='draft' and edited['approved_at'] is None
    assert auth.post(url+'/dispatch',json={'version':edited['version']}).status_code==409


def test_unexpected_failure_rolls_back_and_retry_recovers(auth,lead_data,monkeypatch):
    from backend import commercial_review as service
    for _ in range(2): create(auth,lead_data)
    op,_=preview(auth,queue(auth)['items'],action='prepare')
    original=service.create_draft;calls=[]
    def fail_second(*args):
        calls.append(1)
        if len(calls)==2: raise RuntimeError('Controlled storage failure')
        return original(*args)
    with monkeypatch.context() as patch:
        patch.setattr(service,'create_draft',fail_second)
        with pytest.raises(RuntimeError):commit(auth,op)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(OutreachDraft))==0
        assert db.get(CommercialOperation,op['id']).status=='preview'
    assert all(r['status']=='success' for r in commit(auth,op)['results'])


@pytest.mark.parametrize('statement,service',[
    ('Processos manuais de agendamento observados e confirmados pelo operador.','Sistemas personalizados e automações empresariais'),
    ('Calendário editorial com atualização pendente confirmada pelo operador.','ORLIQ Social')])
def test_service_inferences_require_reviewed_need(auth,lead_data,statement,service):
    lead=create(auth,lead_data);evidence(lead,statement=statement)
    assert queue(auth)['items'][0]['summary']['services'][0]['name']==service


def test_replace_evidence_same_count_invalidates_previous_decision(auth,lead_data):
    lead=create(auth,lead_data);eid=evidence(lead)
    op,_=preview(auth,queue(auth)['items']);commit(auth,op)
    with SessionLocal() as db:db.delete(db.get(OpportunityEvidence,eid));db.commit()
    evidence(lead,statement='Outra observação confirmada com novo escopo.')
    assert queue(auth)['items'][0]['review']['needs_review']


def test_bulk_limit_fifty_and_all_blocked_no_effect(auth,lead_data):
    # Explicit IDs and maximum size are independent from queue page size.
    rows=[]
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='test@example.com'))
        for i in range(50):
            db.add(Lead(user_id=user.id,name=f'Café {i}',category='Cafeteria',city='Recife',latitude=-8,longitude=-34,contact=''))
        db.commit()
    rows=queue(auth,limit=50)['items'];assert len(rows)==50
    op,_=preview(auth,rows,action='prepare');assert op['eligible']==0
    result=commit(auth,op);assert len(result['results'])==50 and all(r['status']=='skipped' for r in result['results'])


def test_foreign_lead_is_neither_exposed_nor_mutated(auth,lead_data):
    own=create(auth,lead_data);rows=queue(auth)['items']
    with SessionLocal() as db:
        owner=User(email='foreign@example.org',password_hash='unused');db.add(owner);db.flush()
        foreign=Lead(user_id=owner.id,name='Private company',category='Cafeteria',city='Recife',latitude=0,longitude=0)
        db.add(foreign);db.commit();identifier=foreign.id
    assert auth.get('/api/commercial-review/leads/'+identifier).status_code==404
    op,_=preview(auth,rows+[{'id':identifier,'version':1,'review':{'version':0}}])
    assert op['eligible']==1 and 'name' not in op['preview'][1]
    assert commit(auth,op)['results'][1]['status']=='skipped'
    with SessionLocal() as db:assert db.get(CommercialReview,identifier) is None


def test_intervening_human_review_prevents_overwrite(auth,lead_data):
    create(auth,lead_data);rows=queue(auth)['items']
    first,_=preview(auth,rows,action='selected');second,_=preview(auth,rows,action='not_priority',reason='Outro entendimento comercial.')
    commit(auth,first);result=commit(auth,second)
    assert result['results'][0]['status']=='failed'
    assert queue(auth,state='selected')['total']==1


def test_high_score_is_not_enough_to_claim_verified_opportunity(auth,lead_data):
    create(auth,lead_data);row,=queue(auth)['items']
    assert row['qualification']['class']=='priority' and not row['summary']['facts']
    op,_=preview(auth,[row],action='prepare')
    assert op['preview'][0]['draft']['strategy']=='initial'
