import os
import sqlite3
import subprocess
import sys
from backend.db import engine
from test_communication import configured,prepared,queued,Controlled,run_controlled


def copied(tmp_path):
    target=tmp_path/'communication-migration.db';raw=engine.raw_connection()
    try:
        with sqlite3.connect(target) as copy:raw.driver_connection.backup(copy)
    finally:raw.close()
    return target,{**os.environ,'DATABASE_URL':'sqlite:///'+str(target)}


def migrate(env,*args):
    return subprocess.run([sys.executable,'-m','alembic',*args],env=env,capture_output=True,text=True)


def test_026_roundtrip_preserves_all_existing_tables(auth,lead_data,tmp_path):
    from test_opportunity_workflow import setup_flow
    setup_flow(auth,lead_data)
    target,env=copied(tmp_path)
    result=migrate(env,'downgrade','025');assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")]
        columns={t:[r[1] for r in db.execute(f'PRAGMA table_info("{t}")')] for t in tables}
        def contents(db):
            return {t:db.execute('SELECT '+','.join('"'+c+'"' for c in columns[t])+f' FROM "{t}" ORDER BY 1').fetchall() for t in tables}
        before=contents(db)
    for direction,revision in [('upgrade','026'),('downgrade','025'),('upgrade','head')]:
        result=migrate(env,direction,revision);assert result.returncode==0,result.stderr
        with sqlite3.connect(target) as db:
            assert contents(db)==before
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_026_refuses_to_erase_attempted_delivery_ledger(auth,lead_data,configured,tmp_path):
    _,_,_,data=prepared(auth,lead_data);queued(auth,data);run_controlled(Controlled())
    target,env=copied(tmp_path);result=migrate(env,'downgrade','025');assert result.returncode!=0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='026'
        assert db.execute('SELECT status FROM communication_outbox').fetchone()[0]=='accepted'
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
