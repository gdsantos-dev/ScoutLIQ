"""Session-bound single-use OAuth. Tokens never enter product JSON or browser storage."""
import base64
import hashlib
import json
import logging
import secrets
import time
from uuid import UUID
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import Field
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, uid
from .schemas import StrictModel
from .security import current_user, limiter, digest
from .communication_models import OAuthState, ChannelAccount
from .communication import lock, cancel_pending, limits
from .opportunity_workflow import owned
from . import gmail_adapter as gmail

router=APIRouter(prefix='/api/communication')


class HideOAuthQuery(logging.Filter):
    def filter(self,record):
        if isinstance(record.args,tuple) and len(record.args)==5:
            args=list(record.args)
            if isinstance(args[2],str) and '/api/communication/gmail/callback' in args[2]:
                args[2]=args[2].split('?',1)[0];record.args=tuple(args)
        return True


logging.getLogger('uvicorn.access').addFilter(HideOAuthQuery())


def account_row(a):
    return {k:getattr(a,k) for k in ('id','provider','channel','identity','status','version','sync_enabled','next_sync_at','error','updated_at')} | {
        'sync':json.loads(a.sync_json),'scopes':a.scopes.split(),'delivery_diagnostics':'operator_review_required'}


@router.get('/accounts')
def accounts(user:User=Depends(current_user),db:Session=Depends(get_db)):
    try: gmail.settings();configured=True
    except gmail.ProviderUnavailable: configured=False
    return {'configured':configured,'send_limit':limits()[0],'allowed_markets':sorted(limits()[2]),
        'accounts':[account_row(a) for a in db.scalars(select(ChannelAccount).where(ChannelAccount.user_id==user.id))],
        'whatsapp_status':'contract_only'}


class Connect(StrictModel):
    account_id: UUID | None = None


