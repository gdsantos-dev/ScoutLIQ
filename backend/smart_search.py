"""Explicit searches coordinated by the existing ResearchExecutor and batches."""
import json
import hashlib
import os
import time
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import SmartSearch, ResearchBatch, ResearchBatchItem, Lead, LeadResearch, User, RadarSavedSearch, ResearchExecutor
from .security import current_user, limiter
from .search_intent import Strict, Intent, InterpretInput, interpret, requirements, SECTORS, discovery_sectors
from .search_sources import capabilities, search_page, QUERIES
from .commercial_fit import assess, norm
from .providers import DiscoveryQuery, DiscoveryBatch
from .scoring import score
from . import discovery_plan
from .search_location import LocationSelection, SearchArea, resolve_selection
from .search_intent import Market, Profile, Requirement, GEOGRAPHIC_MESSAGES

router = APIRouter(prefix='/api/smart-searches', tags=['smart-search'])
ACTIVE = ('pending', 'running', 'investigating')
MAX_CALLS, MAX_CANDIDATES, MAX_INVESTIGATIONS = 12, 600, 200

class Start(Strict):
    intent: Intent
    request_key: UUID

class SavedStart(Strict):
    request_key: UUID
    version: int = Field(ge=1)


@router.post('/saved/{identifier}/launch')
def launch_saved(identifier:str,data:SavedStart,user=Depends(current_user),db=Depends(get_db)):
    from .research_worker import MODE
    from .main import radar_provider
    from .search_compat import create_saved_job, sync_results
    limiter.check('smart-start:'+user.id,6,60)
    if MODE!='worker': raise HTTPException(409,'A busca exige o processo de pesquisa ativo em modo worker.')
    saved=db.scalar(select(RadarSavedSearch).where(RadarSavedSearch.id==identifier,RadarSavedSearch.user_id==user.id))
    if not saved: raise HTTPException(404,'Pesquisa salva não encontrada.')
    existing=db.scalar(select(SmartSearch.id).where(SmartSearch.user_id==user.id,SmartSearch.request_key==str(data.request_key)))
    if not existing and saved.version!=data.version: raise HTTPException(409,'Pesquisa alterada. Atualize antes de executar.')
    try:
        job=create_saved_job(db,saved,user,str(data.request_key),radar_provider,int(time.time()))
        sync_results(db,int(time.time()))
        db.commit()
    except ValueError:
        db.rollback()
        raise HTTPException(422,'Consulta histórica inválida. Revise a busca salva.') from None
    except IntegrityError:
        db.rollback()
        winner=db.scalar(select(SmartSearch.id).where(SmartSearch.user_id==user.id,SmartSearch.request_key==str(data.request_key)))
        if not winner: raise
        job=create_saved_job(db,saved,user,str(data.request_key),radar_provider,int(time.time()))
    return {'status':'started','job':describe(job,db)}

class Criteria(Strict):
    sectors: list[str] = Field(default_factory=list, max_length=4)
    profile: Profile
    requirements: list[Requirement] = Field(default_factory=list, max_length=7)
    preferences: list[Requirement] = Field(default_factory=list, max_length=7)
    exclusions: list[str] = Field(default_factory=list, max_length=12)
    requirement_mode: Literal['all', 'any'] = 'all'
    accept_unresolved: bool = False

class Launch(Strict):
    text: str = Field(default="", max_length=1200)
    location: LocationSelection | None = None
    area: SearchArea | None = None
    target: int = Field(default=50)
    request_key: UUID
    confirm_location: bool = False
    criteria: Criteria | None = None

    @model_validator(mode='after')
    def single_geography(self):
        if bool(self.location) == bool(self.area):
            raise ValueError('Selecione exatamente uma localização ou área do mapa')
        return self


def non_geographic_warnings(intent):
    # Launch supplies independently validated catalog/map geography. Remove only
    # these known geography prompts, never free-form commercial restrictions.
    return [message for message in intent.unresolved if message not in GEOGRAPHIC_MESSAGES.values()]


@router.post('/prepare')
def prepare(data:InterpretInput, user=Depends(current_user)):
    """Optional, free deterministic preview; explicit edits never invoke a model."""
    limiter.check('smart-interpret:'+user.id, 30, 60)
    intent=interpret(data.text,data.target)
    return {'intent':intent, 'warnings':non_geographic_warnings(intent), 'sectors':list(SECTORS)}


