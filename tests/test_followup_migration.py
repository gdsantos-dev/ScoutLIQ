import sqlite3
from test_communication_migration import copied,migrate
from test_commercial_review import create
from test_followup import queue,operation,commit


def test_032_upgrade_preserves_031_records(auth,lead_data,tmp_path):
    create(auth,lead_data)
    target,env=copied(tmp_path)
    r=migrate(env,'downgrade','031');assert r.returncode==0,r.stderr
    with sqlite3.connect(target) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")]
        columns={t:[r[1] for r in db.execute(f'PRAGMA table_info("{t}")')] for t in tables}
        def snap(db): return {t:db.execute('SELECT '+','.join('"'+c+'"' for c in columns[t])+f' FROM "{t}" ORDER BY 1').fetchall() for t in tables}
        before=snap(db)
    r=migrate(env,'upgrade','032');assert r.returncode==0,r.stderr
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='032'
        assert snap(db)==before and db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_032_refuses_to_remove_human_followup(auth,lead_data,tmp_path):
    create(auth,lead_data);row,=queue(auth)['items'];commit(auth,operation(auth,[row],'followup_disable'))
    target,env=copied(tmp_path);r=migrate(env,'downgrade','031');assert r.returncode!=0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT disabled FROM followup_preferences').fetchone()[0]==1
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='032'


def test_032_cache_without_decisions_is_disposable(auth,lead_data,tmp_path):
    create(auth,lead_data);queue(auth)
    target,env=copied(tmp_path);r=migrate(env,'downgrade','031');assert r.returncode==0,r.stderr
    assert migrate(env,'upgrade','032').returncode==0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT COUNT(*) FROM leads').fetchone()[0]==1
