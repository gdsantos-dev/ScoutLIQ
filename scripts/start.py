"""One service/volume, one web child and one supervised background child."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parent.parent


def prepare_volume():
    """Docker bootstrap only; never recurse, follow links, or run app as root."""
    if os.name=='nt' or os.geteuid()!=0: return
    if os.getenv('SCOUTLIQ_CONTAINER')!='1':
        raise RuntimeError('Execute o serviço com usuário sem privilégios.')
    import pwd
    identity=pwd.getpwnam('scout')
    volume=Path('/data')
    if not volume.is_dir() or volume.is_symlink(): raise RuntimeError('Volume de dados indisponível.')
    os.chown(volume,identity.pw_uid,identity.pw_gid)
    for name in ('scoutliq.db','scoutliq.db-wal','scoutliq.db-shm'):
        path=volume/name
        if path.is_symlink(): raise RuntimeError('Arquivo de dados inválido.')
        if path.exists():
            if not path.is_file(): raise RuntimeError('Arquivo de dados inválido.')
            os.chown(path,identity.pw_uid,identity.pw_gid)
    os.setgroups([]);os.setgid(identity.pw_gid);os.setuid(identity.pw_uid)


def validate_environment():
    mode=os.getenv('SCOUTLIQ_PROCESS_MODE','combined')
    if mode not in ('combined','web'): raise RuntimeError('SCOUTLIQ_PROCESS_MODE inválido.')
    if mode=='combined' and os.getenv('RESEARCH_EXECUTION_MODE','worker')!='worker':
        raise RuntimeError('Modo combined exige RESEARCH_EXECUTION_MODE=worker.')
    database=os.getenv('DATABASE_URL','sqlite:///./data/scoutliq.db')
    if database.startswith('sqlite'):
        from sqlalchemy.engine import make_url
        raw=make_url(database).database
        if not raw or raw==':memory:': raise RuntimeError('Web e worker exigem banco persistente compartilhado.')
        path=Path(raw).resolve()
        if os.getenv('RAILWAY_ENVIRONMENT_ID'):
            mount=os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
            if not mount or not path.is_relative_to(Path(mount).resolve()):
                raise RuntimeError('SQLite deve estar no volume persistente do serviço Railway.')
        if os.getenv('SCOUTLIQ_CONTAINER')=='1' and path!=Path('/data/scoutliq.db'):
            raise RuntimeError('A imagem SQLite usa /data/scoutliq.db; migre caminhos fora da inicialização.')
        path.parent.mkdir(parents=True,exist_ok=True)
        if not os.access(path.parent,os.W_OK): raise RuntimeError('Banco sem acesso de escrita seguro.')
    return mode


def stop_children(children, grace=20):
    for child in children:
        if child.poll() is not None: continue
        try: child.send_signal(signal.CTRL_BREAK_EVENT if os.name=='nt' else signal.SIGTERM)
        except (OSError,ValueError): child.terminate()
    deadline=time.monotonic()+grace
    for child in children:
        try: child.wait(timeout=max(0,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            child.kill();child.wait(timeout=5)


def supervise(commands, *, env, health, stop, popen=subprocess.Popen, startup_grace=60, interval=2, grace=20):
    children=[]
    started=time.monotonic()
    try:
        for command in commands:
            children.append(popen(command,cwd=ROOT,env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0))
        while not stop.wait(interval):
            if any(child.poll() is not None for child in children):
                print('Um processo do serviço encerrou; reinício pelo supervisor do host.',flush=True)
                return 1
            if time.monotonic()-started>startup_grace:
                try: alive=health()
                except Exception: alive=False
                if not alive:
                    print('Executor sem progresso no prazo; reinício pelo supervisor do host.',flush=True)
                    return 1
        return 0
    finally: stop_children(children,grace)


def main():
    os.chdir(ROOT)
    sys.path.insert(0,str(ROOT))
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    prepare_volume()
    mode=validate_environment()
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True)
    from backend.bootstrap import bootstrap
    bootstrap()
    web=[sys.executable,'-m','uvicorn','backend.main:app','--host','0.0.0.0','--port',os.getenv('PORT','8000'),
         '--workers','1','--no-server-header','--no-proxy-headers','--timeout-graceful-shutdown','15']
    if mode=='web': os.execv(sys.executable,web)
    identifier=str(uuid4())
    env={**os.environ,'SCOUTLIQ_WORKER_ID':identifier,'SCOUTLIQ_PROCESS_MODE':'combined'}
    from backend.worker_health import snapshot
    from backend.db import SessionLocal
    def health():
        with SessionLocal() as db: return snapshot(db,identifier=identifier)['status']=='ok'
    stop=threading.Event()
    for name in ('SIGTERM','SIGINT','SIGBREAK'):
        if hasattr(signal,name): signal.signal(getattr(signal,name),lambda *_:stop.set())
    return supervise([web,[sys.executable,'-m','backend.research_worker']],env=env,health=health,stop=stop)


if __name__=='__main__':
    try: sys.exit(main())
    except Exception:
        print('Inicialização interrompida. Confira modo, volume, migrações e configuração do serviço.',file=sys.stderr)
        sys.exit(1)
