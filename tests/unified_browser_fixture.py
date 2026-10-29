"""v1.37 browser acceptance fixture. No production catalog or source is replaced."""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import smart_browser_fixture as fixture
from backend import locations
from backend.search_location import SearchLocation


class Source(fixture.Source):
    def general_capabilities(self):
        return {"supported":True,"pagination":True,"coverage":"Fixture multissetorial controlada; sem cobertura real.","reason":""}
    def search_page(self,query,offset,limit):
        if query.category:
            return super().search_page(query,offset,limit)
        from backend.providers import DiscoveryBatch, DiscoveryResult
        from backend.schemas import LeadInput
        rows=[]
        if not offset:
            for index,(name,category) in enumerate([('Café QA Geral','Cafeteria'),('Barbearia QA Geral','Barbearia'),('Starbucks QA Geral','Cafeteria')]):
                rows.append(DiscoveryResult(source_id=f'qa1381-{index}',lead=LeadInput(
                    name=name,category=category,city='Recife',country='BR',address=f'Rua Geral QA, {index+1}',
                    latitude=-8.05,longitude=-34.9-index*.002,phone='5581999999999',
                    website='https://example.org',website_status='unknown')))
        return DiscoveryBatch(provider=self.name,location_label='Recife',results=rows,scanned=len(rows),complete=True)
    def search(self,query):
        return self.search_page(query,0,100)
    def area_capabilities(self,area):
        return {'supported':True,'coverage':'Área sintética de teste; sem provedor externo.'}
    def location_capabilities(self,location):
        return {'supported':True,'coverage':'Limite sintético de teste; sem provedor externo.'}


def catalog(query,country='',lang='pt',*,administrative=False):
    if 'falha' in query.lower(): raise locations.LocationCatalogError('controlled')
    if 'recife' not in query.lower(): return []
    place=SearchLocation(id='qa_recife',name='Recife',formatted='Recife, Pernambuco, Brasil',
        administrative_type='city',city='Recife',state='Pernambuco',country='Brasil',country_code='BR',
        latitude=-8.05,longitude=-34.9,source='geoapify',resolved_at=int(time.time()))
    return [{'resolved':place.model_dump()}]


fixture.main.radar_provider=Source()
locations.search_locations=catalog


# Recovery fixture is injected only in this synthetic host/worker.
from backend import absorption_recovery

def recover_fixture(provider, record, reserve):
    reserve()
    candidate={**record,'category':record.get('category') or 'Cafeteria','city':'Recife','country':'BR',
        'latitude':-8.065432,'longitude':-34.876543,'source_name':'fixture','source_id':'fixture-poi-1'}
    if 'Ambigua' in record.get('name',''):
        return [candidate,{**candidate,'source_id':'fixture-poi-2'}],''
    return [candidate],''

absorption_recovery.lookup=recover_fixture

if __name__=='__main__':
    if sys.argv[1]=='server':
        from alembic import command
        from alembic.config import Config
        import uvicorn
        command.upgrade(Config('alembic.ini'),'head')
        uvicorn.run(fixture.main.app,host='127.0.0.1',port=fixture.port,server_header=False)
    elif sys.argv[1]=='worker':
        fixture.worker.INTERVAL=0
        for _ in range(25):
            task=fixture.worker.claim()
            if task: fixture.worker.execute(task,researcher=fixture.Researcher(),provider=Source())
            else: break
