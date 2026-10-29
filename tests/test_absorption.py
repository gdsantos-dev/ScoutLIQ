"""Absorption never replaces existing Lead/Score and never starts outreach."""
from uuid import uuid4
from sqlalchemy import select, func
from backend.db import SessionLocal
from backend.models import Lead, LeadActivity, User
from backend.absorption_models import AbsorptionBatch
from backend.opportunity_models import OutreachDraft
from backend.communication_models import OutboxMessage

URL='/api/absorption'

def record(name='Café Atlântico', **extra):
    return {'name':name,'category':'Cafeteria','city':'Recife','country':'BR',
            'latitude':-8.065432,'longitude':-34.876543,'source_url':'https://example.org/pesquisa', **extra}

def preview(auth, records, key=None, source='chatgpt'):
    return auth.post(URL+'/preview',json={'request_key':key or str(uuid4()),'source':source,'records':records})

def commit(auth, batch):
    return auth.post(URL+'/batches/'+batch['id']+'/commit',json={'payload_hash':batch['payload_hash'],'confirm':True})

def test_review_commit_creates_canonical_lead_and_provenance_without_outreach(auth):
    p=preview(auth,[record(notes='Precisa revisar o site',website='https://cafe.example/',claims=[{'statement':'Site pode precisar de revisão','source_url':'https://cafe.example/'}])])
    assert p.status_code==201,p.text
    snapshot=p.json()
    assert snapshot['counts']['ready']==1
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead))==0
    r=commit(auth,snapshot)
    assert r.status_code==200,r.text
    item=r.json()['items'][0]
    assert item['status']=='imported' and item['lead_id']
    with SessionLocal() as db:
        lead=db.get(Lead,item['lead_id'])
        assert lead and lead.source=='chatgpt'
        assert lead.website_status=='unknown' and lead.in_pipeline is False
        a=db.scalar(select(LeadActivity).where(LeadActivity.lead_id==lead.id))
        assert a and 'external_absorption' in a.metadata_json
        assert 'Site pode precisar de revisão' in a.metadata_json
    assert commit(auth,snapshot).json()['items'][0]['lead_id']==lead.id
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead))==1
        assert db.scalar(select(func.count()).select_from(OutreachDraft))==0
        assert db.scalar(select(func.count()).select_from(OutboxMessage))==0

def test_missing_coordinates_or_category_stay_pending(auth):
    data=[record('Sem coordenadas',latitude=None,longitude=None),
          record('Sem categoria',category='')]
    p=preview(auth,data)
    assert p.status_code==201,p.text
    assert p.json()['counts']['pending']==2
    done=commit(auth,p.json())
    assert done.status_code==200
    assert done.json()['counts']['imported']==0
    assert done.json()['counts']['pending']==2

def test_duplicate_in_same_batch_and_existing_are_blocked(auth):
    a=record('Loja Comum')
    b={**a, 'source_url':'https://example.net/other'}
    p=preview(auth,[a,b]); assert p.status_code==201,p.text
    assert p.json()['counts']=={'ready':1,'pending':0,'duplicate':1,'imported':0}
    assert commit(auth,p.json()).json()['counts']['imported']==1
    again=preview(auth,[a]); assert again.status_code==201
    assert again.json()['counts']['duplicate']==1
    assert commit(auth,again.json()).json()['counts']['imported']==0

def test_recheck_between_preview_and_commit(auth):
    a=record('Mesmo Local')
    first=preview(auth,[a]).json()
    later=preview(auth,[a]).json()
    assert later['counts']['duplicate']==1
    assert commit(auth,first).json()['counts']['imported']==1
    done=commit(auth,later)
    assert done.status_code==200
    assert done.json()['counts']['duplicate']==1

def test_request_idempotency_and_hash_consistency(auth):
    key=str(uuid4())
    a=preview(auth,[record()],key)
    b=preview(auth,[record()],key)
    assert a.status_code==b.status_code==201
    assert a.json()['id']==b.json()['id']
    changed=preview(auth,[record('Outra Empresa')],key)
    assert changed.status_code==409
    bad=auth.post(URL+'/batches/'+a.json()['id']+'/commit',json={'payload_hash':'0'*64,'confirm':True})
    assert bad.status_code==409
    no_confirmation=auth.post(URL+'/batches/'+a.json()['id']+'/commit',json={'payload_hash':a.json()['payload_hash'],'confirm':False})
    assert no_confirmation.status_code==422

def test_cross_user_cannot_access_or_commit(auth):
    item=preview(auth,[record()]).json()
    with SessionLocal() as db:
        other=User(email='other@example.com',password_hash='not-used',email_verified_at=1)
        db.add(other);db.flush()
        batch=db.get(AbsorptionBatch,item['id'])
        batch.user_id=other.id
        db.commit()
    assert auth.get(URL+'/batches/'+item['id']).status_code==404
    assert commit(auth,item).status_code==404

