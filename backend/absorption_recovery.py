"""Persistent absorption jobs claimed by the shared, token-fenced research executor.

Only explicit recovery requests may query a provider. No Lead, Score or outreach
side effects here. A reservation survives a lost response/process interruption.
"""
import json
import time
from sqlalchemy import select, update, delete
from .db import SessionLocal
from .models import User, Lead, ResearchExecutor
from .absorption_models import AbsorptionBatch, AbsorptionItem, AbsorptionRecovery
from .autonomy_models import WorkAttempt
from .location_budget import LocationCache
from .absorption_input import normalize, key, FIELDS
from .absorption_identity import compare, from_lead
from .absorption import canonical_json, fingerprint, audit, classify_rows, touch, lock_absorption

REQUIRED=('name','category','city','country','latitude','longitude')
ACTIVE=('pending','running','paused')


def missing(record):
    return [k for k in REQUIRED if record.get(k) in (None,'')]


def fill_missing(record, candidate):
    # Optional enrichment belongs to the existing investigation engine.
    return {**record, **{k:candidate[k] for k in missing(record) if candidate.get(k) not in (None,'')}}


def next_task(db, now):
    jobs=db.scalars(select(AbsorptionRecovery).join(User).where(User.is_active.is_(True),
        AbsorptionRecovery.status.in_(['pending','running']),AbsorptionRecovery.retry_at<=now,
        AbsorptionRecovery.lease_until<=now).order_by(AbsorptionRecovery.created_at,AbsorptionRecovery.id)).all()
    for job in jobs:
        if job.deadline<=now or job.attempts>=3:
            job.status='partial';job.error='Prazo ou limite de tentativas atingido. Resultados preservados.'
            job.lease_token='';job.lease_until=0
            continue
        job.status='running'
        return 'absorption',job
    return 'absorption',None


def fenced(db,task,now):
    fence=db.execute(update(ResearchExecutor).where(ResearchExecutor.id==1,
        ResearchExecutor.token==task['token'],ResearchExecutor.lease_until>now).values(id=1))
    if fence.rowcount!=1:return None
    job=db.get(AbsorptionRecovery,task['id'])
    if not job or job.lease_token!=task['token'] or job.status!='running':return None
    user=db.get(User,job.user_id)
    if not user or not user.is_active:return None
    lock_absorption(db,user)
    return job


def candidates_for(record,records,provider):
    result=[];seen=set()
    for raw in records[:10000]:
        if not isinstance(raw,dict):continue
        data,issues=normalize({k:v for k,v in raw.items() if k in FIELDS})
        if issues or missing(data):continue
        kind,reason=compare(record,data)
        if kind=='distinct':continue
        signature=fingerprint(data)
        if signature in seen:continue
        seen.add(signature)
        result.append({'id':signature,'record':data,'provider':provider,'observed_at':int(time.time()),
                       'match':kind,'reason':reason,'source_id':data.get('source_id','')})
        if len(result)==5:break
    return result


