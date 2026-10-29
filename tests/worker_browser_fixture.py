"""Controlled browser acceptance worker. Never contacts a network provider."""
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path.insert(0,str(root))
port=int(os.getenv('E2E_PORT','8004'))
os.environ.update(APP_ENV='test',DATABASE_URL=f'sqlite:///./data/e2e-{port}.db',RESEARCH_EXECUTION_MODE='worker',DEMO_SEED='false')
from backend import research_worker as worker

class FixtureResearcher:
    def research(self,lead,locale):
        time.sleep(1)
        return {'status':'confirmed','provider':'controlled-browser-test','website_url':'https://example.org',
                'website_status':'poor','checked_at':int(time.time()),'checks':[{'key':'viewport','state':'fail'}]}

class FixtureProvider:
    def search(self, query):
        return SimpleNamespace(results=[], provider='controlled-browser-test', location_label='Recife',
                               complete=True, scanned=0, result_limit=None, scope='region')

if __name__=='__main__':
    worker.INTERVAL=0
    for _ in range(5):
        task=worker.claim()
        if task: worker.execute(task,FixtureResearcher(),FixtureProvider())