@router.post('/gmail/connect')
def connect(data:Connect,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('gmail-oauth:'+user.id,5,900)
    try: config=gmail.settings()
    except gmail.ProviderUnavailable: raise HTTPException(503,'Gmail não configurado no servidor.') from None
    lock(db);now=int(time.time())
    db.execute(delete(OAuthState).where(OAuthState.expires_at<=now))
    if data.account_id: owned(db,ChannelAccount,str(data.account_id),user)
    if db.scalar(select(func.count()).select_from(ChannelAccount).where(ChannelAccount.user_id==user.id))>=3 and not data.account_id:
        raise HTTPException(409,'Limite de três contas. Reconecte uma conta existente.')
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    key=digest(state)
    row=OAuthState(id=key,user_id=user.id,session_id=request.state.session.token_hash,
        verifier=gmail.seal(verifier,user.id+':'+key),account_id=str(data.account_id) if data.account_id else None,expires_at=now+600)
    db.add(row);db.commit()
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    query={'client_id':config['client_id'],'redirect_uri':config['redirect_uri'],'response_type':'code',
        'scope':' '.join(sorted(gmail.SCOPES)),'access_type':'offline','prompt':'consent','state':state,
        'code_challenge':challenge,'code_challenge_method':'S256','include_granted_scopes':'false'}
    return {'authorization_url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(query),'expires_at':row.expires_at}


@router.get('/gmail/callback')
def callback(request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
    # Query parameters deliberately handled here: validation errors never echo an OAuth code/state.
    state=request.query_params.get('state','');code=request.query_params.get('code','');error=request.query_params.get('error','')
    limiter.check('gmail-callback:'+user.id,10,900)
    if not 30<=len(state)<=100 or len(code)>5000: raise HTTPException(400,'Retorno OAuth inválido.')
    key=digest(state);now=int(time.time())
    consumed=db.execute(update(OAuthState).where(OAuthState.id==key,OAuthState.user_id==user.id,
        OAuthState.session_id==request.state.session.token_hash,OAuthState.expires_at>now,OAuthState.used_at.is_(None)).values(used_at=now))
    if consumed.rowcount!=1: db.rollback();raise HTTPException(400,'Solicitação OAuth expirada, já utilizada ou de outra sessão.')
    row=db.get(OAuthState,key);encrypted=row.verifier;row.verifier='';db.commit()  # consume before any provider call
    if error or not code: return RedirectResponse('/#integrations?gmail=denied',status_code=303)
    try:
        verifier=gmail.unseal(encrypted,user.id+':'+key)
        credentials=gmail.exchange(code,verifier)
        adapter=gmail.GmailAdapter(credentials);profile=adapter.profile()
        if not credentials['refresh_token']: raise gmail.AuthenticationRequired('Acesso offline não concedido.')
        lock(db)
        account=owned(db,ChannelAccount,row.account_id,user) if row.account_id else db.scalar(select(ChannelAccount).where(
            ChannelAccount.user_id==user.id,ChannelAccount.provider=='gmail',ChannelAccount.identity==profile['identity']))
        if account and account.identity!=profile['identity']:
            raise gmail.AuthenticationRequired('Reconexão exige a mesma identidade.')
        if not account:
            if db.scalar(select(func.count()).select_from(ChannelAccount).where(ChannelAccount.user_id==user.id))>=3:
                raise gmail.AuthenticationRequired('Limite de contas.')
            account=ChannelAccount(id=uid(),user_id=user.id,identity=profile['identity'],cursor=profile['cursor'],version=1)
            db.add(account)
        else:
            cancel_pending(db,user.id,account_id=account.id,reason='Reconexão invalida autorizações anteriores.')
            account.version+=1
        account.credentials=gmail.seal(credentials,user.id+':'+account.id)
        account.status='connected';account.error='';account.scopes=' '.join(credentials['scopes']);account.updated_at=now
        db.commit()
    except (gmail.ProviderUnavailable,ValueError,KeyError,TypeError):
        db.rollback()
        return RedirectResponse('/#integrations?gmail=failed',status_code=303)
    return RedirectResponse('/#integrations?gmail=connected',status_code=303)


class AccountVersion(StrictModel):
    version: int = Field(strict=True,ge=1)


@router.post('/accounts/{identifier}/disconnect')
def disconnect(identifier:str,data:AccountVersion,user:User=Depends(current_user),db:Session=Depends(get_db)):
    limiter.check('gmail-disconnect:'+user.id,5,60);lock(db)
    account=owned(db,ChannelAccount,identifier,user)
    if account.status=='disconnected': return account_row(account)
    if account.version!=data.version: raise HTTPException(409,'Conta alterada.')
    encrypted=account.credentials;account.credentials='';account.status='disconnected';account.sync_enabled=0
    account.version+=1;account.updated_at=int(time.time());account.error=''
    cancel_pending(db,user.id,account_id=account.id,reason='Conta remetente desconectada.')
    db.commit()  # local revocation is immediate even if remote revocation fails
    revoked=False
    try:
        credentials=gmail.unseal(encrypted,user.id+':'+account.id)
        gmail.GmailAdapter(credentials).revoke();revoked=True
    except (gmail.ProviderUnavailable,KeyError,ValueError): pass
    if not revoked:
        account.error='Desconectada localmente. Revogação remota não confirmada; remova o acesso nas permissões da Conta Google.';db.commit()
    return account_row(account)|{'remote_revocation_confirmed':revoked}


class SyncControl(AccountVersion):
    enabled: bool


@router.post('/accounts/{identifier}/sync')
def sync_control(identifier:str,data:SyncControl,user:User=Depends(current_user),db:Session=Depends(get_db)):
    lock(db);account=owned(db,ChannelAccount,identifier,user)
    if account.version!=data.version or account.status!='connected': raise HTTPException(409,'Reconecte ou atualize a conta.')
    account.sync_enabled=int(data.enabled);account.next_sync_at=int(time.time());db.commit();return account_row(account)
