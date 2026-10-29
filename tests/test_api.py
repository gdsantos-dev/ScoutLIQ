from datetime import date, timedelta
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select
from backend.db import SessionLocal
from backend.models import Lead, User, Session
from backend.security import hasher

def make_sale(auth,lead_data,amount=250000):
    lead=auth.post('/api/leads',json=lead_data).json()
    today=str(date.today())
    res=auth.post('/api/sales',json={'lead_id':lead['id'],'service':'Site institucional','amount_cents':amount,'sold_on':today,'due_on':today})
    assert res.status_code==201,res.text
    return lead,res.json()

def test_private_endpoints_and_headers(client):
    for path in ['/api/leads','/api/sales','/api/sites','/api/dashboard','/api/expenses','/api/export','/api/auth/me']:
        response=client.get(path)
        assert response.status_code==401
        assert response.headers['cache-control']=='no-store'
        assert response.headers['x-content-type-options']=='nosniff'
    assert client.get('/api/health').json()=={'status':'ok'}

def test_sites_crud_alerts_conflict_and_export(auth,lead_data):
    _,sale=make_sale(auth,lead_data)
    body={'sale_id':sale['id'],'name':'Site Teste','domain':'example.com','renewal_on':str(date.today()+timedelta(days=10)),'monthly_revenue_cents':14900,'monthly_cost_cents':2900,'status':'active'}
    response=auth.post('/api/sites',json=body)
    assert response.status_code==201,response.text
    item=response.json()
    assert item['monthly_margin_cents']==12000 and len(item['alerts'])==1
    assert item['id'] in [s['id'] for s in auth.get('/api/export').json()['sites']]
    updated={**body,'version':item['version'],'hosting':'Nova hospedagem'}
    assert auth.put('/api/sites/'+item['id'],json=updated).status_code==200
    assert auth.put('/api/sites/'+item['id'],json=updated).status_code==409
    assert auth.get('/api/sites').json()[0]['hosting']=='Nova hospedagem'
    assert auth.delete('/api/sites/'+item['id']).status_code==200
    assert auth.get('/api/sites').json()==[]
    assert len(auth.get('/api/sales').json())==1

def test_sites_ownership_and_input_boundaries(auth,lead_data):
    from backend.models import Sale, Site
    _,sale=make_sale(auth,lead_data)
    body={'sale_id':sale['id'],'name':'Site Seguro'}
    for extra in [{'user_id':'other'},{'demo':False},{'role':'admin'},{'url':'javascript:alert(1)'},{'admin_url':'https://secret@example.com'},{'monthly_cost_cents':-1},{'monthly_revenue_cents':1.5},{'domain':'../../secret'}]:
        assert auth.post('/api/sites',json={**body,**extra}).status_code==422
    with SessionLocal() as db:
        user=User(email='site-other@example.com',password_hash=hasher.hash('other-password-123!'))
        db.add(user);db.flush()
        lead=Lead(user_id=user.id,name='Other',category='Cafe',city='Recife',latitude=-8,longitude=-34)
        db.add(lead);db.flush()
        other_sale=Sale(user_id=user.id,lead_id=lead.id,service='Site',amount_cents=100,sold_on=str(date.today()),due_on=str(date.today()))
        db.add(other_sale);db.flush()
        other=Site(user_id=user.id,sale_id=other_sale.id,name='Private site')
        db.add(other);db.commit();other_id=other.id;other_sale_id=other_sale.id
    mine=auth.post('/api/sites',json=body).json()
    assert auth.post('/api/sites',json={**body,'sale_id':other_sale_id}).status_code==404
    assert auth.put('/api/sites/'+mine['id'],json={**body,'sale_id':other_sale_id,'version':1}).status_code==404
    assert auth.put('/api/sites/'+other_id,json={**body,'version':1}).status_code==404
    assert auth.delete('/api/sites/'+other_id).status_code==404
    assert auth.delete('/api/sales/'+other_sale_id).status_code==404
    assert all(s['id']!=other_id for s in auth.get('/api/sites').json())
    assert all(s['id']!=other_id for s in auth.get('/api/export').json()['sites'])

