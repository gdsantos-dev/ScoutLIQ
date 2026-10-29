"""Same acceptance host; only the external semantic response is replaced with controlled data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import unified_browser_fixture as unified
fixture = unified.fixture
import json
import os
from backend import semantic_intent
from backend.search_intent import interpret
from types import SimpleNamespace
from backend.website_context import inspect

os.environ.update(SCOUT_SEMANTIC_ENABLED='true',SCOUT_SEMANTIC_MODEL='controlled-browser-model',
    SCOUT_SEMANTIC_AUTO_POLICY='complex_only',
    SCOUT_SEMANTIC_API_KEY='synthetic-never-sent',SCOUT_SEMANTIC_DAILY_TOKENS='1000000',
    SCOUT_SEMANTIC_USER_DAILY_TOKENS='500000')


def controlled(body,cfg):
    request=json.loads(body['input'])
    if 'FALHA CONTROLADA' in request['text']: return {'status':'incomplete'}
    intent=interpret(request['text'],request['target'])
    intent.sectors=['odontologia'];intent.requirements=['poor_site']
    intent.unresolved=[]
    return {'status':'completed','usage':{'total_tokens':600},'output':[{'type':'message','content':[
        {'type':'output_text','text':intent.model_dump_json(exclude={'location','area','legacy','search_mode'})}]}]}


class ContextResearcher(fixture.Researcher):
    def research(self,lead,locale):
        result=super().research(lead,locale)
        result['confidence']=91
        result['context']=inspect([SimpleNamespace(final_url='https://example.org',
            links=[('mailto:business@example.org','Contato'),('https://example.org/services','Serviços')],
            form_count=0,booking=False,truncated=False)])
        return result


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='attempt':
        from uuid import UUID
        from sqlalchemy import select
        from backend.db import SessionLocal
        key=str(UUID(sys.argv[2]))
        with SessionLocal() as db:
            row=db.scalar(select(semantic_intent.SemanticAttempt).where(semantic_intent.SemanticAttempt.request_key==key))
            print(json.dumps(None if row is None else dict(status=row.status,model=row.model,reserved_tokens=row.reserved_tokens,actual_tokens=row.actual_tokens)))
        sys.exit(0)
    from alembic import command
    from alembic.config import Config
    import uvicorn
    command.upgrade(Config('alembic.ini'),'head')
    semantic_intent.request_model=controlled
    fixture.main.website_researcher=ContextResearcher()
    uvicorn.run(fixture.main.app,host='127.0.0.1',port=fixture.port,server_header=False)