@router.get('/locations')
def locations(q: str = Query(min_length=2, max_length=160), country: str = Query(default='', pattern=r'^([A-Z]{2})?$'),
              lang: str = Query(default='pt', pattern=r'^(pt|en|es)$'), user=Depends(current_user)):
    limiter.check('search-location:'+user.id, 30, 60)
    from .locations import LocationCatalogError
    from .location_budget import search as catalog_search
    try:
        return [item['resolved'] for item in catalog_search(user.id,q,country,lang,administrative=True) if item.get('resolved')]
    except LocationCatalogError:
        raise HTTPException(503,'Localizações indisponíveis. Tente novamente; nenhuma área foi selecionada.') from None


@router.post('/launch')
def launch(data:Launch, user=Depends(current_user), db=Depends(get_db)):
    """One request prepares a simple intent and queues the existing executor."""
    from .research_worker import MODE
    from .locations import LocationCatalogError
    from .main import radar_provider
    limiter.check('smart-start:'+user.id, 6, 60)
    if data.target not in (25,50,75,100): raise HTTPException(422,'Quantidade inválida.')
    if MODE!='worker': raise HTTPException(409,'A busca exige o processo de pesquisa ativo em modo worker.')
    canonical=data.model_dump(mode='json',exclude={'request_key','confirm_location'})
    if data.area is None: canonical.pop('area')  # Preserve existing launch keys.
    fingerprint=hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()
    existing=db.scalar(select(SmartSearch).where(SmartSearch.user_id==user.id,SmartSearch.request_key==str(data.request_key)))
    if existing:
        if state(existing).get('launch_hash')!=fingerprint: raise HTTPException(409,'Esta solicitação já pertence a outra busca.')
        return {'status':'started','job':describe(existing,db)}
    try: location=resolve_selection(data.location,user.id) if data.location else None
    except LocationCatalogError:
        raise HTTPException(422,'Selecione novamente uma localização válida na lista.') from None
    intent=interpret(data.text,data.target)
    named=norm(intent.market.city)
    compatible={norm(x) for x in (location.name,location.city,location.state,location.country) if x} if location else set()
    conflict=(bool(named) and named not in compatible) or (bool(intent.market.country) and (not location or intent.market.country!=location.country_code))
    if conflict and not data.confirm_location:
        message=f'O pedido menciona outro local. Usar {location.formatted}?' if location else 'O pedido menciona uma localização. Usar os limites selecionados no mapa?'
        return {'status':'location_conflict','message':message}
    intent.unresolved=non_geographic_warnings(intent)
    interpretation={'mode':'deterministic','reason':''}
    if data.criteria:
        intent=Intent.model_validate({**intent.model_dump(), **data.criteria.model_dump(exclude={'accept_unresolved'})})
        if data.criteria.accept_unresolved:
            intent.unresolved=[]
        intent.search_mode='filtered'
        interpretation={'mode':'reviewed','reason':'Critérios ajustados explicitamente pelo operador.'}
    # No implicit spend: the installation must separately authorize this policy.
    if not data.criteria and intent.unresolved and os.getenv('SCOUT_SEMANTIC_AUTO_POLICY','disabled')=='complex_only':
        from .semantic_intent import configuration, interpret_optional
        if configuration()['enabled']:
            enriched=f'{data.text}\nLocal selecionado: {location.formatted if location else data.area.label}'
            intent,interpretation=interpret_optional(enriched,data.target,user.id,str(data.request_key))
            intent.query=data.text
            intent.unresolved=non_geographic_warnings(intent)
    intent.location=location
    intent.area=data.area
    intent.market=Market(country=location.country_code,region=location.state,city=location.city) if location else Market()
    if intent.unresolved:
        return {'status':'clarification','messages':intent.unresolved,'intent':intent.model_dump(),'interpretation':interpretation}
    try:
        job=create_search(db,user,intent,str(data.request_key),radar_provider,int(time.time()),options={'launch_hash':fingerprint,'interpretation':interpretation})
        db.commit()
    except IntegrityError:
        # A competing request may have committed the same key after our read.
        # Roll back the losing transaction before reading the durable winner.
        db.rollback()
        job=db.scalar(select(SmartSearch).where(SmartSearch.user_id==user.id,SmartSearch.request_key==str(data.request_key)))
        if not job:
            raise
        if state(job).get('launch_hash')!=fingerprint:
            raise HTTPException(409,'Esta solicitação já pertence a outra busca.') from None
    return {'status':'started','job':describe(job,db)}

