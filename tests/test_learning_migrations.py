import os
import sqlite3
import subprocess
import sys
from backend.db import engine
from test_opportunity_workflow import setup_flow, approve


def test_024_025_preserve_every_v134_table_and_dependent_record(auth,lead_data,tmp_path):
    lead,base,evidence,payload,draft=setup_flow(auth,lead_data)
    assert approve(auth,base,draft).status_code==200
    destination=tmp_path/'learning-roundtrip.db'
    raw=engine.raw_connection()
    try:
        with sqlite3.connect(destination) as copy: raw.driver_connection.backup(copy)
    finally: raw.close()
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(destination)}
    # Freeze the exact schema this historical 024/025 roundtrip is responsible for.
    process=subprocess.run([sys.executable,'-m','alembic','downgrade','025'],env=env,capture_output=True,text=True)
    assert process.returncode==0,process.stderr
    excluded={'learning_gate','learning_cases','learning_revisions','learning_imports','learning_evaluations',
              'calibration_proposals','calibration_changes','score_configurations','alembic_version'}
    with sqlite3.connect(destination) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0] not in excluded]
        columns={t:[r[1] for r in db.execute(f'PRAGMA table_info("{t}")') if r[1]!='score_criteria_json'] for t in tables}
        def contents(db):
            return {t:db.execute('SELECT '+','.join('"'+c+'"' for c in columns[t])+f' FROM "{t}" ORDER BY 1').fetchall() for t in tables}
        before=contents(db)
    for direction,revision in [('downgrade','023'),('upgrade','head')]:
        process=subprocess.run([sys.executable,'-m','alembic',direction,revision],env=env,capture_output=True,text=True)
        assert process.returncode==0,process.stderr
        with sqlite3.connect(destination) as db:
            assert contents(db)==before
            assert db.execute('SELECT COUNT(*) FROM opportunity_evidence WHERE id=?',(evidence['id'],)).fetchone()[0]==1
            assert db.execute('SELECT COUNT(*) FROM outreach_drafts WHERE id=?',(draft['id'],)).fetchone()[0]==1
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_downgrade_rejects_active_calibration_before_removing_tables(auth,lead_data,tmp_path):
    from test_score_calibration import prepared,proposal,apply
    _,evaluations=prepared(auth,lead_data)
    assert apply(auth,proposal(auth,evaluations).json()).status_code==200
    destination=tmp_path/'active-calibration.db'
    raw=engine.raw_connection()
    try:
        with sqlite3.connect(destination) as copy: raw.driver_connection.backup(copy)
    finally: raw.close()
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(destination)}
    process=subprocess.run([sys.executable,'-m','alembic','downgrade','024'],env=env,capture_output=True,text=True)
    assert process.returncode!=0
    with sqlite3.connect(destination) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='025'
        assert db.execute('SELECT COUNT(*) FROM calibration_changes').fetchone()[0]==1
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
