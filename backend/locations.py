from __future__ import annotations

import json
import os
import socket
import time
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pydantic import ValidationError
from .search_location import SearchLocation


IBGE_MUNICIPALITIES_URL = os.getenv(
    "RADAR_IBGE_MUNICIPALITIES_URL",
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome",
)
_CACHE_TTL = 24 * 60 * 60
_cache_lock = Lock()
_cache_at = 0.0
_cache: list[dict[str, str]] = []


class LocationCatalogError(RuntimeError):
    pass


def _uf_from_item(item: dict[str, object]) -> tuple[str, str]:
    paths = (
        ("regiao-imediata", "regiao-intermediaria", "UF"),
        ("microrregiao", "mesorregiao", "UF"),
    )
    for path in paths:
        current: object = item
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if isinstance(current, dict):
            sigla = str(current.get("sigla") or "").strip().upper()
            nome = str(current.get("nome") or "").strip()
            if len(sigla) == 2 and nome:
                return sigla, nome
    return "", ""


def _load_catalog() -> list[dict[str, str]]:
    timeout = max(3.0, min(float(os.getenv("RADAR_LOCATION_TIMEOUT", "8")), 15.0))
    request = Request(
        IBGE_MUNICIPALITIES_URL,
        headers={"Accept": "application/json", "User-Agent": "ScoutLIQ/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(8_000_001)
    except HTTPError as exc:
        raise LocationCatalogError(f"IBGE HTTP {exc.code}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise LocationCatalogError("IBGE timeout") from exc
    except URLError as exc:
        raise LocationCatalogError("IBGE unavailable") from exc
    if len(payload) > 8_000_000:
        raise LocationCatalogError("IBGE payload too large")
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocationCatalogError("IBGE invalid response") from exc
    if not isinstance(raw, list):
        raise LocationCatalogError("IBGE invalid schema")
    locations: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("nome") or "").strip()
        identifier = str(item.get("id") or "").strip()
        uf, state = _uf_from_item(item)
        if not identifier or len(name) < 2 or not uf:
            continue
        key = f"{identifier}:{uf}"
        if key in seen:
            continue
        seen.add(key)
        locations.append({
            "id": identifier,
            "name": name,
            "uf": uf,
            "state": state,
            "state_code": uf,
            "country": "Brasil",
            "country_code": "BR",
            "formatted": f"{name}, {uf}, Brasil",
        })
    if len(locations) < 5000:
        raise LocationCatalogError("IBGE catalog incomplete")
    locations.sort(key=lambda item: (item["name"].casefold(), item["uf"]))
    return locations


def brazil_municipalities() -> list[dict[str, str]]:
    global _cache_at, _cache
    now = time.monotonic()
    if _cache and now - _cache_at < _CACHE_TTL:
        return _cache
    with _cache_lock:
        now = time.monotonic()
        if _cache and now - _cache_at < _CACHE_TTL:
            return _cache
        data = _load_catalog()
        _cache = data
        _cache_at = time.monotonic()
        return _cache


def search_locations(query: str, country: str = "", lang: str = "en", *, administrative: bool = False) -> list[dict]:
    """Global locality autocomplete via the same Geoapify key used by Radar.

    Brazil keeps an IBGE fallback so the feature remains useful if Geoapify is
    temporarily unavailable. No location is persisted here.
    """
    needle = " ".join(str(query or "").split()).strip()
    if len(needle) < 2:
        return []
    country = str(country or "").strip().upper()
    if country and (len(country) != 2 or not country.isalpha()):
        country = ""
    key = os.getenv("RADAR_GEOAPIFY_API_KEY", "").strip()
    if key:
        base = os.getenv("RADAR_GEOAPIFY_URL", "https://api.geoapify.com").rstrip("/")
        params: dict[str, str | int] = {
            "text": needle,
            "type": "city",
            "format": "json",
            "limit": 8,
            "lang": lang if lang in {"pt", "en", "es"} else "en",
            "apiKey": key,
        }
        if administrative:
            # Omit city-only filtering, then accept administrative results only.
            params.pop('type')
        if country:
            params["filter"] = f"countrycode:{country.lower()}"
        url = f"{base}/v1/geocode/autocomplete?{urlencode(params)}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "ScoutLIQ/1.0"})
        timeout = max(3.0, min(float(os.getenv("RADAR_LOCATION_TIMEOUT", "8")), 12.0))
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read(1_000_001)
            if len(payload) > 1_000_000:
                raise LocationCatalogError("Geoapify payload too large")
            raw = json.loads(payload.decode("utf-8"))
            results = raw.get("results") if isinstance(raw, dict) else None
            if isinstance(results, list):
                output: list[dict[str, str]] = []
                seen: set[str] = set()
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    resolved = _administrative_result(item) if administrative else None
                    if administrative and resolved is None:
                        continue
                    name = str(item.get("city") or item.get("name") or "").strip()
                    if resolved:
                        name = resolved.name
                    state = str(item.get("state") or "").strip()
                    state_code = str(item.get("state_code") or "").strip().upper()
                    country_name = str(item.get("country") or "").strip()
                    country_code = str(item.get("country_code") or "").strip().upper()[:2]
                    place_id = str(item.get("place_id") or "").strip()
                    formatted = str(item.get("formatted") or "").strip()
                    if len(name) < 2 or len(country_code) != 2:
                        continue
                    ident = place_id or f"{name}:{state_code}:{country_code}"
                    if ident in seen:
                        continue
                    seen.add(ident)
                    output.append({
                        "id": ident[:220],
                        "name": name[:100],
                        "uf": state_code[:10],
                        "state": state[:100],
                        "state_code": state_code[:10],
                        "country": country_name[:100],
                        "country_code": country_code,
                        "formatted": formatted[:220] or ", ".join(x for x in (name, state, country_name) if x),
                        **({'resolved': resolved.model_dump()} if resolved else {}),
                    })
                if output:
                    return output[:8]
        except (HTTPError, URLError, TimeoutError, socket.timeout, UnicodeDecodeError, json.JSONDecodeError):
            pass
    if not country or country == "BR":
        try:
            folded = needle.casefold()
            matches = [
                item for item in brazil_municipalities()
                if item["name"].casefold().startswith(folded)
                or folded in item["name"].casefold()
            ]
            if administrative:
                return [{**item, 'resolved': SearchLocation(
                    id=item['id'], name=item['name'], formatted=item['formatted'],
                    administrative_type='city', city=item['name'], state=item['state'],
                    state_code=item['state_code'], country=item['country'], country_code='BR',
                    source='ibge', resolved_at=int(time.time())).model_dump()} for item in matches[:8]]
            return matches[:8]
        except LocationCatalogError:
            pass
    raise LocationCatalogError("Location autocomplete unavailable")


def _administrative_result(item):
    kind = item.get('result_type')
    # Reject addresses/amenities, even if they contain a city field.
    kinds = {'country': 'country', 'state': 'state', 'county': 'county',
             'city': 'city', 'suburb': 'district', 'district': 'district', 'quarter': 'district'}
    if kind not in kinds:
        return None
    name = item.get(kind) or item.get('name')
    if kind == 'district': name = item.get('district') or item.get('suburb') or name
    box = item.get('bbox') or {}
    bbox = ([box.get(k) for k in ('lon1', 'lat1', 'lon2', 'lat2')]
            if isinstance(box, dict) and box else box if isinstance(box, list) else [])
    try:
        return SearchLocation(
            id=item.get('place_id', ''), name=name or '', formatted=item.get('formatted') or name or '',
            administrative_type=kinds[kind], subdivision=item.get('suburb') or item.get('district') or '',
            city=item.get('city') or '', state=item.get('state') or '', state_code=item.get('state_code') or '',
            country=item.get('country') or '', country_code=str(item.get('country_code') or '').upper(),
            latitude=item.get('lat'), longitude=item.get('lon'), bbox=bbox,
            source='geoapify', resolved_at=int(time.time()))
    except (ValidationError, TypeError):
        return None  # Untrusted provider data cannot become a valid selection.
