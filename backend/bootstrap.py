import os
from sqlalchemy import select
from .db import SessionLocal
from .models import User
from .security import hasher

def bootstrap():
    with SessionLocal() as db:
        user = db.scalar(select(User).limit(1))
        if user is None:
            email = os.getenv('ADMIN_EMAIL','').strip().lower()
            password = os.getenv('ADMIN_PASSWORD','')
            if '@' not in email or len(password)<12 or len(password)>256:
                raise RuntimeError('Defina ADMIN_EMAIL e ADMIN_PASSWORD (12 a 256 caracteres) para o primeiro acesso.')
            import time
            user = User(email=email,password_hash=hasher.hash(password),email_verified_at=int(time.time()),role='admin',is_active=True)
            db.add(user)
            db.commit()
        if os.getenv('DEMO_SEED','false').lower()=='true':
            if os.getenv('APP_ENV')=='production':
                raise RuntimeError('DEMO_SEED deve ser false em producao; importe exemplos pela interface.')
            from .seed import seed_demo
            seed_demo(db,user)

if __name__=='__main__':
    bootstrap()
