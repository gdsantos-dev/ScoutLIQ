"""Official Gmail endpoints only. No implicit retries of messages.send."""
import base64
import json
import os
import re
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP
from urllib.parse import urlencode, urlsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from .config import ORIGIN, PRODUCTION
from .consumption import metered

SCOPES = {'https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly'}
API = 'https://gmail.googleapis.com/gmail/v1/users/me/'
TOKEN = 'https://oauth2.googleapis.com/token'
REVOKE = 'https://oauth2.googleapis.com/revoke'


class ProviderUnavailable(RuntimeError): pass
class AuthenticationRequired(ProviderUnavailable): pass
class ProviderRejected(ProviderUnavailable): pass
class ProviderUncertain(ProviderUnavailable): pass


def enabled(): return os.getenv('GMAIL_ENABLED', 'false').lower() == 'true'


def cipher():
    try:
        keys = os.environ['COMMUNICATION_TOKEN_KEYS'].split(',')
        if not 1 <= len(keys) <= 3: raise ValueError()
        return MultiFernet([Fernet(k.strip().encode()) for k in keys])
    except (KeyError, ValueError):
        raise ProviderUnavailable('Cifra de credenciais indisponível.') from None


def seal(value, owner):
    return cipher().encrypt(json.dumps({'owner': owner, 'value': value}).encode()).decode()


def unseal(value, owner):
    try:
        obj = json.loads(cipher().decrypt(value.encode()))
        if obj['owner'] != owner: raise ValueError()
        return obj['value']
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise AuthenticationRequired('Credencial indisponível; reconecte a conta.') from None


def settings():
    redirect = os.getenv('GMAIL_REDIRECT_URI', '')
    p = urlsplit(redirect)
    expected = ORIGIN + '/api/communication/gmail/callback'
    if (not enabled() or redirect != expected or p.username or p.password or p.fragment or p.query
        or (p.scheme != 'https' and (PRODUCTION or p.hostname not in ('localhost','127.0.0.1')))
        or not os.getenv('GMAIL_CLIENT_ID') or not os.getenv('GMAIL_CLIENT_SECRET')):
        raise ProviderUnavailable('Configure o cliente OAuth, a origem e o redirect Gmail no servidor.')
    cipher()
    return {'client_id': os.environ['GMAIL_CLIENT_ID'], 'client_secret': os.environ['GMAIL_CLIENT_SECRET'], 'redirect_uri': redirect}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


@metered('gmail')
def request(method, url, *, token='', form=None, payload=None):
    # Callers supply paths from validated provider IDs, never arbitrary inbound URLs.
    if not (url.startswith(API) or url in (TOKEN, REVOKE)):
        raise ProviderRejected('Destino não permitido.')
    headers = {'Accept': 'application/json'}
    body = None
    if form is not None:
        body = urlencode(form).encode(); headers['Content-Type'] = 'application/x-www-form-urlencoded'
    if payload is not None:
        body = json.dumps(payload).encode(); headers['Content-Type'] = 'application/json'
    if token: headers['Authorization'] = 'Bearer ' + token
    try:
        with build_opener(NoRedirect).open(Request(url, data=body, headers=headers, method=method), timeout=15) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000: raise ProviderUncertain('Resposta excede o limite.')
            result=json.loads(raw) if raw else {}
            if not isinstance(result,dict): raise ProviderUncertain('Resposta inválida do provedor.')
            return result
    except HTTPError as exc:
        # Never surface raw provider text, token, URL, headers or mailbox content.
        code = exc.code
        if url == TOKEN and code in (400,401): raise AuthenticationRequired('Reconexão necessária.') from None
        if code == 401: raise AuthenticationRequired('Reconexão necessária.') from None
        if code == 404: raise ProviderRejected('not_found') from None
        if 400 <= code < 500: raise ProviderRejected('Solicitação recusada pelo provedor.') from None
        raise ProviderUncertain('Resultado da operação não confirmado.') from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ProviderUncertain('Resultado da operação não confirmado.') from None


def provider_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value):
        raise ProviderUncertain('Identificador inválido do provedor.')
    return value