def test_csrf_and_origin(auth,lead_data):
    csrf=auth.headers.pop('X-CSRF-Token')
    assert auth.post('/api/leads',json=lead_data).status_code==403
    auth.headers['X-CSRF-Token']=csrf
    auth.headers['Origin']='https://attacker.example'
    assert auth.post('/api/leads',json=lead_data).status_code==403

def test_login_limits_and_cookie(client):
    for _ in range(8):
        assert client.post('/api/auth/login',json={'email':'bad@example.com','password':'bad'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'bad@example.com','password':'bad'}).status_code==429
    res=client.post('/api/auth/login',json={'email':'test@example.com','password':'testing-password-123!'})
    assert 'HttpOnly' in res.headers['set-cookie'] and 'SameSite=strict' in res.headers['set-cookie']
    with SessionLocal() as db:
        token=db.scalar(select(Session)).token_hash
        assert token!=client.cookies.get('scout_session')

def test_score_and_unknown_data(auth,lead_data):
    result=auth.post('/api/leads',json=lead_data)
    assert result.status_code==201
    lead=result.json()
    assert lead['score']['value']==85
    assert lead['score']['status']=='qualified'
    assert sum(r['points'] for r in lead['score']['reasons'])==90
    assert lead['score']['dimensions']['digital_need']=={'value':50,'max':50}
    assert lead['score']['dimensions']['public_demand']=={'value':18,'max':20}
    assert lead['score']['version']=='3.0'
    assert lead['score']['niche']['key']=='food'
    assert lead['score']['niche']['confidence']>=90
    assert any(item['key']=='no_website' and item['severity']=='high' for item in lead['score']['diagnosis'])
    minimal={k:v for k,v in lead_data.items() if k in ('name','category','city','country','latitude','longitude')}
    unknown=auth.post('/api/leads',json=minimal).json()
    assert unknown['score']['status']=='insufficient'
    assert unknown['score']['commercial_dimensions']['need']['value'] is None


def test_create_lead_directly_in_pipeline(auth,lead_data):
    response=auth.post('/api/leads?to_pipeline=true',json=lead_data)
    assert response.status_code==201,response.text
    lead=response.json()
    assert lead['in_pipeline'] is True
    assert lead['stage']=='discovered'
    listed=auth.get('/api/leads').json()
    assert any(item['id']==lead['id'] and item['in_pipeline'] for item in listed)

def test_next_action_requires_active_pipeline_and_uses_versioning(auth,lead_data):
    lead=auth.post('/api/leads',json=lead_data).json()
    blocked=auth.patch(
        f"/api/leads/{lead['id']}/next-action",
        json={'next_action':'Ligar amanhã','next_action_on':str(date.today()),'version':lead['version']},
    )
    assert blocked.status_code==409

    moved=auth.patch(
        f"/api/leads/{lead['id']}/stage",
        json={'stage':'discovered','version':lead['version']},
    ).json()
    saved=auth.patch(
        f"/api/leads/{lead['id']}/next-action",
        json={'next_action':'  Enviar proposta pelo WhatsApp  ','next_action_on':str(date.today()),'version':moved['version']},
    )
    assert saved.status_code==200,saved.text
    updated=saved.json()
    assert updated['next_action']=='Enviar proposta pelo WhatsApp'
    assert updated['next_action_on']==str(date.today())
    assert auth.patch(
        f"/api/leads/{lead['id']}/next-action",
        json={'next_action':'Outra','next_action_on':None,'version':moved['version']},
    ).status_code==409

    cleared=auth.patch(
        f"/api/leads/{lead['id']}/next-action",
        json={'next_action':'','next_action_on':None,'version':updated['version']},
    ).json()
    assert cleared['next_action']=='' and cleared['next_action_on'] is None

    scheduled=auth.patch(
        f"/api/leads/{lead['id']}/next-action",
        json={'next_action':'Fazer follow-up','next_action_on':str(date.today()),'version':cleared['version']},
    ).json()
    lost=auth.patch(
        f"/api/leads/{lead['id']}/stage",
        json={'stage':'lost','version':scheduled['version']},
    ).json()
    assert lost['next_action']=='' and lost['next_action_on'] is None


