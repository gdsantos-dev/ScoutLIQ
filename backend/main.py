import json
import logging
import math
import os
import secrets
import time
from contextlib import asynccontextmanager
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import select, delete, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm.exc import StaleDataError
from .config import ROOT, PRODUCTION, ORIGIN, REGISTRATION_MODE
from .db import get_db, engine
from .models import User, AccountToken, Session, Lead, LeadResearch, LeadActivity, RadarSavedSearch, ResearchBatch, ResearchBatchItem, AutomationRule, AutomationRun, Campaign, CampaignLead, Sale, Payment, Expense, Site
from .schemas import Login, RegisterInput, EmailInput, TokenInput, ResetPasswordInput, LeadInput, LeadUpdate, StageUpdate, NextActionUpdate, SaleInput, CampaignInput, CampaignUpdate, CampaignLeadsInput, PaymentInput, ExpenseInput, SettingsInput, PasswordInput, ProjectUpdate, SiteInput, SiteUpdate, GoogleMapsImportInput, ImportedLeadInput, ResearchBatchInput, LeadActivityInput, RadarSavedSearchInput, RadarSavedSearchResultsUpdate, RadarSavedSearchMonitorUpdate, RadarNaturalSearchInput, LeadWatchUpdate, AutomationRuleInput, AutomationRuleUpdate, AutomationToggleInput
from .security import current_user, hasher, verify, digest, dummy_hash, limiter, normalize_email
from .scoring import score, niche_context
from .providers import build_provider, DiscoveryQuery, ProviderError, ProviderTimeout, ProviderConfigurationError, LocationNotFound
from .locations import search_locations, brazil_municipalities, LocationCatalogError
from .google_maps_import import import_google_maps_link, GoogleMapsImportError, GoogleMapsImportTimeout
from .research import WebsiteResearcher, ResearchError, SearchConfigurationError
from .radar_query import interpret_natural_radar_query
from .automation import rule_row as automation_rule_row, run_row as automation_run_row, run_automation_event, execute_rule
from .enrichment import start_profile as start_enrichment_profile, missing as enrichment_missing, record_attempt as record_enrichment_attempt, apply_values as apply_enrichment_values, provider_values as provider_enrichment_values, research_values as research_enrichment_values, finalize as finalize_enrichment
from . import email_service
from .orliq_admin_routes import router as orliq_admin_router
from .opportunity_workflow import router as opportunity_router, pause_drafts, export_workflow

@asynccontextmanager
async def lifespan(app):
    from .bootstrap import bootstrap
    bootstrap()
    yield

radar_provider = build_provider()
website_researcher = WebsiteResearcher()

app = FastAPI(title='ScoutLIQ API',docs_url=None if PRODUCTION else '/api/docs',openapi_url=None if PRODUCTION else '/api/openapi.json',redoc_url=None,lifespan=lifespan)
app.include_router(opportunity_router)
from .smart_search import router as smart_search_router
app.include_router(smart_search_router)
from .routines import router as routines_router
app.include_router(routines_router)
from .prospecting import router as prospecting_router
app.include_router(prospecting_router)
from .commercial_learning import router as learning_router, export_learning
app.include_router(learning_router)
from .score_calibration import router as calibration_router
app.include_router(calibration_router)
from .communication import router as communication_router, export_communication
from .gmail_oauth import router as gmail_router
app.include_router(communication_router)
app.include_router(gmail_router)
from .absorption import router as absorption_router
app.include_router(absorption_router)
from .investigation import router as investigation_router
app.include_router(investigation_router)
from .commercial_review import router as commercial_review_router, export_reviews
app.include_router(commercial_review_router)
from .followup import router as followup_router, export_followup
app.include_router(followup_router)
from .operational_intelligence import router as operational_intelligence_router
app.include_router(operational_intelligence_router)

class BodyLimit:
    def __init__(self, app):
        self.app=app
    async def __call__(self, scope, receive, send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        total=0
        messages=[]
        while True:
            message=await receive()
            if message['type']=='http.disconnect':
                return
            total+=len(message.get('body',b''))
            if total>65536:
                response=JSONResponse({'detail':'Requisição muito grande.'},status_code=413)
                return await response(scope,receive,send)
            messages.append(message)
            if not message.get('more_body',False):
                break
        async def buffered_receive():
            if messages:
                return messages.pop(0)
            return await receive()
        await self.app(scope,buffered_receive,send)

app.add_middleware(BodyLimit)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)

@app.middleware('http')
async def security_headers(request, call_next):
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin!=ORIGIN:
        return JSONResponse({'detail':'Origem não autorizada.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer' if request.url.path=='/api/communication/gmail/callback' else 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=(self)'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: blob: https://tile.openstreetmap.org https://api.maptiler.com https://*.maptiler.com; connect-src 'self' https://tile.openstreetmap.org https://api.maptiler.com https://*.maptiler.com data: blob:; font-src 'self' https://fonts.gstatic.com https://api.maptiler.com https://*.maptiler.com; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control']='no-store'
    elif request.url.path.startswith('/assets/') and response.status_code==200:
        response.headers['Cache-Control']='public, max-age=31536000, immutable'
    if PRODUCTION:
        response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    fields=', '.join('.'.join(str(x) for x in e['loc'][1:]) for e in exc.errors())
    return JSONResponse({'detail':f'Confira os campos: {fields}.'},status_code=422)

@app.exception_handler(StaleDataError)
async def stale_error(request,exc):
    return JSONResponse({'detail':'Este registro mudou em outra sessão. Atualize e tente novamente.'},status_code=409)

@app.exception_handler(IntegrityError)
async def integrity_error(request,exc):
    return JSONResponse({'detail':'Operação já registrada ou dados em conflito. Atualize a página.'},status_code=409)

@app.exception_handler(Exception)
async def internal_error(request,exc):
    logging.getLogger('scoutliq').error('Falha interna: %s',type(exc).__name__)
    return JSONResponse({'detail':'Não foi possível concluir. Tente novamente.'},status_code=500)

def row(obj):
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns if c.name!='user_id'}

def lead_row(lead):
    data=row(lead)
    raw=data.pop('website_intelligence_json', '{}')
    try:
        parsed=json.loads(raw or '{}')
        data['website_intelligence']=parsed if isinstance(parsed,dict) else {}
    except (TypeError,json.JSONDecodeError):
        data['website_intelligence']={}
    competitive_raw=data.pop('competitive_context_json', '{}')
    try:
        competitive=json.loads(competitive_raw or '{}')
        data['competitive_context']=competitive if isinstance(competitive,dict) and competitive.get('status') else None
    except (TypeError,json.JSONDecodeError):
        data['competitive_context']=None
    enrichment_raw=data.pop('enrichment_json', '{}')
    try:
        enrichment=json.loads(enrichment_raw or '{}')
        data['enrichment']=enrichment if isinstance(enrichment,dict) else {}
    except (TypeError,json.JSONDecodeError):
        data['enrichment']={}
    data.pop('outcome_snapshot_json', None)
    data.pop('outcome_recorded_at', None)
    data.pop('commercial_signal_json', None)
    data.pop('previous_score_json', None)
    data['qualification']=_json_object(data.pop('qualification_json', '{}'), {})
    data['score']=score(lead)
    return data

def _json_object(value, fallback):
    try:
        parsed=json.loads(value or '')
        return parsed if isinstance(parsed,type(fallback)) else fallback
    except (TypeError,json.JSONDecodeError):
        return fallback

def activity_row(item):
    return {
        'id':item.id,
        'lead_id':item.lead_id,
        'kind':item.kind,
        'body':item.body,
        'metadata':_json_object(item.metadata_json,{}),
        'created_at':item.created_at,
    }

def _add_lead_activity(db:DBSession,lead:Lead,kind:str,body:str='',metadata:dict|None=None,created_at:int|None=None):
    timestamp=created_at or int(time.time())
    item=LeadActivity(
        user_id=lead.user_id,
        lead_id=lead.id,
        kind=kind,
        body=body[:1200],
        metadata_json=json.dumps(metadata or {},ensure_ascii=False,separators=(',',':')),
        created_at=timestamp,
    )
    db.add(item)
    if kind == 'reply':
        pause_drafts(db, lead, 'Resposta recebida; revise os próximos contatos em todos os canais.')
    if kind in {'whatsapp','call','email','meeting','proposal','reply'}:
        lead.last_contact_at=timestamp
    if kind in {'pipeline_added','stage_changed','watch_change'} and not (metadata or {}).get('automation_rule_id'):
        run_automation_event(db,lead,kind,metadata or {})
    return item

def commercial_signal_row(lead:Lead):
    return {
        'lead_id':lead.id,
        'state':_json_object(getattr(lead,'commercial_signal_json','{}'),{}),
        'analyzed_at':getattr(lead,'commercial_signal_analyzed_at',None),
    }

def saved_search_row(item):
    return {
        'id':item.id,
        'name':item.name,
        'query':_json_object(item.query_json,{}),
        'last_result_ids':_json_object(item.result_ids_json,[]),
        'last_new_count':item.last_new_count,
        'last_run_at':item.last_run_at,
        'monitor_enabled':bool(getattr(item,'monitor_enabled',False)),
        'execution_mode':__import__('backend.research_worker',fromlist=['MODE']).MODE,
        'worker_error':item.worker_error, 'attempts':item.attempts, 'retry_at':item.retry_at,
        'monitor_interval':getattr(item,'monitor_interval','daily') or 'daily',
        'next_monitor_at':getattr(item,'next_monitor_at',None),
        'last_monitor_at':getattr(item,'last_monitor_at',None),
        'created_at':item.created_at,
        'updated_at':item.updated_at,
        'version':item.version,
    }


def _campaign_owned(db:DBSession,identifier:str,user:User):
    item=db.scalar(select(Campaign).where(Campaign.id==identifier,Campaign.user_id==user.id))
    if item is None:
        raise HTTPException(404,'Campanha não encontrada.')
    return item


def _campaign_metrics(db:DBSession,campaign:Campaign)->dict:
    member_ids=[value for value in db.scalars(select(CampaignLead.lead_id).where(CampaignLead.campaign_id==campaign.id,CampaignLead.user_id==campaign.user_id)).all()]
    if member_ids:
        leads=db.scalars(select(Lead).where(Lead.user_id==campaign.user_id,Lead.demo.is_(False),Lead.id.in_(member_ids))).all()
    else:
        leads=[]
    stages=defaultdict(int)
    for lead in leads:
        stages[lead.stage]+=1
    sales=db.scalars(select(Sale).where(Sale.user_id==campaign.user_id,Sale.demo.is_(False),Sale.campaign_id==campaign.id)).all()
    revenue=defaultdict(int)
    recurring=defaultdict(int)
    for sale in sales:
        revenue[sale.currency]+=int(sale.amount_cents or 0)
        recurring[sale.currency]+=int(sale.recurring_cents or 0)
    contacted=sum(stages[key] for key in ('contacted','replied','negotiating','won'))
    responded=sum(stages[key] for key in ('replied','negotiating','won'))
    return {
        'members':len(leads),
        'in_pipeline':sum(1 for lead in leads if lead.in_pipeline),
        'contacted':contacted,
        'responded':responded,
        'negotiating':stages['negotiating'],
        'won':len({sale.lead_id for sale in sales}),
        'lost':stages['lost'],
        'attributed_sales':len(sales),
        'revenue_by_currency':dict(revenue),
        'recurring_by_currency':dict(recurring),
    }


def campaign_row(db:DBSession,item:Campaign)->dict:
    data=row(item)
    data['metrics']=_campaign_metrics(db,item)
    return data


def _outcome_snapshot(lead:Lead,outcome:str,*,service:str='')->dict:
    payload=score(lead)
    best=max(payload.get('service_scores') or [],key=lambda item:int(item.get('value') or 0),default={})
    return {
        'outcome':outcome,
        'captured_at':int(time.time()),
        'score':int(payload.get('value') or 0),
        'confidence':int((payload.get('confidence') or {}).get('value') or 0),
        'timing':int((payload.get('timing') or {}).get('value') or 0),
        'structure':int((payload.get('commercial_structure') or {}).get('value') or 0),
        'niche_key':str((payload.get('niche') or {}).get('key') or 'generic'),
        'niche_label':str((payload.get('niche') or {}).get('label') or 'Negócio local'),
        'website_status':str(lead.website_status or 'unknown'),
        'reviews':int(lead.reviews or 0),
        'best_service_key':str(best.get('key') or ''),
        'best_service_label':str(best.get('label') or ''),
        'best_service_score':int(best.get('value') or 0),
        'sold_service':service,
        'diagnosis_keys':[str(item.get('key') or '') for item in (payload.get('diagnosis') or [])[:8] if isinstance(item,dict)],
        'combined_signal_keys':[str(item.get('key') or '') for item in (payload.get('combined_signals') or [])[:8] if isinstance(item,dict)],
    }


def _store_outcome_snapshot(lead:Lead,outcome:str,*,service:str='')->None:
    snapshot=_outcome_snapshot(lead,outcome,service=service)
    lead.outcome_snapshot_json=json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))
    lead.outcome_recorded_at=int(snapshot['captured_at'])


def _outcome_insights(db:DBSession,user:User)->dict:
    leads=db.scalars(select(Lead).where(Lead.user_id==user.id,Lead.demo.is_(False),Lead.stage.in_(['won','lost']))).all()
    samples=[]
    snapshot_count=0
    for lead in leads:
        raw=_json_object(getattr(lead,'outcome_snapshot_json','{}'),{})
        if raw and raw.get('outcome') in {'won','lost'}:
            snapshot=raw
            snapshot_count+=1
        else:
            snapshot=_outcome_snapshot(lead,lead.stage)
        samples.append(snapshot)
    won=sum(1 for item in samples if item.get('outcome')=='won')
    lost=sum(1 for item in samples if item.get('outcome')=='lost')
    total=won+lost
    if total<6 or won<2 or lost<2:
        return {
            'status':'insufficient',
            'closed_count':total,
            'won_count':won,
            'lost_count':lost,
            'snapshot_coverage':round(100*snapshot_count/total) if total else 0,
            'minimum_required':6,
            'insights':[],
        }
    overall=won/total

    def review_band(value:int)->str:
        if value>=300:return '300+ avaliações'
        if value>=100:return '100–299 avaliações'
        if value>=20:return '20–99 avaliações'
        return '0–19 avaliações'

    def band(value:int,low:int,high:int,labels:tuple[str,str,str])->str:
        return labels[2] if value>=high else labels[1] if value>=low else labels[0]

    dimensions=[
        ('niche','Nicho',lambda item:str(item.get('niche_label') or 'Negócio local')),
        ('reviews','Volume público',lambda item:review_band(int(item.get('reviews') or 0))),
        ('website','Situação do site',lambda item:{'none':'Sem site','poor':'Site com problemas','good':'Site bom','unknown':'Site não verificado'}.get(str(item.get('website_status') or 'unknown'),'Outro')),
        ('score','Opportunity Score',lambda item:band(int(item.get('score') or 0),40,70,('Score <40','Score 40–69','Score 70+'))),
        ('timing','Timing',lambda item:band(int(item.get('timing') or 0),25,55,('Timing baixo','Timing médio','Timing alto'))),
        ('structure','Estrutura aparente',lambda item:band(int(item.get('structure') or 0),40,70,('Estrutura baixa','Estrutura média','Estrutura alta'))),
        ('service','Melhor fit',lambda item:str(item.get('best_service_label') or 'Sem fit dominante')),
    ]
    candidates=[]
    for key,label,getter in dimensions:
        groups=defaultdict(lambda:{'won':0,'lost':0})
        for item in samples:
            value=getter(item)
            bucket=groups[value]
            bucket[str(item.get('outcome'))]+=1
        for value,bucket in groups.items():
            sample=bucket['won']+bucket['lost']
            if sample<3:
                continue
            rate=bucket['won']/sample
            delta=round((rate-overall)*100)
            if abs(delta)<15:
                continue
            candidates.append({
                'key':f'{key}:{value}',
                'dimension':label,
                'value':value,
                'sample':sample,
                'won':bucket['won'],
                'lost':bucket['lost'],
                'win_rate':round(rate*100),
                'delta_pp':delta,
                'direction':'higher' if delta>0 else 'lower',
                'explanation':f'{bucket["won"]} ganhos e {bucket["lost"]} perdas nesse grupo. Diferença de {abs(delta)} p.p. em relação ao histórico fechado.',
            })
    candidates.sort(key=lambda item:(-abs(int(item['delta_pp'])),-int(item['sample']),str(item['key'])))
    return {
        'status':'ready',
        'closed_count':total,
        'won_count':won,
        'lost_count':lost,
        'overall_win_rate':round(overall*100),
        'snapshot_coverage':round(100*snapshot_count/total),
        'minimum_required':6,
        'insights':candidates[:8],
        'note':'Padrões descritivos do seu histórico. Eles não alteram o score automaticamente e não são previsão de fechamento.',
    }

