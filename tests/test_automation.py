from backend import main
from backend.schemas import LeadInput


def _create_rule(auth, *, trigger='pipeline_added', stop=None, actions=None, conditions=None):
    payload = {
        'name': 'Regra teste',
        'enabled': True,
        'trigger': trigger,
        'conditions': conditions or [{'field': 'has_phone', 'operator': 'truthy', 'value': None, 'service_key': ''}],
        'actions': actions or [{'type': 'set_next_action', 'text': 'Ligar para responsável', 'due_days': 1}],
        'stop': stop or {'stages': ['won', 'lost'], 'max_runs_per_lead': 3, 'stop_if_next_action_exists': False},
    }
    response = auth.post('/api/automations', json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_pipeline_trigger_runs_rule_and_sets_next_action(auth, lead_data):
    rule = _create_rule(auth)
    response = auth.post('/api/leads?to_pipeline=true', json=lead_data)
    assert response.status_code == 201, response.text
    lead = response.json()
    assert lead['in_pipeline'] is True
    assert lead['next_action'] == 'Ligar para responsável'
    assert lead['next_action_on']

    runs = auth.get(f"/api/automations/{rule['id']}/runs")
    assert runs.status_code == 200
    assert runs.json()[0]['status'] == 'executed'
    assert runs.json()[0]['trigger'] == 'pipeline_added'


def test_stop_condition_blocks_actions_before_execution(auth, lead_data):
    rule = _create_rule(
        auth,
        stop={'stages': ['discovered'], 'max_runs_per_lead': 3, 'stop_if_next_action_exists': False},
    )
    lead = auth.post('/api/leads?to_pipeline=true', json=lead_data).json()
    assert lead['next_action'] == ''

    runs = auth.get(f"/api/automations/{rule['id']}/runs").json()
    assert runs[0]['status'] == 'stopped'
    assert runs[0]['reason'] == 'stage:discovered'


def test_enrichment_waterfall_records_provider_provenance(auth, lead_data, monkeypatch):
    imported = dict(lead_data)
    imported.update({
        'website': 'https://empresa.example',
        'website_status': 'good',
        'phone': '',
        'whatsapp': '',
        'instagram': '',
    })
    created = auth.post('/api/leads/imported', json={
        'lead': imported,
        'source': 'google_maps',
        'source_id': 'gmaps:enrichment-test',
    })
    assert created.status_code == 201, created.text
    lead = created.json()

    class FakeProvider:
        name = 'google_maps'
        def enrich_existing(self, source_id, input_lead):
            data = input_lead.model_dump()
            data['phone'] = '+55 81 98888-7777'
            data['whatsapp'] = '5581988887777'
            data['instagram'] = 'https://instagram.com/empresa'
            return LeadInput(**data)

    monkeypatch.setattr(main, 'radar_provider', FakeProvider())
    response = auth.post(f"/api/leads/{lead['id']}/enrich")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['lead']['phone'] == '+55 81 98888-7777'
    assert payload['lead']['whatsapp'] == '5581988887777'
    assert payload['enrichment']['coverage'] == 100
    assert payload['enrichment']['fields']['phone']['source'] == 'provider:google_maps'
    assert payload['lead']['enrichment']['fields']['instagram']['confidence'] == 92

def test_combined_signal_condition_can_drive_rule(auth, lead_data):
    rule = _create_rule(
        auth,
        trigger='pipeline_added',
        conditions=[{'field': 'combined_signal', 'operator': 'contains', 'value': 'qualified_reachable_fit', 'service_key': ''}],
        actions=[{'type': 'add_note', 'text': 'Sinal combinado validado', 'due_days': 0}],
    )
    lead = auth.post('/api/leads?to_pipeline=true', json=lead_data).json()
    runs = auth.get(f"/api/automations/{rule['id']}/runs").json()
    assert runs and runs[0]['status'] == 'executed'
    activities = auth.get(f"/api/leads/{lead['id']}/activities").json()
    assert any(item['body'] == 'Sinal combinado validado' for item in activities)
