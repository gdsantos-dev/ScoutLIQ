"""Persisted limits on worker network operations; prices are deliberately unknown.

An operation is one adapter call (possibly including redirects), not a billing unit.
Only the explicit worker scope is metered here. Manual/legacy routes are unchanged.
"""
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from functools import wraps
import json
import os
import time
from sqlalchemy import select, update, func
from .db import SessionLocal
from .models import ResearchExecutor, RadarSavedSearch
from .autonomy_models import WorkAttempt, ProviderOperation, RoutineRun

HTTP_BUDGET = max(1, min(100000, int(os.getenv('RESEARCH_HTTP_DAILY_BUDGET','500'))))
PROVIDER_LIMITS = json.loads(os.getenv('RESEARCH_PROVIDER_DAILY_LIMITS','{"geoapify":100,"openstreetmap":100,"brave":100,"website":400}'))
if not isinstance(PROVIDER_LIMITS,dict) or any(k not in {'geoapify','openstreetmap','brave','website','gmail'} or type(v) is not int or not 0<=v<=100000 for k,v in PROVIDER_LIMITS.items()):
    raise ValueError('Configuração de limites por provedor inválida.')
_scope=ContextVar('scoutliq_work_token',default=None)


class ConsumptionLimit(RuntimeError): pass


@contextmanager
def work_scope(token):
    handle=_scope.set(token)
    try: yield
    finally: _scope.reset(handle)


def submit(pool, function, *args, **kwargs):
    # ContextVars do not propagate to ThreadPoolExecutor automatically.
    return pool.submit(copy_context().run, function, *args, **kwargs)


def reserve(provider):
    token=_scope.get()
    if not token: return None
    now=int(time.time());day=now//86400*86400
    with SessionLocal() as db:
        fence=db.execute(update(ResearchExecutor).where(ResearchExecutor.id==1,ResearchExecutor.token==token,
            ResearchExecutor.lease_until>now).values(lease_until=ResearchExecutor.lease_until))
        if fence.rowcount!=1: raise ConsumptionLimit('Permissão de execução expirada.')
        attempt=db.get(WorkAttempt,token)
        if not attempt: raise ConsumptionLimit('Reserva de tarefa ausente.')
        total=db.scalar(select(func.count()).select_from(ProviderOperation).where(ProviderOperation.started_at>=day))
        used=db.scalar(select(func.count()).select_from(ProviderOperation).where(ProviderOperation.started_at>=day,ProviderOperation.provider==provider))
        if total>=HTTP_BUDGET or used>=PROVIDER_LIMITS.get(provider,0):
            raise ConsumptionLimit('Orçamento de operações de rede atingido.')
        from .prospecting import guard_operation as guard_plan_operation
        guard_plan_operation(db, attempt, now)
        from .investigation import guard_operation
        guard_operation(db, attempt, now)
        if attempt.run_id:
            run=db.get(RoutineRun,attempt.run_id)
            saved=db.get(RadarSavedSearch,run.saved_search_id) if run else None
            if not run or run.status!='running' or not saved or saved.routine_state!='active':
                raise ConsumptionLimit('Rotina interrompida.')
            cfg=json.loads(run.config_json)['limits']
            query=select(func.count()).select_from(ProviderOperation).join(WorkAttempt).join(RoutineRun)
            run_used=db.scalar(query.where(RoutineRun.id==run.id))
            day_used=db.scalar(query.where(RoutineRun.saved_search_id==saved.id,ProviderOperation.started_at>=day))
            if run_used>=cfg['operation_limit'] or day_used>=cfg['daily_operation_limit']:
                raise ConsumptionLimit('Orçamento de operações da rotina atingido.')
        operation=ProviderOperation(token=token,provider=provider,started_at=now)
        db.add(operation);db.commit()
        return operation.id


def finish(identifier, status):
    if not identifier: return
    with SessionLocal() as db:
        row=db.get(ProviderOperation,identifier)
        if row:
            row.status=status;row.finished_at=int(time.time());db.commit()


def metered(provider):
    def decorate(function):
        @wraps(function)
        def wrapped(*args,**kwargs):
            identifier=reserve(provider)
            try: result=function(*args,**kwargs)
            except BaseException:
                finish(identifier,'failed');raise
            finish(identifier,'completed')
            return result
        return wrapped
    return decorate