def test_stage_conflict_and_persistence(auth,lead_data):
    lead=auth.post('/api/leads',json=lead_data).json()
    res=auth.patch(f"/api/leads/{lead['id']}/stage",json={'stage':'contacted','version':1})
    assert res.status_code==200 and res.json()['in_pipeline']
    assert auth.patch(f"/api/leads/{lead['id']}/stage",json={'stage':'replied','version':1}).status_code==409
    with SessionLocal() as db:
        assert db.get(Lead,lead['id']).stage=='contacted'

def test_sale_payment_balance_idempotency_and_summary(auth,lead_data):
    lead,sale=make_sale(auth,lead_data)
    assert auth.get('/api/leads').json()[0]['stage']=='won'
    payload={'amount_cents':100000,'paid_on':str(date.today()),'request_id':str(uuid4())}
    path=f"/api/sales/{sale['id']}/payments"
    first=auth.post(path,json=payload)
    second=auth.post(path,json=payload)
    assert first.status_code==second.status_code==201
    assert first.json()['id']==second.json()['id']
    assert auth.post(path,json={**payload,'amount_cents':1}).status_code==409
    assert auth.post(path,json={**payload,'amount_cents':160000,'request_id':str(uuid4())}).status_code==422
    cost=auth.post('/api/expenses',json={'description':'Hospedagem','amount_cents':10000,'incurred_on':str(date.today()),'request_id':str(uuid4())})
    assert cost.status_code==201
    report=auth.get('/api/dashboard').json()
    assert report['revenue_cents']==250000
    assert report['received_cents']==100000
    assert report['receivable_cents']==150000
    assert report['profit_cents']==90000
    assert auth.delete(f"/api/leads/{lead['id']}").status_code==409
    assert auth.patch(f"/api/leads/{lead['id']}/stage",json={'stage':'lost','version':2}).status_code==409

def test_delete_payment_recalculates_sale_and_dashboard(auth,lead_data):
    _,sale=make_sale(auth,lead_data)
    payment=auth.post(
        f"/api/sales/{sale['id']}/payments",
        json={'amount_cents':50000,'paid_on':str(date.today()),'request_id':str(uuid4())}
    ).json()
    assert auth.get('/api/dashboard').json()['received_cents']==50000
    response=auth.delete(f"/api/sales/{sale['id']}/payments/{payment['id']}")
    assert response.status_code==200,response.text
    listed=auth.get('/api/sales').json()[0]
    assert listed['received_cents']==0 and listed['payments']==[]
    assert auth.get('/api/dashboard').json()['received_cents']==0

def test_delete_sale_keeps_lead_and_reopens_pipeline(auth,lead_data):
    lead,sale=make_sale(auth,lead_data)
    auth.post(
        f"/api/sales/{sale['id']}/payments",
        json={'amount_cents':50000,'paid_on':str(date.today()),'request_id':str(uuid4())}
    )
    response=auth.delete(f"/api/sales/{sale['id']}")
    assert response.status_code==200,response.text
    assert auth.get('/api/sales').json()==[]
    restored=next(item for item in auth.get('/api/leads').json() if item['id']==lead['id'])
    assert restored['stage']=='discovered' and restored['in_pipeline'] is True
    assert any(item['kind']=='sale_reopened' for item in auth.get(f"/api/leads/{lead['id']}/activities").json())
    report=auth.get('/api/dashboard').json()
    assert report['revenue_cents']==0 and report['received_cents']==0

