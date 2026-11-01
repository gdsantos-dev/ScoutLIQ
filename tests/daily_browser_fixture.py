"""Daily journey acceptance: isolated SQLite and metered synthetic adapters."""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import unified_browser_fixture as unified
from backend import consumption

class Source(unified.Source):
    def search_page(self,query,offset,limit):
        result=super().search_page(query,offset,limit)
        return result.model_copy(update={'results':[item.model_copy(update={'lead':item.lead.model_copy(update={
            'contact':'team@example.test','reviews':120,'rating':4.8,
            'instagram':'https://instagram.com/example','instagram_active':True})}) for item in result.results]})

source=Source()
consumption.PROVIDER_LIMITS={**consumption.PROVIDER_LIMITS,source.name:100}
source.search_page=consumption.metered(source.name)(source.search_page)
unified.fixture.main.radar_provider=source

if __name__=='__main__':
    if sys.argv[1]=='server':
        from alembic import command
        from alembic.config import Config
        import uvicorn
        command.upgrade(Config('alembic.ini'),'head')
        uvicorn.run(unified.fixture.main.app,host='127.0.0.1',port=unified.fixture.port,server_header=False)
    else:
        worker=unified.fixture.worker
        researcher=unified.fixture.Researcher()
        researcher.research=consumption.metered('website')(researcher.research)
        deadline=time.monotonic()+240;executed=0
        while time.monotonic()<deadline and executed<20:
            task=worker.claim()
            if task:
                if not worker.execute(task,provider=source,researcher=researcher):raise RuntimeError('Synthetic worker failed')
                executed+=1
                if sys.argv[1]=='discover':break
            else:
                from backend.db import SessionLocal
                from sqlalchemy import select
                from backend.models import SmartSearch, ResearchBatch
                # A claim may return just before its integer-second deadline and
                # the clock may cross that deadline before this check. Settle on
                # persisted terminal states, never on a fractional time window.
                with SessionLocal() as db:
                    pending = db.scalar(select(SmartSearch.id).where(SmartSearch.status.in_(['pending','running','investigating'])).limit(1))
                    pending = pending or db.scalar(select(ResearchBatch.id).where(ResearchBatch.status.in_(['pending','running'])).limit(1))
                if pending:time.sleep(1);continue
                break
        else:raise RuntimeError('Bounded worker did not settle')
