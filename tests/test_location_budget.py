import json
import pytest
from sqlalchemy import select, func
from backend import locations
from backend.location_budget import search, LocationCache
from backend.db import SessionLocal
from backend.models import User
from backend.autonomy_models import WorkAttempt, ProviderOperation


def setup(auth, monkeypatch):
    with SessionLocal() as db:
        uid = db.scalar(select(User.id))
    monkeypatch.setenv('RADAR_GEOAPIFY_API_KEY', 'synthetic-never-transmitted')
    monkeypatch.setenv('RADAR_LOCATION_DAILY_CALLS', '2')
    monkeypatch.setenv('RADAR_LOCATION_USER_DAILY_CALLS', '1')
    return uid


def test_cache_persists_and_cannot_bypass_daily_limit(auth, monkeypatch):
    uid = setup(auth, monkeypatch)
    calls = []
    monkeypatch.setattr(locations, 'search_locations', lambda *a, **k: calls.append(a) or [{'id':'recife'}])
    assert search(uid, 'Recife') == [{'id':'recife'}]
    assert search(uid, 'Recife') == [{'id':'recife'}]
    assert len(calls) == 1
    with SessionLocal() as db:
        cache = db.scalar(select(LocationCache))
        assert cache.user_id == uid and 'synthetic' not in cache.id
        cache.expires_at = 0
        db.commit()
    with pytest.raises(locations.LocationCatalogError): search(uid, 'Recife')
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(WorkAttempt).where(WorkAttempt.kind=='location')) == 1
        assert db.scalar(select(ProviderOperation.status)) == 'done'


def test_failed_lookup_consumes_reservation_and_cache_is_user_scoped(auth, monkeypatch):
    uid = setup(auth, monkeypatch)
    def fail(*a, **k): raise locations.LocationCatalogError('controlled')
    monkeypatch.setattr(locations, 'search_locations', fail)
    with pytest.raises(locations.LocationCatalogError): search(uid, 'Recife')
    monkeypatch.setattr(locations, 'search_locations', lambda *a, **k: [{'id':'another'}])
    with pytest.raises(locations.LocationCatalogError): search(uid, 'Recife')
    with SessionLocal() as db:
        other=User(email='catalog@example.test',password_hash='unused');db.add(other);db.flush();oid=other.id;db.commit()
    assert search(oid, 'Recife') == [{'id':'another'}]
    with SessionLocal() as db:
        assert set(db.scalars(select(ProviderOperation.status))) == {'error','done'}


def test_quick_confirmation_cannot_change_facts_or_override_block(auth, lead_data):
    lead = auth.post('/api/leads', json={**lead_data,'name':'Starbucks QA'}).json()
    body = dict(version=lead['version'], independence='unknown',operating_status='unknown',
                business_type='unknown',size='unknown',entity_type='unknown',confirm_existing=True)
    result=auth.post(f"/api/smart-searches/leads/{lead['id']}/review",json=body)
    assert result.status_code==200,result.text
    confirmed=result.json()
    from backend.commercial_fit import assess
    from backend.models import Lead
    with SessionLocal() as db:
        assert assess(db.get(Lead,lead['id']))['status']=='incompatible'
    assert confirmed['qualification']['independence']=='unknown'
    assert confirmed['qualification']['review_reason']
    body.update(version=confirmed['version'],independence='independent')
    assert auth.post(f"/api/smart-searches/leads/{lead['id']}/review",json=body).status_code==422
    body['confirm_existing']=False
    assert auth.post(f"/api/smart-searches/leads/{lead['id']}/review",json=body).status_code==422


def test_concurrent_reservations_do_not_exceed_user_budget(auth, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import time
    uid=setup(auth,monkeypatch)
    calls=[]
    def lookup(*args,**kwargs):
        calls.append(args);time.sleep(.1);return [{'id':'controlled'}]
    monkeypatch.setattr(locations,'search_locations',lookup)
    def request(query):
        try:return search(uid,query)
        except locations.LocationCatalogError:return 'limited'
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(request,['Recife','Olinda']))
    assert outcomes.count('limited')==1 and len(calls)==1