class Action(Strict):
    action: str = Field(pattern=r'^(pause|resume|cancel)$')

class Save(Strict):
    name: str = Field(min_length=2, max_length=80)

class Review(Strict):
    version: int = Field(ge=1)
    independence: str = Field(pattern=r'^(unknown|independent|centralized)$')
    operating_status: str = Field(pattern=r'^(unknown|active|closed)$')
    business_type: str = Field(default='unknown', pattern=r'^(unknown|local|b2b)$')
    size: str = Field(default='unknown', pattern=r'^(unknown|small_medium|large)$')
    entity_type: str = Field(default='unknown', pattern=r'^(unknown|commercial|public)$')
    reason: str = Field(default='', max_length=500)
    confirm_existing: bool = False

@router.post('/leads/{identifier}/review')
def review(identifier:str, data:Review, user=Depends(current_user), db=Depends(get_db)):
    limiter.check('qualification-review:'+user.id,30,60)
    from .main import _add_lead_activity, lead_row
    lead=db.scalar(select(Lead).where(Lead.id==identifier,Lead.user_id==user.id))
    if not lead: raise HTTPException(404,'Empresa não encontrada.')
    if lead.version!=data.version: raise HTTPException(409,'Cadastro alterado. Atualize a busca e reabra a revisão.')
    before=json.loads(lead.qualification_json or '{}')
    keys=('independence','operating_status','business_type','size','entity_type')
    if data.confirm_existing:
        if any(getattr(data,key)!=before.get(key,'unknown') for key in keys):
            raise HTTPException(422,'Alterações exigem justificativa própria.')
        data.reason=(before.get('review_reason') or 'Avaliação exibida confirmada pelo operador: '+ '; '.join(r['label'] for r in assess(lead)['reasons']))[:500]
    elif len(data.reason.strip())<10:
        raise HTTPException(422,'Informe a evidência e o motivo da alteração.')
    after={'independence':data.independence,'operating_status':data.operating_status,'business_type':data.business_type,'size':data.size,'entity_type':data.entity_type,'review_reason':data.reason,'reviewed_at':int(time.time())}
    lead.qualification_json=json.dumps(after)
    _add_lead_activity(db,lead,'qualification_review',data.reason,{'before':before,'after':after})
    # Re-evaluate finished results without restarting collection or sending anything.
    for job in db.scalars(select(SmartSearch).where(SmartSearch.user_id==user.id)).all():
        info=state(job); intent=Intent.model_validate_json(job.intent_json)
        for entry in info.get('candidates',[]):
            if entry['id']==lead.id:
                group,reason=classify(lead,intent); entry.update(group=group,reason=reason)
        job.state_json=json.dumps(info)
    db.commit()
    return lead_row(lead)

def owned(db, identifier, user):
    job = db.scalar(select(SmartSearch).where(SmartSearch.id==identifier, SmartSearch.user_id==user.id))
    if not job: raise HTTPException(404, 'Busca não encontrada.')
    return job

def state(job):
    return json.loads(job.state_json)

def expire(db, now):
    """Deadline enforcement also runs when the shared daily budget is exhausted."""
    jobs=db.scalars(select(SmartSearch).where(SmartSearch.status.in_((*ACTIVE,'paused')),SmartSearch.deadline<=now)).all()
    for job in jobs:
        job.status='partial'; job.lease_token=''; job.lease_until=0; job.updated_at=now
        info=state(job); info['reason']='Prazo encerrado; resultado parcial preservado.'; job.state_json=json.dumps(info)
        if job.batch_id:
            batch=db.get(ResearchBatch,job.batch_id)
            if batch and batch.status!='completed': batch.status='cancelled'
    if jobs: db.commit()

