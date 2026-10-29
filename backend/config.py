import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
PRODUCTION = os.getenv('APP_ENV') == 'production'
ORIGIN = os.getenv('APP_ORIGIN', 'http://localhost:8000').rstrip('/')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./data/scoutliq.db')
REGISTRATION_MODE = os.getenv('REGISTRATION_MODE', 'open').strip().lower()
EMAIL_MODE = os.getenv('EMAIL_MODE', 'brevo' if PRODUCTION else 'console').strip().lower()
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '').strip()
EMAIL_FROM_EMAIL = os.getenv('EMAIL_FROM_EMAIL', '').strip()
EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'ScoutLIQ').strip() or 'ScoutLIQ'
EMAIL_REPLY_TO = os.getenv('EMAIL_REPLY_TO', '').strip()
ORLIQ_ADMIN_API_KEY = os.getenv('ORLIQ_ADMIN_API_KEY', '').strip()
if PRODUCTION and not ORIGIN.startswith('https://'):
    raise RuntimeError('APP_ORIGIN precisa usar HTTPS em producao')
if REGISTRATION_MODE not in {'open', 'closed'}:
    raise RuntimeError('REGISTRATION_MODE deve ser open ou closed')
if EMAIL_MODE not in {'brevo', 'console', 'memory'}:
    raise RuntimeError('EMAIL_MODE deve ser brevo, console ou memory')
if PRODUCTION and ORLIQ_ADMIN_API_KEY and len(ORLIQ_ADMIN_API_KEY) < 32:
    raise RuntimeError('ORLIQ_ADMIN_API_KEY precisa ter pelo menos 32 caracteres em produção')
if DATABASE_URL.startswith('sqlite:///'):
    Path(DATABASE_URL.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