def test_delete_sale_with_site_removes_linked_site(auth,lead_data):
    lead,sale=make_sale(auth,lead_data)
    site=auth.post('/api/sites',json={'sale_id':sale['id'],'name':'Site vinculado'})
    assert site.status_code==201,site.text
    site_id=site.json()['id']
    response=auth.delete(f"/api/sales/{sale['id']}")
    assert response.status_code==200,response.text
    assert auth.get('/api/sales').json()==[]
    assert all(item['id'] != site_id for item in auth.get('/api/sites').json())
    restored=next(item for item in auth.get('/api/leads').json() if item['id']==lead['id'])
    assert restored['stage']=='discovered' and restored['in_pipeline'] is True

def test_concurrent_payments_cannot_overpay(auth,lead_data):
    _,sale=make_sale(auth,lead_data,10000)
    def pay(_):
        return auth.post(f"/api/sales/{sale['id']}/payments",json={'amount_cents':7000,'paid_on':str(date.today()),'request_id':str(uuid4())}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(pay,range(2)))
    assert sorted(result)==[201,422]

def test_input_validation(auth,lead_data):
    for change in ({'latitude':91},{'website':'javascript:alert(1)'},{'whatsapp':'bad'},{'potential_cents':-1},{'reviews':-5},{'country':'BRA'},{'user_id':'attacker'},{'website':'https://example.com'}):
        assert auth.post('/api/leads',json={**lead_data,**change}).status_code==422
    response=auth.post('/api/leads',content='x'*70000)
    assert response.status_code==413

def test_ownership_no_idor(auth,lead_data):
    lead=auth.post('/api/leads',json=lead_data).json()
    with SessionLocal() as db:
        user=User(email='other@example.com',password_hash=hasher.hash('other-password-123!'))
        db.add(user);db.flush()
        other=Lead(user_id=user.id,name='Private',category='Dentista',city='Recife',latitude=-8,longitude=-34)
        db.add(other);db.commit();identifier=other.id
    assert all(l['id']!=identifier for l in auth.get('/api/leads').json())
    assert auth.delete(f'/api/leads/{identifier}').status_code==404
    assert auth.patch(f'/api/leads/{identifier}/stage',json={'stage':'contacted','version':1}).status_code==404

def test_demo_seed_removal_keeps_real_data(auth,lead_data):
    auth.post('/api/leads',json=lead_data)
    assert auth.post('/api/demo').json()['created'] is True
    assert auth.post('/api/demo').json()['created'] is False
    assert len(auth.get('/api/leads').json())==17
    assert auth.delete('/api/demo').status_code==200
    assert len(auth.get('/api/leads').json())==1
    assert not auth.get('/api/sales').json()
    assert not auth.get('/api/expenses').json()

def test_password_revokes_sessions(auth):
    response=auth.put('/api/auth/password',json={'current_password':'testing-password-123!','new_password':'new-testing-password!'})
    assert response.status_code==200
    assert auth.get('/api/leads').status_code==401

def test_export_has_stable_ids_no_credentials(auth,lead_data):
    _,sale=make_sale(auth,lead_data)
    first=auth.get('/api/export').json()
    second=auth.get('/api/export').json()
    assert first['sales'][0]['export_id']==second['sales'][0]['export_id']
    assert 'password' not in str(first) and 'csrf' not in str(first)

def test_invalid_dates_and_money(auth,lead_data):
    lead=auth.post('/api/leads',json=lead_data).json()
    body={'lead_id':lead['id'],'service':'Site','amount_cents':1000,'sold_on':str(date.today()),'due_on':str(date.today()-timedelta(days=1))}
    assert auth.post('/api/sales',json=body).status_code==422
    body['due_on']=str(date.today())
    body['amount_cents']=12.3
    assert auth.post('/api/sales',json=body).status_code==422

def test_settings_persist_and_validate(auth):
    payload={'name':'Operação Teste','accent':'blue','motion':'reduced','timezone':'America/New_York'}
    assert auth.put('/api/settings',json=payload).status_code==200
    assert auth.get('/api/auth/me').json()['user']['accent']=='blue'
    assert auth.put('/api/settings',json={**payload,'timezone':'No/SuchZone'}).status_code==422

