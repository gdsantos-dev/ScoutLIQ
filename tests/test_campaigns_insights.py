from datetime import datetime
from zoneinfo import ZoneInfo

from backend.models import Lead
from backend.scoring import score


def test_combined_signal_uses_multiple_independent_evidence():
    lead=Lead(
        user_id='u',name='Clínica Alfa',category='Clínica odontológica',city='Recife',country='BR',
        latitude=-8.05,longitude=-34.9,rating=4.8,reviews=420,website='',website_status='none',
        phone='+55 81 99999-9999',whatsapp='5581999999999',instagram='https://instagram.com/alfa',instagram_active=True,
        competitive_context_json='{"status":"ready","peers_count":8,"known_site_peers":7,"peer_site_rate":0.8,"strong_site_rate":0.6,"median_reviews":120,"median_rating":4.5,"review_percentile":88,"target_site_state":"missing","site_gap":"missing","demand_above_median":true,"sample_quality":"high","niche_key":"health"}',
        commercial_signal_json='{}',website_intelligence_json='{}',enrichment_json='{}',outcome_snapshot_json='{}',
    )
    payload=score(lead)
    keys={item['key'] for item in payload['combined_signals']}
    assert 'local_demand_digital_gap' in keys
    assert all('recommended_action' in item for item in payload['combined_signals'])


def test_campaign_tracks_members_and_attributed_sale(auth, lead_data):
    lead=auth.post('/api/leads?to_pipeline=true',json=lead_data).json()
    campaign=auth.post('/api/campaigns',json={
        'name':'Clínicas Recife','description':'Teste de atribuição','status':'active','source_saved_search_id':None,
    })
    assert campaign.status_code==201,campaign.text
    campaign=campaign.json()
    added=auth.post(f"/api/campaigns/{campaign['id']}/leads",json={'lead_ids':[lead['id']],'source':'manual'})
    assert added.status_code==200,added.text
    assert added.json()['metrics']['members']==1

    today=datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
    sale=auth.post('/api/sales',json={
        'lead_id':lead['id'],'campaign_id':campaign['id'],'service':'Site institucional',
        'amount_cents':350000,'currency':'BRL','recurring_cents':15000,'sold_on':today,'due_on':today,
    })
    assert sale.status_code==201,sale.text
    listed=auth.get('/api/campaigns').json()
    current=next(item for item in listed if item['id']==campaign['id'])
    assert current['metrics']['attributed_sales']==1
    assert current['metrics']['revenue_by_currency']['BRL']==350000
    assert current['metrics']['won']==1


def test_outcome_insights_use_closed_snapshot_history(auth, lead_data):
    today=datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
    for index in range(3):
        payload={**lead_data,'name':f'Ganha {index}','reviews':500+index*20,'rating':4.8,'website':'','website_status':'none'}
        lead=auth.post('/api/leads?to_pipeline=true',json=payload).json()
        response=auth.post('/api/sales',json={
            'lead_id':lead['id'],'campaign_id':None,'service':'Site institucional',
            'amount_cents':250000,'currency':'BRL','recurring_cents':0,'sold_on':today,'due_on':today,
        })
        assert response.status_code==201,response.text
    for index in range(3):
        payload={**lead_data,'name':f'Perde {index}','reviews':3+index,'rating':4.0,'website':'https://example.com','website_status':'good','whatsapp':'','phone':''}
        lead=auth.post('/api/leads?to_pipeline=true',json=payload).json()
        response=auth.patch(f"/api/leads/{lead['id']}/stage",json={'stage':'lost','version':lead['version']})
        assert response.status_code==200,response.text

    insights=auth.get('/api/insights/outcomes')
    assert insights.status_code==200,insights.text
    payload=insights.json()
    assert payload['status']=='ready'
    assert payload['closed_count']==6
    assert payload['snapshot_coverage']==100
    assert payload['insights']
    assert all(item['sample']>=3 for item in payload['insights'])
