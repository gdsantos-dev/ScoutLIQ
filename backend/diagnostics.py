"""Operator CLI with aggregate states only; no tenant data or exception messages."""
import json
import sys
import time
from sqlalchemy import select, func, text
from .db import SessionLocal
from .models import SmartSearch, ResearchBatchItem, ResearchExecutor
from .prospecting_models import ProspectingPlan
from .worker_health import snapshot

REQUIRED_REVISION = '033'


def schema_ready(db):
    return db.execute(text('SELECT version_num FROM alembic_version')).scalars().all() == [REQUIRED_REVISION]


def collect():
    result = {'status': 'unavailable', 'database': 'unavailable', 'schema': {'expected': REQUIRED_REVISION}}
    try:
        with SessionLocal() as db:
            db.execute(text('SELECT 1'))
            result['database'] = 'ok'
            revisions = db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
            result['schema']['applied'] = revisions
            if revisions != [REQUIRED_REVISION]:
                result['action'] = 'migration_required'
                return result
            result['worker'] = snapshot(db)
            result['tasks'] = {
                'searches': dict(db.execute(select(SmartSearch.status, func.count()).group_by(SmartSearch.status)).all()),
                'investigations': dict(db.execute(select(ResearchBatchItem.status, func.count()).group_by(ResearchBatchItem.status)).all()),
            }
            result['plans'] = dict(db.execute(select(ProspectingPlan.state, func.count()).group_by(ProspectingPlan.state)).all())
            # Only fixed application reasons are exposed, never arbitrary stored text.
            reasons = {
                'authorization_changed': 'Autorização ou fonte alterada; pause, revise e autorize novamente.',
                'outside_window': 'Fora dos dias ou da janela autorizados.',
                'target_reached': 'Meta diária de novas empresas atingida.',
                'run_limit': 'Limite diário de execuções atingido.',
                'plan_budget': 'Orçamento diário do plano esgotado.',
                'provider_budget': 'Limite global ou da fonte indisponível; nenhum novo job criado.',
            }
            result['plan_wait_reasons'] = {code: db.scalar(select(func.count()).select_from(ProspectingPlan).where(
                ProspectingPlan.state == 'active', ProspectingPlan.reason == reason)) for code, reason in reasons.items()}
            now = int(time.time())
            result['retry_pending'] = db.scalar(select(func.count()).select_from(SmartSearch).where(
                SmartSearch.status.in_(['pending', 'running', 'investigating']), SmartSearch.retry_at > now))
            result['expired_claims'] = db.scalar(select(func.count()).select_from(ResearchBatchItem).where(
                ResearchBatchItem.lease_token != '', ResearchBatchItem.lease_until <= now))
            slot = db.get(ResearchExecutor, 1)
            from .research_worker import BUDGET
            result['executor'] = {'leased': bool(slot and slot.lease_until > now),
                'waiting_interval': bool(slot and slot.next_at > now),
                'daily_budget_exhausted': bool(slot and slot.day == now // 86400 and slot.used >= BUDGET)}
            result['status'] = 'ok' if result['worker']['status'] == 'ok' else 'degraded'
            result['action'] = 'none' if result['status'] == 'ok' else 'inspect_worker'
    except Exception:
        result['action'] = 'check_database_and_migrations'
    return result


def main():
    result = collect()
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main())
