"""Local operator recovery. Password read without echo; revokes every session."""
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from sqlalchemy import select, delete
from backend.db import SessionLocal
from backend.models import User, Session
from backend.security import hasher

email=input('E-mail da conta: ').strip().lower()
password=getpass.getpass('Nova senha (12+ caracteres): ')
if not 12<=len(password)<=256 or password!=getpass.getpass('Confirme a nova senha: '):
    raise SystemExit('Senha inválida ou confirmação diferente.')
with SessionLocal() as db:
    user=db.scalar(select(User).where(User.email==email))
    if not user:
        raise SystemExit('Conta não encontrada.')
    user.password_hash=hasher.hash(password)
    db.execute(delete(Session).where(Session.user_id==user.id))
    db.commit()
print('Senha alterada. Sessões encerradas.')