def research_row(item):
    if item is None:
        return None
    def decoded(value, fallback):
        try:
            parsed=json.loads(value or '')
            return parsed if isinstance(parsed, type(fallback)) else fallback
        except (TypeError, json.JSONDecodeError):
            return fallback
    return {
        'id':item.id,
        'lead_id':item.lead_id,
        'status':item.status,
        'provider':item.provider,
        'website_url':item.website_url,
        'website_status':item.website_status,
        'confidence':item.confidence,
        'evidence':decoded(item.evidence_json,[]),
        'checks':decoded(item.checks_json,[]),
        'sources':decoded(item.sources_json,[]),
        'page':decoded(item.page_json,{}),
        'audit_level':item.audit_level,
        'audit':decoded(item.audit_json,{}),
        'audited_at':item.audited_at,
        'search_configured':item.search_configured,
        'candidates_checked':item.candidates_checked,
        'fetch_errors':item.fetch_errors,
        'checked_at':item.checked_at,
    }

def public_user(user):
    return {key:getattr(user,key) for key in ('id','email','name','accent','motion','timezone','locale','default_currency','role')}

VERIFY_EMAIL_PURPOSE='verify_email'
RESET_PASSWORD_PURPOSE='reset_password'

def _new_account_token(db,user,purpose,ttl_seconds):
    now=int(time.time())
    db.execute(delete(AccountToken).where(AccountToken.user_id==user.id,AccountToken.purpose==purpose,AccountToken.used_at.is_(None)))
    raw=secrets.token_urlsafe(32)
    db.add(AccountToken(user_id=user.id,purpose=purpose,token_hash=digest(raw),expires=now+ttl_seconds,created_at=now))
    db.flush()
    return raw

def _consume_account_token(db,raw,purpose):
    now=int(time.time())
    item=db.scalar(select(AccountToken).where(AccountToken.token_hash==digest(raw),AccountToken.purpose==purpose,AccountToken.used_at.is_(None)))
    if not item or item.expires<=now:
        raise HTTPException(400,'Este link é inválido ou expirou.')
    user=db.get(User,item.user_id)
    if not user:
        raise HTTPException(400,'Este link é inválido ou expirou.')
    item.used_at=now
    return item,user

def _send_verification(db,user):
    token=_new_account_token(db,user,VERIFY_EMAIL_PURPOSE,24*3600)
    db.commit()
    try:
        email_service.send_verification_email(user.email,user.name,token)
        return True
    except (email_service.EmailConfigurationError,email_service.EmailDeliveryError) as exc:
        logging.getLogger('scoutliq').warning('Falha no envio de verificação | user_id=%s | erro=%s',user.id,type(exc).__name__)
        return False

def business_today(user):
    return datetime.now(ZoneInfo(user.timezone)).date()

def owned(db,model,identifier,user):
    obj=db.scalar(select(model).where(model.id==identifier,model.user_id==user.id))
    if not obj:
        raise HTTPException(404,'Registro não encontrado.')
    return obj

def sale_rows(db,user):
    sales=db.scalars(select(Sale).where(Sale.user_id==user.id).order_by(Sale.sold_on.desc())).all()
    payments=db.scalars(select(Payment).where(Payment.user_id==user.id)).all()
    leads={l.id:l for l in db.scalars(select(Lead).where(Lead.user_id==user.id)).all()}
    campaigns={c.id:c for c in db.scalars(select(Campaign).where(Campaign.user_id==user.id)).all()}
    payments_by_sale=defaultdict(list)
    for payment in payments:
        payments_by_sale[payment.sale_id].append(payment)
    return [{**row(s),'campaign_name':campaigns[s.campaign_id].name if s.campaign_id in campaigns else '','company':leads[s.lead_id].name,'contact':leads[s.lead_id].contact,'phone':leads[s.lead_id].phone,'received_cents':sum(p.amount_cents for p in payments_by_sale[s.id]),'payments':[row(p) for p in payments_by_sale[s.id]]} for s in sales]

@app.get('/api/health')
def health(db: DBSession=Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status':'ok'}

@app.get('/api/health/worker')
def worker_health(db: DBSession=Depends(get_db)):
    from .worker_health import snapshot
    state=snapshot(db)
    return JSONResponse({'status':state['status']},status_code=200 if state['status']=='ok' else 503)

@app.get('/api/health/ready')
def ready(db: DBSession=Depends(get_db)):
    db.execute(text('SELECT 1'))
    if os.getenv('SCOUTLIQ_PROCESS_MODE','combined')=='combined': return worker_health(db)
    return {'status':'ok'}

@app.get('/api/auth/config')
def auth_config():
    return {'registration_enabled':REGISTRATION_MODE=='open','email_configured':email_service.email_is_configured()}

@app.post('/api/auth/register',status_code=201)
def register(data:RegisterInput,request:Request,db:DBSession=Depends(get_db)):
    if REGISTRATION_MODE!='open':
        raise HTTPException(403,'Novos cadastros estão desativados.')
    address=request.client.host if request.client else 'unknown'
    limiter.check('register-ip:'+address,5,3600)
    try:
        email=normalize_email(data.email)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    limiter.check('register-email:'+digest(email),3,3600)
    name=' '.join(data.name.split())
    if len(name)<2:
        raise HTTPException(400,'Informe seu nome.')
    if db.scalar(select(User.id).where(User.email==email)):
        raise HTTPException(409,'Já existe uma conta com esse e-mail.')
    user=User(email=email,password_hash=hasher.hash(data.password),name=name,email_verified_at=None)
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409,'Já existe uma conta com esse e-mail.') from exc
    sent=_send_verification(db,user)
    return {'message':'Conta criada. Confira seu e-mail para ativá-la.' if sent else 'Conta criada, mas o e-mail não pôde ser enviado agora. Tente reenviar a confirmação.','email':user.email,'email_sent':sent}

@app.post('/api/auth/verify-email')
def verify_email(data:TokenInput,db:DBSession=Depends(get_db)):
    token,user=_consume_account_token(db,data.token,VERIFY_EMAIL_PURPOSE)
    if user.email_verified_at is None:
        user.email_verified_at=int(time.time())
    db.execute(delete(AccountToken).where(AccountToken.user_id==user.id,AccountToken.purpose==VERIFY_EMAIL_PURPOSE,AccountToken.id!=token.id))
    db.commit()
    return {'message':'E-mail confirmado. Sua conta está pronta para entrar.'}

@app.post('/api/auth/resend-verification')
def resend_verification(data:EmailInput,request:Request,db:DBSession=Depends(get_db)):
    address=request.client.host if request.client else 'unknown'
    try:
        email=normalize_email(data.email)
    except ValueError:
        email=''
    limiter.check('verify-ip:'+address,8,3600)
    if email:
        limiter.check('verify-email:'+digest(email),4,3600)
        user=db.scalar(select(User).where(User.email==email))
        if user and user.email_verified_at is None:
            _send_verification(db,user)
    return {'message':'Se essa conta ainda aguarda confirmação, enviaremos um novo e-mail.'}

@app.post('/api/auth/forgot-password')
def forgot_password(data:EmailInput,request:Request,db:DBSession=Depends(get_db)):
    address=request.client.host if request.client else 'unknown'
    try:
        email=normalize_email(data.email)
    except ValueError:
        email=''
    limiter.check('forgot-ip:'+address,8,3600)
    if email:
        limiter.check('forgot-email:'+digest(email),4,3600)
        user=db.scalar(select(User).where(User.email==email))
        if user and user.email_verified_at is not None:
            token=_new_account_token(db,user,RESET_PASSWORD_PURPOSE,3600)
            db.commit()
            try:
                email_service.send_password_reset_email(user.email,user.name,token)
            except (email_service.EmailConfigurationError,email_service.EmailDeliveryError) as exc:
                logging.getLogger('scoutliq').warning('Falha no envio de recuperação | user_id=%s | erro=%s',user.id,type(exc).__name__)
    return {'message':'Se existir uma conta ativa com esse e-mail, enviaremos as instruções de recuperação.'}

@app.post('/api/auth/reset-password')
def reset_password(data:ResetPasswordInput,db:DBSession=Depends(get_db)):
    token,user=_consume_account_token(db,data.token,RESET_PASSWORD_PURPOSE)
    user.password_hash=hasher.hash(data.password)
    db.execute(delete(Session).where(Session.user_id==user.id))
    db.execute(delete(AccountToken).where(AccountToken.user_id==user.id,AccountToken.purpose==RESET_PASSWORD_PURPOSE,AccountToken.id!=token.id))
    db.commit()
    return {'message':'Senha alterada. Entre novamente com a nova senha.'}

@app.post('/api/auth/login')
def login(data:Login,request:Request,response:Response,db:DBSession=Depends(get_db)):
    address=request.client.host if request.client else 'unknown'
    limiter.check('login-ip:'+address,30,900)
    try:
        email=normalize_email(data.email)
    except ValueError:
        email=data.email.strip().lower()
    limiter.check('login-user:'+digest(email),8,900)
    user=db.scalar(select(User).where(User.email==email))
    if not verify(data.password,user.password_hash if user else dummy_hash) or not user:
        raise HTTPException(401,'E-mail ou senha incorretos.')
    if user.email_verified_at is None:
        raise HTTPException(403,'Confirme seu e-mail antes de entrar.')
    if not user.is_active:
        raise HTTPException(403,'Conta suspensa.')
    user.last_login_at=int(time.time())
    token=secrets.token_urlsafe(32)
    csrf=secrets.token_urlsafe(32)
    db.execute(delete(Session).where(Session.expires<int(time.time())))
    db.add(Session(token_hash=digest(token),user_id=user.id,csrf=csrf,expires=int(time.time())+43200))
    db.commit()
    response.set_cookie('scout_session',token,max_age=43200,httponly=True,secure=PRODUCTION,samesite='strict',path='/')
    return {'user':public_user(user),'csrf':csrf}

@app.get('/api/auth/me')
def me(request:Request,user:User=Depends(current_user)):
    return {'user':public_user(user),'csrf':request.state.session.csrf}

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    db.delete(request.state.session)
    db.commit()
    response.delete_cookie('scout_session',path='/',secure=PRODUCTION,httponly=True,samesite='strict')
    return {'ok':True}

