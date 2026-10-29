import sqlite3
from test_communication_migration import copied, migrate
from test_commercial_review import create, queue, preview, commit


def test_031_preserves_every_030_column_and_record(auth, lead_data, tmp_path):
    create(auth, lead_data)
    target, env = copied(tmp_path)
    result = migrate(env, 'downgrade', '030'); assert result.returncode == 0, result.stderr
    with sqlite3.connect(target) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")]
        columns = {t:[r[1] for r in db.execute(f'PRAGMA table_info("{t}")')] for t in tables}
        def snapshot(db):
            return {t:db.execute('SELECT '+','.join('"'+c+'"' for c in columns[t])+f' FROM "{t}" ORDER BY 1').fetchall() for t in tables}
        before = snapshot(db)
    result = migrate(env, 'upgrade', '031'); assert result.returncode == 0, result.stderr
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '031'
        assert snapshot(db) == before
        assert db.execute('SELECT COUNT(*) FROM commercial_reviews').fetchone()[0] == 0
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_031_refuses_to_erase_decisions_or_previews(auth, lead_data, tmp_path):
    create(auth,lead_data); op,_=preview(auth,queue(auth)['items']);commit(auth,op)
    target,env=copied(tmp_path);assert migrate(env,'downgrade','031').returncode==0;result=migrate(env,'downgrade','030')
    assert result.returncode != 0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='031'
        assert db.execute('SELECT state FROM commercial_reviews').fetchone()[0]=='reviewed'
        assert db.execute('SELECT status FROM commercial_operations').fetchone()[0]=='committed'


def test_031_cache_only_can_be_rebuilt_without_losing_business_data(auth,lead_data,tmp_path):
    create(auth,lead_data);queue(auth)
    target,env=copied(tmp_path);assert migrate(env,'downgrade','030').returncode==0
    assert migrate(env,'upgrade','031').returncode==0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT COUNT(*) FROM leads').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM commercial_reviews').fetchone()[0]==0
