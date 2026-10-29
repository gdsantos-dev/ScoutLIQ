import sqlite3
from test_communication_migration import copied,migrate


def test_033_upgrade_is_additive_preserves_032_and_can_reapply(auth,lead_data,tmp_path):
    assert auth.post('/api/leads',json=lead_data).status_code==201
    target,env=copied(tmp_path)
    result=migrate(env,'downgrade','032');assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='alembic_version'")]
        def snapshot():return {t:db.execute('SELECT * FROM "'+t+'" ORDER BY 1').fetchall() for t in names}
        before=snapshot()
    result=migrate(env,'upgrade','033');assert result.returncode==0,result.stderr
    with sqlite3.connect(target) as db:
        assert snapshot()==before
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='033'
        assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT COUNT(*) FROM prospecting_plans').fetchone()[0]==0
    assert migrate(env,'upgrade','head').returncode==0


def test_033_downgrade_refuses_to_erase_plans(auth,tmp_path):
    from backend.db import SessionLocal
    from backend.models import User
    from backend.prospecting_models import ProspectingPlan
    from sqlalchemy import select
    with SessionLocal() as db:
        user=db.scalar(select(User))
        db.add(ProspectingPlan(user_id=user.id,config_json='{}',timezone=user.timezone));db.commit()
    target,env=copied(tmp_path)
    result=migrate(env,'downgrade','032');assert result.returncode!=0
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT COUNT(*) FROM prospecting_plans').fetchone()[0]==1
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='033'