@app.put('/api/auth/password')
def password(data:PasswordInput,response:Response,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    limiter.check('password:'+user.id,5,900)
    if not verify(data.current_password,user.password_hash):
        raise HTTPException(400,'Senha atual incorreta.')
    user.password_hash=hasher.hash(data.new_password)
    db.execute(delete(Session).where(Session.user_id==user.id))
    db.commit()
    response.delete_cookie('scout_session',path='/')
    return {'ok':True}

@app.get('/api/leads')
def leads(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    return sorted([lead_row(l) for l in db.scalars(select(Lead).where(Lead.user_id==user.id)).all()],key=lambda l:l['score']['value'],reverse=True)

def _lead_identity(item):
    clean=lambda value: ' '.join((value or '').casefold().split())
    digits=lambda value: ''.join(ch for ch in (value or '') if ch.isdigit())
    return (
        clean(item.name),
        clean(item.city),
        clean(item.address),
        digits(item.phone),
        round(float(item.latitude),5),
        round(float(item.longitude),5),
    )

def _normalized_category(value:str)->str:
    return ' '.join((value or '').casefold().split())


def _distance_km(a:Lead,b:Lead)->float:
    lat1=math.radians(float(a.latitude)); lat2=math.radians(float(b.latitude))
    dlat=lat2-lat1
    dlon=math.radians(float(b.longitude)-float(a.longitude))
    value=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371.0088*(2*math.atan2(math.sqrt(value),math.sqrt(max(0.0,1-value))))


def _competitive_site_state(lead:Lead)->str:
    status=str(lead.website_status or 'unknown')
    if status=='none':
        return 'missing'
    profile=_json_object(getattr(lead,'website_intelligence_json','{}'),{})
    host=''
    if lead.website:
        try:
            from urllib.parse import urlparse
            host=(urlparse(lead.website).hostname or '').casefold().rstrip('.')
        except ValueError:
            host=''
    aggregators=('linktr.ee','beacons.ai','bio.site','campsite.bio','taplink.cc','instagram.com','facebook.com','wa.me','whatsapp.com')
    free_hosts=('wixsite.com','wordpress.com','weebly.com','webflow.io','carrd.co','sites.google.com','my.canva.site','godaddysites.com','strikingly.com','square.site','site123.me','github.io','pages.dev','netlify.app','vercel.app','web.app','blogspot.com')
    if host and any(host==suffix or host.endswith('.'+suffix) for suffix in aggregators):
        return 'missing'
    if bool(profile.get('free_host_domain')) or (host and any(host==suffix or host.endswith('.'+suffix) for suffix in free_hosts)):
        return 'weak'
    if status=='poor':
        return 'weak'
    if status=='good' and lead.website:
        return 'strong'
    if bool(profile.get('own_domain')) and lead.website:
        return 'strong'
    return 'unknown'


def _median(values:list[float])->float|None:
    if not values:
        return None
    ordered=sorted(values)
    mid=len(ordered)//2
    if len(ordered)%2:
        return float(ordered[mid])
    return float((ordered[mid-1]+ordered[mid])/2)


def _build_competitive_context(target:Lead,pool:list[Lead])->dict:
    target_niche=niche_context(target).get('key','generic')
    target_category=_normalized_category(target.category)
    candidates=[]
    for peer in pool:
        if peer.id==target.id or peer.country!=target.country:
            continue
        peer_niche=niche_context(peer).get('key','generic')
        if target_niche=='generic':
            if not target_category or _normalized_category(peer.category)!=target_category:
                continue
        elif peer_niche!=target_niche:
            continue
        distance=_distance_km(target,peer)
        if distance<=10:
            candidates.append((distance,peer))
    candidates.sort(key=lambda item:item[0])
    radius=5.0
    peers=[peer for distance,peer in candidates if distance<=radius]
    if len(peers)<4:
        radius=10.0
        peers=[peer for distance,peer in candidates if distance<=radius]
    peers=peers[:30]

    states=[_competitive_site_state(peer) for peer in peers]
    known_states=[state for state in states if state!='unknown']
    own_site=sum(1 for state in known_states if state in {'strong','weak'})
    strong_site=sum(1 for state in known_states if state=='strong')
    reviews=[float(peer.reviews) for peer in peers if (peer.reviews or 0)>0]
    ratings=[float(peer.rating) for peer in peers if (peer.rating or 0)>0]
    median_reviews=_median(reviews)
    median_rating=_median(ratings)
    target_reviews=int(target.reviews or 0)
    target_state=_competitive_site_state(target)
    peer_site_rate=round((own_site/len(known_states))*100) if known_states else 0
    strong_site_rate=round((strong_site/len(known_states))*100) if known_states else 0
    site_gap=''
    if len(peers)>=4 and len(known_states)>=3:
        if target_state=='missing' and peer_site_rate>=60:
            site_gap='missing'
        elif target_state=='weak' and strong_site_rate>=50:
            site_gap='weak'
    demand_above_median=bool(median_reviews is not None and target_reviews>=max(20,median_reviews))
    review_percentile=None
    if reviews and target_reviews>0:
        review_percentile=round(100*sum(1 for value in reviews if value<=target_reviews)/len(reviews))
    status='ready' if len(peers)>=4 and len(known_states)>=3 else 'insufficient'
    sample_quality='high' if len(peers)>=8 and len(known_states)>=6 else 'medium' if status=='ready' else 'low'
    return {
        'status':status,
        'radius_km':int(radius),
        'peers_count':len(peers),
        'known_site_peers':len(known_states),
        'peer_site_rate':peer_site_rate,
        'strong_site_rate':strong_site_rate,
        'median_reviews':round(median_reviews) if median_reviews is not None else None,
        'median_rating':round(median_rating,2) if median_rating is not None else None,
        'review_percentile':review_percentile,
        'target_site_state':target_state,
        'site_gap':site_gap,
        'demand_above_median':demand_above_median,
        'sample_quality':sample_quality,
        'niche_key':target_niche,
    }


def _set_competitive_context(lead:Lead,payload:dict,analyzed_at:int|None=None):
    encoded=json.dumps(payload if isinstance(payload,dict) else {},ensure_ascii=False,separators=(',',':'),sort_keys=True)
    current=getattr(lead,'competitive_context_json','{}') or '{}'
    if encoded==current:
        return False
    lead.competitive_context_json=encoded
    lead.competitive_analyzed_at=int(analyzed_at or time.time())
    return True


def _refresh_competitive_contexts(targets:list[Lead],pool:list[Lead]):
    now=int(time.time())
    seen=set()
    for lead in targets:
        if lead.id in seen:
            continue
        seen.add(lead.id)
        _set_competitive_context(lead,_build_competitive_context(lead,pool),now)


def _commercial_snapshot(lead:Lead)->dict:
    return {
        'reviews':int(lead.reviews or 0),
        'rating':round(float(lead.rating or 0),2),
        'website':str(lead.website or '')[:500],
        'website_status':str(lead.website_status or 'unknown')[:20],
        'phone':bool(lead.phone),
        'phone_value':str(lead.phone or '')[:30],
        'whatsapp':bool(lead.whatsapp),
        'whatsapp_value':str(lead.whatsapp or '')[:20],
        'instagram':bool(lead.instagram),
        'instagram_value':str(lead.instagram or '')[:500],
    }


def _commercial_signal_state(lead:Lead)->dict:
    return _json_object(getattr(lead,'commercial_signal_json','{}'),{})


def _sync_commercial_signals(
    lead:Lead,
    *,
    previous_snapshot:dict|None=None,
    brand_locations:int|None=None,
    observed_at:int|None=None,
    track_changes:bool=True,
):
    now=int(observed_at or time.time())
    state=_commercial_signal_state(lead)
    old=previous_snapshot if isinstance(previous_snapshot,dict) else state.get('snapshot') if isinstance(state.get('snapshot'),dict) else None
    new=_commercial_snapshot(lead)
    events=[item for item in (state.get('events') if isinstance(state.get('events'),list) else []) if isinstance(item,dict)]
    original_events=[dict(item) for item in events]

    def event(key:str,detail:str=''):
        nonlocal events
        payload={'key':key,'at':now}
        if detail:
            payload['detail']=detail[:180]
        # Avoid writing the exact same event repeatedly during one observation window.
        if events and events[-1].get('key')==key and now-int(events[-1].get('at') or 0)<3600:
            events[-1]=payload
        else:
            events.append(payload)

    if track_changes and old:
        old_reviews=int(old.get('reviews') or 0)
        new_reviews=int(new.get('reviews') or 0)
        if old_reviews>0 and new_reviews>old_reviews:
            delta=new_reviews-old_reviews
            pct=(delta/max(1,old_reviews))*100
            if delta>=25 and pct>=10:
                event('reviews_growth_strong',f'+{delta} avaliações desde a observação anterior')
            elif delta>=10 and pct>=5:
                event('reviews_growth',f'+{delta} avaliações desde a observação anterior')

        old_rating=float(old.get('rating') or 0)
        new_rating=float(new.get('rating') or 0)
        if old_rating>0 and new_rating>0 and abs(new_rating-old_rating)>=0.2:
            direction='subiu' if new_rating>old_rating else 'caiu'
            event('rating_changed',f'Nota {direction} de {old_rating:.1f} para {new_rating:.1f}')

        old_status=str(old.get('website_status') or 'unknown')
        new_status=str(new.get('website_status') or 'unknown')
        old_website=bool(old.get('website'))
        new_website=bool(new.get('website'))
        if old_website and (new_status=='none' or not new_website):
            event('website_removed','O site observado anteriormente deixou de estar confirmado')
        elif old_status=='good' and new_status=='poor':
            event('website_degraded','A auditoria atual classificou o site abaixo da observação anterior')
        elif (not old_website or old_status in {'none','unknown'}) and new_website and new_status in {'good','poor'}:
            event('website_new','Um site passou a ser confirmado para a empresa')
        elif old_status=='poor' and new_status=='good':
            event('website_improved','A auditoria atual encontrou uma presença web melhor')

        for field,key,label in (
            ('whatsapp','new_whatsapp','WhatsApp passou a estar disponível'),
            ('phone','new_phone','Telefone passou a estar disponível'),
            ('instagram','new_instagram','Instagram passou a estar disponível'),
        ):
            if not bool(old.get(field)) and bool(new.get(field)):
                event(key,label)
            elif bool(old.get(field)) and bool(new.get(field)):
                old_value=str(old.get(f'{field}_value') or '')
                new_value=str(new.get(f'{field}_value') or '')
                if old_value and new_value and old_value!=new_value:
                    event(f'{field}_changed',f'{label.split(" passou")[0]} foi alterado')

    previous_locations=max(1,int(state.get('brand_locations') or 1))
    if brand_locations is None:
        brand_locations=previous_locations
    brand_locations=max(1,int(brand_locations))
    if track_changes and previous_locations>=1 and brand_locations>previous_locations and brand_locations>=2:
        event('additional_location',f'{brand_locations} unidades com o mesmo nome estão agora na base')

    cutoff=now-(120*86400)
    events=[item for item in events if int(item.get('at') or 0)>=cutoff][-16:]
    material_changed=(
        state.get('snapshot')!=new
        or int(state.get('brand_locations') or 1)!=brand_locations
        or original_events!=events
        or not state
    )
    if not material_changed:
        return False
    payload={
        'snapshot':new,
        'brand_locations':brand_locations,
        'events':events,
        'observed_at':now,
    }
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':'),sort_keys=True)
    current=getattr(lead,'commercial_signal_json','{}') or '{}'
    if encoded==current:
        return False
    lead.commercial_signal_json=encoded
    lead.commercial_signal_analyzed_at=now
    return True


def _refresh_brand_signals(pool:list[Lead], *, track_changes:bool=True):
    groups=defaultdict(list)
    for lead in pool:
        name_key=' '.join((lead.name or '').casefold().split())
        category_key=_normalized_category(lead.category)
        if len(name_key)>=6 and category_key:
            groups[(name_key,category_key,lead.country)].append(lead)
    now=int(time.time())
    for leads_in_group in groups.values():
        count=len(leads_in_group)
        for lead in leads_in_group:
            _sync_commercial_signals(lead,brand_locations=count,observed_at=now,track_changes=track_changes)

