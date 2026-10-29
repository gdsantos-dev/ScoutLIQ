"""Deterministic, locale-safe drafting and conservative exact-recipient policy."""
import json
import re
import time
from fastapi import HTTPException
from sqlalchemy import select
from .opportunity_models import RecipientPolicy
from .security import normalize_email
from .evidence_intelligence import observation

def recipient_identity(channel, recipient):
    if channel == 'email':
        try: return normalize_email(recipient.strip())
        except ValueError: raise HTTPException(422, 'Informe um e-mail válido.')
    # Require explicit international prefix/digits; never guess a country or merge by suffix.
    value = re.sub(r'[\s().-]', '', recipient.strip()).removeprefix('+')
    if not re.fullmatch(r'[1-9][0-9]{7,14}', value):
        raise HTTPException(422, 'Informe o telefone completo com código do país.')
    return value

def policy_for(db, user_id, channel, recipient):
    return db.scalar(select(RecipientPolicy).where(RecipientPolicy.user_id == user_id,
        RecipientPolicy.channel == channel, RecipientPolicy.recipient == recipient_identity(channel, recipient)))

def recipient_blocker(db, lead, channel, recipient):
    policy = policy_for(db, lead.user_id, channel, recipient)
    return 'Este destinatário pediu para não receber contato, inclusive em outras oportunidades.' if policy and policy.blocked else ''

def send_condition(db, lead, draft):
    blocked = recipient_blocker(db, lead, draft.channel, draft.recipient)
    if blocked: return 'blocked', blocked
    p = policy_for(db, lead.user_id, draft.channel, draft.recipient)
    if not p or p.basis == 'unknown': return 'unknown', 'Condição de uso do canal ainda não registrada.'
    if p.valid_until and p.valid_until <= int(time.time()): return 'expired', 'A condição de contato registrada venceu.'
    from .communication import verification_for
    if verification_for(db,p,int(time.time())):
        return 'operator_reviewed', 'Condição revisada pelo operador. Envio ainda exige conta válida e autorização específica.'
    # A free-text record is a declaration, never a legal/provider verification.
    return 'pending_verification', 'Condição declarada pelo operador; validação de mercado/provedor e integração oficial pendentes.'

def localized_fact(e, locale):
    if e.observation_key:
        return observation(e.observation_key, e.observation_state, locale)
    if locale == 'pt-BR': return e.statement
    translations = json.loads(e.translations_json or '{}')
    if not translations.get(locale):
        raise HTTPException(409, 'Esta observação livre exige uma tradução revisada no idioma selecionado. Abra a revisão da evidência.')
    return translations[locale]

def compose(lead, data, items, activities):
    strategy = data.strategy
    has_contact = any(a.kind in ('email', 'whatsapp', 'call') for a in activities)
    has_reply = any(a.kind == 'reply' for a in activities)
    if strategy == 'follow_up' and not has_contact:
        raise HTTPException(409, 'Retomada exige contato anterior registrado no histórico.')
    if strategy == 'reply' and not has_reply:
        raise HTTPException(409, 'Resposta a interesse exige uma resposta registrada no histórico.')
    if strategy == 'verified_opportunity' and not any(e.category == 'content' or e.observation_state in ('fail', 'warn') for e in items):
        raise HTTPException(409, 'As evidências selecionadas não sustentam uma necessidade específica. Revise a categoria e o escopo.')
    facts = '\n'.join(localized_fact(e, data.locale) for e in items)
    name = lead.name
    if data.locale == 'en-US':
        opening = {'initial': f'Hello {name} team,', 'verified_opportunity': f'Hello {name} team,',
                   'follow_up': f'Hello {name} team,\n\nI’m following up on our earlier contact.',
                   'reply': f'Hello {name} team,\n\nThank you for getting back to us.'}[strategy]
        intro = 'I’m reaching out from ORLIQ. We design and maintain websites and build web solutions for businesses.'
        detail = f'While reviewing your website, I noted the following:\n{facts}\n\nThese observations relate to the pages reviewed; they are not a full-site assessment.' if facts else ''
        closing = 'Would it be useful if we outlined a focused improvement for your team to review?' if facts else 'Is there a website project or improvement your team is currently considering?'
        subject = f'A website improvement for {name}' if facts else f'Website projects at {name}'
    elif data.locale == 'es':
        opening = f'Hola, equipo de {name}.'
        if strategy == 'follow_up': opening += '\n\nRetomo nuestra conversación anterior.'
        if strategy == 'reply': opening += '\n\nGracias por su respuesta.'
        intro = 'Soy parte de ORLIQ. Desarrollamos y mantenemos sitios web y soluciones web para empresas.'
        detail = f'Al revisar su sitio observé lo siguiente:\n{facts}\n\nEstas observaciones se limitan a las páginas revisadas; no son una evaluación completa del sitio.' if facts else ''
        closing = '¿Les resultaría útil que propusiéramos una mejora puntual para revisar?' if facts else '¿Tienen algún proyecto o mejora de su sitio en consideración?'
        subject = f'Una mejora para el sitio de {name}' if facts else f'Proyectos web de {name}'
    else:
        opening = f'Olá, equipe da {name}.'
        if strategy == 'follow_up': opening += '\n\nRetomo nossa conversa anterior.'
        if strategy == 'reply': opening += '\n\nObrigado pelo retorno.'
        intro = 'Faço parte da ORLIQ. Desenvolvemos e mantemos sites e soluções web para empresas.'
        detail = f'Ao revisar o site, observei:\n{facts}\n\nEssas observações se limitam às páginas revisadas; não são uma avaliação completa do site.' if facts else ''
        closing = 'Faz sentido apresentarmos uma melhoria pontual para vocês avaliarem?' if facts else 'Vocês estão considerando algum projeto ou melhoria para o site?'
        subject = f'Uma melhoria para o site da {name}' if facts else f'Projetos web da {name}'
    removal = {'pt-BR':'Se preferirem não receber novos contatos, respondam solicitando a remoção.',
               'en-US':'To stop receiving messages, reply with "unsubscribe".',
               'es':'Si prefieren no recibir más mensajes, respondan solicitando la baja.'}[data.locale]
    body = '\n\n'.join(p for p in (opening, intro, detail, closing, removal) if p)
    return subject[:200] if data.channel == 'email' else '', body
