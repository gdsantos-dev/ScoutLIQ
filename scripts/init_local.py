"""Create development-only credentials without printing the generated password."""
import secrets
from pathlib import Path

target=Path(__file__).resolve().parent.parent/'.env'
if target.exists():
    print('Arquivo .env existente preservado.')
else:
    target.write_text('APP_ENV=development\nDATABASE_URL=sqlite:///./data/scoutliq.db\nAPP_ORIGIN=http://localhost:8000\nADMIN_EMAIL=owner@scoutliq.local\nADMIN_PASSWORD='+secrets.token_urlsafe(24)+'\nDEMO_SEED=true\nTZ=America/Sao_Paulo\n',encoding='utf-8')
    print('Ambiente local criado. Credenciais em .env, fora do Git.')
