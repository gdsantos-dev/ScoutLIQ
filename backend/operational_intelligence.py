"""Read-only aggregates of canonical operational records; never a second score.

Counts are observations, not a sequential conversion funnel. See the versioned
metric contract for populations, exclusions and historical coverage.
"""
import json
import time
from bisect import bisect_right
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import median
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from .db import engine
from .models import Lead, User, SmartSearch, ResearchBatch, ResearchBatchItem, LeadActivity
from .absorption_models import AbsorptionBatch, AbsorptionItem
from .autonomy_models import WorkAttempt, ProviderOperation
from .commercial_review_models import CommercialReview
from .opportunity_models import OutreachDraft
from .communication_models import ChannelAccount, OutboxMessage, MessageEvent, ReceivedMessage
from .consumption import HTTP_BUDGET, PROVIDER_LIMITS
from .security import current_user, limiter

router = APIRouter(prefix='/api/insights')
MAX_ROWS = 100_000
PERIODS = {'7': 7, '30': 30, '90': 90, 'history': None}


def decoded(raw, fallback=None):
    fallback = {} if fallback is None else fallback
    try:
        value = json.loads(raw or '')
        return value if isinstance(value, type(fallback)) else fallback
    except (ValueError, TypeError):
        return fallback


def window(period, timezone, now):
    local = datetime.fromtimestamp(now, ZoneInfo(timezone))
    days = PERIODS[period]
    start = int((local.replace(hour=0, minute=0, second=0, microsecond=0)
                 - timedelta(days=days-1)).timestamp()) if days else 0
    return start, now, local.date().isoformat()


def rows(db, query):
    # Every relation has a hard ceiling. Never publish a silently truncated rate.
    result = db.execute(query.limit(MAX_ROWS + 1)).mappings().all()
    if len(result) > MAX_ROWS:
        raise HTTPException(422, 'Volume acima do limite seguro deste relatório; nenhuma contagem parcial foi publicada.')
    return result


def columns(model, names):
    return [getattr(model, name) for name in names.split()]


def ratio(key, label, numerator, denominator, population):
    assert 0 <= numerator <= denominator
    return dict(key=key, label=label, numerator=numerator, denominator=denominator,
                value=round(numerator/denominator*100, 2) if denominator else None,
                population=population, status='observed' if denominator else 'unavailable')


def duration(key, label, values, population):
    values = [value for value in values if value is not None and value >= 0]
    return dict(key=key, label=label, samples=len(values), seconds=round(median(values), 2) if values else None,
                population=population, status='observed' if values else 'unavailable')