@app.patch('/api/leads/{identifier}/watchlist')
def update_lead_watchlist(identifier:str,data:LeadWatchUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    lead=owned(db,Lead,identifier,user)
    if lead.version!=data.version:
        raise HTTPException(409,'Empresa alterada. Atualize antes de mudar o acompanhamento.')
    now=int(time.time())
    if data.enabled:
        _sync_commercial_signals(lead,observed_at=now,track_changes=False)
        lead.watchlisted=True
        lead.watch_started_at=lead.watch_started_at or now
        lead.watch_last_checked_at=now
    else:
        lead.watchlisted=False
        lead.watch_started_at=None
        lead.watch_last_checked_at=None
    db.commit()
    return lead_row(lead)


@app.get('/api/radar/map-config')
def radar_map_config(user:User=Depends(current_user)):
    limiter.check('radar-map-config:'+user.id,30,60)
    browser_key=os.getenv('RADAR_MAPTILER_API_KEY','').strip()
    style_id=os.getenv('RADAR_MAPTILER_STYLE_ID','dataviz-v4-dark').strip() or 'dataviz-v4-dark'
    return {
        'provider':'maptiler' if browser_key else 'open',
        'api_key':browser_key,
        'style_id':style_id,
    }

@app.get('/api/radar/locations')
def radar_locations(q:str='',country:str='',lang:str='en',user:User=Depends(current_user)):
    limiter.check('radar-locations:'+user.id,30,60)
    try:
        if not q.strip() and (not country or country.upper()=='BR'):
            return brazil_municipalities()
        from .location_budget import search
        return search(user.id,q,country,lang,administrative=False)
    except LocationCatalogError as exc:
        logging.getLogger('scoutliq').warning(
            'Radar location_catalog_error user=%s error=%s',
            user.id[:8],
            type(exc).__name__,
        )
        raise HTTPException(
            503,
            'Não foi possível carregar as sugestões de localização agora. Você ainda pode digitar a localização manualmente.',
        ) from exc

@app.post('/api/radar/import-google-maps')
def radar_import_google_maps(data:GoogleMapsImportInput,user:User=Depends(current_user)):
    limiter.check('radar-google-maps-import:'+user.id,12,60)
    try:
        return import_google_maps_link(data.url)
    except GoogleMapsImportTimeout as exc:
        logging.getLogger('scoutliq').warning(
            'Radar google_maps_import_timeout user=%s error=%s',
            user.id[:8],
            type(exc).__name__,
        )
        raise HTTPException(504,'O link do Google Maps demorou para responder. Tente novamente em instantes.') from exc
    except GoogleMapsImportError as exc:
        raise HTTPException(422,str(exc)) from exc
    except Exception as exc:
        logging.getLogger('scoutliq').exception(
            'Radar google_maps_import_unexpected user=%s error=%s',
            user.id[:8],
            type(exc).__name__,
        )
        raise HTTPException(503,'Não foi possível analisar esse link agora. Tente novamente em instantes.') from exc

def _event_signature(item:dict)->tuple:
    return (str(item.get('key') or ''), int(item.get('at') or 0), str(item.get('detail') or ''))


def _record_watchlist_changes(db:DBSession, lead:Lead, previous_events:set[tuple], checked_at:int):
    if not bool(getattr(lead,'watchlisted',False)):
        return
    lead.watch_last_checked_at=checked_at
    current=_commercial_signal_state(lead)
    events=[item for item in (current.get('events') if isinstance(current.get('events'),list) else []) if isinstance(item,dict)]
    fresh=[item for item in events if _event_signature(item) not in previous_events]
    if not fresh:
        return
    labels={
        'reviews_growth_strong':'Crescimento forte de avaliações',
        'reviews_growth':'Crescimento de avaliações',
        'rating_changed':'Nota alterada',
        'website_removed':'Site deixou de estar confirmado',
        'website_degraded':'Site piorou',
        'website_new':'Novo site encontrado',
        'website_improved':'Site melhorou',
        'new_whatsapp':'Novo WhatsApp encontrado',
        'new_phone':'Novo telefone encontrado',
        'new_instagram':'Novo Instagram encontrado',
        'whatsapp_changed':'WhatsApp alterado',
        'phone_changed':'Telefone alterado',
        'instagram_changed':'Instagram alterado',
        'additional_location':'Nova unidade detectada',
    }
    relevant=[]
    for item in fresh[-6:]:
        key=str(item.get('key') or '')
        if key not in labels:
            continue
        relevant.append({'key':key,'label':labels[key],'detail':str(item.get('detail') or '')[:180],'at':int(item.get('at') or checked_at)})
    if not relevant:
        return
    body=' · '.join(f"{item['label']}: {item['detail']}" if item['detail'] else item['label'] for item in relevant)[:1200]
    _add_lead_activity(db,lead,'watch_change',body,{'events':relevant},checked_at)
    lead.watch_last_event_at=checked_at


def _point_in_polygon(lng:float, lat:float, polygon:list[list[float]])->bool:
    inside=False
    j=len(polygon)-1
    for i in range(len(polygon)):
        xi,yi=polygon[i]
        xj,yj=polygon[j]
        intersects=((yi>lat)!=(yj>lat)) and (lng < (xj-xi)*(lat-yi)/((yj-yi) or 1e-12)+xi)
        if intersects:
            inside=not inside
        j=i
    return inside


def _discovery_in_territory(lead_input, query:DiscoveryQuery)->bool:
    if query.scope=='bounds' and len(query.bounds)==4:
        west,south,east,north=query.bounds
        return west<=lead_input.longitude<=east and south<=lead_input.latitude<=north
    if query.scope=='polygon' and len(query.polygon)>=3:
        return _point_in_polygon(lead_input.longitude,lead_input.latitude,query.polygon)
    return True


def _haversine_km(a:Lead,b:Lead)->float:
    radius=6371.0088
    lat1,lat2=math.radians(a.latitude),math.radians(b.latitude)
    dlat=lat2-lat1
    dlng=math.radians(b.longitude-a.longitude)
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
    return radius*2*math.asin(min(1,math.sqrt(h)))


def _similarity_score(target:Lead,candidate:Lead)->int:
    if target.id==candidate.id:
        return 0
    total=0.0
    maximum=100.0
    target_score=score(target)
    candidate_score=score(candidate)
    target_niche=((target_score.get('niche') or {}).get('key') or '')
    candidate_niche=((candidate_score.get('niche') or {}).get('key') or '')
    if target_niche and target_niche==candidate_niche:
        total+=28
    target_cat=set(_normalized_category(target.category).split())
    candidate_cat=set(_normalized_category(candidate.category).split())
    if target_cat and candidate_cat:
        if target_cat==candidate_cat:
            total+=24
        else:
            overlap=len(target_cat&candidate_cat)/max(1,len(target_cat|candidate_cat))
            total+=16*overlap
    if (target.city or '').casefold()==(candidate.city or '').casefold():
        total+=8
    if target.country==candidate.country:
        total+=2
    distance=_haversine_km(target,candidate)
    if distance<=2: total+=10
    elif distance<=5: total+=8
    elif distance<=10: total+=5
    elif distance<=25: total+=2
    trv=max(0,int(target.reviews or 0)); crv=max(0,int(candidate.reviews or 0))
    if trv and crv:
        diff=abs(math.log1p(trv)-math.log1p(crv))
        total+=max(0,10-(diff*4))
    if target.rating is not None and candidate.rating is not None:
        total+=max(0,5-abs(float(target.rating)-float(candidate.rating))*5)
    if target.website_status==candidate.website_status:
        total+=4
    target_services={item.get('key') for item in (target_score.get('service_scores') or [])[:3] if isinstance(item,dict)}
    candidate_services={item.get('key') for item in (candidate_score.get('service_scores') or [])[:3] if isinstance(item,dict)}
    if target_services and candidate_services:
        total+=6*(len(target_services&candidate_services)/max(1,len(target_services|candidate_services)))
    target_structure=int(((target_score.get('commercial_structure') or {}).get('value') or 0))
    candidate_structure=int(((candidate_score.get('commercial_structure') or {}).get('value') or 0))
    total+=max(0,3-abs(target_structure-candidate_structure)*0.03)
    return max(0,min(100,round((total/maximum)*100)))


def _monitor_seconds(interval:str)->int:
    return 7*24*60*60 if interval=='weekly' else 24*60*60

@app.post('/api/radar/interpret')
def radar_interpret(data:RadarNaturalSearchInput,user:User=Depends(current_user)):
    limiter.check('radar-interpret:'+user.id,30,60)
    plan=interpret_natural_radar_query(
        data.text,
        fallback_location=data.fallback_location,
        fallback_country=data.fallback_country,
    )
    return plan

@app.get('/api/radar/saved-searches')
def radar_saved_searches(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    items=db.scalars(
        select(RadarSavedSearch)
        .where(RadarSavedSearch.user_id==user.id)
        .order_by(RadarSavedSearch.updated_at.desc())
    ).all()
    return [saved_search_row(item) for item in items]

@app.post('/api/radar/saved-searches',status_code=201)
def create_radar_saved_search(data:RadarSavedSearchInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    if db.scalar(select(func.count()).select_from(RadarSavedSearch).where(RadarSavedSearch.user_id==user.id))>=30:
        raise HTTPException(409,'Limite de 30 buscas salvas por workspace.')
    name=' '.join(data.name.split())
    if db.scalar(select(RadarSavedSearch.id).where(RadarSavedSearch.user_id==user.id,func.lower(RadarSavedSearch.name)==name.casefold())):
        raise HTTPException(409,'Já existe uma busca salva com esse nome.')
    ids=list(data.result_ids)
    if ids:
        owned_ids=set(db.scalars(select(Lead.id).where(Lead.user_id==user.id,Lead.demo.is_(False),Lead.id.in_(ids))).all())
        if len(owned_ids)!=len(ids):
            raise HTTPException(422,'A busca contém estabelecimentos que não pertencem ao workspace.')
    now=int(time.time())
    item=RadarSavedSearch(
        user_id=user.id,
        name=name,
        query_json=json.dumps(data.query.model_dump(),ensure_ascii=False,separators=(',',':')),
        result_ids_json=json.dumps(ids,separators=(',',':')),
        last_new_count=0,
        last_run_at=now,
        monitor_enabled=False,
        monitor_interval='daily',
        next_monitor_at=None,
        last_monitor_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    return saved_search_row(item)

@app.patch('/api/radar/saved-searches/{identifier}/results')
def update_radar_saved_search_results(identifier:str,data:RadarSavedSearchResultsUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=owned(db,RadarSavedSearch,identifier,user)
    from .research_worker import MODE
    if item.monitor_enabled and MODE == 'worker':
        raise HTTPException(409, 'Resultados do monitor são gravados pelo worker; agende uma execução.')
    if item.version!=data.version:
        raise HTTPException(409,'Busca salva alterada. Atualize antes de executar novamente.')
    ids=list(data.result_ids)
    if ids:
        owned_ids=set(db.scalars(select(Lead.id).where(Lead.user_id==user.id,Lead.demo.is_(False),Lead.id.in_(ids))).all())
        if len(owned_ids)!=len(ids):
            raise HTTPException(422,'A busca contém estabelecimentos que não pertencem ao workspace.')
    previous=set(_json_object(item.result_ids_json,[]))
    current=set(ids)
    now=int(time.time())
    item.last_new_count=len(current-previous)
    item.result_ids_json=json.dumps(ids,separators=(',',':'))
    item.last_run_at=now
    if getattr(item,'monitor_enabled',False):
        item.last_monitor_at=now
        item.next_monitor_at=now+_monitor_seconds(getattr(item,'monitor_interval','daily') or 'daily')
    item.updated_at=now
    db.commit()
    return saved_search_row(item)

@app.patch('/api/radar/saved-searches/{identifier}/monitor')
def update_radar_saved_search_monitor(identifier:str,data:RadarSavedSearchMonitorUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=owned(db,RadarSavedSearch,identifier,user)
    if item.version!=data.version:
        raise HTTPException(409,'Busca salva alterada. Atualize antes de configurar o monitoramento.')
    from .search_compat import cancel_linked
    cancel_linked(db,item)
    now=int(time.time())
    if data.enabled and _json_object(item.query_json,{}).get('commercial_intent'):
        raise HTTPException(422,'A intenção comercial é executada sob demanda; monitoramentos legados continuam disponíveis.')
    item.monitor_enabled=bool(data.enabled)
    item.attempts, item.retry_at, item.worker_error = 0, 0, ''
    item.monitor_interval=data.interval
    item.next_monitor_at=(now+_monitor_seconds(data.interval)) if data.enabled else None
    item.updated_at=now
    db.commit()
    return saved_search_row(item)

@app.post('/api/radar/saved-searches/{identifier}/schedule')
def schedule_monitor(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=owned(db,RadarSavedSearch,identifier,user)
    if not item.monitor_enabled:
        raise HTTPException(409,'Ative o monitor antes de agendar.')
    if item.lease_until > int(time.time()):
        return saved_search_row(item)
    item.next_monitor_at=int(time.time())
    item.attempts, item.retry_at, item.worker_error=0,0,''
    db.commit()
    return saved_search_row(item)

@app.delete('/api/radar/saved-searches/{identifier}')
def delete_radar_saved_search(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=owned(db,RadarSavedSearch,identifier,user)
    from .prospecting import guard_saved_deletion
    guard_saved_deletion(db,item,int(time.time()))
    from .routines import cancel_saved
    from .search_compat import cancel_linked
    cancel_linked(db,item)
    cancel_saved(db,item,'Pesquisa salva removida; rotina interrompida.')
    db.delete(item)
    db.commit()
    return {'ok':True}

@app.post('/api/radar/search')
def radar_search(data:DiscoveryQuery,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    limiter.check('radar:'+user.id,10,60)
    if radar_provider is None:
        raise HTTPException(503,'A fonte de busca do Radar está desativada neste ambiente.')
    try:
        from .search_compat import collect_compatible
        batch=collect_compatible(radar_provider,data)
    except LocationNotFound:
        raise HTTPException(422,'Não encontramos essa região. Informe cidade, bairro ou região com mais detalhes.')
    except ProviderConfigurationError as exc:
        logging.getLogger('scoutliq').warning(
            'Radar provider_config_error provider=%s user=%s error=%s',
            getattr(radar_provider,'name','unknown'),
            user.id[:8],
            type(exc).__name__,
        )
        raise HTTPException(
            503,
            'A fonte de empresas do Radar ainda não está configurada neste ambiente.',
        ) from exc
    except ProviderTimeout as exc:
        logging.getLogger('scoutliq').warning('Radar timeout provider=%s user=%s',getattr(radar_provider,'name','unknown'),user.id[:8])
        raise HTTPException(504,'A fonte de empresas demorou para responder. Tente novamente em instantes.') from exc
    except ProviderError as exc:
        logging.getLogger('scoutliq').warning('Radar provider_error provider=%s user=%s status=%s error=%s',getattr(radar_provider,'name','unknown'),user.id[:8],exc.status_code,type(exc).__name__)
        detail='A fonte de empresas está indisponível no momento. Tente novamente em instantes.'
        if exc.status_code==429:
            detail='A fonte de empresas atingiu o limite temporário de consultas. Aguarde um pouco e tente novamente.'
        raise HTTPException(503,detail) from exc

    return _persist_discovery(data, batch, user, db)


def _persist_discovery(data, batch, user, db, *, commit=True):
    current=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    by_source={(lead.source,lead.source_id):lead for lead in current if lead.source_id}
    by_identity={_lead_identity(lead):lead for lead in current}
    count=len(current)
    found=[]
    created=0
    investigation_ids=[]
    workspace_limit_reached=False
    watch_before={}
    score_before={}
    for discovered in batch.results:
        if not _discovery_in_territory(discovered.lead,data):
            continue
        lead=by_source.get((batch.provider,discovered.source_id))
        if not lead:
            from .commercial_fit import same_business
            lead=next((candidate for candidate in current if same_business(candidate,discovered.lead)),None)
        if lead and bool(getattr(lead,'watchlisted',False)):
            state_before=_commercial_signal_state(lead)
            watch_before[lead.id]={_event_signature(item) for item in (state_before.get('events') if isinstance(state_before.get('events'),list) else []) if isinstance(item,dict)}
        if lead and lead.id not in score_before:
            score_before[lead.id]=int(score(lead).get('value') or 0)
        if not lead:
            if count>=2000:
                # A region-wide scan can legitimately discover more than the V1
                # workspace cap. Keep the successful portion instead of rolling
                # the entire search back with a 409. The response is marked
                # partial so the UI never pretends coverage was exhaustive.
                workspace_limit_reached=True
                continue
            lead=Lead(**discovered.lead.model_dump(),user_id=user.id,source=batch.provider,source_id=discovered.source_id)
            db.add(lead)
            db.flush()
            score_before[lead.id]=0
            _sync_commercial_signals(lead,track_changes=False)
            count+=1
            created+=1
            investigation_ids.append(lead.id)
            by_source[(batch.provider,discovered.source_id)]=lead
            by_identity[_lead_identity(lead)]=lead
            current.append(lead)
        else:
            before=_commercial_snapshot(lead)
            fresh=discovered.lead
            if fresh.reviews is not None:
                lead.reviews=fresh.reviews
            if fresh.rating is not None:
                lead.rating=fresh.rating
            if not lead.phone and fresh.phone:
                lead.phone=fresh.phone
            if not lead.whatsapp and fresh.whatsapp:
                lead.whatsapp=fresh.whatsapp
            if not lead.instagram and fresh.instagram:
                lead.instagram=fresh.instagram
            if not lead.website and lead.website_status=='unknown' and fresh.website:
                lead.website=fresh.website
                lead.website_status=fresh.website_status
            _sync_commercial_signals(lead,previous_snapshot=before,track_changes=True)
        found.append(lead)
    db.flush()
    pool=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    _refresh_brand_signals(pool)
    _refresh_competitive_contexts(found,pool)
    checked_at=int(time.time())
    handled_score_events=set()
    for lead in found:
        if bool(getattr(lead,'watchlisted',False)):
            _record_watchlist_changes(db,lead,watch_before.get(lead.id,set()),checked_at)
        if lead.id not in handled_score_events:
            handled_score_events.add(lead.id)
            old_value=int(score_before.get(lead.id,0))
            new_value=int(score(lead).get('value') or 0)
            if new_value!=old_value:
                run_automation_event(db,lead,'score_changed',{'from':old_value,'to':new_value})
    from .investigation import enqueue
    enqueue(db,user,investigation_ids,source='search')
    if commit: db.commit()
    rows=sorted((lead_row(lead) for lead in found),key=lambda item:item['score']['value'],reverse=True)
    return {
        'provider':batch.provider,
        'location':batch.location_label,
        'count':len(rows),
        'created':created,
        'results':rows,
        'complete':bool(batch.complete and not workspace_limit_reached),
        'scanned':batch.scanned,
        'result_limit':batch.result_limit,
        'scope':data.scope if data.scope in {'bounds','polygon'} else batch.scope,
        'workspace_limit_reached':workspace_limit_reached,
    }

@app.post('/api/leads/{identifier}/similar')
def find_similar_leads(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    limiter.check('similar-leads:'+user.id,6,60)
    target=owned(db,Lead,identifier,user)
    discovered_count=0
    if radar_provider is not None and not target.demo and target.city and target.category:
        try:
            batch=radar_provider.search(DiscoveryQuery(
                location=target.city,
                country=target.country,
                category=target.category,
                radius_km=10,
                scope='region',
                city_name=target.city,
            ))
            current=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
            by_source={(lead.source,lead.source_id):lead for lead in current if lead.source_id}
            by_identity={_lead_identity(lead):lead for lead in current}
            count=len(current)
            for discovered in batch.results:
                lead=by_source.get((batch.provider,discovered.source_id)) or by_identity.get(_lead_identity(discovered.lead))
                if lead is None:
                    if count>=2000:
                        break
                    lead=Lead(**discovered.lead.model_dump(),user_id=user.id,source=batch.provider,source_id=discovered.source_id)
                    db.add(lead); db.flush()
                    _sync_commercial_signals(lead,track_changes=False)
                    by_source[(batch.provider,discovered.source_id)]=lead
                    by_identity[_lead_identity(lead)]=lead
                    current.append(lead)
                    count+=1; discovered_count+=1
                else:
                    before=_commercial_snapshot(lead)
                    fresh=discovered.lead
                    if fresh.reviews is not None: lead.reviews=fresh.reviews
                    if fresh.rating is not None: lead.rating=fresh.rating
                    if not lead.phone and fresh.phone: lead.phone=fresh.phone
                    if not lead.whatsapp and fresh.whatsapp: lead.whatsapp=fresh.whatsapp
                    if not lead.instagram and fresh.instagram: lead.instagram=fresh.instagram
                    if not lead.website and lead.website_status=='unknown' and fresh.website:
                        lead.website=fresh.website; lead.website_status=fresh.website_status
                    _sync_commercial_signals(lead,previous_snapshot=before,track_changes=True)
            db.flush()
        except (ProviderError,LocationNotFound):
            logging.getLogger('scoutliq').info('Similar discovery unavailable lead=%s',target.id[:8])
    pool=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    _refresh_brand_signals(pool)
    _refresh_competitive_contexts([target],pool)
    ranked=[]
    for candidate in pool:
        if candidate.id==target.id:
            continue
        similarity=_similarity_score(target,candidate)
        if similarity<25:
            continue
        row_data=lead_row(candidate)
        row_data['similarity']=similarity
        ranked.append(row_data)
    ranked.sort(key=lambda item:(item['similarity'],item['score']['confidence']['value'],item['score']['value']),reverse=True)
    db.commit()
    return {
        'source_lead_id':target.id,
        'discovered':discovered_count,
        'count':min(20,len(ranked)),
        'results':ranked[:20],
        'basis':{'category':target.category,'city':target.city,'niche':(score(target).get('niche') or {}).get('label','')},
    }



def _set_website_intelligence(lead:Lead, payload:dict, analyzed_at:int|None=None):
    """Persist only stable, score-relevant website evidence on the lead.

    The full research/audit remains in lead_research; this compact profile lets list scoring stay cheap.
    """
    if not isinstance(payload,dict):
        return
    technologies=payload.get('technologies') if isinstance(payload.get('technologies'),list) else []
    analytics=payload.get('analytics') if isinstance(payload.get('analytics'),list) else []
    raw_findings=payload.get('findings') if isinstance(payload.get('findings'),list) else []
    findings=[]
    for item in raw_findings[:16]:
        if not isinstance(item,dict):
            continue
        key=str(item.get('key') or '')[:80]
        if not key:
            continue
        findings.append({
            'key':key,
            'severity':str(item.get('severity') or 'medium')[:12],
            'detail':str(item.get('detail') or '')[:240],
        })
    profile={
        'quality_score':payload.get('quality_score') if isinstance(payload.get('quality_score'),(int,float)) else None,
        'high_findings':int(payload.get('high_findings') or 0),
        'medium_findings':int(payload.get('medium_findings') or 0),
        'own_domain':bool(payload.get('own_domain',False)),
        'free_host_domain':bool(payload.get('free_host_domain',False)),
        'email':bool(payload.get('email',False)),
        'forms':int(payload.get('forms') or 0),
        'social':bool(payload.get('social',False)),
        'whatsapp_site':bool(payload.get('whatsapp_site',payload.get('whatsapp',False))),
        'analytics':analytics[:6],
        'technologies':technologies[:12],
        'booking':bool(payload.get('booking',False)),
        'ecommerce':bool(payload.get('ecommerce',False)),
        'catalog_or_menu':bool(payload.get('catalog_or_menu',False)),
        'live_chat':bool(payload.get('live_chat',False)),
        'mixed_content':int(payload.get('mixed_content') or 0),
        'pages_checked':int(payload.get('pages_checked') or 0),
        'findings':findings,
    }
    profile['_observed_fields']=list(payload.keys())
    lead.website_intelligence_json=json.dumps(profile,ensure_ascii=False,separators=(',',':'))
    lead.website_analyzed_at=int(analyzed_at or time.time())


def _intelligence_from_audit(audit:dict)->dict:
    signals=audit.get('signals') if isinstance(audit.get('signals'),dict) else {}
    findings=audit.get('findings') if isinstance(audit.get('findings'),list) else []
    return {
        **signals,
        **({'whatsapp_site':bool(signals['whatsapp'])} if 'whatsapp' in signals else {}),
        'quality_score':audit.get('quality_score'),
        'high_findings':sum(1 for item in findings if isinstance(item,dict) and item.get('severity')=='high'),
        'medium_findings':sum(1 for item in findings if isinstance(item,dict) and item.get('severity')=='medium'),
        'findings':findings[:16],
        'pages_checked':audit.get('pages_checked',0),
    }

def _persist_research_result(db:DBSession,user:User,lead:Lead,result:dict,*,reset_audit:bool=True):
    before_snapshot=_commercial_snapshot(lead)
    item=db.scalar(select(LeadResearch).where(LeadResearch.lead_id==lead.id,LeadResearch.user_id==user.id))
    if item is None:
        item=LeadResearch(user_id=user.id,lead_id=lead.id)
        db.add(item)
    item.status=result['status']
    item.provider=result['provider']
    item.website_url=result.get('website_url','')
    item.website_status=result.get('website_status','unknown')
    item.confidence=int(result.get('confidence',0))
    item.evidence_json=json.dumps(result.get('evidence',[]),ensure_ascii=False,separators=(',',':'))
    item.checks_json=json.dumps(result.get('checks',[]),ensure_ascii=False,separators=(',',':'))
    item.sources_json=json.dumps(result.get('sources',[]),ensure_ascii=False,separators=(',',':'))
    item.page_json=json.dumps(result.get('page',{}),ensure_ascii=False,separators=(',',':'))
    item.search_configured=bool(result.get('search_configured',False))
    item.candidates_checked=int(result.get('candidates_checked',0))
    item.fetch_errors=int(result.get('fetch_errors',0))
    item.checked_at=int(result.get('checked_at',time.time()))
    if reset_audit:
        item.audit_level='none'
        item.audit_json='{}'
        item.audited_at=None

    if result['status']=='confirmed' and result.get('website_url'):
        lead.website=result['website_url'][:500]
        lead.website_status=result.get('website_status','unknown')
        contacts=result.get('contacts') or {}
        if not lead.phone and contacts.get('phone'):
            lead.phone=str(contacts['phone'])[:30]
        if not lead.whatsapp and contacts.get('whatsapp'):
            lead.whatsapp=str(contacts['whatsapp'])[:20]
        if not lead.instagram and contacts.get('instagram'):
            lead.instagram=str(contacts['instagram'])[:500]
        page=result.get('page') or {}
        if isinstance(page,dict):
            _set_website_intelligence(lead,page,int(result.get('checked_at',time.time())))
    _sync_commercial_signals(lead,previous_snapshot=before_snapshot,track_changes=True)
    db.flush()
    from .evidence_intelligence import reconcile
    reconcile(db, lead, item)
    from .website_context import persist as persist_context
    persist_context(db, lead, item, result.get('context'), item.checked_at)
    return item

@app.get('/api/leads/{identifier}/research')
def lead_research(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    lead=owned(db,Lead,identifier,user)
    item=db.scalar(select(LeadResearch).where(LeadResearch.lead_id==lead.id,LeadResearch.user_id==user.id))
    return {'research':research_row(item)}

@app.post('/api/leads/{identifier}/research')
def run_lead_research(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    limiter.check('lead-research:'+user.id,8,60)
    lead=owned(db,Lead,identifier,user)
    if lead.demo:
        raise HTTPException(422,'A pesquisa web não é executada em estabelecimentos fictícios.')
    try:
        result=website_researcher.research(lead,user.locale)
    except SearchConfigurationError as exc:
        logging.getLogger('scoutliq').warning('Lead research search_config_error user=%s lead=%s',user.id[:8],lead.id[:8])
        raise HTTPException(503,'A pesquisa web está configurada com uma chave inválida.') from exc
    except ResearchError as exc:
        logging.getLogger('scoutliq').warning('Lead research provider_error user=%s lead=%s error=%s',user.id[:8],lead.id[:8],type(exc).__name__)
        raise HTTPException(503,'Não foi possível concluir a pesquisa web agora. Tente novamente em instantes.') from exc

    item=_persist_research_result(db,user,lead,result,reset_audit=True)
    db.flush()
    pool=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    _refresh_competitive_contexts([lead],pool)
    db.commit()
    db.refresh(lead)
    db.refresh(item)
    return {'lead':lead_row(lead),'research':research_row(item)}

@app.post('/api/leads/{identifier}/research/deep')
def run_lead_deep_research(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    limiter.check('lead-deep-research:'+user.id,4,60)
    lead=owned(db,Lead,identifier,user)
    if lead.demo:
        raise HTTPException(422,'A auditoria não é executada em estabelecimentos fictícios.')
    item=db.scalar(select(LeadResearch).where(LeadResearch.lead_id==lead.id,LeadResearch.user_id==user.id))
    try:
        if item is None or item.status!='confirmed' or not item.website_url:
            result=website_researcher.research(lead,user.locale)
            item=_persist_research_result(db,user,lead,result,reset_audit=True)
            if result.get('status')!='confirmed' or not result.get('website_url'):
                db.flush()
                pool=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
                _refresh_competitive_contexts([lead],pool)
                db.commit()
                db.refresh(lead)
                db.refresh(item)
                return {'lead':lead_row(lead),'research':research_row(item),'audit_unavailable':True}
        audit=website_researcher.deep_audit(lead,item.website_url or lead.website)
    except SearchConfigurationError as exc:
        raise HTTPException(503,'A pesquisa web está configurada com uma chave inválida.') from exc
    except ResearchError as exc:
        logging.getLogger('scoutliq').warning('Lead deep audit provider_error user=%s lead=%s error=%s',user.id[:8],lead.id[:8],type(exc).__name__)
        raise HTTPException(503,'Não foi possível concluir a auditoria do site agora.') from exc

    before_snapshot=_commercial_snapshot(lead)
    item.audit_level='deep'
    item.audit_json=json.dumps(audit,ensure_ascii=False,separators=(',',':'))
    item.audited_at=int(audit.get('audited_at',time.time()))
    item.website_status=str(audit.get('website_status','unknown'))[:20]
    lead.website_status=item.website_status
    _set_website_intelligence(lead,_intelligence_from_audit(audit),item.audited_at)
    from .website_context import persist as persist_context
    persist_context(db, lead, item, audit.get('context'), item.audited_at)
    _sync_commercial_signals(lead,previous_snapshot=before_snapshot,track_changes=True)
    db.flush()
    pool=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    _refresh_competitive_contexts([lead],pool)
    db.commit()
    db.refresh(lead)
    db.refresh(item)
    return {'lead':lead_row(lead),'research':research_row(item)}


@app.post('/api/leads/{identifier}/reanalysis')
def intelligent_lead_reanalysis(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    """Use the cheapest useful research step to improve evidence coverage.

    The endpoint never manufactures evidence: web discovery runs when identity/site
    coverage is weak or stale, deep audit runs only for a confirmed website, and
    local competitive context is refreshed from the user's own Radar dataset.
    """
    limiter.check('lead-reanalysis:'+user.id,4,60)
    lead=owned(db,Lead,identifier,user)
    if lead.demo:
        raise HTTPException(422,'A reanálise não é executada em estabelecimentos fictícios.')

    before=score(lead)
    before_conf=int((before.get('confidence') or {}).get('value') or 0)
    now=int(time.time())
    cutoff=now-(30*86400)
    item=db.scalar(select(LeadResearch).where(LeadResearch.lead_id==lead.id,LeadResearch.user_id==user.id))
    actions=[]

    research_fresh=bool(item and int(item.checked_at or 0)>=cutoff)
    need_web=bool(
        item is None
        or not research_fresh
        or (before_conf<55 and item.status!='confirmed')
    )

    try:
        if need_web:
            result=website_researcher.research(lead,user.locale)
            item=_persist_research_result(db,user,lead,result,reset_audit=True)
            actions.append('web_research')

        profile=_json_object(getattr(lead,'website_intelligence_json','{}'),{})
        audit_fresh=bool(item and item.audit_level=='deep' and int(item.audited_at or 0)>=cutoff)
        website_verified=bool(item and item.status=='confirmed' and item.website_url)
        need_deep=bool(
            website_verified
            and (
                not audit_fresh
                or int(profile.get('pages_checked') or 0)<2
            )
        )
        if need_deep:
            before_snapshot=_commercial_snapshot(lead)
            audit=website_researcher.deep_audit(lead,item.website_url or lead.website)
            item.audit_level='deep'
            item.audit_json=json.dumps(audit,ensure_ascii=False,separators=(',',':'))
            item.audited_at=int(audit.get('audited_at',time.time()))
            item.website_status=str(audit.get('website_status','unknown'))[:20]
            lead.website_status=item.website_status
            _set_website_intelligence(lead,_intelligence_from_audit(audit),item.audited_at)
            from .website_context import persist as persist_context
            persist_context(db, lead, item, audit.get('context'), item.audited_at)
            _sync_commercial_signals(lead,previous_snapshot=before_snapshot,track_changes=True)
            actions.append('deep_audit')
    except SearchConfigurationError as exc:
        raise HTTPException(503,'A pesquisa web está configurada com uma chave inválida.') from exc
    except ResearchError as exc:
        logging.getLogger('scoutliq').warning('Lead intelligent reanalysis failed user=%s lead=%s error=%s',user.id[:8],lead.id[:8],type(exc).__name__)
        raise HTTPException(503,'Não foi possível aprofundar esta oportunidade agora. Tente novamente em instantes.') from exc

    db.flush()
    pool=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    previous_context=getattr(lead,'competitive_context_json','{}') or '{}'
    _refresh_competitive_contexts([lead],pool)
    if (getattr(lead,'competitive_context_json','{}') or '{}')!=previous_context:
        actions.append('competitive_refresh')
    db.commit()
    db.refresh(lead)
    if item is not None:
        db.refresh(item)
    after=score(lead)
    after_conf=int((after.get('confidence') or {}).get('value') or 0)
    status='improved' if after_conf>before_conf else 'up_to_date' if not actions else 'checked'
    return {
        'lead':lead_row(lead),
        'research':research_row(item),
        'actions':actions,
        'status':status,
        'before_confidence':before_conf,
        'after_confidence':after_conf,
    }



@app.post('/api/leads/{identifier}/enrich')
def enrich_lead_waterfall(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    """Enrich one business progressively while keeping provenance for every accepted field."""
    limiter.check('lead-enrichment:'+user.id,6,60)
    lead=owned(db,Lead,identifier,user)
    if lead.demo:
        raise HTTPException(422,'O enriquecimento não é executado em estabelecimentos fictícios.')

    now=int(time.time())
    before_snapshot=_commercial_snapshot(lead)
    profile=start_enrichment_profile(lead,now)
    research_item=db.scalar(select(LeadResearch).where(LeadResearch.lead_id==lead.id,LeadResearch.user_id==user.id))

    # 1) Provider details: cheap and authoritative when the Radar source exposes a detail endpoint.
    try:
        values=provider_enrichment_values(radar_provider,lead)
        if values:
            changed=apply_enrichment_values(profile,lead,values,f'provider:{getattr(radar_provider,"name","radar")}',92,now)
            record_enrichment_attempt(profile,f'provider:{getattr(radar_provider,"name","radar")}','used' if changed else 'checked',changed)
        else:
            record_enrichment_attempt(profile,'provider','unavailable',[])
    except (ProviderError,ProviderTimeout,ProviderConfigurationError) as exc:
        record_enrichment_attempt(profile,'provider','failed',[],type(exc).__name__)

    # 2) Web research: only spend the slower lookup when some commercial identity field is still missing
    # or the website has never been verified.
    need_web=bool(enrichment_missing(profile) or lead.website_status=='unknown')
    if need_web:
        try:
            result=website_researcher.research(lead,user.locale)
            research_item=_persist_research_result(db,user,lead,result,reset_audit=research_item is None)
            profile['observed_contacts']=json.loads(lead.enrichment_json or '{}').get('observed_contacts',[])
            values=research_enrichment_values(result)
            confidence=max(55,min(int(result.get('confidence') or 0),100))
            changed=apply_enrichment_values(profile,lead,values,'web_research',confidence,int(result.get('checked_at') or now))
            record_enrichment_attempt(profile,'web_research','used' if changed else 'checked',changed)
        except SearchConfigurationError as exc:
            record_enrichment_attempt(profile,'web_research','failed',[],'search_not_configured')
        except ResearchError as exc:
            logging.getLogger('scoutliq').info('Lead enrichment web step failed user=%s lead=%s error=%s',user.id[:8],lead.id[:8],type(exc).__name__)
            record_enrichment_attempt(profile,'web_research','failed',[],type(exc).__name__)
    else:
        record_enrichment_attempt(profile,'web_research','skipped',[],'coverage_complete')

    _sync_commercial_signals(lead,previous_snapshot=before_snapshot,track_changes=True)
    profile=finalize_enrichment(profile,lead,now)
    _add_lead_activity(db,lead,'note','Dados enriquecidos em cascata.',{'enrichment':True,'coverage':profile.get('coverage',0)},created_at=now)
    run_automation_event(db,lead,'enriched',{'coverage':profile.get('coverage',0)})
    db.flush()
    pool=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    _refresh_competitive_contexts([lead],pool)
    db.commit()
    db.refresh(lead)
    if research_item is not None:
        db.refresh(research_item)
    return {'lead':lead_row(lead),'enrichment':profile,'research':research_row(research_item)}


def _research_batch_row(db:DBSession,batch:ResearchBatch,include_details=True):
    items=db.scalars(
        select(ResearchBatchItem)
        .where(ResearchBatchItem.batch_id==batch.id)
        .order_by(ResearchBatchItem.position.asc())
    ).all()
    counts=defaultdict(int)
    for item in items:
        counts[item.status]+=1
    processed=counts['done']+counts['error']+counts['skipped']+counts['cancelled']
    leads={lead.id:lead for lead in db.scalars(select(Lead).where(Lead.user_id==batch.user_id,Lead.id.in_([item.lead_id for item in items]))).all()} if items and include_details else {}
    from .investigation import projection
    researches={r.lead_id:r for r in db.scalars(select(LeadResearch).where(LeadResearch.user_id==batch.user_id,LeadResearch.lead_id.in_(list(leads))))} if include_details else {}
    return {
        'id':batch.id,
        'mode':batch.mode,
        'ordinal':batch.ordinal,
        'execution_mode':__import__('backend.research_worker',fromlist=['MODE']).MODE,
        'status':batch.status,
        'requested_count':batch.requested_count,
        'skipped_recent':batch.skipped_recent,
        'total':len(items),
        'processed':processed,
        'pending':counts['pending'],
        'running':counts['running'],
        'done':counts['done'],
        'errors':counts['error'],
        'created_at':batch.created_at,
        'updated_at':batch.updated_at,
        'completed_at':batch.completed_at,
        'items':[
            {
                'lead_id':item.lead_id,
                'name':leads[item.lead_id].name if item.lead_id in leads else '',
                'status':item.status,
                'outcome':item.outcome,
                'qualification':projection(leads[item.lead_id],researches.get(item.lead_id),item) if item.lead_id in leads else None,
                'attempts':item.attempts, 'retry_at':item.retry_at, 'lease_until':item.lease_until,
                'error':item.error,
            }
            for item in items if include_details
        ],
    }


def _research_batch_owned(db:DBSession,identifier:str,user:User):
    batch=db.scalar(select(ResearchBatch).where(ResearchBatch.id==identifier,ResearchBatch.user_id==user.id))
    if batch is None:
        raise HTTPException(404,'Fila de pesquisa não encontrada.')
    return batch


@app.get('/api/research/batches/active')
def active_research_batch(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    batch=db.scalar(
        select(ResearchBatch)
        .where(ResearchBatch.user_id==user.id,ResearchBatch.status.in_(['pending','running','paused']))
        .order_by(ResearchBatch.created_at.desc())
    )
    return {'batch':_research_batch_row(db,batch) if batch else None}


@app.get('/api/research/batches/{identifier}')
def get_research_batch(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    batch = _research_batch_owned(db, identifier, user)
    completed = select(ResearchBatchItem.lead_id).where(ResearchBatchItem.batch_id == batch.id, ResearchBatchItem.status == 'done')
    leads = db.scalars(select(Lead).where(Lead.user_id == user.id, Lead.id.in_(completed))).all()
    return {'batch': _research_batch_row(db, batch), 'leads': [lead_row(lead) for lead in leads]}


@app.post('/api/research/batches',status_code=201)
def create_research_batch(data:ResearchBatchInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    limiter.check('research-batch-create:'+user.id,10,60)
    from .investigation import lock_user
    lock_user(db,user)
    lead_rows=db.scalars(select(Lead).where(Lead.user_id==user.id,Lead.id.in_(data.lead_ids))).all()
    by_id={lead.id:lead for lead in lead_rows}
    if len(by_id)!=len(data.lead_ids):
        raise HTTPException(404,'Um dos estabelecimentos selecionados não existe mais.')

    pending_ids=set(db.scalars(select(ResearchBatchItem.lead_id).join(ResearchBatch).where(ResearchBatch.user_id==user.id,ResearchBatch.status.in_(['pending','running','paused']),ResearchBatchItem.status.in_(['pending','running']))))
    research_rows=db.scalars(
        select(LeadResearch).where(LeadResearch.user_id==user.id,LeadResearch.lead_id.in_(data.lead_ids))
    ).all()
    research_by_lead={item.lead_id:item for item in research_rows}
    cutoff=int(time.time())-(data.stale_days*86400)
    queued=[]
    skipped=0
    for lead_id in data.lead_ids:
        lead=by_id[lead_id]
        if lead.demo or lead_id in pending_ids:
            skipped+=1
            continue
        item=research_by_lead.get(lead_id)
        fresh=False
        if item and data.stale_days>0:
            if data.mode=='deep':
                fresh=item.audit_level=='deep' and bool(item.audited_at) and int(item.audited_at or 0)>=cutoff
            else:
                fresh=bool(item.checked_at) and int(item.checked_at)>=cutoff
        if fresh:
            skipped+=1
            continue
        queued.append(lead_id)

    now=int(time.time())
    batch=ResearchBatch(
        user_id=user.id,
        mode=data.mode,
        status='pending' if queued else 'completed',
        requested_count=len(data.lead_ids),
        skipped_recent=skipped,
        created_at=now,
        updated_at=now,
        completed_at=None if queued else now,
    )
    db.add(batch)
    db.flush()
    for position,lead_id in enumerate(queued):
        db.add(ResearchBatchItem(batch_id=batch.id,lead_id=lead_id,position=position,status='pending'))
    db.commit()
    db.refresh(batch)
    return {'batch':_research_batch_row(db,batch),'existing':False}


@app.post('/api/research/batches/{identifier}/step')
def step_research_batch(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    from .research_worker import MODE, claim, execute
    batch = _research_batch_owned(db, identifier, user)
    if MODE != 'legacy':
        raise HTTPException(409, 'Execução controlada pelo worker. O navegador deve apenas consultar o progresso.')
    db.rollback()
    task = claim(batch_id=identifier)
    changed_lead_id = None
    if task:
        task_item = db.get(ResearchBatchItem, task['id'])
        changed_lead_id = task_item.lead_id if task_item else None
        db.rollback()
        execute(task)
    db.expire_all()
    changed = db.get(Lead, changed_lead_id) if changed_lead_id else None
    return {'batch': _research_batch_row(db, _research_batch_owned(db, identifier, user)), 'lead': lead_row(changed) if changed else None}


@app.post('/api/research/batches/{identifier}/pause')
def pause_research_batch(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    batch=_research_batch_owned(db,identifier,user)
    if batch.status in ('completed','cancelled'):
        return {'batch':_research_batch_row(db,batch)}
    from .smart_search import sync_batch_control
    sync_batch_control(db,batch,'pause')
    from .investigation import fence_control
    fence_control(db,batch,int(time.time()))
    batch.status='paused'
    batch.updated_at=int(time.time())
    db.commit()
    return {'batch':_research_batch_row(db,batch)}


@app.post('/api/research/batches/{identifier}/resume')
def resume_research_batch(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    batch=_research_batch_owned(db,identifier,user)
    if batch.status=='paused':
        from .smart_search import sync_batch_control
        sync_batch_control(db,batch,'resume')
        batch.status='pending'
        batch.updated_at=int(time.time())
        db.commit()
    return {'batch':_research_batch_row(db,batch)}


@app.post('/api/research/batches/{identifier}/cancel')
def cancel_research_batch(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    batch=_research_batch_owned(db,identifier,user)
    if batch.status=='completed':
        return {'batch':_research_batch_row(db,batch)}
    from .smart_search import sync_batch_control
    sync_batch_control(db,batch,'cancel')
    from .investigation import fence_control
    fence_control(db,batch,int(time.time()))
    now=int(time.time())
    items=db.scalars(select(ResearchBatchItem).where(ResearchBatchItem.batch_id==batch.id,ResearchBatchItem.status.in_(['pending','running']))).all()
    for item in items:
        item.status='cancelled'
        item.finished_at=now
    batch.status='cancelled'
    batch.updated_at=now
    batch.completed_at=now
    db.commit()
    return {'batch':_research_batch_row(db,batch)}


def _automation_owned(db:DBSession,identifier:str,user:User):
    item=db.scalar(select(AutomationRule).where(AutomationRule.id==identifier,AutomationRule.user_id==user.id))
    if item is None:
        raise HTTPException(404,'Automação não encontrada.')
    return item


@app.get('/api/automations')
def list_automations(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    rules=db.scalars(select(AutomationRule).where(AutomationRule.user_id==user.id).order_by(AutomationRule.created_at.desc())).all()
    return [automation_rule_row(item) for item in rules]


@app.post('/api/automations',status_code=201)
def create_automation(data:AutomationRuleInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    if db.scalar(select(func.count()).select_from(AutomationRule).where(AutomationRule.user_id==user.id))>=50:
        raise HTTPException(409,'Limite atual: 50 automações por operação.')
    now=int(time.time())
    item=AutomationRule(
        user_id=user.id,
        name=data.name,
        enabled=data.enabled,
        trigger=data.trigger,
        conditions_json=json.dumps([entry.model_dump() for entry in data.conditions],ensure_ascii=False,separators=(',',':')),
        actions_json=json.dumps([entry.model_dump() for entry in data.actions],ensure_ascii=False,separators=(',',':')),
        stop_json=json.dumps(data.stop.model_dump(),ensure_ascii=False,separators=(',',':')),
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return automation_rule_row(item)


@app.put('/api/automations/{identifier}')
def update_automation(identifier:str,data:AutomationRuleUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_automation_owned(db,identifier,user)
    if item.version!=data.version:
        raise HTTPException(409,'Esta automação mudou em outra sessão. Atualize e tente novamente.')
    item.name=data.name
    item.enabled=data.enabled
    item.trigger=data.trigger
    item.conditions_json=json.dumps([entry.model_dump() for entry in data.conditions],ensure_ascii=False,separators=(',',':'))
    item.actions_json=json.dumps([entry.model_dump() for entry in data.actions],ensure_ascii=False,separators=(',',':'))
    item.stop_json=json.dumps(data.stop.model_dump(),ensure_ascii=False,separators=(',',':'))
    item.updated_at=int(time.time())
    db.commit()
    db.refresh(item)
    return automation_rule_row(item)


@app.patch('/api/automations/{identifier}/enabled')
def toggle_automation(identifier:str,data:AutomationToggleInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_automation_owned(db,identifier,user)
    if item.version!=data.version:
        raise HTTPException(409,'Esta automação mudou em outra sessão. Atualize e tente novamente.')
    item.enabled=data.enabled
    item.updated_at=int(time.time())
    db.commit()
    db.refresh(item)
    return automation_rule_row(item)


@app.delete('/api/automations/{identifier}')
def delete_automation(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_automation_owned(db,identifier,user)
    db.delete(item)
    db.commit()
    return {'ok':True}


@app.get('/api/automations/{identifier}/runs')
def automation_runs(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_automation_owned(db,identifier,user)
    runs=db.scalars(select(AutomationRun).where(AutomationRun.rule_id==item.id,AutomationRun.user_id==user.id).order_by(AutomationRun.created_at.desc()).limit(40)).all()
    return [automation_run_row(run) for run in runs]


@app.post('/api/automations/{identifier}/run/{lead_id}')
def run_automation_manually(identifier:str,lead_id:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_automation_owned(db,identifier,user)
    lead=owned(db,Lead,lead_id,user)
    run=execute_rule(db,item,lead,'manual',force=True)
    if run is None:
        raise HTTPException(422,'A automação não pôde ser executada neste estabelecimento.')
    db.commit()
    db.refresh(lead)
    db.refresh(run)
    return {'run':automation_run_row(run),'lead':lead_row(lead)}


@app.post('/api/leads/imported',status_code=201)
def create_imported_lead(data:ImportedLeadInput,to_pipeline:bool=False,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    if db.scalar(select(func.count()).select_from(Lead).where(Lead.user_id==user.id))>=2000:
        raise HTTPException(409,'Limite da V1: 2.000 estabelecimentos por operação.')
    if data.lead.website_status=='none' and data.lead.website:
        raise HTTPException(422,'Remova o endereço do site ou altere a situação do site.')
    current=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    if any(lead.source==data.source and lead.source_id==data.source_id for lead in current):
        raise HTTPException(409,'Este estabelecimento já foi importado anteriormente.')
    imported_identity=_lead_identity(data.lead)
    if any(_lead_identity(lead)==imported_identity for lead in current):
        raise HTTPException(409,'Já existe um estabelecimento com essa identidade na sua base.')
    lead=Lead(**data.lead.model_dump(),user_id=user.id,source=data.source,source_id=data.source_id,in_pipeline=to_pipeline,pipeline_added_at=int(time.time()) if to_pipeline else None)
    _set_competitive_context(lead,_build_competitive_context(lead,current+[lead]))
    db.add(lead)
    brand_key=' '.join((lead.name or '').casefold().split())
    brand_category=_normalized_category(lead.category)
    brand_locations=1+sum(1 for item in current if ' '.join((item.name or '').casefold().split())==brand_key and _normalized_category(item.category)==brand_category and item.country==lead.country)
    _sync_commercial_signals(lead,brand_locations=brand_locations,track_changes=False)
    if to_pipeline:
        db.flush()
        _add_lead_activity(db,lead,'pipeline_added',metadata={'stage':lead.stage},created_at=lead.pipeline_added_at)
    db.commit()
    return lead_row(lead)

@app.post('/api/leads',status_code=201)
def create_lead(data:LeadInput,to_pipeline:bool=False,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    if db.scalar(select(func.count()).select_from(Lead).where(Lead.user_id==user.id))>=2000:
        raise HTTPException(409,'Limite da V1: 2.000 estabelecimentos por operação.')
    if data.website_status=='none' and data.website:
        raise HTTPException(422,'Remova o endereço do site ou altere a situação do site.')
    current=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    lead=Lead(**data.model_dump(),user_id=user.id,in_pipeline=to_pipeline,pipeline_added_at=int(time.time()) if to_pipeline else None)
    _set_competitive_context(lead,_build_competitive_context(lead,current+[lead]))
    db.add(lead)
    brand_key=' '.join((lead.name or '').casefold().split())
    brand_category=_normalized_category(lead.category)
    brand_locations=1+sum(1 for item in current if ' '.join((item.name or '').casefold().split())==brand_key and _normalized_category(item.category)==brand_category and item.country==lead.country)
    _sync_commercial_signals(lead,brand_locations=brand_locations,track_changes=False)
    if to_pipeline:
        db.flush()
        _add_lead_activity(db,lead,'pipeline_added',metadata={'stage':lead.stage},created_at=lead.pipeline_added_at)
    db.commit()
    return lead_row(lead)

@app.put('/api/leads/{identifier}')
def edit_lead(identifier:str,data:LeadUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    lead=owned(db,Lead,identifier,user)
    if lead.version!=data.version:
        raise HTTPException(409,'Registro alterado em outra sessão. Atualize antes de salvar.')
    if data.website_status=='none' and data.website:
        raise HTTPException(422,'Sem site não pode ter endereço de site.')
    previous_website=lead.website
    previous_website_status=lead.website_status
    previous_enrichment_fields=(lead.website,lead.phone,lead.whatsapp,lead.instagram)
    for key,value in data.model_dump(exclude={'version'}).items():
        setattr(lead,key,value)
    if (lead.website,lead.phone,lead.whatsapp,lead.instagram)!=previous_enrichment_fields:
        # Provenance belongs to the values that were actually checked. Manual edits start a fresh chain.
        lead.enrichment_json='{}'
        lead.enrichment_analyzed_at=None
    if lead.website!=previous_website or lead.website_status!=previous_website_status:
        # Website evidence belongs to the analyzed URL/state. Never carry it over to a manual replacement.
        lead.website_intelligence_json='{}'
        lead.website_analyzed_at=None
        research=db.scalar(select(LeadResearch).where(LeadResearch.lead_id==lead.id,LeadResearch.user_id==user.id))
        if research is not None:
            research.status='unverified'
            research.website_url=lead.website
            research.website_status=lead.website_status
            research.confidence=0
            research.evidence_json='[]'
            research.checks_json='[]'
            research.sources_json='[]'
            research.page_json='{}'
            research.audit_level='none'
            research.audit_json='{}'
            research.audited_at=None
            research.candidates_checked=0
            research.fetch_errors=0
            research.checked_at=int(time.time())
    db.flush()
    _sync_commercial_signals(lead,track_changes=False)
    pool=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    _refresh_brand_signals(pool,track_changes=False)
    _refresh_competitive_contexts([lead],pool)
    db.commit()
    return lead_row(lead)

@app.patch('/api/leads/{identifier}/stage')
def stage(identifier:str,data:StageUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    lead=owned(db,Lead,identifier,user)
    if lead.version!=data.version:
        raise HTTPException(409,'Registro alterado. Atualize antes de mover.')
    if data.stage=='won' or lead.stage=='won':
        raise HTTPException(409,'Use Registrar venda para fechar. Vendas fechadas permanecem em Clientes.')
    previous_stage=lead.stage
    was_in_pipeline=lead.in_pipeline
    now=int(time.time())
    lead.stage=data.stage
    lead.in_pipeline=True
    if not was_in_pipeline:
        lead.pipeline_added_at=lead.pipeline_added_at or now
        _add_lead_activity(db,lead,'pipeline_added',metadata={'stage':data.stage},created_at=now)
    elif previous_stage!=data.stage:
        _add_lead_activity(db,lead,'stage_changed',metadata={'from':previous_stage,'to':data.stage},created_at=now)
    if data.stage=='lost':
        _store_outcome_snapshot(lead,'lost')
        lead.next_action=''
        lead.next_action_on=None
    elif previous_stage=='lost':
        lead.outcome_snapshot_json='{}'
        lead.outcome_recorded_at=None
    db.commit()
    return lead_row(lead)

@app.patch('/api/leads/{identifier}/next-action')
def next_action(identifier:str,data:NextActionUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    lead=owned(db,Lead,identifier,user)
    if lead.version!=data.version:
        raise HTTPException(409,'Registro alterado. Atualize antes de salvar a próxima ação.')
    if not lead.in_pipeline or lead.stage in ('won','lost'):
        raise HTTPException(409,'A próxima ação só pode ser definida em uma oportunidade ativa do Pipeline.')
    if data.next_action_on and data.next_action_on < business_today(user):
        raise HTTPException(422,'A data da próxima ação não pode estar no passado.')
    action=data.next_action.strip()
    previous_action=lead.next_action
    previous_due=lead.next_action_on
    lead.next_action=action
    lead.next_action_on=str(data.next_action_on) if action and data.next_action_on else None
    if not action:
        lead.next_action_on=None
    if action!=previous_action or lead.next_action_on!=previous_due:
        _add_lead_activity(
            db,lead,'next_action' if action else 'next_action_cleared',
            body=action,
            metadata={'due_on':lead.next_action_on} if lead.next_action_on else {},
        )
    db.commit()
    return lead_row(lead)

@app.get('/api/leads/{identifier}/activities')
def lead_activities(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    lead=owned(db,Lead,identifier,user)
    items=db.scalars(
        select(LeadActivity)
        .where(LeadActivity.user_id==user.id,LeadActivity.lead_id==lead.id)
        .order_by(LeadActivity.created_at.desc())
        .limit(100)
    ).all()
    return [activity_row(item) for item in items]

@app.post('/api/leads/{identifier}/activities',status_code=201)
def create_lead_activity(identifier:str,data:LeadActivityInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    from .investigation import lock_user
    from .outreach_intelligence import recipient_blocker, recipient_identity
    from .followup import NAMESPACE
    from uuid import uuid5
    import hashlib
    limiter.check('manual-activity:'+user.id,30,60)
    from .communication import lock as communication_lock
    communication_lock(db)
    lock_user(db,user)
    lead=owned(db,Lead,identifier,user)
    signature=hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    activity_id=str(uuid5(NAMESPACE,user.id+':manual:'+str(data.request_id))) if data.request_id else None
    if activity_id:
        previous=db.get(LeadActivity,activity_id)
        if previous:
            if previous.user_id!=user.id or previous.lead_id!=lead.id or _json_object(previous.metadata_json,{}).get('request_hash')!=signature:
                raise HTTPException(409,'Identificador usado por outra atividade.')
            return {'activity':activity_row(previous),'lead':lead_row(lead)}
    if lead.contact_blocked and data.kind in ('whatsapp', 'email', 'call'):
        raise HTTPException(409,'Contato suspenso nesta oportunidade.')
    if lead.stage in ('won','lost'):
        raise HTTPException(409,'O histórico comercial só aceita novos registros em oportunidades ativas.')
    if data.kind=='note' and not data.body:
        raise HTTPException(422,'A anotação precisa ter conteúdo.')
    if data.occurred_on and data.occurred_on>business_today(user):
        raise HTTPException(422,'Atividade realizada não pode ter data futura.')
    channel=data.channel or {'email':'email','whatsapp':'whatsapp','call':'phone','meeting':'meeting'}.get(data.kind,'other')
    expected_channel={'email':'email','whatsapp':'whatsapp','call':'phone','meeting':'meeting'}.get(data.kind)
    if expected_channel and channel!=expected_channel: raise HTTPException(422,'Canal incompatível com a atividade.')
    if data.kind in ('email','whatsapp','call','proposal'):
        for candidate,raw in [('email',lead.contact),('whatsapp',lead.whatsapp)]:
            if raw:
                try: recipient=recipient_identity(candidate,raw)
                except HTTPException: continue
                if recipient_blocker(db,lead,candidate,recipient): raise HTTPException(409,'Destinatário bloqueado; registre somente uma nota de revisão.')
    occurred_at=int(time.time()) if not data.occurred_on else min(int(time.time()),int(datetime.combine(data.occurred_on,datetime.min.time(),ZoneInfo(user.timezone)).timestamp()))
    previous_contact_at=lead.last_contact_at or 0
    item=_add_lead_activity(db,lead,data.kind,data.body,metadata={'event':'manual_activity','provenance':'operator_declared',
        'occurred_at':occurred_at,'occurred_on':(data.occurred_on or business_today(user)).isoformat(),'timezone':user.timezone,
        'channel':channel,'result':data.result,'request_hash':signature,'provider_verified':False})
    if data.kind in ('email','whatsapp','call','meeting','proposal','reply'):
        lead.last_contact_at=max(previous_contact_at,occurred_at)
    if activity_id: item.id=activity_id
    if data.kind=='reply' and data.result in ('refusal','opt_out'):
        lead.contact_blocked=True;lead.contact_block_reason='Recusa declarada pelo operador; revisar histórico.'
        from .opportunity_workflow import pause_drafts
        pause_drafts(db,lead,lead.contact_block_reason)
    db.commit()
    db.refresh(item)
    return {'activity':activity_row(item),'lead':lead_row(lead)}

@app.delete('/api/leads/{identifier}')
def remove_lead(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    lead=owned(db,Lead,identifier,user)
    if lead.stage=='won':
        raise HTTPException(409,'Clientes com vendas não podem ser excluídos.')
    db.delete(lead)
    db.commit()
    return {'ok':True}


@app.get('/api/campaigns')
def campaigns(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    items=db.scalars(select(Campaign).where(Campaign.user_id==user.id).order_by(Campaign.created_at.desc())).all()
    return [campaign_row(db,item) for item in items]


@app.post('/api/campaigns',status_code=201)
def create_campaign(data:CampaignInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    now=int(time.time())
    source_search=None
    if data.source_saved_search_id:
        source_search=db.scalar(select(RadarSavedSearch).where(RadarSavedSearch.id==data.source_saved_search_id,RadarSavedSearch.user_id==user.id))
        if source_search is None:
            raise HTTPException(404,'Busca salva não encontrada.')
    item=Campaign(
        user_id=user.id,
        name=' '.join(data.name.split()),
        description=data.description.strip(),
        status=data.status,
        source_saved_search_id=data.source_saved_search_id,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.flush()
    if source_search is not None:
        ids=[value for value in _json_object(source_search.result_ids_json,[]) if isinstance(value,str)][:500]
        valid=set(db.scalars(select(Lead.id).where(Lead.user_id==user.id,Lead.demo.is_(False),Lead.id.in_(ids))).all()) if ids else set()
        for lead_id in ids:
            if lead_id in valid:
                db.add(CampaignLead(user_id=user.id,campaign_id=item.id,lead_id=lead_id,source='saved_search',added_at=now))
    db.commit()
    db.refresh(item)
    return campaign_row(db,item)


@app.put('/api/campaigns/{identifier}')
def update_campaign(identifier:str,data:CampaignUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_campaign_owned(db,identifier,user)
    if item.version!=data.version:
        raise HTTPException(409,'Campanha alterada em outra sessão. Atualize antes de salvar.')
    if data.source_saved_search_id:
        saved=db.scalar(select(RadarSavedSearch.id).where(RadarSavedSearch.id==data.source_saved_search_id,RadarSavedSearch.user_id==user.id))
        if saved is None:
            raise HTTPException(404,'Busca salva não encontrada.')
    item.name=' '.join(data.name.split())
    item.description=data.description.strip()
    item.status=data.status
    item.source_saved_search_id=data.source_saved_search_id
    item.updated_at=int(time.time())
    db.commit()
    return campaign_row(db,item)


@app.get('/api/campaigns/{identifier}/leads')
def campaign_leads(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_campaign_owned(db,identifier,user)
    ids=db.scalars(select(CampaignLead.lead_id).where(CampaignLead.campaign_id==item.id,CampaignLead.user_id==user.id).order_by(CampaignLead.added_at.desc())).all()
    if not ids:
        return []
    leads={lead.id:lead for lead in db.scalars(select(Lead).where(Lead.user_id==user.id,Lead.id.in_(ids))).all()}
    return [lead_row(leads[lead_id]) for lead_id in ids if lead_id in leads]


@app.post('/api/campaigns/{identifier}/leads')
def add_campaign_leads(identifier:str,data:CampaignLeadsInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_campaign_owned(db,identifier,user)
    valid=set(db.scalars(select(Lead.id).where(Lead.user_id==user.id,Lead.demo.is_(False),Lead.id.in_(data.lead_ids))).all())
    if len(valid)!=len(data.lead_ids):
        raise HTTPException(404,'Um ou mais estabelecimentos não foram encontrados.')
    existing=set(db.scalars(select(CampaignLead.lead_id).where(CampaignLead.campaign_id==item.id,CampaignLead.lead_id.in_(data.lead_ids))).all())
    now=int(time.time())
    for lead_id in data.lead_ids:
        if lead_id not in existing:
            db.add(CampaignLead(user_id=user.id,campaign_id=item.id,lead_id=lead_id,source=data.source,added_at=now))
    item.updated_at=now
    db.commit()
    return campaign_row(db,item)


@app.delete('/api/campaigns/{identifier}/leads/{lead_id}')
def remove_campaign_lead(identifier:str,lead_id:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=_campaign_owned(db,identifier,user)
    membership=db.scalar(select(CampaignLead).where(CampaignLead.campaign_id==item.id,CampaignLead.lead_id==lead_id,CampaignLead.user_id==user.id))
    if membership is None:
        raise HTTPException(404,'Estabelecimento não está nesta campanha.')
    if db.scalar(select(Sale.id).where(Sale.user_id==user.id,Sale.lead_id==lead_id,Sale.campaign_id==item.id)):
        raise HTTPException(409,'Esta empresa possui venda atribuída à campanha. Remova a atribuição antes de retirar o estabelecimento.')
    db.delete(membership)
    item.updated_at=int(time.time())
    db.commit()
    return {'ok':True}


@app.get('/api/insights/outcomes')
def outcome_insights(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    return _outcome_insights(db,user)

@app.get('/api/sales')
def sales(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    return sale_rows(db,user)

@app.post('/api/sales',status_code=201)
def create_sale(data:SaleInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    if data.sold_on>business_today(user):
        raise HTTPException(422,'A data da venda não pode estar no futuro no fuso da operação.')
    lead=owned(db,Lead,data.lead_id,user)
    if db.scalar(select(Sale.id).where(Sale.lead_id==lead.id)):
        raise HTTPException(409,'Este estabelecimento já possui uma venda.')
    if data.due_on<data.sold_on:
        raise HTTPException(422,'Vencimento deve ser igual ou posterior à venda.')
    campaign=None
    campaign_id=data.campaign_id
    if campaign_id:
        campaign=_campaign_owned(db,campaign_id,user)
        membership=db.scalar(select(CampaignLead).where(CampaignLead.campaign_id==campaign.id,CampaignLead.lead_id==lead.id,CampaignLead.user_id==user.id))
        if membership is None:
            db.add(CampaignLead(user_id=user.id,campaign_id=campaign.id,lead_id=lead.id,source='manual',added_at=int(time.time())))
    else:
        active_campaign_ids=db.scalars(
            select(CampaignLead.campaign_id)
            .join(Campaign,Campaign.id==CampaignLead.campaign_id)
            .where(CampaignLead.user_id==user.id,CampaignLead.lead_id==lead.id,Campaign.status=='active')
        ).all()
        unique=list(dict.fromkeys(active_campaign_ids))
        if len(unique)==1:
            campaign_id=unique[0]
            campaign=_campaign_owned(db,campaign_id,user)
    values=data.model_dump(exclude={'campaign_id'})
    values['campaign_id']=campaign_id
    values.update(sold_on=str(data.sold_on),due_on=str(data.due_on))
    sale=Sale(**values,user_id=user.id,demo=lead.demo)
    now=int(time.time())
    _store_outcome_snapshot(lead,'won',service=data.service)
    if not lead.in_pipeline:
        lead.pipeline_added_at=lead.pipeline_added_at or now
    lead.stage='won'
    lead.in_pipeline=True
    lead.next_action=''
    lead.next_action_on=None
    _add_lead_activity(db,lead,'sale_won',metadata={'amount_cents':data.amount_cents,'currency':data.currency,'campaign_id':campaign_id,'campaign_name':campaign.name if campaign else ''},created_at=now)
    db.add(sale)
    db.commit()
    return row(sale)

@app.patch('/api/sales/{identifier}')
def project_status(identifier:str,data:ProjectUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    sale=owned(db,Sale,identifier,user)
    sale.project_status=data.project_status
    db.commit()
    return row(sale)

@app.delete('/api/sales/{identifier}')
def remove_sale(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    sale=owned(db,Sale,identifier,user)
    lead=owned(db,Lead,sale.lead_id,user)
    db.execute(delete(Site).where(Site.sale_id==sale.id,Site.user_id==user.id))
    db.execute(delete(Payment).where(Payment.sale_id==sale.id,Payment.user_id==user.id))
    db.delete(sale)
    lead.stage='discovered'
    lead.in_pipeline=True
    lead.outcome_snapshot_json='{}'
    lead.outcome_recorded_at=None
    _add_lead_activity(db,lead,'sale_reopened',metadata={'sale_id':sale.id})
    db.commit()
    logging.getLogger('scoutliq').info('Venda excluida user=%s sale=%s lead=%s',user.id[:8],identifier[:8],lead.id[:8])
    return {'ok':True,'lead':lead_row(lead)}

@app.delete('/api/sales/{identifier}/payments/{payment_id}')
def remove_payment(identifier:str,payment_id:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    sale=owned(db,Sale,identifier,user)
    payment=db.scalar(select(Payment).where(Payment.id==payment_id,Payment.sale_id==sale.id,Payment.user_id==user.id))
    if not payment:
        raise HTTPException(404,'Recebimento não encontrado.')
    db.delete(payment)
    db.commit()
    logging.getLogger('scoutliq').info('Recebimento excluido user=%s sale=%s payment=%s',user.id[:8],identifier[:8],payment_id[:8])
    return {'ok':True}

@app.post('/api/sales/{identifier}/payments',status_code=201)
def payment(identifier:str,data:PaymentInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    if data.paid_on>business_today(user):
        raise HTTPException(422,'O recebimento não pode estar no futuro no fuso da operação.')
    # Serialize balance check and insert, including across concurrent SQLite connections.
    db.rollback()
    if engine.dialect.name=='sqlite':
        db.execute(text('BEGIN IMMEDIATE'))
    sale=db.scalar(select(Sale).where(Sale.id==identifier,Sale.user_id==user.id).with_for_update())
    if not sale:
        raise HTTPException(404,'Venda não encontrada.')
    if data.currency!=sale.currency:
        raise HTTPException(422,'A moeda do recebimento deve ser a mesma da venda.')
    prior=db.scalar(select(Payment).where(Payment.request_id==data.request_id,Payment.user_id==user.id))
    if prior:
        if prior.sale_id!=identifier or prior.amount_cents!=data.amount_cents or prior.paid_on!=str(data.paid_on) or prior.currency!=sale.currency:
            raise HTTPException(409,'Identificador de operação já utilizado.')
        return row(prior)
    total=db.scalar(select(func.coalesce(func.sum(Payment.amount_cents),0)).where(Payment.sale_id==sale.id))
    if total+data.amount_cents>sale.amount_cents:
        raise HTTPException(422,'Recebimento excede o saldo da venda.')
    if str(data.paid_on)<sale.sold_on:
        raise HTTPException(422,'Recebimento não pode ser anterior à venda.')
    item=Payment(user_id=user.id,sale_id=sale.id,amount_cents=data.amount_cents,currency=sale.currency,paid_on=str(data.paid_on),request_id=data.request_id)
    db.add(item)
    db.commit()
    return row(item)

@app.get('/api/expenses')
def expenses(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    return [row(e) for e in db.scalars(select(Expense).where(Expense.user_id==user.id).order_by(Expense.incurred_on.desc())).all()]

@app.post('/api/expenses',status_code=201)
def create_expense(data:ExpenseInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    if data.incurred_on>business_today(user):
        raise HTTPException(422,'O custo não pode estar no futuro no fuso da operação.')
    prior=db.scalar(select(Expense).where(Expense.request_id==data.request_id,Expense.user_id==user.id))
    if prior:
        if prior.description!=data.description or prior.amount_cents!=data.amount_cents or prior.incurred_on!=str(data.incurred_on) or prior.currency!=data.currency:
            raise HTTPException(409,'Identificador de operação já utilizado.')
        return row(prior)
    item=Expense(user_id=user.id,description=data.description,amount_cents=data.amount_cents,currency=data.currency,incurred_on=str(data.incurred_on),request_id=data.request_id)
    db.add(item)
    db.commit()
    return row(item)

@app.delete('/api/expenses/{identifier}')
def remove_expense(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    db.delete(owned(db,Expense,identifier,user))
    db.commit()
    return {'ok':True}

def site_row(item, user):
    result=row(item)
    today=business_today(user)
    alerts=[]
    if item.status!='archived':
        for field,label in [('renewal_on','Domínio'),('ssl_expires_on','SSL')]:
            value=getattr(item,field)
            if value:
                days=(datetime.strptime(value,'%Y-%m-%d').date()-today).days
                if days<0:
                    alerts.append(f'{label}: vencido há {abs(days)} dia(s)')
                elif days<=30:
                    alerts.append(f'{label}: vence em {days} dia(s)')
        if item.status=='issue': alerts.append('Site com problema registrado')
        if item.ssl_status in ('issue','expiring'): alerts.append('Revisar SSL')
    return {**result,'alerts':alerts,'monthly_margin_cents':item.monthly_revenue_cents-item.monthly_cost_cents}

@app.get('/api/sites')
def sites(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    return [site_row(item,user) for item in db.scalars(select(Site).where(Site.user_id==user.id).order_by(Site.name)).all()]

@app.post('/api/sites',status_code=201)
def create_site(data:SiteInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    sale=owned(db,Sale,data.sale_id,user)
    if db.scalar(select(func.count()).select_from(Site).where(Site.user_id==user.id))>=2000:
        raise HTTPException(409,'Limite da V1: 2.000 sites por operação.')
    item=Site(**data.model_dump(mode='json'),user_id=user.id,demo=sale.demo)
    db.add(item)
    db.commit()
    return site_row(item,user)

@app.put('/api/sites/{identifier}')
def edit_site(identifier:str,data:SiteUpdate,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    item=owned(db,Site,identifier,user)
    sale=owned(db,Sale,data.sale_id,user)
    if item.version!=data.version:
        raise HTTPException(409,'Site alterado em outra sessão. Atualize antes de salvar.')
    for key,value in data.model_dump(mode='json',exclude={'version'}).items():
        setattr(item,key,value)
    item.demo=sale.demo
    db.commit()
    return site_row(item,user)

@app.delete('/api/sites/{identifier}')
def remove_site(identifier:str,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    db.delete(owned(db,Site,identifier,user))
    db.commit()
    return {'ok':True}

@app.get('/api/dashboard')
def dashboard(period:str='7d',user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    if period not in ('today','7d','30d','month'):
        raise HTTPException(422,'Período inválido.')
    today=datetime.now(ZoneInfo(user.timezone)).date()
    start=today if period=='today' else today.replace(day=1) if period=='month' else today-timedelta(days=6 if period=='7d' else 29)
    sales=sale_rows(db,user)
    costs=db.scalars(select(Expense).where(Expense.user_id==user.id)).all()
    currencies=sorted(set([user.default_currency,*[s['currency'] for s in sales],*[c.currency for c in costs]]))
    by_currency={}
    for currency in currencies:
        currency_sales=[s for s in sales if s['currency']==currency]
        currency_costs=[c for c in costs if c.currency==currency]
        day_sales=[s for s in currency_sales if s['sold_on']==str(today)]
        previous=sum(s['amount_cents'] for s in currency_sales if s['sold_on']==str(today-timedelta(days=1)))
        trend=[]
        for delta in range((today-start).days+1):
            day=str(start+timedelta(days=delta))
            trend.append({'date':day,'amount_cents':sum(s['amount_cents'] for s in currency_sales if s['sold_on']==day)})
        revenue=sum(s['amount_cents'] for s in currency_sales)
        received=sum(s['received_cents'] for s in currency_sales)
        cost=sum(c.amount_cents for c in currency_costs)
        by_currency[currency]={'today_cents':sum(s['amount_cents'] for s in day_sales),'today_count':len(day_sales),'previous_cents':previous,'trend':trend,'revenue_cents':revenue,'received_cents':received,'cost_cents':cost,'profit_cents':received-cost,'receivable_cents':revenue-received,'recurring_cents':sum(s['recurring_cents'] for s in currency_sales if s['project_status']!='finished')}
    selected=by_currency.get(user.default_currency,{'today_cents':0,'today_count':0,'previous_cents':0,'trend':[],'revenue_cents':0,'received_cents':0,'cost_cents':0,'profit_cents':0,'receivable_cents':0,'recurring_cents':0})
    return {'today':str(today),**selected,'currency':user.default_currency,'by_currency':by_currency,'has_demo':any(s['demo'] for s in sales)}

@app.put('/api/settings')
def settings(data:SettingsInput,user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    for key,value in data.model_dump().items():
        setattr(user,key,value)
    db.commit()
    return public_user(user)

@app.post('/api/demo')
def demo(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    from .seed import seed_demo
    limiter.check('demo:'+user.id,3,3600)
    return {'created':seed_demo(db,user)}

@app.delete('/api/demo')
def remove_demo(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    ids=select(Sale.id).where(Sale.user_id==user.id,Sale.demo==True)
    db.execute(delete(Site).where(Site.sale_id.in_(ids),Site.user_id==user.id))
    db.execute(delete(Payment).where(Payment.sale_id.in_(ids),Payment.user_id==user.id))
    db.execute(delete(Sale).where(Sale.user_id==user.id,Sale.demo==True))
    db.execute(delete(Lead).where(Lead.user_id==user.id,Lead.demo==True))
    db.execute(delete(Expense).where(Expense.user_id==user.id,Expense.demo==True))
    db.commit()
    return {'ok':True}

@app.get('/api/export')
def export(user:User=Depends(current_user),db:DBSession=Depends(get_db)):
    limiter.check('export:'+user.id,5,60)
    lead_items=db.scalars(select(Lead).where(Lead.user_id==user.id)).all()
    campaign_items=db.scalars(select(Campaign).where(Campaign.user_id==user.id).order_by(Campaign.created_at.asc())).all()
    return {**export_followup(db,user),**export_reviews(db,user),**export_communication(db,user),**export_learning(db,user),**export_workflow(db,user),'schema_version':13,'sites':[site_row(item,user) for item in db.scalars(select(Site).where(Site.user_id==user.id)).all()],'currency':user.default_currency,'locale':user.locale,'exported_at':datetime.now(ZoneInfo('UTC')).isoformat(),'leads':[lead_row(l) for l in lead_items],'outcome_snapshots':[{'lead_id':l.id,'recorded_at':l.outcome_recorded_at,'snapshot':_json_object(l.outcome_snapshot_json,{})} for l in lead_items if _json_object(l.outcome_snapshot_json,{})],'commercial_signals':[commercial_signal_row(l) for l in lead_items],'lead_activities':[activity_row(item) for item in db.scalars(select(LeadActivity).where(LeadActivity.user_id==user.id).order_by(LeadActivity.created_at.asc())).all()],'radar_saved_searches':[saved_search_row(item) for item in db.scalars(select(RadarSavedSearch).where(RadarSavedSearch.user_id==user.id).order_by(RadarSavedSearch.updated_at.desc())).all()],'campaigns':[campaign_row(db,item) for item in campaign_items],'campaign_memberships':[row(item) for item in db.scalars(select(CampaignLead).where(CampaignLead.user_id==user.id).order_by(CampaignLead.added_at.asc())).all()],'outcome_insights':_outcome_insights(db,user),'lead_research':[research_row(item) for item in db.scalars(select(LeadResearch).where(LeadResearch.user_id==user.id)).all()],'research_batches':[_research_batch_row(db,item) for item in db.scalars(select(ResearchBatch).where(ResearchBatch.user_id==user.id).order_by(ResearchBatch.created_at.desc())).all()],'automations':[automation_rule_row(item) for item in db.scalars(select(AutomationRule).where(AutomationRule.user_id==user.id).order_by(AutomationRule.created_at.asc())).all()],'automation_runs':[automation_run_row(item) for item in db.scalars(select(AutomationRun).where(AutomationRun.user_id==user.id).order_by(AutomationRun.created_at.asc())).all()],'sales':sale_rows(db,user),'expenses':[row(e) for e in db.scalars(select(Expense).where(Expense.user_id==user.id)).all()]}

app.include_router(orliq_admin_router)

dist=ROOT/'frontend'/'dist'
if (dist/'assets').exists():
    app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')

@app.get('/{path:path}')
def spa(path:str):
    if path.startswith('api/'):
        raise HTTPException(404,'Endpoint não encontrado.')
    if not (dist/'index.html').exists():
        raise HTTPException(503,'Frontend ainda não compilado.')

    # Vite copies everything from frontend/public to the root of dist.
    # Serve those files directly (favicon, manifest, ScoutLIQ mark, PWA icons, etc.)
    # before falling back to index.html for client-side routes.
    dist_root = dist.resolve()
    candidate = (dist / path).resolve()
    if candidate.is_relative_to(dist_root) and candidate.is_file():
        return FileResponse(candidate, headers={'Cache-Control':'no-cache'})

    return FileResponse(dist/'index.html',headers={'Cache-Control':'no-cache'})