def lookup(provider,record,reserve):
    """Existing Geoapify primitives: administrative boundary is only a filter.
    Coordinates used for a business always come from a named POI with source ID.
    """
    from .providers import GeoapifyProvider, GEOAPIFY_DEFAULT_CATEGORIES, DiscoveryQuery
    if not isinstance(provider,GeoapifyProvider):return [],'A fonte configurada não oferece recuperação de empresas compatível.'
    if not record.get('city') or not record.get('country'):
        return [],'Informe cidade e país para delimitar a consulta externa com segurança.'
    reserve()  # Conservative reservation even if the existing geocode cache hits.
    query=DiscoveryQuery(location=record['city'],city_name=record['city'],country=record['country'],state=record.get('state',''))
    area=provider._geocode(query)
    if not area.get('place_id') or key(area.get('city') or area.get('name'))!=key(record['city']) or str(area.get('country_code','')).upper()!=record['country']:
        return [],'Limite administrativo não confirmado. Corrija a localização.'
    if record.get('state') and key(record['state']) not in (key(area.get('state')),key(area.get('state_code'))):
        return [],'Estado do limite administrativo não confirmado. Revise a localização.'
    reserve()
    response=provider._request_json('/v2/places',{'name':record['name'],'categories':','.join(GEOAPIFY_DEFAULT_CATEGORIES),
        'filter':'place:'+str(area['place_id']),'limit':5,'lang':'pt','apiKey':provider.api_key},timeout=8,max_bytes=500000)
    if not isinstance(response,dict) or not isinstance(response.get('features'),list):raise ValueError('Invalid provider shape')
    records=[]
    for feature in response['features'][:5]:
        if not isinstance(feature,dict):continue
        props=feature.get('properties')
        if not isinstance(props,dict) or not props.get('city') or not props.get('country_code'):continue
        if not isinstance(props.get('categories'),list) or not props['categories']:continue
        if any(str(c).startswith(('administrative','populated_place')) for c in props['categories']):continue
        if record.get('state') and props.get('state') and key(record['state']) not in (key(props.get('state')),key(props.get('state_code'))):continue
        if key(props['city'])!=key(record['city']) or str(props['country_code']).upper()!=record['country']:continue
        # Empty query.city_name prevents converter from replacing observed city.
        result=provider._place_to_result(feature,'',query.model_copy(update={'city_name':''}), '', (0,0),enforce_radius=False)
        if result:
            row={k:v for k,v in result.lead.model_dump().items() if k in FIELDS}
            row.update(source_name='geoapify',source_id=result.source_id)
            records.append(row)
    return records,''


class Stopped(Exception):pass
class BudgetReached(Exception):pass