def sync_batch_control(db, batch, action):
    from .routines import guard_child_control
    guard_child_control(db,action,batch_id=batch.id)
    job=db.scalar(select(SmartSearch).where(SmartSearch.batch_id==batch.id,SmartSearch.user_id==batch.user_id))
    if not job: return
    if job.status not in (*ACTIVE,'paused') or (action=='resume' and job.deadline<=int(time.time())):
        raise HTTPException(409,'A busca associada encerrou. Reutilize a intenção em uma nova execução.')
    job.status={'pause':'paused','resume':'investigating','cancel':'cancelled'}[action]
    job.lease_token='';job.lease_until=0;job.updated_at=int(time.time())

def describe(job, db, include_results=True):
    info = state(job)
    rows = []
    all_entries=info.get('candidates',[])+info.get('duplicate_records',[])
    for entry in all_entries if include_results else []:
        lead = db.get(Lead, entry['id'])
        if not lead or lead.user_id != job.user_id: continue
        from .main import lead_row
        canonical=lead_row(lead)
        rows.append({**entry, 'name': lead.name, 'city': lead.city, 'category': lead.category, 'priority': canonical['score'], 'version':lead.version, 'qualification':json.loads(lead.qualification_json or '{}'), 'lead':canonical})
    counters = {k: info.get(k, 0) for k in ('discovered','duplicates','created','existing','investigated','calls','skipped_recent')}
    for key in ('qualified','investigating','discarded'):
        counters[key] = sum(r['group']==key for r in (rows if include_results else all_entries))
    return {'id':job.id, 'intent':json.loads(job.intent_json), 'status':job.status,
            'reason':info.get('reason',''), 'error':job.error, 'counters':counters,
            'results':rows, 'limits':{'provider_pages':info.get('page_limit',MAX_CALLS),'candidates':info.get('candidate_limit',MAX_CANDIDATES),'investigations':info.get('investigation_limit',MAX_INVESTIGATIONS)},
            'diversity':info.get('diversity'), 'coverage':info.get('coverage',[]), 'plan':discovery_plan.describe(info), 'created_at':job.created_at, 'updated_at':job.updated_at,
            'deadline':job.deadline, 'batch_id':job.batch_id}

@router.post('/interpret')
def parse(data:InterpretInput, user=Depends(current_user)):
    limiter.check('smart-interpret:'+user.id, 30, 60)
    from .main import radar_provider
    intent = interpret(data.text, data.target)
    interpretation = {'mode':'deterministic','reason':'Interpretador determinístico; revise o resumo antes de executar.'}
    if data.mode == 'semantic' and data.text.strip():
        if not data.request_key: raise HTTPException(422,'Identificador da interpretação obrigatório.')
        from .semantic_intent import interpret_optional
        intent, interpretation = interpret_optional(data.text, data.target, user.id, str(data.request_key))
    return {'intent':intent, 'interpretation':interpretation, 'sectors':list(SECTORS), 'capabilities':{s:capabilities(radar_provider,s) for s in intent.sectors}}

@router.get('/interpretation-config')
def interpretation_config(user=Depends(current_user)):
    from .semantic_intent import availability
    return availability()

@router.get('')
def listing(user=Depends(current_user), db=Depends(get_db)):
    jobs = db.scalars(select(SmartSearch).where(SmartSearch.user_id==user.id).order_by(SmartSearch.created_at.desc()).limit(20)).all()
    return [describe(job,db,include_results=False) for job in jobs]

@router.post('')
def start(data:Start, user=Depends(current_user), db=Depends(get_db)):
    limiter.check('smart-start:'+user.id, 6, 60)
    from .research_worker import MODE
    if MODE!='worker': raise HTTPException(409,'A busca inteligente exige RESEARCH_EXECUTION_MODE=worker e o processo de pesquisa ativo.')
    existing = db.scalar(select(SmartSearch).where(SmartSearch.user_id==user.id, SmartSearch.request_key==str(data.request_key)))
    if existing: return describe(existing,db)
    from .main import radar_provider
    job = create_search(db, user, data.intent, str(data.request_key), radar_provider, int(time.time()))
    db.commit()
    return describe(job,db)