def test_future_dates_use_business_timezone(auth,lead_data):
    auth.put('/api/settings',json={'name':'Test','accent':'crimson','motion':'full','timezone':'Pacific/Kiritimati'})
    from datetime import datetime
    from zoneinfo import ZoneInfo
    today=datetime.now(ZoneInfo('Pacific/Kiritimati')).date()
    lead=auth.post('/api/leads',json=lead_data).json()
    body={'lead_id':lead['id'],'service':'Site','amount_cents':10000,'sold_on':str(today),'due_on':str(today)}
    assert auth.post('/api/sales',json={**body,'sold_on':str(today+timedelta(days=1))}).status_code==422
    assert auth.post('/api/sales',json=body).status_code==201

def test_password_whitespace_preserved(auth):
    assert auth.put('/api/auth/password',json={'current_password':'testing-password-123!','new_password':'  new-password-spaces  '}).status_code==200
    assert auth.post('/api/auth/login',json={'email':'test@example.com','password':'new-password-spaces'}).status_code==401
    assert auth.post('/api/auth/login',json={'email':'test@example.com','password':'  new-password-spaces  '}).status_code==200

def test_commercial_history_tracks_manual_and_system_events(auth,lead_data):
    lead=auth.post('/api/leads?to_pipeline=true',json=lead_data).json()
    assert lead['pipeline_added_at'] is not None
    initial=auth.get(f"/api/leads/{lead['id']}/activities")
    assert initial.status_code==200
    assert initial.json()[0]['kind']=='pipeline_added'

    logged=auth.post(
        f"/api/leads/{lead['id']}/activities",
        json={'kind':'whatsapp','body':'  Cliente pediu portfólio e valores.  '},
    )
    assert logged.status_code==201,logged.text
    logged_body=logged.json()
    assert logged_body['activity']['body']=='Cliente pediu portfólio e valores.'
    assert logged_body['lead']['last_contact_at'] is not None
    version=logged_body['lead']['version']

    moved=auth.patch(
        f"/api/leads/{lead['id']}/stage",
        json={'stage':'contacted','version':version},
    )
    assert moved.status_code==200,moved.text
    timeline=auth.get(f"/api/leads/{lead['id']}/activities").json()
    kinds=[item['kind'] for item in timeline]
    assert 'whatsapp' in kinds and 'stage_changed' in kinds and 'pipeline_added' in kinds
    stage_event=next(item for item in timeline if item['kind']=='stage_changed')
    assert stage_event['metadata']=={'from':'discovered','to':'contacted'}


def test_radar_saved_search_tracks_new_results_and_version(auth,lead_data):
    first=auth.post('/api/leads',json=lead_data).json()
    second=auth.post('/api/leads',json={**lead_data,'name':'Empresa Dois','latitude':-8.06,'longitude':-34.91}).json()
    query={
        'location':'Recife, PE, Brasil',
        'category':'Cafeteria',
        'radius_km':10,
        'scope':'radius',
        'country':'BR',
        'municipality_id':'2611606',
        'city_name':'Recife',
        'state':'Pernambuco',
        'state_code':'PE',
    }
    created=auth.post('/api/radar/saved-searches',json={
        'name':'Cafeterias Recife',
        'query':query,
        'result_ids':[first['id']],
    })
    assert created.status_code==201,created.text
    saved=created.json()
    assert saved['query']['scope']=='radius' and saved['last_new_count']==0
    assert saved['query']['problem_keys']==[]
    assert saved['monitor_enabled'] is False and saved['next_monitor_at'] is None
    monitored=auth.patch(
        f"/api/radar/saved-searches/{saved['id']}/monitor",
        json={'enabled':True,'interval':'daily','version':saved['version']},
    )
    assert monitored.status_code==200,monitored.text
    saved=monitored.json()
    assert saved['monitor_enabled'] is True
    assert saved['monitor_interval']=='daily'
    assert saved['next_monitor_at'] is not None
    assert auth.post('/api/radar/saved-searches',json={
        'name':'cafeterias recife','query':query,'result_ids':[]
    }).status_code==409

    rerun=auth.patch(
        f"/api/radar/saved-searches/{saved['id']}/results",
        json={'result_ids':[first['id'],second['id']],'version':saved['version']},
    )
    assert rerun.status_code==200,rerun.text
    updated=rerun.json()
    assert updated['last_new_count']==1
    assert updated['version']>saved['version']
    assert auth.patch(
        f"/api/radar/saved-searches/{saved['id']}/results",
        json={'result_ids':[first['id']],'version':saved['version']},
    ).status_code==409
    listed=auth.get('/api/radar/saved-searches').json()
    assert len(listed)==1 and listed[0]['id']==saved['id']
    exported=auth.get('/api/export').json()
    assert exported['schema_version']==13
    assert exported['radar_saved_searches'][0]['id']==saved['id']
    assert 'lead_activities' in exported
    assert 'commercial_signals' in exported and exported['commercial_signals']
    assert auth.delete(f"/api/radar/saved-searches/{saved['id']}").status_code==200
    assert auth.get('/api/radar/saved-searches').json()==[]