def token_record(result):
    if not isinstance(result,dict) or not isinstance(result.get('access_token'),str) or not 1 <= len(result['access_token']) <= 10000:
        raise AuthenticationRequired('Resposta OAuth inválida.')
    if result.get('token_type','').lower() != 'bearer': raise AuthenticationRequired('Tipo de token inválido.')
    granted = set(str(result.get('scope','')).split())
    if not SCOPES.issubset(granted): raise AuthenticationRequired('Escopos necessários não foram concedidos.')
    expiry = result.get('expires_in')
    if type(expiry) is not int or not 1 <= expiry <= 86400: raise AuthenticationRequired('Validade OAuth inválida.')
    refresh = result.get('refresh_token','')
    if not isinstance(refresh,str) or len(refresh)>10000: raise AuthenticationRequired('Refresh token inválido.')
    return {'access_token':result['access_token'],'refresh_token':refresh,'expires_at':int(time.time())+expiry,'scopes':sorted(granted)}


def exchange(code, verifier):
    config = settings()
    return token_record(request('POST',TOKEN,form={**config,'code':code,'code_verifier':verifier,'grant_type':'authorization_code'}))


def refresh(credentials):
    config = settings()
    if not credentials.get('refresh_token'): raise AuthenticationRequired('Reconexão necessária.')
    result = request('POST',TOKEN,form={'client_id':config['client_id'],'client_secret':config['client_secret'],
        'refresh_token':credentials['refresh_token'],'grant_type':'refresh_token'})
    # Google may omit unchanged scopes in refresh responses.
    result.setdefault('scope',' '.join(credentials.get('scopes',[])))
    renewed = token_record(result)
    renewed['refresh_token'] = renewed['refresh_token'] or credentials['refresh_token']
    return renewed


@dataclass(frozen=True)
class Acceptance:
    message_id: str
    thread_id: str


class GmailAdapter:
    channel = 'email'
    provider = 'gmail'

    def __init__(self, credentials):
        settings()
        self.credentials = credentials
        self.token = credentials['access_token']

    def profile(self):
        result = request('GET',API+'profile',token=self.token)
        from .security import normalize_email
        try:
            return {'identity':normalize_email(result['emailAddress']), 'cursor':str(int(result['historyId']))}
        except (ValueError,KeyError,TypeError): raise ProviderUnavailable('Identidade Gmail inválida.') from None

    def send(self, snapshot, message_id):
        message = EmailMessage(policy=SMTP)
        # EmailMessage rejects CR/LF header injection. Body is plain text only.
        message['From'] = snapshot['sender']
        message['To'] = snapshot['recipient']
        message['Subject'] = snapshot['subject']
        message['Message-ID'] = message_id
        message['Date'] = snapshot['date']
        message.set_content(snapshot['body'])
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        result = request('POST',API+'messages/send',token=self.token,payload={'raw':raw})
        return Acceptance(provider_id(result.get('id')),provider_id(result.get('threadId')))

    def message(self, identifier):
        return request('GET',API+'messages/'+provider_id(identifier)+'?format=full',token=self.token)

    def reconcile(self, snapshot, message_id):
        query = urlencode({'q':'in:sent rfc822msgid:'+message_id,'maxResults':10})
        rows = request('GET',API+'messages?'+query,token=self.token)
        found = []
        from .communication_replies import headers, participants
        for row in rows.get('messages',[])[:10]:
            msg = self.message(row['id']); h = headers(msg)
            if (h.get('message-id') == message_id and participants(h.get('from','')) == {snapshot['sender']}
                and participants(h.get('to','')) == {snapshot['recipient']} and 'SENT' in msg.get('labelIds',[])):
                found.append(Acceptance(provider_id(msg.get('id')),provider_id(msg.get('threadId'))))
        return found[0] if len(found)==1 and not rows.get('nextPageToken') else None

    def history(self, cursor, page=''):
        args = {'startHistoryId':cursor,'historyTypes':'messageAdded','maxResults':25}
        if page: args['pageToken'] = page
        return request('GET',API+'history?'+urlencode(args),token=self.token)

    def thread(self, identifier):
        return request('GET',API+'threads/'+provider_id(identifier)+'?format=full',token=self.token)

    def revoke(self):
        request('POST',REVOKE,form={'token':self.credentials.get('refresh_token') or self.token})
