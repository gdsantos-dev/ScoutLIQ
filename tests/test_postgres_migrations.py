"""Real PostgreSQL preservation checks, complementary to SQLite backup tests."""
import os
import subprocess
import sys
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from backend.models import User, Lead
from backend.prospecting_models import ProspectingPlan
from database_fixture import postgres_database

pytestmark = pytest.mark.skipif(not os.getenv('SCOUT_TEST_POSTGRES_URL'), reason='Requires the isolated PostgreSQL test service.')


def test_postgres_032_upgrade_033_preserves_data_and_refuses_destructive_downgrade():
    url, cleanup = postgres_database(os.environ['SCOUT_TEST_POSTGRES_URL'])
    engine = create_engine(url, hide_parameters=True)
    env = {**os.environ, 'DATABASE_URL': url, 'APP_ENV': 'test'}
    def migrate(*args):
        return subprocess.run([sys.executable, '-m', 'alembic', *args], env=env,
                              capture_output=True, text=True, timeout=90)
    try:
        result = migrate('upgrade', '032')
        assert result.returncode == 0, result.stderr
        with Session(engine) as db:
            user = User(email='preservation@example.test', password_hash='synthetic-hash')
            db.add(user); db.flush()
            lead = Lead(user_id=user.id, name='PostgreSQL preservation', category='Cafe', city='Recife', latitude=-8, longitude=-34)
            db.add(lead); db.commit(); lead_id, user_id = lead.id, user.id
        before = set(inspect(engine).get_table_names())
        assert migrate('upgrade', 'head').returncode == 0
        assert before <= set(inspect(engine).get_table_names())
        with Session(engine) as db:
            assert db.get(Lead, lead_id).name == 'PostgreSQL preservation'
            assert db.scalar(text('SELECT version_num FROM alembic_version')) == '033'
            db.add(ProspectingPlan(user_id=user_id, config_json='{}', timezone='America/Recife')); db.commit()
        assert migrate('downgrade', '032').returncode != 0
        with Session(engine) as db:
            assert db.scalar(select(ProspectingPlan.user_id)) == user_id
            assert db.get(Lead, lead_id).name == 'PostgreSQL preservation'
        assert migrate('upgrade', 'head').returncode == 0
    finally:
        engine.dispose(); cleanup()