def validate_intent(intent):
    intent = intent.model_copy(deep=True)
    if intent.legacy:
        if intent.sectors != [intent.legacy.category or 'empresas'] or intent.unresolved:
            raise HTTPException(422,'Consulta histórica inconsistente.')
        return intent
    if intent.location:
        intent.market=Market(country=intent.location.country_code,region=intent.location.state,city=intent.location.city)
    elif intent.area:
        intent.market=Market()  # Coordinates alone do not confirm a city or country.
    if intent.profile.independence=='required' and 'independent' not in intent.requirements:
        intent.requirements.append('independent')
    if intent.unresolved or (not intent.location and not intent.area and (not intent.market.city or not intent.market.country)) or intent.search_mode=='ambiguous' or (not intent.sectors and intent.search_mode not in ('general','filtered')):
        raise HTTPException(422,'Revise cidade, país, setor e interpretações pendentes antes de executar.')
    if intent.search_mode=='legacy' or (intent.search_mode=='general' and intent.sectors):
        raise HTTPException(422,'Modo de busca inconsistente.')
    if any(s not in SECTORS for s in intent.sectors): raise HTTPException(422,'Setor sem contrato de descoberta.')
    if any(s not in {*SECTORS, 'centralized_chains','public_entities','closed'} for s in intent.exclusions):
        raise HTTPException(422,'Exclusão não suportada.')
    if set(intent.sectors) & set(intent.exclusions): raise HTTPException(422,'O mesmo setor está incluído e excluído.')
    return intent

def create_search(db, user, intent, request_key, provider, now, options=None):
    intent = validate_intent(intent)
    if db.scalar(select(func.count()).select_from(SmartSearch).where(SmartSearch.user_id==user.id, SmartSearch.status.in_((*ACTIVE,'paused')))) >= 3:
        raise HTTPException(409,'Conclua ou cancele uma das três buscas abertas.')
    from .search_sources import legacy_capabilities
    coverage = [{'sector':s, **(legacy_capabilities(provider,intent.legacy.discovery()) if intent.legacy else capabilities(provider,s,intent.location,intent.area))} for s in discovery_sectors(intent)]
    unsupported = all(not c['supported'] for c in coverage)
    options = options or {}
    job = SmartSearch(user_id=user.id, request_key=request_key,intent_json=intent.model_dump_json(),
        status='partial' if unsupported else 'pending', deadline=now+options.get('duration_minutes',120)*60,
        state_json=json.dumps({'candidates':[], 'sector':0,'offset':0,'calls':0,'discovered':0,'duplicates':0,'created':0,'existing':0,'investigated':0,
                              **options,
                              'plan':discovery_plan.initialize(coverage),
                              'authorized_provider':getattr(provider,'name','unconfigured'),
                              'coverage':coverage,'reason':coverage[0]['reason'] if unsupported else ''}))
    info=state(job); discovery_plan.choose(info); job.state_json=json.dumps(info)
    db.add(job); db.flush()
    return job

@router.get('/{identifier}')
def detail(identifier:str, user=Depends(current_user), db=Depends(get_db)):
    return describe(owned(db,identifier,user),db)

@router.post('/{identifier}/action')
def control(identifier:str, data:Action, user=Depends(current_user), db=Depends(get_db)):
    job=owned(db,identifier,user)
    from .routines import guard_child_control
    guard_child_control(db,data.action,search_id=job.id)
    expected = job.status
    if data.action=='resume':
        if job.status!='paused': raise HTTPException(409,'A busca não está pausada.')
        if job.deadline <= int(time.time()): raise HTTPException(409,'Prazo encerrado. Reutilize a intenção em uma nova busca.')
        status = 'investigating' if job.batch_id else 'pending'
    else:
        if job.status not in (*ACTIVE,'paused'): raise HTTPException(409,'Busca já encerrada.')
        status = 'paused' if data.action=='pause' else 'cancelled'
    # Serialize with the worker's fenced transaction, invalidate stale responses.
    changed=db.execute(update(SmartSearch).where(SmartSearch.id==job.id,SmartSearch.user_id==user.id,SmartSearch.status==expected)
        .values(status=status,lease_token='',lease_until=0,updated_at=int(time.time())))
    if changed.rowcount!=1: raise HTTPException(409,'A busca mudou. Atualize e tente novamente.')
    if job.batch_id:
        batch=db.get(ResearchBatch,job.batch_id)
        if batch and batch.status!='completed':
            batch.status='pending' if data.action=='resume' else status
    db.commit(); db.refresh(job)
    return describe(job,db)

