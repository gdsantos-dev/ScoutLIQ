"""Compatibility adapters onto the same search contract and worker.

Historical predicates and provider query are retained, never re-parsed as prose.
No new scheduler, provider, score or research engine is introduced here.
"""
import hashlib
import json
from uuid import UUID, uuid5, NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select
from .models import RadarSavedSearch, SmartSearch, ResearchBatch, Lead, User
from .search_intent import Intent, Profile
from .discovery_contract import LegacySearch, DiscoveryQuery


def fingerprint(saved):
    return hashlib.sha256(saved.query_json.encode()).hexdigest()


def intent_from_saved(saved):
    raw=json.loads(saved.query_json)
    if raw.get('commercial_intent'):
        return Intent.model_validate(raw['commercial_intent'])
    query=LegacySearch.model_validate({k:v for k,v in raw.items() if k!='commercial_intent'})
    return Intent(query=f'{query.category or "Empresas"} · {query.location}',legacy=query,
                  sectors=[query.category or 'empresas'],profile=Profile(business_type='any',size='any',independence='any'))


def collect_compatible(provider, query):
    # Synchronous API callers keep their candidate response contract; collection
    # and persistence are shared with SmartSearch, not a second provider engine.
    from .search_sources import search_page
    return search_page(provider,query,0,100,compatible=True)


def create_saved_job(db,saved,user,key,provider,now,*,monitor=False):
    from .smart_search import create_search, state
    existing=db.scalar(select(SmartSearch).where(SmartSearch.user_id==user.id,SmartSearch.request_key==key))
    if existing:
        info=state(existing)
        if info.get('saved_search_id')!=saved.id or info.get('saved_query_hash')!=fingerprint(saved):
            raise HTTPException(409,'Esta solicitação já pertence a outra busca.')
        return existing
    intent=intent_from_saved(saved)
    options={'saved_search_id':saved.id,'saved_query_hash':fingerprint(saved),'saved_monitor':monitor}
    if monitor:
        # A historical monitor did not authorize website research. It now shares
        # classification/execution, while retaining its original operation scope.
        options.update(investigation_limit=0,page_limit=1)
    job=create_search(db,user,intent,key,provider,now,options=options)
    return job


def linked_jobs(db,saved):
    from .smart_search import ACTIVE, state
    rows=db.scalars(select(SmartSearch).where(SmartSearch.user_id==saved.user_id,SmartSearch.status.in_((*ACTIVE,'paused')))).all()
    return [job for job in rows if state(job).get('saved_search_id')==saved.id]


def cancel_linked(db,saved):
    for job in linked_jobs(db,saved):
        job.status='cancelled';job.lease_token='';job.lease_until=0
        if job.batch_id:
            batch=db.get(ResearchBatch,job.batch_id)
            if batch and batch.status!='completed': batch.status='cancelled'


def schedule_monitors(db,now,provider):
    from .smart_search import ACTIVE
    rows=db.scalars(select(RadarSavedSearch).join(User).where(User.is_active.is_(True),
        RadarSavedSearch.monitor_enabled.is_(True),RadarSavedSearch.next_monitor_at<=now,
        RadarSavedSearch.retry_at<=now,RadarSavedSearch.lease_until<=now)).all()
    for saved in rows:
        if linked_jobs(db,saved): continue
        from .main import _monitor_seconds
        key=str(uuid5(NAMESPACE_URL,f'scoutliq-monitor:{saved.id}:{saved.next_monitor_at}:{saved.version}'))
        try:
            job=create_saved_job(db,saved,db.get(User,saved.user_id),key,provider,now,monitor=True)
        except HTTPException as exc:
            if exc.status_code!=409: raise
            saved.retry_at=now+60
            continue
        except ValueError:
            saved.worker_error='Consulta histórica inválida. Revise a busca salva.'
            saved.next_monitor_at=now+_monitor_seconds(saved.monitor_interval)
            continue
        saved.next_monitor_at=now+_monitor_seconds(saved.monitor_interval)
        saved.worker_error='';saved.retry_at=0
    db.flush()


def sync_results(db,now):
    from .smart_search import state
    from .main import lead_row, _monitor_seconds
    from .monitor_matching import matches
    db.flush()
    rows=db.scalars(select(SmartSearch).where(SmartSearch.status.in_(['completed','partial','cancelled']),
        SmartSearch.state_json.contains('"saved_search_id"'))).all()
    for job in rows:
        info=state(job)
        if info.get('saved_synced'): continue
        saved=db.get(RadarSavedSearch,info['saved_search_id'])
        user=db.get(User,job.user_id)
        allowed=(saved and user and user.is_active and saved.user_id==job.user_id and
                 fingerprint(saved)==info['saved_query_hash'] and job.status!='cancelled' and
                 (not info.get('saved_monitor') or saved.monitor_enabled))
        if allowed:
            raw=json.loads(saved.query_json)
            ids=[]
            for entry in info.get('candidates',[]):
                lead=db.get(Lead,entry['id'])
                if lead and lead.user_id==job.user_id and matches(lead_row(lead),raw): ids.append(lead.id)
            # A failed collection must not erase the last successful snapshot.
            if info.get('calls',0):
                saved.last_new_count=len(set(ids)-set(json.loads(saved.result_ids_json)))
                saved.result_ids_json=json.dumps(ids)
                saved.last_run_at=saved.updated_at=now
            saved.worker_error=job.error or ''
            if info.get('saved_monitor'):
                saved.last_monitor_at=now
                saved.next_monitor_at=now+_monitor_seconds(saved.monitor_interval)
                saved.attempts=saved.retry_at=0
        info['saved_synced']=True;job.state_json=json.dumps(info)
