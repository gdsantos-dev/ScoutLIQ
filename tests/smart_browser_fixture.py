"""Isolated acceptance host/worker; only synthetic data, never a live provider."""
import os
import sys
import time
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
os.chdir(root);sys.path.insert(0,str(root))
port=int(os.getenv('E2E_PORT','8004'))
os.environ.update(APP_ENV='test',DATABASE_URL=f'sqlite:///./data/e2e-{port}.db',
    ADMIN_EMAIL='e2e@example.test',ADMIN_PASSWORD='E2e-only-not-for-production!',
    APP_ORIGIN=f'http://localhost:{port}',DEMO_SEED='true',RADAR_PROVIDER='demo',
    RESEARCH_EXECUTION_MODE='worker',EMAIL_MODE='memory')
if __name__=='__main__' and sys.argv[1]=='server':
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True)

from backend import main, research_worker as worker
from backend.providers import DemoProvider, DiscoveryBatch, DiscoveryResult
from backend.schemas import LeadInput

class Source(DemoProvider):
    name='controlled-browser-v132'
    def capabilities(self,sector): return {'supported':True,'pagination':True,'coverage':'Fixture sintética local; sem validação de provedor real.','reason':''}
    def search_page(self,query,offset,limit):
        items=[]
        if offset==0:
            for index,name in enumerate(['Clínica QA Aurora','Clínica QA Horizonte','Starbucks QA Centro']):
                lead=LeadInput(name=name,category='Clínica odontológica',city='Recife',country='BR',address=f'Rua de QA, {index+1}',latitude=-8.05,longitude=-34.9-index*.002,phone='5581999999999',website='https://example.org',website_status='unknown')
                items.append(DiscoveryResult(source_id=f'qa132-{index}',lead=lead))
        return DiscoveryBatch(provider=self.name,location_label='Recife',results=items,scanned=len(items),complete=True)

class Researcher:
    def research(self,lead,locale):
        return {'status':'confirmed','provider':'controlled-browser-v132','website_url':'https://example.org','website_status':'poor','checked_at':int(time.time()),'page':{'pages_checked':1,'forms':1},'checks':[{'key':'viewport','state':'fail'}]}
    def deep_audit(self,lead,url):
        return {'website_status':'poor','pages_checked':2,'quality_score':40,'signals':{'forms':1,'booking':False},'findings':[{'key':'no_cta','severity':'high','detail':'Observação sintética de QA.'}]}

main.radar_provider=Source()
if __name__=='__main__':
    if sys.argv[1]=='server':
        import uvicorn
        uvicorn.run(main.app,host='127.0.0.1',port=port,server_header=False)
    elif sys.argv[1]=='worker':
        worker.INTERVAL=0
        for _ in range(25):
            task=worker.claim()
            if task: worker.execute(task,researcher=Researcher(),provider=Source())
            else: break
