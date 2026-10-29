from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(value: str) -> str:
    value = unicodedata.normalize('NFKD', (value or '').casefold())
    value = ''.join(ch for ch in value if not unicodedata.combining(ch))
    return ' '.join(value.split())


def _first_float(patterns: list[str], text: str) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except (TypeError, ValueError):
                return None
    return None


def _first_int(patterns: list[str], text: str) -> int | None:
    value = _first_float(patterns, text)
    if value is None:
        return None
    return int(value)


FILTER_PHRASES: tuple[str, ...] = (
    'sem site', 'no website', 'without website', 'sin sitio', 'sin web',
    'site ruim', 'site com problema', 'website ruim', 'poor website', 'bad website', 'sitio malo',
    'sem agendamento', 'sem reserva', 'without booking', 'no booking', 'sin reservas', 'sin reserva',
    'sem cardapio', 'sem menu', 'without menu', 'no menu', 'sin menu',
    'sem catalogo', 'without catalog', 'no catalog', 'sin catalogo',
    'sem ecommerce', 'sem e-commerce', 'sem loja online', 'without ecommerce', 'no ecommerce', 'sin ecommerce',
    'presenca digital fraca', 'presença digital fraca', 'weak digital presence', 'presencia digital debil',
    'concorrentes melhores', 'competitive gap', 'brecha competitiva',
    'alta prioridade', 'high priority', 'alta prioridad',
    'timing alto', 'high timing', 'momento alto',
    'confianca alta', 'confiança alta', 'high confidence', 'confianza alta',
    'com whatsapp', 'with whatsapp', 'con whatsapp',
    'com telefone', 'with phone', 'con telefono',
    'com instagram', 'with instagram', 'con instagram',
)

GENERIC_CATEGORIES = {
    'empresa', 'empresas', 'negocio', 'negocios', 'negócio', 'negócios', 'estabelecimento', 'estabelecimentos',
    'company', 'companies', 'business', 'businesses', 'local businesses', 'negocio local', 'negocios locais',
}

SERVICE_TERMS: tuple[tuple[tuple[str, ...], str], ...] = (
    (('site institucional', 'institutional website', 'sitio institucional'), 'site_institucional'),
    (('landing page',), 'landing_page'),
    (('redesign', 'reformar site', 'refazer site', 'rediseño'), 'redesign'),
    (('agendamento', 'booking system', 'sistema de reservas', 'sistema de agendamento'), 'sistema_agendamento'),
    (('catalogo', 'catálogo', 'catalog'), 'catalogo'),
    (('ecommerce', 'e-commerce', 'loja online', 'online store'), 'ecommerce'),
    (('seo local',), 'seo_local'),
    (('otimizacao', 'otimização', 'performance', 'optimization'), 'otimizacao'),
)


