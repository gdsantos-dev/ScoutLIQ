"""Isolated planning host/worker, only metered synthetic adapters."""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import unified_browser_fixture as unified
from backend import consumption

source=unified.fixture.main.radar_provider
consumption.PROVIDER_LIMITS={**consumption.PROVIDER_LIMITS,source.name:100}
source.search_page=consumption.metered(source.name)(source.search_page)

if __name__=='__main__':
    if sys.argv[1]=='server':
        from alembic import command
        from alembic.config import Config
        import uvicorn
        command.upgrade(Config('alembic.ini'),'head')
        uvicorn.run(unified.fixture.main.app,host='127.0.0.1',port=unified.fixture.port,server_header=False)
    elif sys.argv[1]=='worker':
        worker=unified.fixture.worker
        for _ in range(60):
            task=worker.claim()
            if not task:
                from backend.db import SessionLocal
                from backend.models import ResearchExecutor
                with SessionLocal() as db: next_at=db.get(ResearchExecutor,1).next_at
                if 0<next_at-time.time()<=20:
                    time.sleep(1);continue
                break
            worker.execute(task,provider=source,researcher=unified.fixture.Researcher())