def report(db, user, period='30', origin='all', now=None):
    now = int(time.time()) if now is None else now
    start, end, today = window(period, user.timezone, now)
    within = lambda stamp: type(stamp) is int and start <= stamp <= end
    owned = [Lead.user_id == user.id, Lead.demo.is_(False), Lead.created_at <= now]
    leads = {r['id']: r for r in rows(db, select(*columns(Lead,
        'id source source_id category city country created_at stage in_pipeline pipeline_added_at '
        'next_action next_action_on outcome_recorded_at outcome_snapshot_json contact whatsapp contact_blocked')).where(*owned))}
    searches = rows(db, select(*columns(SmartSearch, 'id intent_json state_json status created_at updated_at'))
                    .where(SmartSearch.user_id == user.id, SmartSearch.created_at <= now))
    absorption = rows(db, select(*columns(AbsorptionItem, 'id lead_id status issues_json payload_json matches_json'),
        AbsorptionBatch.created_at).join(AbsorptionBatch).where(AbsorptionItem.user_id == user.id,
        AbsorptionBatch.user_id == user.id, AbsorptionBatch.created_at <= now))
    # A Lead may belong to several origins; the all view counts it only once.
    sources = defaultdict(set)
    strategies = defaultdict(set)
    search_entries = []
    for search in searches:
        state, intent = decoded(search['state_json']), decoded(search['intent_json'])
        strategy = 'Busca geral' if intent.get('search_mode') == 'general' else 'Busca direcionada'
        if intent.get('search_mode') not in ('general', 'filtered', 'legacy'):
            strategy = 'Busca sem modo registrado'
        for entry in state.get('candidates', []) + state.get('duplicate_records', []):
            identifier = entry.get('id') if isinstance(entry, dict) else None
            if identifier in leads:
                sources[identifier].add('search'); strategies[identifier].add(strategy)
                if within(search['created_at']):
                    search_entries.append((identifier, entry, search['id']))
    for item in absorption:
        if item['lead_id'] in leads:
            sources[item['lead_id']].add('absorption'); strategies[item['lead_id']].add('Absorção externa')
    # Executions whose only linked candidates are excluded (demo, foreign or
    # deleted) cannot contribute to real-company metrics or provider averages.
    searches = [s for s in searches if not decoded(s['state_json']).get('candidates') or
                any(isinstance(e,dict) and e.get('id') in leads for e in decoded(s['state_json']).get('candidates',[]))]
    for identifier, lead in leads.items():
        if (lead['source_id'] or '').startswith('absorption:'):
            sources[identifier].add('absorption'); strategies[identifier].add('Absorção externa')
        elif lead['source'] == 'manual':
            sources[identifier].add('manual'); strategies[identifier].add('Entrada manual')
        elif lead['source'] in ('geoapify', 'openstreetmap', 'osm', 'brave'):
            sources[identifier].add('search')
        if not sources[identifier]: sources[identifier].add('unknown')
    selected = {i for i in leads if origin == 'all' or origin in sources[i]}
    # Queries below are bounded projections; no message bodies, credentials or N+1.
    def linked(model, names):
        return select(*columns(model, names)).join(Lead, Lead.id == model.lead_id).where(
            *owned, model.user_id == user.id)
    reviews = {r['lead_id']: r for r in rows(db, linked(CommercialReview,
        'lead_id state decided_at classification dirty refresh_at followup_dirty followup_refresh_at followup_category')) if r['lead_id'] in selected}
    drafts = [r for r in rows(db, linked(OutreachDraft, 'id lead_id status created_at approved_at')) if r['lead_id'] in selected]
    activities = [dict(r, meta=decoded(r['metadata_json'])) for r in rows(db, linked(LeadActivity,
        'id lead_id kind created_at metadata_json').where(LeadActivity.created_at <= now)) if r['lead_id'] in selected]
    items = {r['id']: r for r in rows(db, select(*columns(ResearchBatchItem,
        'id lead_id status phase outcome error started_at finished_at'), ResearchBatch.created_at.label('queued_at'),
        ResearchBatch.mode, ResearchBatch.status.label('batch_status')).join(ResearchBatch).join(Lead, Lead.id == ResearchBatchItem.lead_id)
        .where(*owned, ResearchBatch.user_id == user.id)) if r['lead_id'] in selected}
    boxes = {r['id']: r for r in rows(db, linked(OutboxMessage,
        'id lead_id account_id thread_id status provider_id created_at wire_started_at')
        .join(ChannelAccount, ChannelAccount.id == OutboxMessage.account_id).where(ChannelAccount.user_id == user.id)) if r['lead_id'] in selected}
    events = rows(db, select(*columns(MessageEvent, 'outbox_id event created_at')).join(OutboxMessage)
        .join(Lead, Lead.id == OutboxMessage.lead_id).join(ChannelAccount, ChannelAccount.id == OutboxMessage.account_id)
        .where(*owned, MessageEvent.user_id == user.id, OutboxMessage.user_id == user.id, ChannelAccount.user_id == user.id,
               MessageEvent.created_at <= now))
    received = rows(db, select(*columns(ReceivedMessage,
        'id lead_id account_id thread_id classification association sent_at received_at'))
        .join(ChannelAccount, ChannelAccount.id == ReceivedMessage.account_id)
        .outerjoin(Lead, Lead.id == ReceivedMessage.lead_id).where(ReceivedMessage.user_id == user.id,
            ChannelAccount.user_id == user.id, or_(ReceivedMessage.lead_id.is_(None), and_(*owned))))
    attempts = rows(db, select(*columns(WorkAttempt, 'token kind item_id started_at finished_at status'))
        .where(WorkAttempt.user_id == user.id, WorkAttempt.started_at <= now))
    operations = rows(db, select(*columns(ProviderOperation, 'token provider status started_at'))
        .join(WorkAttempt).where(WorkAttempt.user_id == user.id, ProviderOperation.started_at <= now))

    metrics = []
    def metric(key, label, value, unit='empresas', population='Eventos no período', status='observed'):
        metrics.append(dict(key=key, label=label, value=value, unit=unit, population=population, status=status))
    stock = 'Estado atual das empresas da origem selecionada; não limitado pela data de entrada'
    search_entries = [r for r in search_entries if r[0] in selected] if origin in ('all', 'search') else []
    absorb_period = [r for r in absorption if within(r['created_at']) and (r['lead_id'] is None or r['lead_id'] in selected)] if origin in ('all', 'absorption') else []
    manual = {i for i in selected if 'manual' in sources[i] and within(leads[i]['created_at'])} if origin in ('all', 'manual') else set()
    found = {r[0] for r in search_entries} | {r['lead_id'] for r in absorb_period if r['lead_id'] in selected} | manual
    duplicate_records = sum(e.get('origin') == 'duplicate' for _, e, _ in search_entries) + sum(r['status'] == 'duplicate' for r in absorb_period)
    occurrences = len(search_entries) + len(absorb_period) + len(manual)
    eligible = sum(r['status'] in ('ready', 'imported') for r in absorb_period)
    metric('discovered', 'Registros encontrados ou recebidos', occurrences, 'registros', 'Candidatos rastreáveis das buscas + itens de absorção + entradas manuais; cobertura parcial', 'partial')
    metric('unique', 'Empresas identificadas no Radar', len(found), population='IDs canônicos distintos nos registros observados; registros ainda sem vínculo não são empresas deduplicadas', status='partial')
    metric('unlinked', 'Registros recebidos sem vínculo canônico', sum(r['lead_id'] is None for r in absorb_period), 'registros')
    metric('duplicates', 'Duplicatas explicitamente registradas', duplicate_records, 'registros')
    metric('incomplete', 'Absorções pendentes de dados ou revisão', sum(r['status'] == 'pending' for r in absorb_period), 'registros', 'Estado atual dos itens recebidos no período')
    metric('eligible', 'Registros elegíveis para absorção', eligible, 'registros', 'Itens ready ou imported; elegibilidade histórica de buscas/manuais não registrada', 'partial')
    metric('incorporated', 'Empresas incorporadas ao Radar', sum(within(leads[i]['created_at']) for i in selected), population='Lead.created_at; reencontros não são novas incorporações')
    rates = [ratio('eligibility', 'Elegibilidade na absorção', eligible, len(absorb_period), 'Itens recebidos na absorção no período; classificação atual'),
             ratio('duplication', 'Duplicação explícita', duplicate_records, occurrences, 'Ocorrências rastreáveis; não estima duplicatas desconhecidas')]
    # Retried phases share one item. The earliest attempt is the reliable start,
    # since ResearchBatchItem.started_at is overwritten at every claim.
    by_item = defaultdict(list)
    relevant_attempts = {}
    search_ids = {s['id'] for s in searches} if origin in ('all', 'search') else set()
    for a in attempts:
        if a['kind'] == 'batch' and a['item_id'] in items:
            by_item[a['item_id']].append(a)
            relevant_attempts[a['token']] = a
        elif a['kind'] == 'smart' and a['item_id'] in search_ids:
            relevant_attempts[a['token']] = a
    began = {i: min(a['started_at'] for a in by_item[i]) if by_item[i] else item['started_at'] for i, item in items.items()}
    started = {i for i in items if within(began[i])}
    completed = {i for i, item in items.items() if item['status'] == 'done' and within(item['finished_at'])}
    completed_cohort = {i for i in started if items[i]['status'] == 'done' and items[i]['finished_at'] is not None and items[i]['finished_at'] <= now}
    metric('investigations_started', 'Investigações iniciadas', len(started), 'investigações', 'Primeira tentativa do item no período; retomadas não multiplicam o início')
    metric('companies_investigated', 'Empresas investigadas', len({items[i]['lead_id'] for i in started}))
    metric('investigations_completed', 'Investigações concluídas', len(completed), 'investigações', 'Itens done com término no período; não implica qualidade comercial')
    metric('investigation_failures', 'Investigações com falha terminal', sum(r['status'] == 'error' and within(r['finished_at']) for r in items.values()), 'investigações')
    metric('investigation_cancelled', 'Investigações canceladas', sum(r['status'] == 'cancelled' and within(r['finished_at']) for r in items.values()), 'investigações')
    metric('expired_attempts', 'Tentativas interrompidas ou expiradas', sum(a['status'] == 'expired' and within(a['started_at']) for a in relevant_attempts.values()), 'tentativas')
    metric('investigation_queue', 'Investigações aguardando execução', sum(r['status'] == 'pending' and r['batch_status'] in ('pending','running','paused') for r in items.values()), 'investigações', stock)
    metric('deepening', 'Itens que alcançaram fase aprofundada', sum(r['phase'] == 'deep' for i, r in items.items() if i in started), 'investigações', 'Coorte de inícios; fase alcançada não comprova auditoria concluída')
    rates.append(ratio('completion', 'Conclusão dos inícios observados', len(completed_cohort), len(started), 'Itens iniciados no período e concluídos até a consulta'))
    fresh = {i:r for i, r in reviews.items() if not r['dirty'] and r['refresh_at'] > now}
    metric('opportunities', 'Oportunidades prioritárias no Score 3.0', sum(r['classification'] == 'priority' for r in fresh.values()), population=stock+'; somente projeções canônicas vigentes', status='partial' if len(fresh) < len(selected) else 'observed')
    metric('qualification_coverage', 'Empresas com classificação vigente', len(fresh), population=stock)
    metric('insufficient_evidence', 'Classificações pendentes de evidências', sum(r['classification'] == 'pending' for r in fresh.values()), population=stock+'; somente projeções vigentes', status='partial')
    reviewed = {i:r for i, r in reviews.items() if r['state'] != 'unreviewed' and within(r['decided_at'])}
    metric('reviewed', 'Empresas com decisão humana', len(reviewed), population='Última decisão registrada no período; reaberturas não são decisões atuais')
    metric('selected', 'Selecionadas para possível abordagem', sum(r['state'] == 'selected' for r in reviewed.values()), population='Última decisão humana no período')
    metric('deferred', 'Adiadas', sum(r['state'] == 'deferred' for r in reviewed.values()), population='Última decisão humana no período')
    metric('not_priority', 'Não prioritárias pelo operador', sum(r['state'] == 'not_priority' for r in reviewed.values()), population='Última decisão humana no período')
    metric('review_pending', 'Empresas sem decisão humana atual', sum(i not in reviews or reviews[i]['state'] == 'unreviewed' for i in selected), population=stock)
    rates.append(ratio('selection', 'Seleção entre decisões humanas', sum(r['state'] == 'selected' for r in reviewed.values()), len(reviewed), 'Empresas com última decisão humana no período; inclui adiadas e não prioritárias'))
    metric('drafts', 'Rascunhos preparados', sum(within(d['created_at']) for d in drafts), 'rascunhos', 'Criação do rascunho; não comprova contato')
    metric('drafts_unreviewed', 'Rascunhos sem aprovação', sum(d['status'] == 'draft' for d in drafts), 'rascunhos', stock)
    metric('drafts_approved', 'Rascunhos aprovados no período', sum(within(d['approved_at']) for d in drafts), 'rascunhos', 'Aprovação não autoriza nem comprova envio')
    active = [leads[i] for i in selected if leads[i]['in_pipeline'] and leads[i]['stage'] not in ('won','lost')]
    metric('followup_pending', 'Empresas com próxima ação definida', sum(bool(l['next_action']) for l in active), population=stock)
    metric('overdue', 'Próximas ações vencidas', sum(bool(l['next_action']) and bool(l['next_action_on']) and l['next_action_on'] < today for l in active), population=stock+'; dia local da conta')
    metric('tasks_completed', 'Conclusões de tarefa registradas', sum(a['meta'].get('action') == 'followup_complete' and within(a['created_at']) for a in activities), 'eventos', 'Atividades canônicas de conclusão explícita')
    # Provider acceptance needs account ownership, an accepted outbox, provider ID
    # and the canonical receipt. Activity mirrors are excluded from manual events.
    receipts = defaultdict(list)
    for e in events:
        if e['outbox_id'] in boxes: receipts[e['outbox_id']].append(e)
    accepted = {}
    for i, box in boxes.items():
        stamps = [e['created_at'] for e in receipts[i] if e['event'] == 'accepted']
        if box['status'] == 'accepted' and box['provider_id'] and stamps:
            accepted[i] = dict(box, at=min(stamps))
    contacts = [dict(id=i, lead_id=b['lead_id'], at=b['at'], provenance='provider_accepted') for i,b in accepted.items()]
    manual_acts = []
    for a in activities:
        meta = a['meta']; at = meta.get('occurred_at', a['created_at'])
        if meta.get('event') in (None, 'manual_activity') and type(at) is int and 0 < at <= now:
            manual_acts.append(dict(a, at=at))
            if a['kind'] in ('email','whatsapp','call') and meta.get('result') not in ('not_reached','delivery_failure'):
                contacts.append(dict(id=a['id'], lead_id=a['lead_id'], at=at, provenance='operator_declared'))
    period_contacts = [c for c in contacts if within(c['at'])]
    metric('contacts', 'Contatos registrados', len(period_contacts), 'eventos', 'Aceitações técnicas + declarações manuais; espelhos da Outbox excluídos')
    for key, provenance, label in [('contacts_declared','operator_declared','Contatos declarados pelo operador'), ('contacts_accepted','provider_accepted','Execuções aceitas pelo provedor')]:
        metric(key, label, sum(c['provenance'] == provenance for c in period_contacts), 'eventos', 'Ocorrência no período; aceitação não comprova entrega ou leitura')
    for kind, label in [('delivered','Entregas confirmadas'), ('read','Leituras confirmadas')]:
        metric(kind, label, sum(any(e['event'] == kind and within(e['created_at']) and e['created_at'] >= b['at'] for e in receipts[i]) for i,b in accepted.items()), 'mensagens', 'Somente recibo explícito, sem inferência a partir de aceitação')
    threads = defaultdict(list)
    for b in accepted.values():
        if b['thread_id']: threads[(b['lead_id'],b['account_id'],b['thread_id'])].append(b['at'])
    first_acceptance = {key:min(stamps) for key,stamps in threads.items()}
    first_period_acceptance = {key:min(stamps) for key,values in threads.items() if (stamps:=[at for at in values if within(at)])}
    traced = []
    for r in received:
        if r['lead_id'] not in selected or r['association'] != 'matched' or not r['thread_id'] or not within(r['sent_at']): continue
        if first_acceptance.get((r['lead_id'],r['account_id'],r['thread_id']),float('inf')) <= r['sent_at']: traced.append(r)
    manual_replies = [a for a in manual_acts if a['kind'] == 'reply' and within(a['at'])]
    human_classes = ('interest','information_request','objection','refusal','opt_out')
    human_replies = [r for r in traced if r['classification'] in human_classes]
    metric('replies', 'Respostas comerciais conhecidas', len(human_replies)+len(manual_replies), 'eventos', 'Mensagens associadas com classificação comercial + respostas declaradas; categorias automáticas/insuficientes separadas')
    metric('replies_provider', 'Respostas comerciais associadas', len(human_replies), 'mensagens')
    metric('replies_declared', 'Respostas declaradas pelo operador', len(manual_replies), 'eventos')
    metric('replies_uncertain', 'Mensagens sem associação ou classificação comercial', sum(within(r['sent_at']) and ((r['lead_id'] is None and origin=='all') or r['lead_id'] in selected) for r in received) - len(human_replies), 'mensagens', 'Inclui automáticas, insuficientes, falhas e associações não comprovadas. Sem vínculo aparece somente em todas as origens; não equivale a recusa')
    metric('information_requests', 'Pedidos de informação associados', sum(r['classification'] == 'information_request' for r in human_replies), 'mensagens')
    eligible_threads = {(b['lead_id'],b['account_id'],b['thread_id']) for b in accepted.values() if b['thread_id'] and within(b['at'])}
    replied_threads = {(r['lead_id'],r['account_id'],r['thread_id']) for r in human_replies
        if first_period_acceptance.get((r['lead_id'],r['account_id'],r['thread_id']),float('inf')) <= r['sent_at']} & eligible_threads
    rates.append(ratio('response', 'Conversas com resposta comercial conhecida', len(replied_threads), len(eligible_threads), 'Conversas com aceitação técnica no período; resposta posterior à aceitação e até a consulta. Entrega e representatividade desconhecidas; contatos manuais excluídos'))
    for kind, label in [('meeting','Reuniões declaradas'),('proposal','Propostas declaradas')]:
        metric(kind, label, sum(a['kind'] == kind and within(a['at']) for a in manual_acts), 'eventos')
    for stage, label in [('won','Ganhos registrados'),('lost','Perdas registradas')]:
        metric(stage, label, sum(leads[i]['stage'] == stage and within(leads[i]['outcome_recorded_at']) for i in selected), population='Estágio atual com data explícita do desfecho no período; declaração operacional')
    metric('negotiating', 'Negociações em andamento', sum(leads[i]['in_pipeline'] and leads[i]['stage'] == 'negotiating' for i in selected), population=stock)
    metric('outcomes_undated', 'Desfechos sem data confiável', sum(leads[i]['stage'] in ('won','lost') and not leads[i]['outcome_recorded_at'] for i in selected), population=stock)
    from .opportunity_workflow import recipient_identity
    invalid_contacts = 0
    for i in selected:
        valid = False
        for channel, raw in [('email',leads[i]['contact']),('whatsapp',leads[i]['whatsapp'])]:
            if raw:
                try: recipient_identity(channel,raw); valid = True
                except HTTPException: pass
        invalid_contacts += not valid
    metric('invalid_recipient', 'Empresas sem destinatário válido para rascunho', invalid_contacts, population=stock+'; formato de e-mail/WhatsApp, não autorização de contato')
    metric('contact_blocked','Empresas com bloqueio de contato',sum(leads[i]['contact_blocked'] for i in selected),population=stock)

    # Durations are calendar time. An expired attempt is not a measured busy interval.
    waits = [began[i]-r['queued_at'] for i,r in items.items() if i in started and began[i] >= r['queued_at']]
    processing = [a['finished_at']-a['started_at'] for a in relevant_attempts.values() if within(a['started_at']) and a['finished_at'] and a['finished_at'] <= now and a['status'] in ('committed','failed')]
    search_times = [s['updated_at']-s['created_at'] for s in searches if within(s['created_at']) and s['status'] in ('completed','partial') and s['updated_at'] <= now] if origin in ('all','search') else []
    review_stamps = defaultdict(list)
    for a in activities:
        if a['kind'] == 'commercial_triage' and a['meta'].get('action') in ('reviewed','selected','deferred','not_priority'):
            review_stamps[a['lead_id']].append(a['created_at'])
    for stamps in review_stamps.values(): stamps.sort()
    def previous(stamps, at):
        index = bisect_right(stamps,at)
        return stamps[index-1] if index else None
    review_draft = []
    for d in drafts:
        stamp = previous(review_stamps[d['lead_id']], d['created_at'])
        if within(d['created_at']) and stamp is not None: review_draft.append(d['created_at']-stamp)
    contact_stamps = defaultdict(list)
    for c in contacts: contact_stamps[c['lead_id']].append(c['at'])
    for stamps in contact_stamps.values(): stamps.sort()
    next_times = []
    for a in activities:
        stamp = previous(contact_stamps[a['lead_id']], a['created_at'])
        if a['meta'].get('action') == 'followup_set' and within(a['created_at']) and stamp is not None:
            next_times.append(a['created_at']-stamp)
    times = [duration('search','Duração de buscas encerradas',search_times,'Calendário, inclui esperas; criação até atualização terminal'),
             duration('queue','Espera até a primeira tentativa',waits,'Criação do lote até primeira tentativa registrada'),
             duration('processing','Duração das tentativas finalizadas',processing,'Tentativas committed/failed; inclui latência, exclui expiradas/em aberto'),
             duration('available_review','Tempo até disponibilidade para revisão',[],'Não há evento canônico de disponibilização; não equiparado ao fim técnico'),
             duration('review_draft','Decisão humana até rascunho',review_draft,'Última atividade de decisão anterior à criação do rascunho'),
             duration('contact_action','Contato até definição de próxima ação',next_times,'Contato anterior e atividade followup_set; não mede execução da tarefa'),
             duration('human','Tempo de trabalho humano',[],'Não instrumentado; não há estimativa de economia')]
    used_ops = [o for o in operations if o['token'] in relevant_attempts and within(o['started_at'])]
    provider_counts = Counter(o['provider'] for o in used_ops)
    failed_counts = Counter(o['provider'] for o in used_ops if o['status'] == 'failed')
    day = now//86400*86400
    daily = Counter(o['provider'] for o in operations if o['started_at'] >= day)
    # Budgets are deployment-wide. User-specific consumption is not global balance.
    providers = [dict(provider=p, operations=provider_counts[p], failed=failed_counts[p],
        reserved=sum(o['provider']==p and o['status']=='reserved' for o in used_ops),
        own_today=daily[p], configured_daily_limit=PROVIDER_LIMITS.get(p)) for p in sorted(set(provider_counts)|set(PROVIDER_LIMITS))]
    searches_period = {s['id'] for s in searches if within(s['created_at'])} & search_ids
    search_ops = [o for o in used_ops if relevant_attempts[o['token']]['kind']=='smart' and relevant_attempts[o['token']]['item_id'] in searches_period]
    investigation_ops = [o for o in used_ops if relevant_attempts[o['token']]['kind']=='batch' and relevant_attempts[o['token']]['item_id'] in started]
    metric('provider_operations', 'Operações de provedor registradas', len(used_ops), 'operações', 'Ledger do worker, escopo de busca/investigação; rotas legadas não instrumentadas', 'partial')
    metric('provider_failures', 'Operações com falha', sum(o['status']=='failed' for o in used_ops), 'operações')
    limit_searches = sum(bool(decoded(s['state_json']).get('source_limited')) for s in searches if s['id'] in search_ids and within(s['created_at']))
    metric('source_limits','Buscas com cobertura limitada pela fonte',limit_searches,'execuções','Flag source_limited canônica; não atribui a limite financeiro')
    limit_config = sum(r['status']=='error' and within(r['finished_at']) and r['error']=='Limite ou configuração indisponível; resultados anteriores preservados.' for r in items.values())
    metric('limit_or_configuration','Investigações interrompidas por limite ou configuração',limit_config,'investigações','Motivo canônico não distingue orçamento de configuração; causa exata desconhecida')
    metric('cache_avoided', 'Requisições evitadas por cache', None, 'requisições', 'Reuso não registra quantas chamadas teriam ocorrido', 'unavailable')
    reused = sum(s['status'] in ('completed','partial') and within(s['created_at']) and isinstance(decoded(s['state_json']).get('skipped_recent'),int) and decoded(s['state_json'])['skipped_recent'] for s in searches) if origin in ('all','search') else 0
    metric('reuse', 'Investigações dispensadas por pesquisa recente', reused, 'registros', 'Contador skipped_recent de buscas encerradas; não equivale a chamadas evitadas', 'partial')
    metric('monetary_cost', 'Custo monetário', None, 'moeda', 'Ledger não possui tarifas faturáveis, moeda e cobrança verificada', 'unavailable')
    no_result = [s for s in searches if s['id'] in searches_period and s['status'] in ('completed','partial') and not decoded(s['state_json']).get('candidates')]
    metric('empty_searches', 'Buscas encerradas sem candidatos rastreáveis', len(no_result), 'execuções', 'Não conclui ausência de empresas no mercado nem qualidade comercial')
    averages = [dict(key='per_search', label='Operações por busca iniciada', total=len(search_ops), samples=len(searches_period), value=len(search_ops)/len(searches_period) if searches_period else None),
        dict(key='per_company', label='Operações de investigação por empresa', total=len(investigation_ops), samples=len({items[i]['lead_id'] for i in started}), value=len(investigation_ops)/len({items[i]['lead_id'] for i in started}) if started else None)]
    # Descriptive cohorts overlap by design; no winner/ranking or weight adjustment.
    cohorts = []
    for dimension in ('origin','strategy','sector','location','level','period'):
        groups = defaultdict(set)
        for i in selected:
            lead = leads[i]
            if dimension == 'origin': values = sources[i]
            elif dimension == 'strategy': values = strategies[i] or {'Estratégia desconhecida'}
            elif dimension == 'sector': values = {lead['category'] or 'Desconhecido'}
            elif dimension == 'location': values = {lead['country']+'/'+lead['city']}
            elif dimension == 'level': continue
            else:
                values = {datetime.fromtimestamp(lead['created_at'],ZoneInfo(user.timezone)).strftime('%Y-%m')}
            if within(lead['created_at']):
                for value in values: groups[value].add(i)
        if dimension == 'level':
            for i in started: groups[items[i]['mode']+':'+items[i]['phase']].add(items[i]['lead_id'])
        total_groups = len(groups)
        for name, ids in sorted(groups.items(), key=lambda pair: (-len(pair[1]),pair[0]))[:30]:
            covered = ids & fresh.keys()
            cohorts.append(dict(dimension=dimension, group=name, companies=len(ids), classified=len(covered),
                opportunities=sum(fresh[i]['classification']=='priority' for i in covered), selected=sum(i in reviews and reviews[i]['state']=='selected' for i in ids),
                known_outcomes=sum(leads[i]['stage'] in ('won','lost') and bool(leads[i]['outcome_recorded_at']) for i in ids),
                small_sample=len(ids)<30, groups_available=total_groups))
    values = {m['key']:m['value'] for m in metrics}
    diagnostics = []
    def diagnose(key, count, observation, consequence, action, href, population):
        if count:
            diagnostics.append(dict(key=key, count=count, observation=observation, consequence=consequence,
                action=action, href=href, population=population, from_at=start, to_at=end))
    coordinates = sum(r['status']=='pending' and (decoded(r['payload_json']).get('latitude') is None or decoded(r['payload_json']).get('longitude') is None) for r in absorb_period)
    diagnose('coordinates',coordinates,'Registros recebidos aguardam coordenadas','Podem impedir a incorporação ao Radar.','Revisar absorção','#radar','Itens recebidos no período, estado atual')
    diagnose('duplicates',duplicate_records,'Ocorrências foram marcadas como duplicatas','Repetição pode consumir capacidade de descoberta.','Revisar fontes da Busca Unificada','#radar','Ocorrências no período')
    for key,observation,consequence,action,href in [
        ('investigation_queue','Investigações aguardam execução','A fila pode atrasar a revisão.','Revisar fila de investigação','#radar'),
        ('review_pending','Empresas estão sem decisão humana atual','O avanço comercial depende da triagem.','Abrir fila comercial','#radar'),
        ('drafts_unreviewed','Rascunhos estão sem aprovação','A abordagem ainda exige revisão humana.','Revisar rascunhos','#radar'),
        ('invalid_recipient','Empresas não têm e-mail ou WhatsApp com formato válido','A preparação de rascunhos pode ficar bloqueada.','Revisar contatos no Radar','#radar'),
        ('overdue','Próximas ações estão vencidas','O acompanhamento pode estar atrasado.','Abrir acompanhamento comercial','#pipeline'),
        ('outcomes_undated','Desfechos não possuem data confiável','Comparações por período ficam incompletas.','Revisar histórico das negociações','#pipeline')]:
        diagnose(key,values[key],observation,consequence,action,href,stock)
    diagnose('source_limits',limit_searches,'Buscas registraram cobertura limitada pela fonte','A descoberta pode ter cobertura parcial.','Revisar configuração e histórico da busca','#radar','Buscas iniciadas no período')
    diagnose('limit_or_configuration',limit_config,'Investigações registraram limite ou configuração indisponível','Pode impedir novas consultas; o registro não discrimina a causa.','Revisar integrações e orçamento','#integrations','Falhas terminais no período')
    return dict(version='1.38.6-dev', generated_at=now, window=dict(period=period,origin=origin,from_at=start,to_at=end,timezone=user.timezone),
        coverage=dict(companies=len(selected), classified=len(fresh), multi_source=sum(len(sources[i])>1 for i in selected), demo_excluded=True,
            identity='Lead.id; sem fusão por nome. Itens sem vínculo ficam fora de empresas únicas.', origin_unknown=sum(sources[i]=={'unknown'} for i in selected)),
        metrics=metrics, rates=rates, times=times, providers=providers, averages=averages, diagnostics=diagnostics, cohorts=cohorts,
        history=history_summary([leads[i] for i in selected], activities, contacts, within),
        budgets=dict(configured_daily_operations=HTTP_BUDGET, scope='Limites globais do worker por dia UTC; consumo mostrado é somente desta conta. Saldo global não exposto.', monetary=None),
        limitations=[
            'As etapas não formam uma sequência obrigatória. Eventos no período e pendências atuais têm populações distintas.',
            'Empresas únicas usam o ID canônico; duplicatas não resolvidas e registros removidos não são reconstruídos.',
            'Busca antiga sem execução persistida e elegibilidade anterior à incorporação têm cobertura parcial.',
            'Classificação é lida do índice canônico vigente. A leitura não recalcula Score nem atualiza filas; índices ausentes ou vencidos são desconhecidos.',
            'Demonstrações identificadas no Lead são excluídas. Instalações de teste devem permanecer isoladas; não existe inferência de dados sintéticos por nome.',
            'Coortes mostram entradas no período e estado atual, exceto níveis de investigação (inícios). Grupos podem se sobrepor; até 30 por dimensão, por volume.',
            'Amostras de conveniência, sem inferência causal. Menos de 30 empresas é amostra pequena; nenhuma contagem comprova qualidade comercial.',
            'Avaliação de precisão, falsos positivos e ordenação continua em Casos revisados, com as regras de selection_quality.',
            'Ledger cobre o worker. Operações não são requisições HTTP faturáveis; reservas sem conclusão permanecem incertas.',
            'Durações são tempo de calendário, não esforço humano. Sem minutos economizados ou custo financeiro estimado.',
            'Respostas automáticas, falhas e mensagens ambíguas não são respostas comerciais nem recusas. Aprovação, aceitação, entrega e leitura são distintas.',
            'Leitura limitada a 100.000 linhas por relação; excesso recusa o relatório inteiro. Nenhum dado pessoal ou corpo de mensagem é retornado.'])


