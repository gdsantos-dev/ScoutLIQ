import sqlite3
from test_communication_migration import copied, migrate


def test_027_roundtrip_preserves_business_and_consumption_records(auth, lead_data, tmp_path):
    assert auth.post('/api/leads', json=lead_data).status_code == 201
    target, env = copied(tmp_path)
    result=migrate(env,'downgrade','027');assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                  if r[0] not in ('location_cache', 'location_gate', 'absorption_batches', 'absorption_items', 'absorption_recoveries', 'alembic_version')]
        before = {t: db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    for action, revision in [('downgrade', '026'), ('upgrade', '027')]:
        result = migrate(env, action, revision)
        assert result.returncode == 0, result.stderr
        with sqlite3.connect(target) as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == revision
            assert {t: db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables} == before
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
