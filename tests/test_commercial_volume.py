"""Controlled volume acceptance, never connected to a user's database."""
import json
import time
from pathlib import Path
from sqlalchemy import select, event
from backend.db import SessionLocal, engine
from backend.models import Lead, User


def test_thousand_companies_index_in_bounded_blocks_and_page_without_n_plus_one(auth):
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email=='test@example.com'))
        db.add_all([Lead(user_id=user.id,name=f'Empresa controlada {i:04}',category='Cafeteria',city='Recife',
            latitude=-8,longitude=-34,source='controlled_volume') for i in range(1000)])
        db.commit()
    start=time.monotonic();pending=[]
    for _ in range(4):
        response=auth.get('/api/commercial-review/queue');assert response.status_code==200,response.text
        data=response.json();pending.append(data['index_pending']);assert len(data['items'])==25
    elapsed=time.monotonic()-start
    assert pending==[750,500,250,0]
    statements=[]
    def capture(*args):statements.append(args[2])
    event.listen(engine,'before_cursor_execute',capture)
    try:
        start=time.monotonic();first=auth.get('/api/commercial-review/queue',params={'limit':50}).json();warm=time.monotonic()-start
        assert first['total']==1000 and len(first['items'])==50 and len(statements)<20
    finally:event.remove(engine,'before_cursor_execute',capture)
    second=auth.get('/api/commercial-review/queue',params={'limit':50,'offset':50}).json()
    assert not set(r['id'] for r in first['items'])&set(r['id'] for r in second['items'])
    output = Path('artifacts/commercial-volume.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'companies':1000,'index_blocks':4,'pending_after_each_block':pending,
        'cold_index_seconds':round(elapsed,3),'warm_page_seconds':round(warm,3),'warm_page_queries':len(statements),
        'rows_per_page':50,'real_provider_calls':0,'scope':'SQLite local fixture; not a production latency guarantee'},indent=2))
