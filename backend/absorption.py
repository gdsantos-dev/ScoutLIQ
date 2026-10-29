"""External research -> owned staging -> canonical leads, never automatic outreach.

Unverified outside research is not promoted to confirmed website diagnosis or
confirmed evidence. Coordinates are mandatory to enter the current Lead model.
"""
import hashlib
import json
import time
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator, field_validator
from sqlalchemy import select, func, update
from sqlalchemy.orm import Session

from .db import get_db
from .models import Lead, User, LeadActivity
from .schemas import StrictModel, LeadInput
from .security import current_user, limiter
from .absorption_models import AbsorptionBatch, AbsorptionItem, AbsorptionRecovery

router = APIRouter(prefix='/api/absorption')

class ExternalClaim(StrictModel):
    statement: str = Field(min_length=5, max_length=350)
    source_url: str = Field(min_length=10, max_length=1000)

    @field_validator('source_url')
    @classmethod
    def validate_http_url(cls, value):
        try: parsed=urlsplit(value)
        except ValueError: raise ValueError('URL inválida')
        if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password
                or any(ord(c)<32 for c in value)):
            raise ValueError('Fonte HTTP(S) sem credenciais obrigatória')
        return value

class ResearchRecord(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(default='', max_length=80)
    city: str = Field(default='', max_length=100)
    country: str = Field(default='BR', pattern=r'^([A-Z]{2})?$')
    state: str = Field(default='',max_length=100)
    district: str = Field(default='',max_length=100)
    source_name: str = Field(default='',max_length=100)
    address: str = Field(default='', max_length=250)
    latitude: float | None = Field(default=None, ge=-85, le=85, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    rating: float | None = Field(default=None, ge=0, le=5, allow_inf_nan=False)
    reviews: int | None = Field(default=None, ge=0, le=10_000_000)
    website: str = Field(default='', max_length=500)
    instagram: str = Field(default='', max_length=500)
    phone: str = Field(default='', max_length=30)
    whatsapp: str = Field(default='', max_length=20)
    contact: str = Field(default='', max_length=100)
    notes: str = Field(default='', max_length=2000)
    source_url: str = Field(default='', max_length=1000)
    source_id: str = Field(default='', max_length=120)
    claims: list[ExternalClaim] = Field(default_factory=list, max_length=6)

    @field_validator('website','instagram','source_url')
    @classmethod
    def validate_http_url(cls, value):
        if value:
            try: parsed=urlsplit(value)
            except ValueError: raise ValueError('URL inválida')
            if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password
                    or any(ord(c)<32 for c in value)):
                raise ValueError('URLs devem ser HTTP(S) sem credenciais')
        return value

    @field_validator('whatsapp')
    @classmethod
    def validate_whatsapp(cls, value):
        import re
        if value and not re.fullmatch(r'\d{8,15}',value):
            raise ValueError('WhatsApp exige código de país e dígitos')
        return value

    @model_validator(mode='after')
    def coordinate_pair(self):
        if (self.latitude is None)!=(self.longitude is None):
            raise ValueError('Informe as duas coordenadas ou nenhuma')
        return self

class AbsorptionPreview(StrictModel):
    request_key: UUID
    source: Literal['chatgpt','json','csv','manual'] = 'chatgpt'
    records: list[ResearchRecord] = Field(min_length=1, max_length=50)

class AbsorptionCommit(StrictModel):
    payload_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirm: Literal[True]
    version: int | None = Field(default=None,ge=1)


def canonical_json(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def fingerprint(data):
    return hashlib.sha256(canonical_json(data).encode('utf-8')).hexdigest()

def norm(value):
    return ' '.join(str(value or '').casefold().split())

def digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())

def same_company(record,another):
    from .absorption_identity import compare,from_lead
    a=record.model_dump() if hasattr(record,'model_dump') else record
    b=another.model_dump() if hasattr(another,'model_dump') else from_lead(another)
    return compare(a,b)[0]=='confirmed'


def external_identity(record):
    return 'absorption:'+fingerprint(record.model_dump() if hasattr(record,'model_dump') else record)[:32]


def items_for(db,batch):
    return db.scalars(select(AbsorptionItem).where(AbsorptionItem.user_id==batch.user_id,
        AbsorptionItem.batch_id==batch.id).order_by(AbsorptionItem.position)).all()


def batch_detail(db,batch):
    items=items_for(db,batch)
    runs=db.scalars(select(AbsorptionRecovery).where(AbsorptionRecovery.user_id==batch.user_id,
        AbsorptionRecovery.batch_id==batch.id)).all()
    recovery=max(runs,key=lambda r:(json.loads(r.state_json).get('sequence',0),r.created_at,r.id),default=None)
    progress=None
    if recovery:
        info=json.loads(recovery.state_json)
        progress={'id':recovery.id,'status':recovery.status,'error':recovery.error,'processed':info.get('cursor',0),
                  'total':len(info.get('queue',[])),'calls':info.get('calls',0),'limit':info.get('limit',0)}
    return {'id':batch.id,'source':batch.source,'status':batch.status,'payload_hash':batch.payload_hash,
        'version':batch.version,'created_at':batch.created_at,'committed_at':batch.committed_at,'recovery':progress,
        'counts':{key:sum(i.status==key for i in items) for key in ('ready','pending','duplicate','imported')},
        'items':[{'id':i.id,'version':i.version,'position':i.position,'status':i.status,'reason':i.reason,
                  'lead_id':i.lead_id,'record':json.loads(i.payload_json),'original':json.loads(i.original_json),
                  'history':json.loads(i.history_json),'issues':json.loads(i.issues_json),
                  'matches':json.loads(i.matches_json),'suggestions':json.loads(i.suggestions_json)} for i in items]}


def owned_batch(db,identifier,user):
    batch=db.scalar(select(AbsorptionBatch).where(AbsorptionBatch.id==identifier,AbsorptionBatch.user_id==user.id))
    if not batch:raise HTTPException(404,'Lote não encontrado.')
    return batch


def lock_absorption(db,user):
    db.execute(update(User).where(User.id==user.id).values(id=User.id).execution_options(synchronize_session=False))


def revision(batch,version):
    if version is not None and version!=batch.version:raise HTTPException(409,'Lote alterado. Atualize antes de continuar.')


def audit(item,action,before,after,reason='',provenance=None):
    events=json.loads(item.history_json or '[]')
    if len(events)>=100:raise HTTPException(409,'Limite de correções deste registro atingido.')
    events.append({'action':action,'at':int(time.time()),'before':before,'after':after,
                   'reason':reason,'provenance':provenance or {}})
    item.history_json=canonical_json(events)
    item.version+=1


def touch(db,batch):
    db.flush();items=items_for(db,batch)
    batch.version+=1
    batch.payload_hash=fingerprint({'source':batch.source,'records':[json.loads(i.payload_json) for i in items]})
    if batch.committed_at:batch.status='partial' if any(i.status in ('pending','ready') for i in items) else 'committed'


def classify_rows(db,batch):
    from .absorption_identity import compare,from_lead
    leads=db.scalars(select(Lead).where(Lead.user_id==batch.user_id)).all()
    references=[('lead:'+lead.id,from_lead(lead),lead.id) for lead in leads]
    earlier=db.scalars(select(AbsorptionItem).join(AbsorptionBatch).where(AbsorptionItem.user_id==batch.user_id,
        AbsorptionBatch.user_id==batch.user_id,AbsorptionBatch.ordinal<batch.ordinal,AbsorptionItem.status.in_(['ready','imported']))).all()
    references += [('item:'+row.id,json.loads(row.payload_json),row.lead_id) for row in earlier]
    for item in items_for(db,batch):
        if item.status=='imported':continue
        record=json.loads(item.payload_json);matches=[];review=json.loads(item.review_json or '{}')
        for ref,other,lead_id in references:
            kind,reason=compare(record,other)
            if kind=='distinct':continue
            signature=fingerprint([ref,other])
            if kind=='possible' and signature in review.get('distinct',[]):continue
            matches.append({'ref':ref,'kind':kind,'reason':reason,'name':other.get('name',''),
                            'city':other.get('city',''),'address':other.get('address',''),'signature':signature,'lead_id':lead_id})
            if len(matches)>=8:break
        item.matches_json=canonical_json(matches)
        confirmed=next((m for m in matches if m['kind']=='confirmed'),None)
        if review.get('duplicate') and any(m['signature'] in review.get('signatures',[]) for m in matches):
            item.status='duplicate';item.reason='Duplicata confirmada pelo operador.'
        elif confirmed:
            item.status='duplicate';item.reason='Já existe um estabelecimento correspondente.'
        elif matches:
            item.status='pending';item.reason='Possível duplicata. Revise o estabelecimento antes de absorver.'
        elif json.loads(item.issues_json or '[]'):
            item.status='pending';item.reason='Corrija os campos inválidos deste registro.'
        else:
            missing=[label for field,label in [('name','nome'),('category','categoria'),('city','cidade'),('country','país')]
                     if len(str(record.get(field) or ''))<2]
            if record.get('latitude') is None or record.get('longitude') is None:missing.append('coordenadas do estabelecimento')
            item.status='pending' if missing else 'ready'
            item.reason=('Completar '+', '.join(missing)+'.')[:240] if missing else 'Elegível para absorção; pesquisa externa ainda não verificada.'
        if item.status=='ready':references.append(('item:'+item.id,record,None))
    db.flush()


@router.get('/batches')
def list_batches(user:User=Depends(current_user),db:Session=Depends(get_db)):
    batches=db.scalars(select(AbsorptionBatch).where(AbsorptionBatch.user_id==user.id).order_by(AbsorptionBatch.ordinal.desc()).limit(30)).all()
    return [{'id':b.id,'source':b.source,'status':b.status,'created_at':b.created_at,'committed_at':b.committed_at,'version':b.version} for b in batches]


@router.get('/batches/{identifier}')
def read_batch(identifier:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return batch_detail(db,owned_batch(db,identifier,user))


def create_preview(db,user,key,source,records,extra_errors=None,originals=None):
    from .absorption_input import normalize
    lock_absorption(db,user)
    signature=fingerprint({'source':source,'records':records,'originals':originals} if originals else {'source':source,'records':records})
    same=db.scalar(select(AbsorptionBatch).where(AbsorptionBatch.user_id==user.id,AbsorptionBatch.request_key==str(key)))
    if same:
        if (same.input_hash or same.payload_hash)!=signature:raise HTTPException(409,'Chave reutilizada com dados diferentes.')
        return batch_detail(db,same)
    if db.scalar(select(func.count()).select_from(AbsorptionBatch).where(AbsorptionBatch.user_id==user.id))>=200:
        raise HTTPException(409,'Limite de 200 lotes atingido. Os lotes existentes continuam disponíveis no histórico.')
    ordinal=(db.scalar(select(func.max(AbsorptionBatch.ordinal)).where(AbsorptionBatch.user_id==user.id)) or 0)+1
    batch=AbsorptionBatch(user_id=user.id,request_key=str(key),source=source,input_hash=signature,payload_hash=signature,ordinal=ordinal)
    db.add(batch);db.flush()
    for position,original in enumerate(records):
        data,issues=normalize(original)
        issues += (extra_errors or {}).get(str(position),[])
        db.add(AbsorptionItem(user_id=user.id,batch_id=batch.id,position=position,payload_json=canonical_json(data),
            original_json=canonical_json(originals[position] if originals else original),issues_json=canonical_json(issues),status='pending'))
    db.flush();classify_rows(db,batch);touch(db,batch);db.commit()
    return batch_detail(db,batch)


@router.post('/preview',status_code=201)
def preview(data:AbsorptionPreview,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('absorption-preview:'+user.id,12,60)
    return create_preview(db,user,data.request_key,data.source,[r.model_dump() for r in data.records])


class TableInput(StrictModel):
    raw:str=Field(min_length=1,max_length=48000)
    format:Literal['auto','json','csv','table']='auto'
    mapping:dict[str,str]=Field(default_factory=dict,max_length=32)
    delimiter:str|None=Field(default=None,max_length=1)

class IntakeInput(TableInput):
    request_key:UUID
    source:Literal['chatgpt','json','csv','manual']='manual'


def parsed_input(data):
    from .absorption_input import parse,ParseError
    try:return parse(data.raw,data.format,data.mapping,data.delimiter)
    except ParseError as exc:raise HTTPException(422,str(exc)) from None


@router.post('/parse')
def parse_input(data:TableInput,user:User=Depends(current_user)):
    limiter.check('absorption-parse:'+user.id,30,60)
    result=parsed_input(data)
    from .absorption_input import FIELDS
    return {**result,'fields':list(FIELDS)}


@router.post('/intake',status_code=201)
def intake(data:IntakeInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('absorption-preview:'+user.id,12,60)
    result=parsed_input(data)
    if result['mapping_required']:raise HTTPException(422,'Confira o mapeamento: cada coluna deve ter um destino único ou ser ignorada.')
    return create_preview(db,user,data.request_key,data.source,result['records'],result['row_errors'],result.get('originals'))


class EditInput(StrictModel):
    version:int=Field(ge=1)
    changes:dict=Field(min_length=1,max_length=22)
    reason:str=Field(default='Correção manual.',min_length=5,max_length=500)


def editable_item(db,batch,identifier,version):
    item=db.scalar(select(AbsorptionItem).where(AbsorptionItem.id==identifier,AbsorptionItem.batch_id==batch.id,AbsorptionItem.user_id==batch.user_id))
    if not item:raise HTTPException(404,'Registro não encontrado.')
    if item.version!=version:raise HTTPException(409,'Registro alterado. Atualize antes de editar.')
    if item.status=='imported':raise HTTPException(409,'Registro já absorvido. Edite a empresa no Radar.')
    return item


@router.patch('/batches/{identifier}/items/{item_id}')
def edit_item(identifier:str,item_id:str,data:EditInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    from .absorption_input import FIELDS,normalize
    limiter.check('absorption-edit:'+user.id,60,60)
    if any(k not in FIELDS for k in data.changes):raise HTTPException(422,'Campo não permitido.')
    if len(canonical_json(data.changes).encode())>12000:raise HTTPException(422,'Correção muito extensa.')
    lock_absorption(db,user);batch=owned_batch(db,identifier,user);item=editable_item(db,batch,item_id,data.version)
    before=json.loads(item.payload_json);after,issues=normalize({**before,**data.changes})
    if any(issue.split(':')[0] in data.changes or (issue.startswith('coordinates:') and {'latitude','longitude'} & data.changes.keys()) for issue in issues):raise HTTPException(422,'Confira o formato dos campos alterados.')
    audit(item,'edit',before,after,data.reason)
    item.payload_json=canonical_json(after);item.issues_json=canonical_json(issues)
    item.review_json='{}';item.suggestions_json='[]'
    classify_rows(db,batch);touch(db,batch);db.commit();return batch_detail(db,batch)


class DecisionInput(StrictModel):
    version:int=Field(ge=1)
    action:Literal['distinct','duplicate','accept','reject']
    suggestion_id:str=Field(default='',max_length=64)
    reason:str=Field(min_length=10,max_length=500)


@router.post('/batches/{identifier}/items/{item_id}/decision')
def decide(identifier:str,item_id:str,data:DecisionInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('absorption-edit:'+user.id,60,60)
    lock_absorption(db,user);batch=owned_batch(db,identifier,user);item=editable_item(db,batch,item_id,data.version)
    before=json.loads(item.payload_json)
    if data.action in ('accept','reject'):
        suggestion=next((s for s in json.loads(item.suggestions_json) if s['id']==data.suggestion_id),None)
        if not suggestion:raise HTTPException(409,'Sugestão não disponível. Atualize o registro.')
        after=before
        if data.action=='accept':
            from .absorption_recovery import fill_missing
            from .absorption_input import normalize
            after,issues=normalize(fill_missing(before,suggestion['record']))
            if issues:raise HTTPException(422,'A sugestão exige correção de campos antes de ser aceita.')
            item.payload_json=canonical_json(after);item.issues_json='[]'
        audit(item,data.action,before,after,data.reason,{'suggestion':suggestion})
        item.suggestions_json='[]'
    else:
        classify_rows(db,batch);matches=json.loads(item.matches_json)
        if not matches:raise HTTPException(409,'Não há duplicata para revisar.')
        if data.action=='distinct':
            if any(m['kind']=='confirmed' for m in matches):raise HTTPException(422,'Corrija o identificador ou endereço coincidente antes de distinguir as empresas.')
            item.review_json=canonical_json({'distinct':[m['signature'] for m in matches],'reason':data.reason})
        else:item.review_json=canonical_json({'duplicate':True,'reason':data.reason,'signatures':[m['signature'] for m in matches]})
        audit(item,data.action,before,before,data.reason)
    classify_rows(db,batch)
    if data.action=='duplicate':item.status='duplicate';item.reason='Duplicata confirmada pelo operador.'
    touch(db,batch);db.commit();return batch_detail(db,batch)


@router.post('/batches/{identifier}/commit')
def commit(identifier:str,data:AbsorptionCommit,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('absorption-commit:'+user.id,12,60)
    lock_absorption(db,user);batch=owned_batch(db,identifier,user)
    if batch.payload_hash!=data.payload_hash:raise HTTPException(409,'A prévia não corresponde ao conteúdo confirmado.')
    if data.version is not None and data.version!=batch.version:
        if batch.committed_at and not any(i.status=='ready' for i in items_for(db,batch)):return batch_detail(db,batch)
        revision(batch,data.version)
    classify_rows(db,batch)
    existing=db.scalars(select(Lead).where(Lead.user_id==user.id)).all();current_count=len(existing)
    from . import main as canonical
    changed=False
    investigation_ids=[]
    for item in items_for(db,batch):
        if item.status!='ready':continue
        if current_count>=2000:item.status='pending';item.reason='Limite de 2.000 oportunidades atingido.';continue
        record=ResearchRecord.model_validate_json(item.payload_json)
        payload=LeadInput(name=record.name,category=record.category,city=record.city,country=record.country,
            address=record.address,latitude=record.latitude,longitude=record.longitude,rating=record.rating,reviews=record.reviews,
            website=record.website,website_status='unknown',instagram=record.instagram,instagram_active=False,
            phone=record.phone,whatsapp=record.whatsapp,contact=record.contact,notes=record.notes)
        lead=Lead(**payload.model_dump(),user_id=user.id,source=batch.source,source_id='absorption:'+item.id,in_pipeline=False)
        canonical._set_competitive_context(lead,canonical._build_competitive_context(lead,existing+[lead]))
        existing.append(lead)
        brand_key=norm(lead.name);brand_cat=canonical._normalized_category(lead.category)
        locations=sum(1 for entry in existing if norm(entry.name)==brand_key and canonical._normalized_category(entry.category)==brand_cat and entry.country==lead.country)
        canonical._sync_commercial_signals(lead,brand_locations=locations,track_changes=False)
        db.add(lead);db.flush()
        db.add(LeadActivity(user_id=user.id,lead_id=lead.id,kind='note',
            body='Registro absorvido de pesquisa externa. Dados e alegações exigem verificação.',
            metadata_json=canonical_json({'event':'external_absorption','batch_id':batch.id,'item_id':item.id,
                'source':batch.source,'source_url':record.source_url,'source_id':record.source_id,
                'original':json.loads(item.original_json),'normalized':record.model_dump(),
                'corrections':json.loads(item.history_json),'claims':[c.model_dump() for c in record.claims],'verification':'unverified'}),created_at=int(time.time())))
        item.status='imported';item.reason='Incluído no Radar; sem envio ou contato automático.';item.lead_id=lead.id;item.version+=1
        current_count+=1;changed=True
        investigation_ids.append(lead.id)
    from .investigation import enqueue
    enqueue(db,user,investigation_ids,source='absorption')
    if changed:
        batch.committed_at=int(time.time());touch(db,batch)
    db.commit();return batch_detail(db,batch)

class RecoverInput(StrictModel):
    version:int=Field(ge=1)
    request_key:UUID
    allow_external:bool=False
    limit:int=Field(default=20,ge=1,le=50)


@router.post('/batches/{identifier}/recover',status_code=202)
def recover(identifier:str,data:RecoverInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    from .absorption_recovery import missing,ACTIVE
    limiter.check('absorption-recover:'+user.id,10,60)
    lock_absorption(db,user);batch=owned_batch(db,identifier,user)
    previous=db.scalar(select(AbsorptionRecovery).where(AbsorptionRecovery.user_id==user.id,AbsorptionRecovery.request_key==str(data.request_key)))
    if previous:
        state=json.loads(previous.state_json)
        if previous.batch_id!=batch.id or state['allow_external']!=data.allow_external or state['limit']!=data.limit:raise HTTPException(409,'Chave reutilizada com outra recuperação.')
        return batch_detail(db,batch)
    revision(batch,data.version)
    if db.scalar(select(AbsorptionRecovery.id).where(AbsorptionRecovery.user_id==user.id,AbsorptionRecovery.status.in_(ACTIVE)).limit(1)):
        raise HTTPException(409,'Conclua ou cancele a recuperação ativa antes de iniciar outra.')
    runs=db.scalars(select(AbsorptionRecovery).where(AbsorptionRecovery.user_id==user.id,AbsorptionRecovery.batch_id==batch.id)).all()
    if len(runs)>=20:raise HTTPException(409,'Limite de 20 recuperações neste lote atingido. A correção manual continua disponível.')
    queue=[{'id':i.id,'version':i.version} for i in items_for(db,batch) if i.status=='pending' and
        missing(json.loads(i.payload_json)) and not json.loads(i.issues_json) and len(json.loads(i.history_json))<100]
    if not queue:raise HTTPException(422,'Não há pendências recuperáveis. Revise erros de formato ou duplicatas.')
    if data.allow_external and sum(json.loads(r.state_json).get('calls',0) for r in runs)>=50:raise HTTPException(409,'Orçamento externo de 50 reservas por lote atingido. Use correção manual ou cache interno.')
    db.add(AbsorptionRecovery(user_id=user.id,batch_id=batch.id,request_key=str(data.request_key),deadline=int(time.time())+1800,
        state_json=canonical_json({'queue':queue,'cursor':0,'calls':0,'limit':data.limit,'allow_external':data.allow_external,'sequence':len(runs)+1})))
    touch(db,batch);db.commit();return batch_detail(db,batch)


class RecoveryControl(StrictModel):
    version:int=Field(ge=1)
    action:Literal['pause','resume','cancel']


@router.post('/batches/{identifier}/recovery/{run_id}')
def recovery_control(identifier:str,run_id:str,data:RecoveryControl,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('absorption-control:'+user.id,30,60)
    lock_absorption(db,user);batch=owned_batch(db,identifier,user);revision(batch,data.version)
    job=db.scalar(select(AbsorptionRecovery).where(AbsorptionRecovery.id==run_id,AbsorptionRecovery.user_id==user.id,AbsorptionRecovery.batch_id==batch.id))
    if not job:raise HTTPException(404,'Recuperação não encontrada.')
    allowed={'pause':('pending','running'),'resume':('paused',),'cancel':('pending','running','paused')}
    if job.status not in allowed[data.action]:raise HTTPException(409,'A recuperação mudou de estado. Atualize o lote.')
    if data.action=='resume' and job.deadline<=int(time.time()):raise HTTPException(409,'Prazo encerrado. Cancele esta execução para iniciar outra.')
    job.status={'pause':'paused','resume':'pending','cancel':'cancelled'}[data.action]
    # Invalidates in-flight results without taking the shared executor lock in reverse order.
    job.lease_token='';job.lease_until=0
    touch(db,batch);db.commit();return batch_detail(db,batch)

@router.post('/batches/{identifier}/recheck')
def recheck(identifier:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('absorption-recheck:'+user.id,30,60)
    lock_absorption(db,user);batch=owned_batch(db,identifier,user)
    classify_rows(db,batch);touch(db,batch);db.commit();return batch_detail(db,batch)