def test_bounded_and_untrusted_urls_rejected(auth):
    assert preview(auth,[record(name='Loja '+str(i),latitude=-8.0-i*.0001) for i in range(51)]).status_code==422
    assert preview(auth,[record(source_url='file:///etc/passwd')]).status_code==422
    assert preview(auth,[record(website='https://example.com@internal.local/')]).status_code==422
    assert preview(auth,[record(latitude=None)]).status_code==422
    assert preview(auth,[record(source_url='https://u:p@example.org/')]).status_code==422


def test_incomplete_anchor_does_not_hide_complete_record(auth):
    pending=record('Mesmo cadastro',address='Rua A, 10',latitude=None,longitude=None)
    ready=record('Mesmo cadastro',address='Rua A, 10')
    batch=preview(auth,[pending,ready]).json()
    assert batch['counts']['pending']==1 and batch['counts']['ready']==1
    assert commit(auth,batch).json()['counts']['imported']==1


def test_short_category_and_city_remain_pending_instead_of_crashing_commit(auth):
    batch=preview(auth,[record(category='A'),record('Outra',city='R')]).json()
    assert batch['counts']['pending']==2
    assert commit(auth,batch).json()['counts']['imported']==0


def test_branches_with_shared_phone_are_preserved(auth):
    batch=preview(auth,[record('Rede Local',address='Rua A, 1',phone='558130001000'),
                        record('Rede Local',address='Rua B, 2',phone='558130001000',latitude=-8.07)]).json()
    assert batch['counts']['ready']==2
    assert commit(auth,batch).json()['counts']['imported']==2


def test_parallel_previews_and_same_batch_commits_are_idempotent(auth):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    key=str(uuid4()); barrier=Barrier(2)
    def start(_):
        barrier.wait()
        return preview(auth,[record()],key)
    with ThreadPoolExecutor(max_workers=2) as pool:
        previews=list(pool.map(start,range(2)))
    assert [r.status_code for r in previews]==[201,201]
    assert previews[0].json()['id']==previews[1].json()['id']
    barrier=Barrier(2)
    def finish(_):
        barrier.wait()
        return commit(auth,previews[0].json())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(finish,range(2)))
    assert [r.status_code for r in results]==[200,200]
    assert results[0].json()['items'][0]['lead_id']==results[1].json()['items'][0]['lead_id']
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead))==1
        assert db.scalar(select(func.count()).select_from(LeadActivity))==1


def test_parallel_different_batches_recheck_duplicates(auth):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    batches=[preview(auth,[record()]).json() for _ in range(2)]
    barrier=Barrier(2)
    def finish(batch):
        barrier.wait()
        return commit(auth,batch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(finish,batches))
    assert [r.status_code for r in results]==[200,200]
    assert sum(r.json()['counts']['imported'] for r in results)==1
    assert sum(r.json()['counts']['duplicate'] for r in results)==1


def test_absorption_failure_rolls_back_claim_and_lead(auth,monkeypatch):
    from backend import main
    batch=preview(auth,[record(),record('Outra Empresa')]).json()
    original=main._sync_commercial_signals
    count=0
    def fail_second(*args,**kwargs):
        nonlocal count
        count+=1
        if count==2: raise RuntimeError('controlled transaction failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(main,'_sync_commercial_signals',fail_second)
    import pytest
    with pytest.raises(RuntimeError,match='controlled transaction failure'): commit(auth,batch)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead))==0
        assert db.scalar(select(func.count()).select_from(LeadActivity))==0
        assert db.get(AbsorptionBatch,batch['id']).status=='previewed'
    monkeypatch.setattr(main,'_sync_commercial_signals',original)
    assert commit(auth,batch).json()['counts']['imported']==2


def test_csrf_mass_assignment_and_request_limit(auth):
    assert preview(auth,[record(user_id='other')]).status_code==422
    assert preview(auth,[record(website_status='poor')]).status_code==422
    assert auth.post(URL+'/preview',headers={'X-CSRF-Token':'bad'},json={}).status_code==403
    key=str(uuid4())
    for _ in range(12): assert preview(auth,[record()],key).status_code==201
    assert preview(auth,[record()],key).status_code==429
    assert auth.post(URL+'/preview',content='x'*65537).status_code==413


def test_two_users_have_separate_history_and_canonical_records(auth):
    from backend.security import hasher
    import time
    first=preview(auth,[record()]).json()
    first_lead=commit(auth,first).json()['items'][0]['lead_id']
    with SessionLocal() as db:
        db.add(User(email='second@example.com',password_hash=hasher.hash('testing-password-123!'),email_verified_at=int(time.time())))
        db.commit()
    login=auth.post('/api/auth/login',json={'email':'second@example.com','password':'testing-password-123!'})
    assert login.status_code==200
    auth.headers['X-CSRF-Token']=login.json()['csrf']
    assert auth.get(URL+'/batches').json()==[]
    assert auth.get(URL+'/batches/'+first['id']).status_code==404
    assert commit(auth,first).status_code==404
    second=preview(auth,[record()]).json()
    assert second['counts']['ready']==1
    assert commit(auth,second).json()['items'][0]['lead_id']!=first_lead
