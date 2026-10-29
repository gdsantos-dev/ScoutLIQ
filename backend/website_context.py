"""Facts from already-inspected, identity-matched HTML. No social scraping or inferred people."""
import json
import re
from urllib.parse import urlparse, parse_qs, unquote


def public_contacts(page):
    found = []
    for raw, _ in page.links:
        parsed = urlparse(raw)
        host = (parsed.hostname or '').lower().removeprefix('www.')
        field, value = '', ''
        if parsed.scheme == 'tel':
            digits = re.sub(r'\D', '', parsed.path)
            if 8 <= len(digits) <= 15: field, value = 'phone', digits
        elif parsed.scheme == 'mailto':
            candidate = unquote(parsed.path).strip()
            if len(candidate) <= 254 and re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', candidate):
                field, value = 'email', candidate
        elif parsed.scheme in ('http', 'https') and not parsed.username:
            if host == 'wa.me':
                candidate = parsed.path.strip('/')
                if re.fullmatch(r'\d{8,15}', candidate): field, value = 'whatsapp', candidate
            elif host in ('api.whatsapp.com', 'web.whatsapp.com') and parsed.path.rstrip('/') == '/send':
                candidate = parse_qs(parsed.query).get('phone', [''])[0].lstrip('+')
                if re.fullmatch(r'\d{8,15}', candidate): field, value = 'whatsapp', candidate
            elif host == 'instagram.com' and re.fullmatch(r'/[A-Za-z0-9._]{1,30}/?', parsed.path):
                if parsed.path.strip('/') not in ('p', 'reel', 'stories', 'explore', 'accounts'):
                    field, value = 'instagram', 'https://www.instagram.com/' + parsed.path.strip('/') + '/'
        if field and (field, value) not in {(c['field'], c['value']) for c in found}:
            found.append({'field': field, 'value': value, 'source_url': page.final_url[:500],
                          'method': 'explicit_html_link', 'page_identity_matched': True,
                          'contact_authorized': False})
    return found[:20]


def inspect(pages):
    checks, contacts = [], []
    for page in pages[:4]:
        contacts.extend(public_contacts(page))
        labels = ' '.join(label for _, label in page.links).lower()
        predicates = {
            'context_services': bool(re.search(r'\b(servi[cç]os?|services?|produtos?|products?|menu|card[aá]pio)\b', labels)),
            'context_contact': bool(public_contacts(page) or page.form_count),
            'context_booking': bool(page.booking),
        }
        for key, present in predicates.items():
            # Truncated snapshots cannot establish missing HTML features.
            if not present and page.truncated: continue
            checks.append({'key': key, 'state': 'pass' if present else 'warn', 'source_url': page.final_url[:500]})
    unique = {(c['field'], c['value'], c['source_url']): c for c in contacts}
    return {'version': 'html-context-1', 'checks': checks, 'contacts': list(unique.values())[:40],
            'scope': 'Links e formulários do HTML consultado; sem execução de JavaScript, teste de envio ou confirmação de atividade comercial.'}


def persist(db, lead, research, context, now):
    """Reuse provenance and evidence; never overwrite the operator or choose among conflicting contacts."""
    from .enrichment import start_profile, apply_values, finalize
    from .evidence_intelligence import reconcile
    from .research import _same_site
    if research.status != 'confirmed' or not research.website_url or not isinstance(context, dict): return
    sources = {p.get('url') for p in json.loads(research.audit_json or '{}').get('pages', [])}
    sources.add(research.website_url)
    contacts = [c for c in context.get('contacts', [])[:40] if c.get('source_url') in sources
        and _same_site(c['source_url'], research.website_url) and c.get('method') == 'explicit_html_link']
    profile = start_profile(lead, now)
    profile['observed_contacts'] = [{**c, 'observed_at': now, 'contact_authorized': False} for c in contacts]
    for field in ('phone', 'whatsapp', 'instagram'):
        matches = [c for c in contacts if c.get('field') == field]
        if len({c['value'] for c in matches}) == 1:
            value = matches[0]
            apply_values(profile, lead, {field: value['value']}, value['source_url'], 85, now)
    finalize(profile, lead, now)
    existing = json.loads(research.checks_json or '[]')
    # Retain the original homepage checks, replace this analyzer's current snapshot.
    existing = [c for c in existing if not str(c.get('key', '')).startswith('context_')]
    existing.extend(c for c in context.get('checks', [])[:12] if c.get('source_url') in sources)
    research.checks_json = json.dumps(existing)
    reconcile(db, lead, research)