def test_radar_natural_search_interpretation_endpoint(auth):
    response=auth.post('/api/radar/interpret',json={
        'text':'dentistas em Recife sem site, 100+ avaliações e com WhatsApp',
        'fallback_country':'BR',
    })
    assert response.status_code==200,response.text
    plan=response.json()
    assert plan['query']['location']=='recife'
    assert plan['query']['category']=='dentistas'
    assert plan['query']['problem_keys']==['no_site']
    assert plan['query']['min_reviews']==100
    assert plan['query']['contact_filter']=='whatsapp'


def test_score_recognizes_social_aggregator_as_website_gap(auth, lead_data):
    payload = {
        **lead_data,
        'website': 'https://linktr.ee/empresa-teste',
        'website_status': 'unknown',
        'rating': None,
        'reviews': None,
        'instagram': '',
        'instagram_active': False,
        'phone': '',
        'whatsapp': '',
    }
    lead = auth.post('/api/leads', json=payload).json()
    assert lead['score']['dimensions']['digital_need']['value'] == 42
    assert any(item['key'] == 'aggregator_website' for item in lead['score']['reasons'])


def test_manual_website_change_clears_stale_site_intelligence(auth, lead_data, monkeypatch):
    from backend import main

    lead = auth.post('/api/leads', json=lead_data).json()

    class Researcher:
        search_configured = True
        def research(self, selected, locale='pt-BR'):
            return {
                'status': 'confirmed',
                'provider': 'direct',
                'website_url': 'https://old.example/',
                'website_status': 'good',
                'confidence': 90,
                'checked_at': 1_700_001_000,
                'evidence': [],
                'checks': [],
                'sources': [],
                'contacts': {},
                'search_configured': False,
                'candidates_checked': 1,
                'fetch_errors': 0,
                'page': {
                    'domain': 'old.example',
                    'own_domain': True,
                    'analytics': ['Google Analytics'],
                    'technologies': ['WordPress'],
                    'forms': 1,
                    'social': True,
                },
            }

    monkeypatch.setattr(main, 'website_researcher', Researcher())
    researched = auth.post(f"/api/leads/{lead['id']}/research").json()['lead']
    assert researched['website_intelligence']['technologies'] == ['WordPress']
    updated_payload = {
        key: researched[key]
        for key in (
            'name','category','city','country','address','latitude','longitude','rating','reviews',
            'website','website_status','instagram','instagram_active','phone','whatsapp','contact',
            'potential_cents','potential_currency','notes'
        )
    }
    updated_payload['website'] = 'https://new.example/'
    updated_payload['website_status'] = 'unknown'
    updated_payload['version'] = researched['version']
    response = auth.put(f"/api/leads/{lead['id']}", json=updated_payload)
    assert response.status_code == 200, response.text
    changed = response.json()
    assert changed['website_intelligence'] == {}
    assert changed['website_analyzed_at'] is None
