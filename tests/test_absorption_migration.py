"""Migration 028 is additive; staged records prevent silent downgrade data loss."""
import sqlite3
from test_communication_migration import copied, migrate


def test_028_empty_roundtrip_preserves_existing_leads(auth, lead_data, tmp_path):
    lead=auth.post('/api/leads',json=lead_data).json()
    target, env=copied(tmp_path)
    for direction,version in [('downgrade','027'),('upgrade','028')]:
        result=migrate(env,direction,version)
        assert result.returncode==0,result.stderr
        with sqlite3.connect(target) as db:
            assert db.execute('SELECT name FROM leads WHERE id=?',(lead['id'],)).fetchone()[0]==lead['name']
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_028_downgrade_refuses_to_erase_staged_records(auth,tmp_path):
    from test_absorption import preview,record
    response=preview(auth,[record()]);assert response.status_code==201,response.text
    target,env=copied(tmp_path)
    result=migrate(env,'downgrade','027')
    assert result.returncode!=0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='028'
        assert db.execute('SELECT COUNT(*) FROM absorption_items').fetchone()[0]==1


def test_028_preserves_every_historical_table(auth,lead_data,tmp_path):
    auth.post('/api/leads',json=lead_data)
    target,env=copied(tmp_path)
    result=migrate(env,'downgrade','028');assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                if r[0] not in ('absorption_batches','absorption_items','absorption_recoveries','alembic_version')]
        before={t:db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    for direction,revision in [('downgrade','027'),('upgrade','028')]:
        result=migrate(env,direction,revision);assert result.returncode==0,result.stderr
        with sqlite3.connect(target) as db:
            assert {t:db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}==before
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_028_clean_install(tmp_path):
    import os
    target=tmp_path/'clean-028.db'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(target)}
    result=migrate(env,'upgrade','028');assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='028'
        assert db.execute('SELECT COUNT(*) FROM absorption_items').fetchone()[0]==0
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
