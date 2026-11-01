"""Daily projection of canonical queues; no new score, executor or consent."""
import json
import time
from sqlalchemy import select, func, case, or_, and_
from .models import Lead, ResearchBatch, ResearchBatchItem, SmartSearch
from .commercial_review_models import CommercialReview as Review, CommercialOperation
from .prospecting_models import PlanIncorporation, PlanDecision, ProspectingPlan
from .autonomy_models import RoutineRun
from . import prospecting


def investigated(user_id):
    return select(ResearchBatchItem.id).join(ResearchBatch).where(
        ResearchBatch.user_id == user_id, ResearchBatchItem.lead_id == Lead.id,
        ResearchBatchItem.status == 'done').exists()


def ready(user_id):
    return and_(Review.state == 'unreviewed', Review.classification == 'priority', investigated(user_id),
        Lead.contact_blocked.is_(False), ~Lead.stage.in_(['won','lost']),
        ~Review.followup_category.in_(['blocked','execution','closed','paused','completed','awaiting']))


def attention_rank(user_id):
    """Operational precedence only; the cached Score remains the sole score."""
    stale = and_(Review.decided_at.is_not(None), Review.context_hash != Review.review_hash)
    return case(
        (Review.followup_rank == 0, 1),
        (or_(Review.followup_category.in_(['blocked', 'execution']), Review.classification == 'unavailable'), 5),
        (ready(user_id), 2),
        (stale, 3),
        (Review.followup_category.in_(['today', 'overdue', 'review']), 2),
        (and_(Review.state == 'unreviewed', Review.classification.in_(['pending', 'promising', 'priority'])), 4),
        else_=6)


def attention_scope(user_id):
    return [~Review.followup_category.in_(['closed', 'paused', 'completed', 'awaiting']),
        or_(~Review.state.in_(['deferred', 'not_priority']), Review.context_hash != Review.review_hash,
            Review.followup_rank == 0, Review.followup_category == 'blocked'), attention_rank(user_id) <= 5]


def day_scope(user, now):
    _, start, end = prospecting.bounds(user.timezone, now)
    return [Lead.created_at >= start, Lead.created_at < min(end, now + 1)]


def plan_leads(user, now):
    return select(PlanIncorporation.lead_id).join(PlanDecision).join(ProspectingPlan).where(
        ProspectingPlan.user_id == user.id, PlanIncorporation.discarded.is_(False),
        PlanIncorporation.at >= prospecting.bounds(user.timezone, now)[1], PlanIncorporation.at <= now)


def focus_filter(user, focus):
    rank = attention_rank(user.id)
    return {'response': rank == 1, 'ready': ready(user.id), 'stale': rank == 3,
            'pending': rank == 4, 'blocked': rank == 5}.get(focus)


def row_reason(review, is_ready):
    follow = json.loads(review.followup_json or '{}')
    if review.followup_rank == 0:
        return {'kind':'response', 'label':'Resposta exige revisão', 'reason':follow.get('reason','Revisar resposta associada.')}
    if review.followup_category in ('blocked','execution') or review.classification == 'unavailable':
        return {'kind':'blocked', 'label':'Bloqueio operacional', 'reason':follow.get('reason','Investigar a indisponibilidade registrada.')}
    if is_ready:
        return {'kind':'ready', 'label':'Oportunidade para revisão', 'reason':'Avaliação canônica prioritária; a decisão comercial permanece humana.'}
    if review.decided_at and review.context_hash != review.review_hash:
        return {'kind':'stale', 'label':'Decisão com contexto alterado', 'reason':'Revisar novos dados preservando a decisão e o motivo anteriores.'}
    if review.followup_category in ('today','overdue','review'):
        return {'kind':'action', 'label':follow.get('title','Ação humana pendente'), 'reason':follow.get('reason','Revisar a próxima ação registrada.')}
    return {'kind':'pending', 'label':'Dados ou investigação pendentes', 'reason':follow.get('reason','Completar as evidências disponíveis.')}


