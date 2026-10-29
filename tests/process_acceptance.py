"""Isolated real web/worker lifecycle check; no provider calls or personal DB."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT);sys.path.insert(0,str(ROOT))


def main():
    with tempfile.TemporaryDirectory(prefix='process-qa-',dir=ROOT/'artifacts') as directory:
        os.environ.update(APP_ENV='test',DATABASE_URL='sqlite:///'+str(Path(directory)/'qa.db'),
            ADMIN_EMAIL='process@example.test',ADMIN_PASSWORD='Synthetic-process-QA-only!',DEMO_SEED='false',
            RADAR_PROVIDER='demo',RESEARCH_EXECUTION_MODE='worker',SCOUTLIQ_PROCESS_MODE='combined',
            APP_ORIGIN='http://localhost:8007',EMAIL_MODE='memory')
        subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True)
        from backend.bootstrap import bootstrap
        from backend.db import SessionLocal,engine
        from backend.worker_health import snapshot
        from scripts.start import supervise,validate_environment
        assert validate_environment()=='combined'
        bootstrap()
        evidence=[]
        for crash in (True,False):
            identifier=str(uuid4());stop=threading.Event();children=[];failures=[]
            env={**os.environ,'SCOUTLIQ_WORKER_ID':identifier}
            def popen(*args,**kwargs):
                child=subprocess.Popen(*args,**kwargs);children.append(child);return child
            def health():
                with SessionLocal() as db: return snapshot(db,identifier=identifier)['status']=='ok'
            def driver():
                try:
                    deadline=time.monotonic()+50
                    while time.monotonic()<deadline:
                        try:
                            with urlopen('http://127.0.0.1:8007/api/health/ready',timeout=2) as response:
                                if response.status==200 and health(): break
                        except OSError: pass
                        time.sleep(.25)
                    else: raise AssertionError('Real service failed readiness')
                    if crash: children[1].kill()
                    else: stop.set()
                except Exception as exc: failures.append(type(exc).__name__);stop.set()
            thread=threading.Thread(target=driver);thread.start()
            with (ROOT/'artifacts/process-children.log').open('a',encoding='utf-8') as log:
                original=popen
                def logged(*args,**kwargs): return original(*args,stdout=log,stderr=log,**kwargs)
                result=supervise([[sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8007'],
                    [sys.executable,'-m','backend.research_worker']],env=env,health=health,stop=stop,popen=logged,interval=.25)
            thread.join(5)
            assert not failures,failures
            assert result==(1 if crash else 0)
            assert all(child.poll() is not None for child in children)
            evidence.append({'scenario':'worker_crash_stops_web' if crash else 'restart_and_graceful_shutdown',
                'ready':True,'exit':result,'children_stopped':True})
        engine.dispose()
    (ROOT/'artifacts/process-acceptance.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence))


if __name__=='__main__': main()