@router.post('/{identifier}/save')
def save(identifier:str, data:Save, user=Depends(current_user), db=Depends(get_db)):
    job=owned(db,identifier,user)
    intent=Intent.model_validate_json(job.intent_json)
    if db.scalar(select(func.count()).select_from(RadarSavedSearch).where(RadarSavedSearch.user_id==user.id))>=30:
        raise HTTPException(409,'Limite de 30 pesquisas salvas.')
    from .schemas import RadarSavedQuery
    source_query=(intent.legacy.model_dump(exclude={'resolved_location'}) if intent.legacy else query_for(intent,{'sector':0}).model_dump(exclude={'resolved_location'}) if intent.area else
                  dict(location=(intent.location.formatted[:160] if intent.location else intent.market.city),country=intent.market.country,category=QUERIES.get(discovery_sectors(intent)[0],discovery_sectors(intent)[0])))
    query=RadarSavedQuery(**source_query,commercial_intent=intent).model_dump()
    saved=RadarSavedSearch(user_id=user.id,name=data.name,query_json=json.dumps(query),monitor_enabled=False)
    db.add(saved); db.commit()
    return {'id':saved.id,'name':saved.name}

def query_for(intent, info):
    if intent.legacy: return intent.legacy.discovery()
    sector=discovery_sectors(intent)[info['sector']]
    if intent.area:
        area=intent.area
        lat,lng=area.center
        return DiscoveryQuery(location=area.label,category=QUERIES.get(sector,sector),scope=area.kind,
                              center_lat=lat,center_lng=lng,radius_km=area.radius_km,bounds=area.bounds,
                              polygon=[list(point) for point in area.polygon])
    if intent.location:
        location=intent.location
        return DiscoveryQuery(location=location.formatted[:160], city_name=location.city,
                              country=location.country_code, state=location.state,
                              category=QUERIES.get(sector,sector), resolved_location=location)
    return DiscoveryQuery(location=', '.join(x for x in (intent.market.city,intent.market.region,intent.market.country) if x),
                          city_name=intent.market.city,country=intent.market.country,category=QUERIES.get(sector,sector))

def collect(job, provider):
    """Outside transaction. One finite source page, never an unbounded search loop."""
    info=state(job); intent=Intent.model_validate_json(job.intent_json)
    if job.status=='investigating' or job.deadline<=int(time.time()): return None
    if info.get('authorized_provider') and info['authorized_provider']!=getattr(provider,'name','unconfigured'):
        from .providers import ProviderConfigurationError
        raise ProviderConfigurationError('Fonte autorizada indisponível.')
    if intent.area and info['sector'] < len(discovery_sectors(intent)) and not capabilities(provider,discovery_sectors(intent)[info['sector']],area=intent.area)['supported']:
        from .providers import ProviderConfigurationError
        raise ProviderConfigurationError('A fonte não suporta a área selecionada.')
    if info.get('attempted_pages',0)>info.get('page_limit',MAX_CALLS) or info['discovered']>=info.get('candidate_limit',MAX_CANDIDATES) or info['sector']>=len(discovery_sectors(intent)): return None
    return search_page(provider,query_for(intent,info),info['offset'],min(100,info.get('candidate_limit',MAX_CANDIDATES)-info['discovered']),compatible=bool(intent.legacy))

def classify(lead, intent):
    fit=assess(lead)
    if fit['status']=='incompatible': return 'discarded',fit['reasons'][0]['label']
    if lead.contact_blocked: return 'discarded','Contato bloqueado; opt-out preservado.'
    if intent.profile.business_type=='b2b':
        from .commercial_fit import facts
        business_type=facts(lead).get('business_type','unknown')
        if business_type=='local': return 'discarded','Atendimento B2B não confirmado na revisão comercial.'
        if business_type=='unknown': return 'investigating','Verificar atendimento B2B; o setor sozinho não comprova o modelo comercial.'
    # Provider sector normalization is authoritative only for its exact selector.
    for excluded in intent.exclusions:
        if excluded in SECTORS and any(term in norm(lead.category) for term in SECTORS[excluded]):
            return 'discarded','Setor excluído da intenção.'
    required=requirements(lead,intent)
    if required=='unmet': return 'discarded','Requisito comercial não atendido.'
    result=score(lead)
    if required=='met' and result['status']=='qualified': return 'qualified','Necessidade, contexto e canal suficientes para revisão comercial.'
    return 'investigating','Evidência insuficiente para qualificação.' if required=='met' else 'Requisito ainda não verificado.'