def _strip_known_fragments(value: str) -> str:
    cleaned = value
    for phrase in FILTER_PHRASES:
        cleaned = re.sub(rf'\b{re.escape(_norm(phrase))}\b', ' ', cleaned)
    cleaned = re.sub(r'\b(?:com|with|con)?\s*(?:mais de|acima de|at least|more than|mas de|más de)?\s*\d+[\d.,]*\s*\+?\s*(?:avaliacoes|reviews|reseñas)\b', ' ', cleaned)
    cleaned = re.sub(r'\b(?:nota|rating|calificacion|calificación)\s*(?:acima de|maior que|above|over|superior a)?\s*\d[\d.,]*\+?', ' ', cleaned)
    cleaned = re.sub(r'\b(?:raio de|radius of|radio de|radius|raio|radio)\s*\d+[\d.,]*\s*km\b', ' ', cleaned)
    cleaned = re.sub(r'\b(?:score|pontuacao|pontuação)\s*(?:acima de|maior que|above|over|superior a)?\s*\d+\+?', ' ', cleaned)
    cleaned = re.sub(r'\b(?:confianca|confidence|confianza)\s*(?:acima de|above|over|superior a)?\s*\d+\+?', ' ', cleaned)
    cleaned = re.sub(r'\b(?:timing|momento)\s*(?:acima de|above|over|superior a)?\s*\d+\+?', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,.-')
    return cleaned


def _extract_location_and_category(normalized: str, fallback_location: str) -> tuple[str, str]:
    # Natural search is intentionally conservative: explicit "em/in/en" wins.
    # The tail is cut before the first known filter marker so "Recife sem site"
    # resolves to Recife instead of becoming an invalid location string.
    match = None
    for token in (' em ', ' in ', ' en '):
        pos = normalized.rfind(token)
        if pos > 0 and (match is None or pos > match[0]):
            match = (pos, token)
    if match:
        pos, token = match
        category_part = normalized[:pos].strip()
        tail = normalized[pos + len(token):].strip()
        cuts = [len(tail)]
        for marker in (' sem ', ' com ', ' with ', ' con ', ' mais de ', ' at least ', ' more than ', ' nota ', ' rating ', ' raio ', ' radius ', ' score ', ' timing ', ' confianca ', ' confidence ', ' confianza '):
            marker_pos = tail.find(marker)
            if marker_pos >= 0:
                cuts.append(marker_pos)
        location = tail[:min(cuts)].strip(' ,.-')
        category = _strip_known_fragments(category_part)
    else:
        location = _norm(fallback_location)
        category = _strip_known_fragments(normalized)

    # Remove generic lead words that add no value to provider search.
    category = re.sub(r'^(?:quero|buscar|busque|encontre|ache|find|search for|buscar por)\s+', '', category).strip()
    if category in GENERIC_CATEGORIES:
        category = ''
    return location, category


def interpret_natural_radar_query(text: str, *, fallback_location: str = '', fallback_country: str = '') -> dict[str, Any]:
    normalized = _norm(text)
    location, category = _extract_location_and_category(normalized, fallback_location)
    detected: list[str] = []
    unresolved: list[str] = []

    problem_keys: list[str] = []
    def problem(key: str, label: str, terms: tuple[str, ...]) -> None:
        if any(_norm(term) in normalized for term in terms):
            if key not in problem_keys:
                problem_keys.append(key)
            detected.append(label)

    problem('no_site', 'Sem site próprio', ('sem site', 'no website', 'without website', 'sin sitio', 'sin web'))
    problem('website_issues', 'Site com problemas', ('site ruim', 'site com problema', 'website ruim', 'poor website', 'bad website', 'sitio malo'))
    problem('booking_gap', 'Sem agendamento/reserva', ('sem agendamento', 'sem reserva', 'without booking', 'no booking', 'sin reservas', 'sin reserva'))
    problem('menu_gap', 'Sem cardápio/menu digital', ('sem cardapio', 'sem menu', 'without menu', 'no menu', 'sin menu'))
    problem('catalog_gap', 'Sem catálogo', ('sem catalogo', 'without catalog', 'no catalog', 'sin catalogo'))
    problem('ecommerce_gap', 'Sem e-commerce', ('sem ecommerce', 'sem e-commerce', 'sem loja online', 'without ecommerce', 'no ecommerce', 'sin ecommerce'))
    problem('weak_digital', 'Presença digital fraca', ('presenca digital fraca', 'presença digital fraca', 'weak digital presence', 'presencia digital debil'))
    problem('competitive_gap', 'Gap competitivo local', ('concorrentes melhores', 'competitive gap', 'brecha competitiva'))

    min_reviews = _first_int([
        r'(?:mais de|acima de|at least|more than|mas de|más de)\s*(\d+)\s*(?:avaliacoes|reviews|reseñas)',
        r'(\d+)\s*\+\s*(?:avaliacoes|reviews|reseñas)',
    ], normalized) or 0
    if min_reviews:
        detected.append(f'{min_reviews}+ avaliações')

    min_rating = _first_float([
        r'(?:nota|rating|calificacion|calificación)\s*(?:acima de|maior que|above|over|superior a)?\s*(\d(?:[.,]\d+)?)\+?',
        r'(\d(?:[.,]\d+)?)\+\s*(?:estrelas|stars|estrellas)',
    ], normalized) or 0.0
    if min_rating:
        min_rating = max(0.0, min(5.0, min_rating))
        detected.append(f'Nota {min_rating:g}+')

    radius_km = _first_int([
        r'(?:raio de|radius of|radio de|radius|raio|radio)\s*(\d+)\s*km',
    ], normalized) or 0
    radius_km = max(1, min(25, radius_km)) if radius_km else 5
    scope = 'radius' if re.search(r'\b(?:raio|radius|radio)\b', normalized) else 'region'
    if scope == 'radius':
        detected.append(f'Raio de {radius_km} km')

    min_score = 70 if any(term in normalized for term in ('alta prioridade', 'high priority', 'alta prioridad')) else 0
    explicit_score = _first_int([r'(?:score|pontuacao|pontuação)\s*(?:acima de|maior que|above|over|superior a)?\s*(\d+)\+?'], normalized)
    if explicit_score is not None:
        min_score = max(0, min(100, explicit_score))
    if min_score:
        detected.append(f'Score {min_score}+')

    min_confidence = 70 if any(term in normalized for term in ('confianca alta', 'confiança alta', 'high confidence', 'confianza alta')) else 0
    explicit_conf = _first_int([r'(?:confianca|confidence|confianza)\s*(?:acima de|above|over|superior a)?\s*(\d+)\+?'], normalized)
    if explicit_conf is not None:
        min_confidence = max(0, min(100, explicit_conf))
    if min_confidence:
        detected.append(f'Confiança {min_confidence}+')

    min_timing = 70 if any(term in normalized for term in ('timing alto', 'high timing', 'momento alto')) else 0
    explicit_timing = _first_int([r'(?:timing|momento)\s*(?:acima de|above|over|superior a)?\s*(\d+)\+?'], normalized)
    if explicit_timing is not None:
        min_timing = max(0, min(100, explicit_timing))
    if min_timing:
        detected.append(f'Timing {min_timing}+')

    contact_filter = ''
    if any(term in normalized for term in ('com whatsapp', 'with whatsapp', 'con whatsapp')):
        contact_filter = 'whatsapp'
        detected.append('Com WhatsApp')
    elif any(term in normalized for term in ('com instagram', 'with instagram', 'con instagram')):
        contact_filter = 'instagram'
        detected.append('Com Instagram')
    elif any(term in normalized for term in ('com telefone', 'with phone', 'con telefono')):
        contact_filter = 'phone'
        detected.append('Com telefone')

    service_key = ''
    for terms, key in SERVICE_TERMS:
        if any(_norm(term) in normalized for term in terms):
            service_key = key
            detected.append(f'Fit de serviço: {key}')
            break

    if not location:
        unresolved.append('location')
    if category:
        detected.insert(0, f'Nicho: {category}')
    if location:
        detected.insert(0, f'Local: {location}')

    return {
        'query': {
            'location': location,
            'category': category,
            'radius_km': radius_km,
            'scope': scope,
            'country': (fallback_country or '').upper()[:2],
            'municipality_id': '',
            'city_name': '',
            'state': '',
            'state_code': '',
            'problem_keys': problem_keys,
            'min_score': min_score,
            'min_rating': min_rating,
            'min_reviews': min_reviews,
            'contact_filter': contact_filter,
            'min_confidence': min_confidence,
            'min_timing': min_timing,
            'service_key': service_key,
            'min_service_score': 60 if service_key else 0,
        },
        'detected': detected[:12],
        'unresolved': unresolved,
    }