def execute(task,provider=None):
    from . import main
    from .consumption import ConsumptionLimit
    from .providers import ProviderConfigurationError, LocationNotFound
    provider=provider or main.radar_provider
    now=int(time.time());external=False;cached=False;error='';retry=False;candidates=[];cache_id='';source='cache interno'
    with SessionLocal() as db:
        job=fenced(db,task,now)
        if not job:db.rollback();release(task);return False
        info=json.loads(job.state_json);cursor=info['cursor']
        if job.deadline<=now or cursor>=len(info['queue']):
            job.status='partial' if cursor<len(info['queue']) else 'completed';db.commit();release(task);return True
        entry=info['queue'][cursor];item=db.get(AbsorptionItem,entry['id'])
        if not item or item.user_id!=job.user_id or item.batch_id!=job.batch_id:db.rollback();release(task);return False
        version=item.version;record=json.loads(item.payload_json);user_id=job.user_id
        skipped=version!=entry['version'] or item.status=='imported' or not missing(record) or bool(json.loads(item.issues_json))
        if not skipped:
            leads=db.scalars(select(Lead).where(Lead.user_id==job.user_id,Lead.demo.is_(False))).all()
            candidates=candidates_for(record,[from_lead(lead) for lead in leads],'Radar interno')
            if not candidates:
                rows=db.scalars(select(AbsorptionItem).where(AbsorptionItem.user_id==job.user_id,
                    AbsorptionItem.id!=item.id,AbsorptionItem.status.in_(['ready','imported']))).all()
                candidates=candidates_for(record,[json.loads(row.payload_json) for row in rows],'Lote interno')
            cache_id=fingerprint(['absorption-v1',user_id,record,getattr(provider,'name',''),getattr(provider,'base_url',''),getattr(provider,'api_key','')])
            cache=db.get(LocationCache,cache_id)
            if not candidates and cache and cache.user_id==user_id and cache.expires_at>now:
                candidates=json.loads(cache.payload);cached=True
            external=not candidates and not cached and info['allow_external']
        db.commit()
    def reserve():
        with SessionLocal() as db:
            job=fenced(db,task,int(time.time()))
            if not job or job.deadline<=int(time.time()):raise Stopped()
            latest=db.get(AbsorptionItem,entry['id'])
            if latest.version!=version or latest.status=='imported':raise Stopped()
            state=json.loads(job.state_json)
            siblings=db.scalars(select(AbsorptionRecovery).where(AbsorptionRecovery.batch_id==job.batch_id,AbsorptionRecovery.user_id==job.user_id)).all()
            if state['calls']>=state['limit'] or sum(json.loads(j.state_json).get('calls',0) for j in siblings)>=50:raise BudgetReached()
            state['calls']+=1;job.state_json=canonical_json(state);db.commit()
    if external and not skipped:
        try:
            records,error=lookup(provider,record,reserve)
            candidates=candidates_for(record,records,getattr(provider,'name','fonte externa'))
        except Stopped:
            release(task);return False
        except (BudgetReached,ConsumptionLimit):error='Orçamento esgotado. Resultados preservados.'
        except (ProviderConfigurationError,LocationNotFound,ValueError):error='Fonte ou localização indisponível. Confira a configuração e os dados.'
        except Exception:
            error='Consulta temporariamente indisponível; tentativa limitada agendada.';retry=True
    if not candidates and not error and not skipped:
        error='Nenhuma correspondência segura. Corrija os campos ou revise a fonte.'
    now=int(time.time())
    with SessionLocal() as db:
        job=fenced(db,task,now)
        if not job:db.rollback();release(task);return False
        info=json.loads(job.state_json);item=db.get(AbsorptionItem,entry['id']);batch=db.get(AbsorptionBatch,job.batch_id)
        if job.deadline<=now:
            job.status='partial';job.error='Prazo de recuperação encerrado. Resultados anteriores preservados.'
        elif retry and job.attempts<3:
            job.status='pending';job.retry_at=now+30*2**(job.attempts-1);job.error=error
        else:
            if not skipped and item.version==version and item.status!='imported':
                confirmed=[c for c in candidates if c['match']=='confirmed']
                after=record
                # Any competing candidate requires human review, even with one exact match.
                if len(confirmed)==1 and len(candidates)==1:
                    after,issues=normalize(fill_missing(record,confirmed[0]['record']))
                    if not issues:
                        item.payload_json=canonical_json(after);item.issues_json='[]';item.suggestions_json='[]'
                    else:after=record;item.suggestions_json=canonical_json(candidates)
                else:item.suggestions_json=canonical_json(candidates)
                audit(item,'recover',record,after,error or 'Correspondência de estabelecimento.',
                    {'candidates':candidates,'automatic':after!=record,'run_id':job.id,'cache':cached})
                classify_rows(db,batch);touch(db,batch)
                if error and item.status=='pending':item.reason=error
                if external and not retry and not error:
                    db.execute(delete(LocationCache).where(LocationCache.user_id==user_id,LocationCache.expires_at<=now))
                    existing=db.get(LocationCache,cache_id)
                    if not existing:existing=LocationCache(id=cache_id,user_id=user_id);db.add(existing)
                    existing.payload=canonical_json(candidates);existing.expires_at=now+3600
            info['cursor']+=1;job.state_json=canonical_json(info);job.attempts=0;job.retry_at=0
            job.error=error
            job.status='completed' if info['cursor']>=len(info['queue']) else 'pending'
            if 'Orçamento' in error:job.status='partial'
        job.lease_token='';job.lease_until=0
        slot=db.get(ResearchExecutor,1);slot.token='';slot.lease_until=0
        attempt=db.get(WorkAttempt,task['token'])
        if attempt:attempt.status='failed' if error else 'committed';attempt.finished_at=now
        db.commit()
    return True


def release(task):
    with SessionLocal() as db:
        db.execute(update(ResearchExecutor).where(ResearchExecutor.id==1,ResearchExecutor.token==task['token']).values(token='',lease_until=0))
        db.execute(update(AbsorptionRecovery).where(AbsorptionRecovery.id==task['id'],AbsorptionRecovery.lease_token==task['token']).values(lease_token='',lease_until=0))
        db.commit()
