"""Independent worker probe. No main/web import and no personal data in output."""
import json
import sys
import time
from sqlalchemy import select, delete
from .db import SessionLocal
from .autonomy_models import WorkerHeartbeat

STALE_SECONDS=30


def healthy(row, now):
    return row.state in ('idle','busy') and (row.heartbeat_at>=now-STALE_SECONDS or
        (row.state=='busy' and row.task_deadline>now))


def snapshot(db, now=None, identifier=None):
    now=int(time.time()) if now is None else now
    query=select(WorkerHeartbeat)
    if identifier: query=query.where(WorkerHeartbeat.id==identifier)
    rows=db.scalars(query).all()
    live=[r for r in rows if healthy(r,now)]
    return {'status':'ok' if live else 'unavailable','active_processes':len(live),
            'last_heartbeat_at':max((r.heartbeat_at for r in rows),default=None)}


def beat(identifier, state='idle', deadline=0, error=''):
    now=int(time.time())
    with SessionLocal() as db:
        db.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.heartbeat_at<now-86400,WorkerHeartbeat.id!=identifier))
        row=db.get(WorkerHeartbeat,identifier)
        if not row:
            row=WorkerHeartbeat(id=identifier,started_at=now);db.add(row)
        row.heartbeat_at=now;row.state=state;row.task_deadline=deadline;row.error=error
        db.commit()


def main():
    try:
        with SessionLocal() as db: result=snapshot(db)
    except Exception: result={'status':'unavailable'}
    print(json.dumps(result))
    return 0 if result['status']=='ok' else 1


if __name__=='__main__': sys.exit(main())