def snapshot(db, user, now=None):
    now = int(time.time()) if now is None else now
    day, start, end = prospecting.bounds(user.timezone, now)
    plan = prospecting.owned(db, user)
    base = [Lead.user_id == user.id, Lead.demo.is_(False), *day_scope(user, now)]
    discarded = select(PlanIncorporation.lead_id).where(PlanIncorporation.discarded.is_(True))
    valid = [*base, ~Lead.id.in_(discarded)]
    count = lambda *filters: db.scalar(select(func.count()).select_from(Lead).where(*filters)) or 0
    total = count(*valid)
    credited = count(*valid, Lead.id.in_(plan_leads(user, now)))
    active_item = select(ResearchBatchItem.id).join(ResearchBatch).where(
        ResearchBatch.user_id == user.id, ResearchBatchItem.lead_id == Lead.id,
        ResearchBatch.status.in_(['pending','running','paused']), ResearchBatchItem.status.in_(['pending','running'])).exists()
    index_current = and_(Review.user_id == user.id, Review.dirty == 0, Review.refresh_at > now)
    counts = db.execute(select(
        func.sum(case((and_(index_current, Review.classification == 'priority'),1),else_=0)),
        func.sum(case((and_(index_current, ready(user.id)),1),else_=0)),
        func.sum(case((and_(index_current, ready(user.id), Lead.id.in_(plan_leads(user,now))),1),else_=0)),
        func.sum(case((and_(index_current, Review.classification.in_(['pending','promising','unavailable'])),1),else_=0)),
        func.sum(case((index_current,0),else_=1))
    ).select_from(Lead).outerjoin(Review,Review.lead_id==Lead.id).where(*valid)).one()
    jobs = db.scalars(select(SmartSearch).where(SmartSearch.user_id==user.id,or_(
        and_(SmartSearch.created_at>=start,SmartSearch.created_at<=now),
        SmartSearch.status.in_(['pending','running','investigating','paused'])))
        .order_by(SmartSearch.updated_at.desc(),SmartSearch.id).limit(21)).all()
    jobs_shown = jobs[:20]
    runs = {r.search_id:r for r in db.scalars(select(RoutineRun).where(RoutineRun.user_id==user.id,
        RoutineRun.search_id.in_([j.id for j in jobs_shown])))} if jobs_shown else {}
    searches=[]
    for job in jobs_shown:
        info=json.loads(job.state_json or '{}'); run=runs.get(job.id)
        searches.append({'id':job.id,'status':job.status,'created_at':job.created_at,
            'new':info.get('created',0),'reencounters':info.get('existing',0),
            'reason':job.error or info.get('reason',''),'batch_id':job.batch_id,
            'run_id':run.id if run else None,'plan':bool(info.get('prospecting_plan_id'))})
    decisions=db.scalars(select(PlanDecision).where(PlanDecision.plan_id==plan.id,
        PlanDecision.at>=start,PlanDecision.at<=now).order_by(PlanDecision.at.desc(),PlanDecision.id).limit(5)).all() if plan else []
    operations=db.scalars(select(CommercialOperation).where(CommercialOperation.user_id==user.id,
        CommercialOperation.created_at>=start,CommercialOperation.created_at<=now)
        .order_by(CommercialOperation.created_at.desc(),CommercialOperation.id).limit(6)).all()
    return {'day':day,'timezone':user.timezone,'cohort':'Empresas incorporadas hoje; estados atuais, não conversões.',
        'incorporated':total,'plan_incorporated':credited,'other_incorporated':total-credited,
        'discarded':count(*base,Lead.id.in_(discarded)), 'investigating':count(*valid,active_item),
        'investigated':count(*valid,investigated(user.id)),
        'qualified':counts[0] or 0,'ready':counts[1] or 0,'plan_ready':counts[2] or 0,
        'needs_data':counts[3] or 0,'index_pending':counts[4] or 0,
        'plan':{'state':plan.state,'target':prospecting.config(plan).daily_target,'reason':plan.reason,
                'version':plan.version,'operations':prospecting.progress(db,plan,now)['operations']} if plan else None,
        'searches':searches,'searches_truncated':len(jobs)>20,
        'decisions':[{'action':d.action,'reason':d.reason,'at':d.at} for d in decisions],
        'operations':[{'id':o.id,'action':o.action,'status':o.status,
            'failures':[{'status':r.get('status'),'reason':r.get('reason','Revisar resultado individual.')} for r in json.loads(o.result_json or '[]') if r.get('status') not in ('success',)]} for o in operations[:5]],
        'operations_truncated':len(operations)>5}
