"""030 preserves every pre-existing column, including 029 recovery provenance."""
import sqlite3
from test_communication_migration import copied, migrate
from test_absorption import preview, record
from test_progressive_investigation import create, request, prefs

def test_030_upgrade_preserves_029_and_defaults_off(auth, tmp_path):
    preview(auth, [record()])
    target, env = copied(tmp_path)
    result = migrate(env, 'downgrade', '029'); assert result.returncode == 0, result.stderr
    with sqlite3.connect(target) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")]
        columns = {t: [r[1] for r in db.execute(f'PRAGMA table_info("{t}")')] for t in tables}
        def contents(db):
            return {t: db.execute('SELECT '+','.join('"'+c+'"' for c in columns[t])+f' FROM "{t}" ORDER BY 1').fetchall() for t in tables}
        before = contents(db)
    result = migrate(env, 'upgrade', '030'); assert result.returncode == 0, result.stderr
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '030'
        assert contents(db) == before
        assert db.execute('SELECT investigation_json FROM users').fetchone()[0] == '{}'
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

def test_030_downgrade_refuses_discarding_queue(auth, lead_data, tmp_path):
    request(auth, create(auth, lead_data))
    target, env = copied(tmp_path)
    assert migrate(env, 'downgrade', '030').returncode == 0
    result = migrate(env, 'downgrade', '029'); assert result.returncode != 0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '030'
        assert db.execute('SELECT COUNT(*) FROM research_batch_items').fetchone()[0] == 1

def test_030_downgrade_preserves_preferences_by_refusal(auth, tmp_path):
    prefs(auth, search=True)
    target, env = copied(tmp_path)
    assert migrate(env, 'downgrade', '030').returncode == 0
    result = migrate(env, 'downgrade', '029'); assert result.returncode != 0
    with sqlite3.connect(target) as db:
        assert 'true' in db.execute('SELECT investigation_json FROM users').fetchone()[0]
