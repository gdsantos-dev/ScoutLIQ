"""Isolated QA server/worker. Gmail HTTP replaced by synthetic responses, no internet."""
import sys
import os
import time
import json
import base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import intelligence_browser_fixture as fixture
from backend import gmail_adapter as gmail
from backend import consumption
from backend.db import SessionLocal
from backend.models import User,uid
from backend.communication_models import ChannelAccount,OutboxMessage
from sqlalchemy import select
from email import policy
from email.parser import BytesParser
from urllib.parse import urlsplit,parse_qs

os.environ.update(GMAIL_ENABLED='true',GMAIL_CLIENT_ID='qa-controlled',GMAIL_CLIENT_SECRET='qa-not-a-secret',
    GMAIL_REDIRECT_URI=f'http://localhost:{fixture.fixture.port}/api/communication/gmail/callback',
    COMMUNICATION_TOKEN_KEYS=base64.urlsafe_b64encode(b'Q'*32).decode(),  # Synthetic fixture only.
    OUTREACH_DAILY_SEND_LIMIT='100',OUTREACH_ALLOWED_MARKETS='BR')
consumption.PROVIDER_LIMITS['gmail']=1000


@consumption.metered('gmail')
def controlled(method,url,**kwargs):
    if url==gmail.TOKEN:
        return {'access_token':'controlled-access','refresh_token':'controlled-refresh','expires_in':3600,'token_type':'Bearer','scope':' '.join(gmail.SCOPES)}
    if url==gmail.REVOKE:return {}
    if url==gmail.API+'profile':return {'emailAddress':'sender@example.test','historyId':'100'}
    if url==gmail.API+'messages/send':
        raw=base64.urlsafe_b64decode(kwargs['payload']['raw']);msg=BytesParser(policy=policy.default).parsebytes(raw)
        token=str(msg['Message-ID']).split('.')[1].split('@')[0].replace('-','')
        return {'id':'sent'+token,'threadId':'thread'+token}
    if url.startswith(gmail.API+'history?'):
        with SessionLocal() as db:
            rows=db.scalars(select(OutboxMessage).where(OutboxMessage.status=='accepted')).all()
            return {'historyId':'200','history':[{'messagesAdded':[{'message':{'id':'reply'+r.id.replace('-',''),'threadId':r.thread_id}} for r in rows]}]}
    if url.startswith(gmail.API+'messages/reply'):
        token=urlsplit(url).path.rsplit('/',1)[-1].removeprefix('reply')
        with SessionLocal() as db:
            rows=db.scalars(select(OutboxMessage).where(OutboxMessage.status=='accepted')).all()
            row=next(x for x in rows if x.id.replace('-','')==token);snapshot=json.loads(row.snapshot_json)
            return {'id':'reply'+token,'threadId':row.thread_id,'labelIds':['INBOX'],'internalDate':str(int(time.time())*1000),
                'payload':{'mimeType':'text/plain','headers':[{'name':'From','value':row.recipient},{'name':'To','value':snapshot['sender']},
                    {'name':'In-Reply-To','value':row.message_id}], 'body':{'data':base64.urlsafe_b64encode(b'Temos interesse em conversar.').decode()}}}
    raise AssertionError('Unexpected controlled provider operation')


if __name__=='__main__':
    from alembic import command
    from alembic.config import Config
    from backend.bootstrap import bootstrap
    command.upgrade(Config('alembic.ini'),'head');bootstrap()
    gmail.request=controlled
    fixture.semantic_intent.request_model=fixture.controlled
    fixture.fixture.main.website_researcher=fixture.ContextResearcher()
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='e2e@example.test'))
        a=db.scalar(select(ChannelAccount).where(ChannelAccount.user_id==user.id))
        if not a:
            a=ChannelAccount(id=uid(),user_id=user.id,identity='sender@example.test',cursor='100')
            a.credentials=gmail.seal({'access_token':'controlled-access','refresh_token':'controlled-refresh',
                'expires_at':int(time.time())+86400,'scopes':sorted(gmail.SCOPES)},user.id+':'+a.id)
            a.scopes=' '.join(gmail.SCOPES);db.add(a);db.commit()
    if len(sys.argv)>1 and sys.argv[1]=='worker':
        worker=fixture.fixture.worker;worker.INTERVAL=0
        for _ in range(8):
            task=worker.claim()
            if not task:break
            worker.execute(task)
    else:
        import uvicorn
        uvicorn.run(fixture.fixture.main.app,host='127.0.0.1',port=fixture.fixture.port,server_header=False)
