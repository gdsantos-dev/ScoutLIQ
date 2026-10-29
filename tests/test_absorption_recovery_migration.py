"""029 preserves 028 business records and refuses to discard new provenance."""
import os,sqlite3,json
from test_communication_migration import copied,migrate
from test_absorption import preview,record
from test_absorption_intelligence import intake,edit,start,pending


def test_029_upgrade_preserves_028_records_and_seeds_versions(auth,tmp_path):
    preview(auth,[record()])
    target,env=copied(tmp_path)
    result=migrate(env,'downgrade','028');assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0]!='alembic_version']
        before={t:db.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for t in tables}
    result=migrate(env,'upgrade','029');assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='029'
        for table,rows in before.items():
            after=db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
            assert [r[:len(rows[0])] for r in after]==rows if rows else not after
        assert db.execute('SELECT original_json=payload_json,version FROM absorption_items').fetchone()==(1,1)
        assert db.execute('SELECT input_hash=payload_hash,ordinal FROM absorption_batches').fetchone()==(1,1)
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_029_refuses_loss_of_normalization_original(auth,tmp_path):
    intake(auth,[record(country='Brasil',phone='(81) 99999-0000')])
    target,env=copied(tmp_path);result=migrate(env,'downgrade','028');assert result.returncode!=0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='029'
        original=db.execute('SELECT original_json FROM absorption_items').fetchone()[0]
        assert json.loads(original)['country']=='Brasil'


def test_029_refuses_loss_of_recovery_and_correction(auth,tmp_path):
    b=pending(auth);b=edit(auth,b,category='Odontologia').json();start(auth,b)
    target,env=copied(tmp_path);result=migrate(env,'downgrade','028');assert result.returncode!=0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT COUNT(*) FROM absorption_recoveries').fetchone()[0]==1
        assert len(json.loads(db.execute('SELECT history_json FROM absorption_items').fetchone()[0]))==1


def test_029_clean_install(tmp_path):
    target=tmp_path/'clean-029.db';result=migrate({**os.environ,'DATABASE_URL':'sqlite:///'+str(target)},'upgrade','029')
    assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='029'
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
