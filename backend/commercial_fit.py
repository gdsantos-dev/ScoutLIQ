"""Source-independent commercial eligibility. Unknown facts remain unknown."""
import json
import re
import unicodedata


def norm(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(value or '').casefold()) if not unicodedata.combining(c)).split())


CHAINS = tuple(norm(n) for n in ("McDonald's", 'Burger King', 'Subway', 'Starbucks', 'KFC', 'Pizza Hut', "Domino's", "Habib's", 'Giraffas', "Bob's", 'Cacau Show', 'O Boticário', 'Carrefour', 'Atacadão', 'Assaí', 'Pão de Açúcar', 'Drogasil', 'Droga Raia', 'Pague Menos', 'Casas Bahia', 'Magazine Luiza', 'Riachuelo', 'Renner', 'C&A', 'Smart Fit', 'Bluefit', 'Walmart', 'Target', 'Apple Store'))


def facts(lead):
    try:
        value = json.loads(getattr(lead, 'qualification_json', '{}') or '{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def assess(lead, *, allow_chains=False):
    data = facts(lead)
    name, category = norm(lead.name), norm(lead.category)
    reasons = []
    # A reviewed exception needs an explicit reason, retained in the lead history.
    reviewed = bool(data.get('review_reason'))
    independent = reviewed and data.get('independence') == 'independent'
    chain = any(name == c or name.startswith(c + ' ') or name.startswith(c + '-') for c in CHAINS)
    public = bool(re.search(r'\b(prefeitura|secretaria municipal|camara municipal|orgao publico|city hall|government|public administration)\b', name + ' ' + category))
    if reviewed and data.get('entity_type') in ('commercial','public'): public=data['entity_type']=='public'
    closed = data.get('operating_status') == 'closed'
    if public: reasons.append({'key': 'public_entity', 'label': 'Órgão público identificado pelo nome ou categoria.'})
    if closed: reasons.append({'key': 'closed', 'label': 'Encerramento registrado na revisão comercial.'})
    if reviewed and data.get('size')=='large': reasons.append({'key':'large_company','label':'Grande organização registrada na revisão; fora do perfil inicial.'})
    if (chain or data.get('independence') == 'centralized') and not independent and not allow_chains:
        reasons.append({'key': 'centralized_chain', 'label': 'Rede identificada; autonomia local precisa de revisão.'})
    if reasons:
        return {'status': 'incompatible', 'reasons': reasons, 'version': 'fit-1', 'independence': data.get('independence', 'unknown')}
    if not category or category in {'servicos', 'empresa', 'negocio', 'desconhecido'}:
        return {'status': 'indeterminate', 'reasons': [{'key': 'unknown_business', 'label': 'Categoria comercial insuficiente.'}], 'version': 'fit-1', 'independence': 'unknown'}
    return {'status': 'compatible', 'reasons': [{'key': 'business_category', 'label': 'Categoria comercial identificada; sem exclusão conhecida.'}], 'version': 'fit-1', 'independence': 'independent' if independent else 'unknown'}


def same_business(a, b):
    """Names alone never merge businesses, including homonyms in the same city."""
    if norm(a.name) != norm(b.name) or norm(a.city) != norm(b.city) or norm(a.country) != norm(b.country):
        return False
    digits = lambda x: re.sub(r'\D', '', str(x or ''))
    phone = digits(a.phone)
    address = norm(a.address)
    coordinates = all(getattr(x, 'latitude', 0) and getattr(x, 'longitude', 0) for x in (a, b))
    nearby = coordinates and abs(a.latitude-b.latitude) < .0003 and abs(a.longitude-b.longitude) < .0003
    if coordinates and not nearby: return False
    if address and norm(b.address) and address != norm(b.address):
        return bool(phone and phone == digits(b.phone) and nearby)
    return bool((phone and phone == digits(b.phone)) or (address and address == norm(b.address)) or nearby)