def history_summary(leads, activities, contacts, within):
    """Existing behavior comparison, moved server-side; missing dates stay unknown.

    Unlike the legacy browser calculation, absence of a close event never borrows
    creation/last-contact timestamps. Only canonical outcomes enter dated cohorts.
    """
    by_lead, by_contact = defaultdict(list), defaultdict(list)
    for a in activities: by_lead[a['lead_id']].append(a)
    for c in contacts: by_contact[c['lead_id']].append(c['at'])
    records, snapshots = [], []
    for l in leads:
        closed = l['outcome_recorded_at']
        if l['stage'] not in ('won','lost') or not within(closed): continue
        acts = [a for a in by_lead[l['id']] if a['created_at'] <= closed]
        outbound = sorted(t for t in by_contact[l['id']] if t <= closed)
        pipeline = l['pipeline_added_at']
        difference = lambda a,b: (b-a)/86400 if a is not None and b is not None and b>=a else None
        first = difference(pipeline,outbound[0]) if outbound else None
        loss = [a for a in acts if a['kind']=='stage_changed' and a['meta'].get('to')=='lost']
        records.append(dict(outcome=l['stage'],cycle=difference(pipeline,closed),first=first,
            interactions=len(outbound)+sum(a['kind'] in ('meeting','proposal','reply') for a in acts),
            followups=max(0,len(outbound)-1),proposal=any(a['kind']=='proposal' for a in acts),
            meeting=any(a['kind']=='meeting' for a in acts),reply=any(a['kind']=='reply' for a in acts),
            fast=first is not None and first<=1,loss=max(loss,key=lambda a:a['created_at'])['meta'].get('from','unknown') if loss else 'unknown',
            covered=bool(acts)))
        snap=decoded(l['outcome_snapshot_json'])
        if snap.get('outcome')==l['stage']: snapshots.append(snap)
    won=[r for r in records if r['outcome']=='won' and r['covered']]
    lost=[r for r in records if r['outcome']=='lost' and r['covered']]
    def med(rows,key):
        values=[r[key] for r in rows if r[key] is not None]
        return round(median(values),1) if values else None
    def behavior(rows):
        return dict(count=len(rows),medianCycleDays=med(rows,'cycle'),medianFirstContactDays=med(rows,'first'),
            medianInteractions=med(rows,'interactions'),medianFollowUps=med(rows,'followups'))
    pct=lambda n,d: round(n/d*100) if d else 0
    patterns=[]
    for key,predicate in [('proposal',lambda r:r['proposal']),('meeting',lambda r:r['meeting']),('reply',lambda r:r['reply']),
                           ('follow_up',lambda r:r['followups']>0),('fast_first_contact',lambda r:r['fast'])]:
        if len(won)>=2 and len(lost)>=2:
            w,l=sum(predicate(r) for r in won),sum(predicate(r) for r in lost)
            patterns.append(dict(key=key,wonRate=pct(w,len(won)),lostRate=pct(l,len(lost)),deltaPp=pct(w,len(won))-pct(l,len(lost)),wonMatches=w,lostMatches=l,wonSample=len(won),lostSample=len(lost)))
    stages=Counter(r['loss'] for r in lost)
    intelligence=dict(closedCount=len(records),wonCount=sum(r['outcome']=='won' for r in records),lostCount=sum(r['outcome']=='lost' for r in records),
        activityCoverage=pct(len(won)+len(lost),len(records)),ready=len(won)+len(lost)>=6 and len(won)>=2 and len(lost)>=2,
        won=behavior(won),lost=behavior(lost),patterns=sorted(patterns,key=lambda r:-abs(r['deltaPp'])),
        lossStages=[dict(stage=k,count=v,share=pct(v,len(lost))) for k,v in stages.items()],records=[])
    # Keep the existing snapshot comparison, without synthesizing missing snapshots.
    insights=[]; sw=sum(s['outcome']=='won' for s in snapshots); sl=len(snapshots)-sw
    if len(snapshots)>=6 and sw>=2 and sl>=2:
        def band(value, low, high, labels):
            return labels[2] if value>=high else labels[1] if value>=low else labels[0]
        dimensions=[('niche','Nicho',lambda s:s.get('niche_label')),
            ('website','Situação do site',lambda s:s.get('website_status')),
            ('service','Melhor fit',lambda s:s.get('best_service_label')),
            ('reviews','Volume público',lambda s:band(s['reviews'],20,100,('0–19 avaliações','20–99 avaliações','100+ avaliações')) if type(s.get('reviews')) in (int,float) else None),
            ('score','Opportunity Score',lambda s:band(s['score'],40,70,('Score <40','Score 40–69','Score 70+')) if type(s.get('score')) in (int,float) else None),
            ('timing','Timing',lambda s:band(s['timing'],25,55,('Timing baixo','Timing médio','Timing alto')) if type(s.get('timing')) in (int,float) else None),
            ('structure','Estrutura aparente',lambda s:band(s['structure'],40,70,('Estrutura baixa','Estrutura média','Estrutura alta')) if type(s.get('structure')) in (int,float) else None)]
        for key,label,getter in dimensions:
            buckets=defaultdict(list)
            for s in snapshots:
                value=getter(s)
                if value is not None: buckets[str(value)].append(s)
            for name, samples in buckets.items():
                n=len(samples); w=sum(s['outcome']=='won' for s in samples); delta=pct(w,n)-pct(sw,len(snapshots))
                if n>=3 and abs(delta)>=15:
                    insights.append(dict(key=key+':'+name,dimension=label,value=name,sample=n,won=w,lost=n-w,win_rate=pct(w,n),delta_pp=delta,
                        direction='higher' if delta>0 else 'lower',explanation=f'{w} ganhos e {n-w} perdas com snapshot; associação descritiva.'))
    return dict(intelligence=intelligence,outcomes=dict(status='ready' if len(snapshots)>=6 and sw>=2 and sl>=2 else 'insufficient',
        closed_count=len(records),won_count=intelligence['wonCount'],lost_count=intelligence['lostCount'],snapshot_coverage=pct(len(snapshots),len(records)),
        minimum_required=6,insights=sorted(insights,key=lambda r:-abs(r['delta_pp']))[:8]))


@router.get('/operations')
def operations(period: Literal['7','30','90','history']='30', origin: Literal['all','search','absorption','manual']='all', user: User=Depends(current_user)):
    limiter.check('operational-intelligence:'+user.id, 30, 60)
    # A repeatable snapshot avoids mixing concurrent confirmations across tables.
    isolation = 'SERIALIZABLE' if engine.dialect.name == 'sqlite' else 'REPEATABLE READ'
    with engine.connect().execution_options(isolation_level=isolation) as connection:
        with connection.begin():
            if engine.dialect.name == 'sqlite': connection.exec_driver_sql('BEGIN')
            with Session(bind=connection, autoflush=False) as db:
                return report(db,user,period,origin)
