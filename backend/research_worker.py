"""Single bounded executor over the existing batch items and saved searches.

Network reads occur outside transactions. A token-fenced write transaction commits
results and completion together. Expired claims can repeat reads, never committed
CRM effects. One executor per SQLite database; budgets survive process restarts.
"""
import json
import os
import time
from uuid import uuid4
from sqlalchemy import select, update, or_
from .db import SessionLocal
from .models import ResearchExecutor, ResearchBatch, ResearchBatchItem, RadarSavedSearch, Lead, User, SmartSearch
from .autonomy_models import WorkAttempt
from .consumption import work_scope, ConsumptionLimit

MODE = os.getenv('RESEARCH_EXECUTION_MODE', 'worker')
LEASE = max(60, int(os.getenv('RESEARCH_LEASE_SECONDS', '300')))
INTERVAL = max(5, int(os.getenv('RESEARCH_MIN_INTERVAL_SECONDS', '15')))
BUDGET = max(1, int(os.getenv('RESEARCH_DAILY_BUDGET', '100')))
MAX_ATTEMPTS = 3

def claim(now=None, batch_id=None):
    now = int(time.time()) if now is None else now
    token = str(uuid4())
    with SessionLocal() as db:
        from .smart_search import expire
        expire(db, now)
        # Conditional UPDATE is atomic on SQLite and PostgreSQL; no read-then-set claim.
        lock = db.execute(update(ResearchExecutor).where(ResearchExecutor.id == 1,
            ResearchExecutor.lease_until <= now)
            .values(token=token, lease_until=now + LEASE))
        if lock.rowcount != 1: db.rollback(); return None
        slot = db.get(ResearchExecutor, 1)
        from .routines import reconcile, schedule_due, run_for_task
        reconcile(db,now)
        from .search_compat import sync_results, schedule_monitors
        sync_results(db,now)
        if slot.next_at>now or (slot.day==now//86400 and slot.used>=BUDGET):
            slot.token,slot.lease_until='',0;db.commit();return None
        if not batch_id and MODE=='worker':
            from .main import radar_provider
            schedule_due(db,now,radar_provider)
            schedule_monitors(db,now,radar_provider)
            reconcile(db,now)
        candidates = select(ResearchBatchItem).join(ResearchBatch).join(User, User.id == ResearchBatch.user_id).where(
            ResearchBatch.status.in_(['pending', 'running']), User.is_active.is_(True),
            ResearchBatchItem.retry_at <= now,
            or_(ResearchBatchItem.status == 'pending',
                (ResearchBatchItem.status == 'running') & (ResearchBatchItem.lease_until <= now)))
        if batch_id: candidates = candidates.where(ResearchBatch.id == batch_id)
        # A removed Lead cascades to its item; close empty progressive batches.
        db.execute(update(ResearchBatch).where(ResearchBatch.mode=='progressive',ResearchBatch.status.in_(['pending','running']),
            ~ResearchBatch.id.in_(select(ResearchBatchItem.batch_id).where(ResearchBatchItem.status.in_(['pending','running']))))
            .values(status='completed',completed_at=now,updated_at=now))
        from .investigation import admit
        item = None
        for candidate in db.scalars(candidates.order_by(ResearchBatch.created_at, ResearchBatch.ordinal, ResearchBatch.id, ResearchBatchItem.position)).all():
            if admit(db, candidate, db.get(ResearchBatch, candidate.batch_id), now):
                item = candidate
                break
        kind = 'batch'
        if item is None and not batch_id:
            item = db.scalar(select(SmartSearch).join(User).where(User.is_active.is_(True),
                SmartSearch.status.in_(['pending','running','investigating']), SmartSearch.retry_at <= now,
                SmartSearch.lease_until <= now,
                or_(SmartSearch.batch_id.is_(None), SmartSearch.status != 'investigating',
                    SmartSearch.batch_id.in_(select(ResearchBatch.id).where(ResearchBatch.status.in_(['completed','cancelled']))), SmartSearch.deadline <= now)
                ).order_by(SmartSearch.created_at).limit(1))
            kind = 'smart'
        if item is None and not batch_id:
            from .communication import next_task
            kind,item=next_task(db,now)
        if item is None and not batch_id:
            from .absorption_recovery import next_task as next_absorption
            kind,item=next_absorption(db,now)
        if item is None:
            slot.token, slot.lease_until = '', 0
            db.commit(); return None
        if kind == 'batch' and item.attempts >= MAX_ATTEMPTS:
            item.status, item.error, item.finished_at = 'error', 'Limite de recuperação atingido. Revise e crie outro lote.', now
            finish_batch(db, item.batch_id, now)
            slot.token, slot.lease_until = '', 0
            db.commit(); return None
        if kind == 'smart' and item.attempts >= MAX_ATTEMPTS:
            item.status, item.error = 'partial', 'Limite de recuperação atingido; resultado parcial preservado.'
            item.lease_token, item.lease_until = '', 0
            slot.token, slot.lease_until = '', 0
            db.commit(); return None
        item.attempts += 1
        if kind == 'smart' and item.status != 'investigating':
            info = json.loads(item.state_json)
            info['attempted_pages'] = info.get('attempted_pages', 0) + 1
            item.state_json = json.dumps(info)
            item.status = 'running'
        item.lease_token, item.lease_until = token, now + LEASE
        run=run_for_task(db,kind,item)
        if kind == 'batch':
            item.status, item.started_at = 'running', now
            batch = db.get(ResearchBatch, item.batch_id)
            batch.status, batch.updated_at = 'running', now
        slot.used = (slot.used if slot.day == now // 86400 else 0) + 1
        slot.day, slot.next_at = now // 86400, now + INTERVAL
        user_id = batch.user_id if kind=='batch' else item.user_id
        db.execute(update(WorkAttempt).where(WorkAttempt.item_id==item.id,WorkAttempt.kind==kind,WorkAttempt.status=='claimed')
            .values(status='expired',finished_at=now))
        db.add(WorkAttempt(token=token,user_id=user_id,run_id=run.id if run else None,kind=kind,item_id=item.id,started_at=now))
        db.commit()
        return {'kind': kind, 'id': item.id, 'token': token, 'expires': now + LEASE}

def finish_batch(db, batch_id, now):
    db.flush()
    batch = db.get(ResearchBatch, batch_id)
    if batch.status in ('cancelled', 'paused'): return
    pending = db.scalar(select(ResearchBatchItem.id).where(ResearchBatchItem.batch_id == batch_id,
        ResearchBatchItem.status.in_(['pending', 'running'])))
    batch.status = 'pending' if pending else 'completed'
    batch.updated_at = now
    if not pending: batch.completed_at = now

def execute(task, researcher=None, provider=None):
    try:
        with work_scope(task['token']):
            return _execute(task,researcher,provider)
    finally:
        with SessionLocal() as db:
            attempt=db.get(WorkAttempt,task['token'])
            if attempt and attempt.status=='claimed':
                attempt.status='obsolete';attempt.finished_at=int(time.time());db.commit()


def _execute(task, researcher=None, provider=None):
    if task['kind']=='absorption':
        from .absorption_recovery import execute as execute_absorption
        return execute_absorption(task,provider)
    if task['kind']=='outreach':
        from .communication import execute_outreach
        return execute_outreach(task,provider)
    if task['kind']=='mail_sync':
        from .communication_replies import execute_sync
        return execute_sync(task,provider)
    from . import main
    from .research import SearchConfigurationError
    from .providers import ProviderConfigurationError, LocationNotFound
    researcher = researcher or main.website_researcher
    if task['kind'] == 'batch':
        with SessionLocal() as db:
            queued = db.get(ResearchBatchItem, task['id'])
            progressive = queued and db.get(ResearchBatch, queued.batch_id).mode == 'progressive'
        if progressive:
            from .investigation import execute as execute_progressive
            return execute_progressive(task, researcher)
    model = {'batch':ResearchBatchItem,'monitor':RadarSavedSearch,'smart':SmartSearch}[task['kind']]
    # Detached input snapshot avoids holding SQLite locks during a provider request.
    with SessionLocal() as db:
        item = db.get(model, task['id'])
        if not item or item.lease_token != task['token']: return False
        if task['kind'] == 'batch':
            batch = db.get(ResearchBatch, item.batch_id)
            user, lead = db.get(User, batch.user_id), db.get(Lead, item.lead_id)
            mode = batch.mode
        elif task['kind'] == 'monitor':
            user = db.get(User, item.user_id)
            query_data = json.loads(item.query_json)
            query = main.DiscoveryQuery(**{k:v for k,v in query_data.items() if k in main.DiscoveryQuery.model_fields})
    error, permanent, result, audit = '', False, None, None
    try:
        if task['kind'] == 'batch':
            if not lead or lead.demo or lead.user_id != user.id: raise ValueError('Unavailable lead')
            result = researcher.research(lead, user.locale)
            if mode == 'deep' and result.get('status') == 'confirmed' and result.get('website_url'):
                audit = researcher.deep_audit(lead, result['website_url'])
        elif task['kind'] == 'smart':
            from .smart_search import collect
            result = collect(item, provider or main.radar_provider)
        else:
            source = provider or main.radar_provider
            if source is None: raise SearchConfigurationError('Unavailable provider')
            from .search_compat import collect_compatible
            result = collect_compatible(source,query)
    except Exception as exc:
        permanent = isinstance(exc, (SearchConfigurationError, ProviderConfigurationError, LocationNotFound, ValueError, ConsumptionLimit))
        # Never store provider exceptions, URLs or credentials in logs/state.
        error = 'Configuração ou entrada indisponível.' if permanent else 'Coleta temporariamente indisponível; nova tentativa agendada.'
        if isinstance(exc,ConsumptionLimit): error='Permissão ou orçamento de operações de rede indisponível; coleta interrompida.'
    now = int(time.time())
    with SessionLocal() as db:
        # Acquire the write lock before reading cancellation/version state.
        fence = db.execute(update(ResearchExecutor).where(ResearchExecutor.id == 1,
            ResearchExecutor.token == task['token'], ResearchExecutor.lease_until > now).values(next_at=now + INTERVAL))
        if fence.rowcount != 1: db.rollback(); return False
        item = db.get(model, task['id'])
        if not item or item.lease_token != task['token']: db.rollback(); return False
        slot = db.get(ResearchExecutor, 1)
        slot.token, slot.lease_until = '', 0
        item.lease_token, item.lease_until = '', 0
        if task['kind'] == 'batch':
            batch = db.get(ResearchBatch, item.batch_id)
            if batch.status in ('cancelled', 'paused'):
                item.status = 'cancelled' if batch.status == 'cancelled' else 'pending'
                if batch.status == 'paused': item.attempts = max(0, item.attempts - 1)
                db.commit(); return False
            if error:
                item.status = 'error' if permanent or item.attempts >= MAX_ATTEMPTS else 'pending'
                item.error, item.retry_at = error, now + 30 * (2 ** (item.attempts - 1))
                item.outcome = 'collection_failed'
                if item.status == 'error': item.finished_at = now
            else:
                lead, user = db.get(Lead, item.lead_id), db.get(User, batch.user_id)
                if not lead or not user or not user.is_active or lead.user_id != user.id: db.rollback(); return False
                research = main._persist_research_result(db, user, lead, result)
                if audit:
                    before = main._commercial_snapshot(lead)
                    research.audit_level, research.audit_json, research.audited_at = 'deep', json.dumps(audit), now
                    research.website_status = str(audit.get('website_status', 'unknown'))[:20]
                    lead.website_status = research.website_status
                    main._set_website_intelligence(lead, main._intelligence_from_audit(audit), now)
                    from .website_context import persist as persist_context
                    persist_context(db, lead, research, audit.get('context'), now)
                    main._sync_commercial_signals(lead, previous_snapshot=before, track_changes=True)
                item.status, item.outcome, item.error, item.finished_at = 'done', str(result.get('status', 'unverified'))[:40], '', now
            finish_batch(db, batch.id, now)
        elif task['kind'] == 'smart':
            if item.status not in ('pending','running','investigating'): db.commit(); return False
            if error:
                item.error, item.retry_at = error, now + 30 * (2 ** (item.attempts - 1))
                if permanent or item.attempts >= MAX_ATTEMPTS: item.status = 'partial'
            else:
                from .smart_search import persist
                persist(db,item,result,now)
                item.attempts, item.retry_at, item.error = 0, 0, ''
        else:
            if not item.monitor_enabled: db.commit(); return False
            if error:
                item.worker_error, item.retry_at = error, now + 60 * (2 ** (item.attempts - 1))
                if permanent: item.attempts = MAX_ATTEMPTS
            else:
                user = db.get(User, item.user_id)
                if not user or not user.is_active: db.rollback(); return False
                response = main._persist_discovery(query, result, user, db, commit=False)
                from .monitor_matching import matches
                ids = [r['id'] for r in response['results'] if matches(r, query_data)]
                item.last_new_count = len(set(ids) - set(json.loads(item.result_ids_json)))
                item.result_ids_json = json.dumps(ids)
                item.last_monitor_at = item.last_run_at = item.updated_at = now
                item.next_monitor_at = now + main._monitor_seconds(item.monitor_interval)
                item.attempts, item.retry_at, item.worker_error = 0, 0, ''
        attempt=db.get(WorkAttempt,task['token'])
        if attempt:
            attempt.status='failed' if error else 'committed';attempt.finished_at=now
            if error and permanent and attempt.run_id:
                from .routines import stop_run
                from .autonomy_models import RoutineRun
                run=db.get(RoutineRun,attempt.run_id)
                if run: stop_run(db,run,'partial',error,now)
        from .search_compat import sync_results
        sync_results(db,now)
        db.commit()
    return True

def tick(batch_id=None):
    task = claim(batch_id=batch_id)
    return execute(task) if task else False

def run():
    if MODE != 'worker': raise SystemExit('RESEARCH_EXECUTION_MODE deve ser worker para iniciar este processo.')
    import signal
    import threading
    from uuid import UUID
    from .worker_health import beat
    identifier=str(UUID(os.environ['SCOUTLIQ_WORKER_ID'])) if os.getenv('SCOUTLIQ_WORKER_ID') else str(uuid4())
    stopped=threading.Event()
    for name in ('SIGTERM','SIGINT','SIGBREAK'):
        if hasattr(signal,name): signal.signal(getattr(signal,name),lambda *_:stopped.set())
    try:
        while not stopped.is_set():
            try:
                beat(identifier)
                task=claim()
                if task and not stopped.is_set():
                    beat(identifier,'busy',task['expires'])
                    execute(task)
                beat(identifier)
            except Exception:
                import logging
                logging.getLogger('scoutliq.worker').error('Falha local do executor; recuperação por lease.')
                beat(identifier,'error',error='Falha local; aguarde recuperação ou revise o serviço.')
            stopped.wait(3)
    finally:
        beat(identifier,'stopped')

if __name__ == '__main__': run()
