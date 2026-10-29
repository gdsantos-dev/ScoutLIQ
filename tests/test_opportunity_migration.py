import os
import sqlite3
import subprocess
import sys
import json
from backend.db import engine


def test_023_roundtrip_preserves_all_v133_tables(auth, lead_data, tmp_path):
    auth.post('/api/leads', json=lead_data)
    destination=tmp_path/'migration-023.db'
    raw=engine.raw_connection()
    try:
        with sqlite3.connect(destination) as copy: raw.driver_connection.backup(copy)
    finally: raw.close()
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(destination)}
    # Exercise 023 against its actual source schema, after checking later migrations separately.
    baseline=subprocess.run([sys.executable,'-m','alembic','downgrade','023'],env=env,capture_output=True,text=True)
    assert baseline.returncode==0,baseline.stderr
    with sqlite3.connect(destination) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0] not in ('semantic_attempts','semantic_gate','alembic_version')]
        before={table:db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall() for table in tables}
    for direction,revision in [('downgrade','022'),('upgrade','023')]:
        result=subprocess.run([sys.executable,'-m','alembic',direction,revision],env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        with sqlite3.connect(destination) as db:
            for table in tables: assert db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()==before[table]
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_022_roundtrip_preserves_all_canonical_records(auth, lead_data, tmp_path):
    from test_opportunity_workflow import setup_flow,approve
    from backend.search_intent import interpret
    lead,base,evidence,payload,draft=setup_flow(auth,lead_data)
    assert approve(auth,base,draft).status_code==200
    saved=auth.post('/api/radar/saved-searches',json={'name':'Preservação 021','query':{'location':'Recife','country':'BR','category':'dentista',
        'commercial_intent':interpret('Clínicas odontológicas em Recife, Brasil',25).model_dump()}})
    assert saved.status_code==201
    destination=tmp_path/'migration-022.db'
    raw=engine.raw_connection()
    try:
        with sqlite3.connect(destination) as copy: raw.driver_connection.backup(copy)
    finally: raw.close()
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(destination)}
    baseline=subprocess.run([sys.executable,'-m','alembic','downgrade','022'],env=env,capture_output=True,text=True)
    assert baseline.returncode==0,baseline.stderr
    tables=['users','sessions','leads','lead_activities','opportunity_evidence','outreach_drafts','recipient_policies','smart_searches']
    with sqlite3.connect(destination) as db:
        before={table:db.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall() for table in tables}
        search_before=db.execute('SELECT id,user_id,name,query_json,version FROM radar_saved_searches').fetchall()
    for direction,revision in [('downgrade','021'),('upgrade','022')]:
        result=subprocess.run([sys.executable,'-m','alembic',direction,revision],env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        with sqlite3.connect(destination) as db:
            for table in tables: assert db.execute(f'SELECT * FROM {table} ORDER BY 1').fetchall()==before[table]
            assert db.execute('SELECT id,user_id,name,query_json,version FROM radar_saved_searches').fetchall()==search_before
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
            if direction=='upgrade': assert db.execute('SELECT routine_state FROM radar_saved_searches').fetchone()[0]=='disabled'


def test_019_downgrade_and_upgrade_preserve_existing_lead(auth, lead_data, tmp_path):
    lead = auth.post('/api/leads', json=lead_data).json()
    destination = tmp_path / 'migration-copy.db'
    raw = engine.raw_connection()
    try:
        with sqlite3.connect(destination) as copy:
            raw.driver_connection.backup(copy)
    finally:
        raw.close()
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(destination)}
    for direction, revision in [('downgrade', '018'), ('upgrade', 'head')]:
        result = subprocess.run([sys.executable, '-m', 'alembic', direction, revision], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        with sqlite3.connect(destination) as db:
            assert db.execute('select name, version from leads where id=?', (lead['id'],)).fetchone() == (lead['name'], lead['version'])
            assert db.execute('pragma integrity_check').fetchone()[0] == 'ok'
            assert db.execute('pragma foreign_key_check').fetchall() == []


def test_020_roundtrip_preserves_v130_evidence(auth, lead_data, tmp_path):
    lead = auth.post('/api/leads', json=lead_data).json()
    evidence = auth.post(f"/api/leads/{lead['id']}/evidence", json={'statement':'Observação registrada antes da migração.',
        'source_url':'https://example.org'}).json()
    destination = tmp_path / 'migration-020.db'
    raw = engine.raw_connection()
    try:
        with sqlite3.connect(destination) as copy: raw.driver_connection.backup(copy)
    finally: raw.close()
    env = {**os.environ, 'DATABASE_URL':'sqlite:///'+str(destination)}
    for direction, revision in [('downgrade','019'),('upgrade','020')]:
        result = subprocess.run([sys.executable,'-m','alembic',direction,revision],env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        with sqlite3.connect(destination) as db:
            assert db.execute('select statement from opportunity_evidence where id=?',(evidence['id'],)).fetchone()[0]==evidence['statement']
            assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
            assert db.execute('pragma foreign_key_check').fetchall()==[]

def test_021_preserves_identity_history_and_freezes_previous_score(auth, lead_data, tmp_path):
    lead=auth.post('/api/leads',json=lead_data).json()
    evidence=auth.post(f"/api/leads/{lead['id']}/evidence",json={'statement':'Evidência anterior à busca inteligente.','source_url':'https://example.org'}).json()
    destination=tmp_path/'migration-021.db'
    raw=engine.raw_connection()
    try:
        with sqlite3.connect(destination) as copy: raw.driver_connection.backup(copy)
    finally: raw.close()
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(destination)}
    for direction,revision in [('downgrade','020'),('upgrade','021')]:
        result=subprocess.run([sys.executable,'-m','alembic',direction,revision],env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        with sqlite3.connect(destination) as db:
            assert db.execute('SELECT name,version,stage FROM leads WHERE id=?',(lead['id'],)).fetchone()==(lead['name'],lead['version'],lead['stage'])
            assert db.execute('SELECT statement FROM opportunity_evidence WHERE id=?',(evidence['id'],)).fetchone()[0]==evidence['statement']
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
            if direction=='upgrade':
                old=json.loads(db.execute('SELECT previous_score_json FROM leads WHERE id=?',(lead['id'],)).fetchone()[0])
                assert old['version']=='2.5' and old['value']==90

