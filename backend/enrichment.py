from __future__ import annotations

import json
import time
from typing import Any

from .schemas import LeadInput

FIELDS = ('website', 'phone', 'whatsapp', 'instagram')


def _decoded(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or '{}')
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _value(lead: Any, field: str) -> str:
    raw = getattr(lead, field, '')
    return str(raw or '').strip()


def lead_input(lead: Any) -> LeadInput:
    return LeadInput(
        name=lead.name,
        category=lead.category,
        city=lead.city,
        country=lead.country,
        address=lead.address,
        latitude=lead.latitude,
        longitude=lead.longitude,
        rating=lead.rating,
        reviews=lead.reviews,
        website=lead.website,
        website_status=lead.website_status,
        instagram=lead.instagram,
        instagram_active=lead.instagram_active,
        phone=lead.phone,
        whatsapp=lead.whatsapp,
        contact=lead.contact,
        potential_cents=lead.potential_cents,
        potential_currency=lead.potential_currency,
        notes=lead.notes,
    )


def start_profile(lead: Any, now: int | None = None) -> dict[str, Any]:
    checked_at = int(now or time.time())
    previous = _decoded(getattr(lead, 'enrichment_json', '{}'))
    fields = previous.get('fields') if isinstance(previous.get('fields'), dict) else {}
    attempts: list[dict[str, Any]] = []
    for field in FIELDS:
        value = _value(lead, field)
        if not value:
            continue
        existing = fields.get(field) if isinstance(fields.get(field), dict) else {}
        fields[field] = {
            'value': value,
            'source': existing.get('source') or (getattr(lead, 'source', '') or 'existing'),
            'confidence': int(existing.get('confidence') or 70),
            'checked_at': int(existing.get('checked_at') or checked_at),
        }
    return {'fields': fields, 'attempts': attempts, 'checked_at': checked_at, 'coverage': 0,
            'observed_contacts': previous.get('observed_contacts', [])}


def missing(profile: dict[str, Any]) -> list[str]:
    fields = profile.get('fields') if isinstance(profile.get('fields'), dict) else {}
    return [field for field in FIELDS if not (isinstance(fields.get(field), dict) and fields[field].get('value'))]


def record_attempt(profile: dict[str, Any], source: str, status: str, fields: list[str] | None = None, detail: str = '') -> None:
    attempts = profile.setdefault('attempts', [])
    if not isinstance(attempts, list):
        attempts = []
        profile['attempts'] = attempts
    attempts.append({
        'source': source[:50],
        'status': status[:20],
        'fields': (fields or [])[:8],
        'detail': detail[:180],
    })


def apply_values(profile: dict[str, Any], lead: Any, values: dict[str, Any], source: str, confidence: int, checked_at: int | None = None) -> list[str]:
    timestamp = int(checked_at or time.time())
    fields = profile.setdefault('fields', {})
    changed: list[str] = []
    for field in FIELDS:
        value = str(values.get(field) or '').strip()
        if not value:
            continue
        current = _value(lead, field)
        if not current:
            setattr(lead, field, value)
            changed.append(field)
            current = value
        if current == value:
            fields[field] = {
                'value': current,
                'source': source,
                'confidence': max(0, min(int(confidence), 100)),
                'checked_at': timestamp,
            }
    return changed


def provider_values(provider: Any, lead: Any) -> dict[str, str]:
    if provider is None or not getattr(lead, 'source_id', None):
        return {}
    if getattr(provider, 'name', '') != getattr(lead, 'source', ''):
        return {}
    enrich = getattr(provider, 'enrich_existing', None)
    if not callable(enrich):
        return {}
    enriched = enrich(str(lead.source_id), lead_input(lead))
    return {field: str(getattr(enriched, field, '') or '') for field in FIELDS}


def research_values(result: dict[str, Any]) -> dict[str, str]:
    if result.get('status') != 'confirmed':
        return {}
    contacts = result.get('contacts') if isinstance(result.get('contacts'), dict) else {}
    return {
        'website': str(result.get('website_url') or ''),
        'phone': str(contacts.get('phone') or ''),
        'whatsapp': str(contacts.get('whatsapp') or ''),
        'instagram': str(contacts.get('instagram') or ''),
    }


def finalize(profile: dict[str, Any], lead: Any, now: int | None = None) -> dict[str, Any]:
    timestamp = int(now or time.time())
    fields = profile.get('fields') if isinstance(profile.get('fields'), dict) else {}
    present = sum(1 for field in FIELDS if isinstance(fields.get(field), dict) and fields[field].get('value'))
    profile['coverage'] = round(present / len(FIELDS) * 100)
    profile['completed_at'] = timestamp
    profile['missing'] = missing(profile)
    lead.enrichment_json = json.dumps(profile, ensure_ascii=False, separators=(',', ':'))
    lead.enrichment_analyzed_at = timestamp
    return profile