def persist(db, job, result, now):
    """Called under the shared executor fence. CRM changes and cursor commit once."""
    from .main import _persist_discovery
    intent=Intent.model_validate_json(job.intent_json); info=state(job)
    entries=info['candidates']; user=db.get(User,job.user_id)
    newly_incorporated=[]
    if not user or not user.is_active: return
    if result is not None:
        if info.get('prospecting_plan_id'):
            # An adapter returning more than requested cannot exceed the plan's
            # incorporation cap. Preserve its scanned count as technical evidence.
            remaining=max(0,info['candidate_limit']-info['discovered'])
            result=result.model_copy(update={'results':result.results[:remaining]})
        previous_count=len(entries)
        known=set(db.scalars(select(Lead.id).where(Lead.user_id==user.id)).all())
        response=_persist_discovery(query_for(intent,info),result,user,db,commit=False)
        newly_incorporated=[r['id'] for r in response['results'] if r['id'] not in known]
        if intent.legacy:
            from .monitor_matching import matches
            response['results']=[row for row in response['results'] if matches(row,intent.legacy.model_dump())]
        info['calls']+=1
        scanned=max(result.scanned,len(result.results))
        info['discovered']+=scanned
        seen={e['id'] for e in entries}
        for row in response['results']:
            if row['id'] in seen:
                info['duplicates']+=1
                info.setdefault('duplicate_records',[]).append({'id':row['id'],'occurrence':f"duplicate-{info['duplicates']}",'origin':'duplicate','group':'discarded','reason':'Duplicata da mesma identidade nesta execução; cadastro e investigação reutilizados.'})
                continue
            seen.add(row['id']); old=row['id'] in known
            info['existing' if old else 'created']+=1
            entries.append({'id':row['id'],'origin':'existing' if old else 'new','group':'investigating','reason':''})
        info['offset']+=scanned
        cap=info['coverage'][info['sector']]
        discovery_plan.record(info,result,[r['id'] for r in response['results']])
        if not info.get('plan') and (result.complete or not scanned or not cap['pagination']):
            if not result.complete: info['source_limited']=True
            info['sector']+=1; info['offset']=0
        if response.get('workspace_limit_reached'): info['workspace_limit']=True
        if info.get('exclude_pipeline'):
            info['stalled_pages']=info.get('stalled_pages',0)+1 if len(entries)==previous_count else 0
    # Keep strong references and compute each priority once per persisted step.
    # Diversity must not turn its comparisons into repeated ORM queries/scoring.
    leads={e['id']:db.get(Lead,e['id']) for e in entries}
    priorities={}
    categories={}
    for identifier,lead in leads.items():
        if not lead or lead.user_id!=job.user_id:
            priorities[identifier]=(-1,0);categories[identifier]='';continue
        preferred=sum(requirements(lead,intent.model_copy(update={'requirements':[key],'requirement_mode':'all'}))=='met' for key in intent.preferences)
        priorities[identifier]=(score(lead)['value'],preferred)
        categories[identifier]=norm(lead.category)
    # Preferences break ties; never inflate the one main priority or become requirements.
    def ranking(entry): return priorities[entry['id']]
    def category(entry): return categories[entry['id']]
    entries.sort(key=ranking,reverse=True)
    if not intent.sectors and not intent.legacy:
        entries[:]=discovery_plan.diverse(entries,ranking,category)
    qualified=0
    for entry in entries:
        lead=leads[entry['id']]
        if not lead or lead.user_id!=job.user_id:
            entry.update(group='discarded',reason='Registro removido.'); continue
        group,reason=classify(lead,intent)
        if info.get('exclude_pipeline') and lead.in_pipeline:
            group,reason='discarded','Empresa já no pipeline; não é uma nova descoberta.'
        elif lead.id in info.get('suppress_ids',[]):
            group,reason='discarded','Oportunidade já apresentada nesta rotina.'
        if group=='qualified':
            qualified+=1
            if qualified>intent.target: group,reason='investigating','Qualificado além da meta; disponível para revisão.'
        entry.update(group=group,reason=reason)
    from .prospecting import record_incorporations
    record_incorporations(db,job,newly_incorporated,entries,now)
    batch=db.get(ResearchBatch,job.batch_id) if job.batch_id else None
    attempted=set()
    if batch:
        items=db.scalars(select(ResearchBatchItem).where(ResearchBatchItem.batch_id==batch.id)).all()
        attempted={i.lead_id for i in items}
        info['investigated']=sum(i.status in ('done','error','skipped') for i in items)
        if any(i.status in ('pending','running') for i in items) and now<job.deadline:
            job.status='investigating'; job.state_json=json.dumps(info); return
    discovery_plan.choose(info)
    stalled=(info.get('stalled_pages',0)>=2 and not info.get('plan')) or (bool(info.get('plan')) and info['sector']>=len(discovery_sectors(intent)) and any(s.get('stalled',0)>=2 for s in info['plan']['steps']))
    exhausted=stalled or info['sector']>=len(discovery_sectors(intent)) or info.get('attempted_pages',0)>=info.get('page_limit',MAX_CALLS) or info['discovered']>=info.get('candidate_limit',MAX_CANDIDATES) or info.get('workspace_limit')
    # Sample a second broad page when available before stopping at the first-page
    # target. This is bounded by the same page/candidate/deadline budgets.
    broad=not intent.sectors and not intent.legacy
    if broad:
        info['diversity']={'categories':len({category(e) for e in entries if leads[e['id']] and e['group']!='discarded'}),
                           'strategy':'Diversidade entre prioridades equivalentes; Score preservado.'}
    if broad and not exhausted and now<job.deadline and info['calls']<min(2,info.get('page_limit',MAX_CALLS)):
        job.status='pending';job.updated_at=now;job.state_json=json.dumps(info);return
    if qualified>=intent.target:
        job.status='completed'; info['reason']='Meta de oportunidades qualificadas atingida.'
    elif now>=job.deadline:
        job.status='partial'; info['reason']='Prazo da execução encerrado; resultado parcial preservado.'
        if batch and batch.status not in ('completed','cancelled'): batch.status='cancelled'
    else:
        candidates=[e for e in entries if e['group']=='investigating' and e['id'] not in attempted]
        if info.get('cooldown_days'):
            recent=set(db.scalars(select(LeadResearch.lead_id).where(LeadResearch.user_id==user.id,
                LeadResearch.checked_at>now-info['cooldown_days']*86400)).all())
            info['skipped_recent']=sum(e['id'] in recent for e in candidates)
            candidates=[e for e in candidates if e['id'] not in recent]
        if broad:
            candidates=discovery_plan.diverse(candidates,
                lambda e: (ranking(e)[0]//10, ranking(e)[1]),
                category,
                [categories[i] for i in attempted if i in categories])
        pending_elsewhere=set(db.scalars(select(ResearchBatchItem.lead_id).join(ResearchBatch).where(
            ResearchBatch.user_id==user.id,ResearchBatch.status.in_(['pending','running','paused']),
            ResearchBatchItem.status.in_(['pending','running']))))
        candidates=[entry for entry in candidates if entry['id'] not in pending_elsewhere]
        remaining=info.get('investigation_limit',MAX_INVESTIGATIONS)-len(attempted)
        candidates=candidates[:min(remaining,max(0,intent.target-qualified)*2,50)]
        if candidates:
            if not batch:
                batch=ResearchBatch(user_id=user.id,mode=info.get('research_mode','deep'),status='pending',requested_count=0)
                db.add(batch); db.flush(); job.batch_id=batch.id
            batch.status='pending'; batch.completed_at=None
            for index,entry in enumerate(candidates):
                db.add(ResearchBatchItem(batch_id=batch.id,lead_id=entry['id'],position=len(attempted)+index))
            batch.requested_count+=len(candidates)
            job.status='investigating'
        elif exhausted or remaining<=0:
            job.status='partial'
            info['reason']='Coleta interrompida após duas páginas sem novas empresas.' if stalled else 'Limite de investigação atingido.' if remaining<=0 else 'Limite de cadastros atingido.' if info.get('workspace_limit') else 'Fonte ou orçamento de coleta esgotado; nenhuma oportunidade foi inventada para completar a meta.'
        else: job.status='pending'
    job.updated_at=now; job.state_json=json.dumps(info)
