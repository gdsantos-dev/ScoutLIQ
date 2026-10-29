from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, unquote_plus, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .providers import (
    GeoapifyProvider,
    ProviderConfigurationError,
    ProviderError,
    ProviderTimeout,
    _clean_text,
    _contact_instagram,
    _contact_phone,
    _contact_website,
    _contact_whatsapp,
    _geoapify_category,
    _normalized,
)


class GoogleMapsImportError(RuntimeError):
    pass


class GoogleMapsImportTimeout(GoogleMapsImportError):
    pass


@dataclass(frozen=True)
class ParsedGoogleMapsLink:
    resolved_url: str
    name: str
    query_text: str
    latitude: float | None
    longitude: float | None
    source_id: str


_ALLOWED_HOSTS = {
    "google.com",
    "www.google.com",
    "maps.google.com",
    "google.com.br",
    "www.google.com.br",
    "maps.google.com.br",
    "maps.app.goo.gl",
    "goo.gl",
}
_SHORT_HOSTS = {"maps.app.goo.gl", "goo.gl"}
_COORD_RE = re.compile(r"(?<!\d)(-?\d{1,2}(?:\.\d+)?),\s*(-?\d{1,3}(?:\.\d+)?)(?!\d)")


def _allowed_google_host(host: str | None) -> bool:
    value = (host or "").lower().rstrip(".")
    return value in _ALLOWED_HOSTS


def _validate_google_maps_url(raw: str) -> str:
    value = raw.strip()
    if not value or len(value) > 2000:
        raise GoogleMapsImportError("Cole um link válido do Google Maps.")
    try:
        parsed = urlparse(value)
    except ValueError as exc:
        raise GoogleMapsImportError("Cole um link válido do Google Maps.") from exc
    if parsed.scheme != "https" or not _allowed_google_host(parsed.hostname) or parsed.username:
        raise GoogleMapsImportError("Aceitamos apenas links HTTPS do Google Maps.")
    if parsed.hostname not in _SHORT_HOSTS and "/maps" not in parsed.path and parsed.hostname not in {"maps.google.com", "maps.google.com.br"}:
        raise GoogleMapsImportError("Esse link não parece ser do Google Maps.")
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


def resolve_google_maps_url(raw: str) -> str:
    current = _validate_google_maps_url(raw)
    parsed = urlparse(current)
    if parsed.hostname not in _SHORT_HOSTS:
        return current

    timeout = max(2.0, min(float(os.getenv("RADAR_GOOGLE_LINK_TIMEOUT", "5")), 8.0))
    opener = build_opener(_NoRedirect())
    user_agent = os.getenv("RADAR_USER_AGENT", "ScoutLIQ/1.0")[:250]
    for _ in range(5):
        request = Request(current, headers={"User-Agent": user_agent, "Accept": "text/html,*/*"}, method="GET")
        try:
            response = opener.open(request, timeout=timeout)
            location = response.headers.get("Location")
            if not location:
                return current
        except HTTPError as exc:
            if 300 <= exc.code < 400:
                location = exc.headers.get("Location")
                if not location:
                    raise GoogleMapsImportError("O link encurtado do Google Maps não pôde ser resolvido.") from exc
            else:
                raise GoogleMapsImportError("O Google Maps recusou esse link no momento.") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise GoogleMapsImportTimeout("O link do Google Maps demorou para responder.") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise GoogleMapsImportTimeout("O link do Google Maps demorou para responder.") from exc
            raise GoogleMapsImportError("Não foi possível abrir o link do Google Maps.") from exc

        next_url = urljoin(current, location)
        _validate_google_maps_url(next_url)
        current = next_url
        if urlparse(current).hostname not in _SHORT_HOSTS:
            return current
    raise GoogleMapsImportError("O link do Google Maps redirecionou vezes demais.")


def _coords_from_text(value: str) -> tuple[float, float] | None:
    match = _COORD_RE.search(value)
    if not match:
        return None
    try:
        lat = float(match.group(1))
        lon = float(match.group(2))
    except ValueError:
        return None
    if -85 <= lat <= 85 and -180 <= lon <= 180:
        return lat, lon
    return None


def parse_google_maps_url(resolved_url: str) -> ParsedGoogleMapsLink:
    resolved_url = _validate_google_maps_url(resolved_url)
    parsed = urlparse(resolved_url)
    query = parse_qs(parsed.query)
    decoded_path = unquote(parsed.path)
    full = unquote(resolved_url)

    name = ""
    place_match = re.search(r"/(?:maps/)?place/([^/@?]+)", decoded_path, flags=re.IGNORECASE)
    if place_match:
        name = " ".join(unquote_plus(place_match.group(1)).replace("+", " ").split())[:160]

    query_text = ""
    for key in ("query", "q", "destination", "daddr"):
        values = query.get(key)
        if values:
            candidate = " ".join(values[0].split())
            if candidate:
                query_text = candidate[:500]
                break
    if not name and query_text and not _coords_from_text(query_text):
        name = query_text[:160]

    coords = None
    # !3d/!4d is the place coordinate when present; /@lat,lon is often only the viewport center.
    data_match = re.search(r"!3d(-?\d{1,2}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)", full)
    if data_match:
        coords = _coords_from_text(f"{data_match.group(1)},{data_match.group(2)}")
    if coords is None:
        at_match = re.search(r"/@(-?\d{1,2}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)", full)
        if at_match:
            coords = _coords_from_text(f"{at_match.group(1)},{at_match.group(2)}")
    if coords is None:
        for key in ("ll", "query", "q"):
            values = query.get(key)
            if values:
                coords = _coords_from_text(values[0])
                if coords:
                    break

    source_token = ""
    for key in ("cid", "query_place_id", "place_id"):
        values = query.get(key)
        if values and values[0]:
            source_token = values[0][:120]
            break
    if not source_token:
        opaque = re.search(r"!1s([^!]+)", full)
        if opaque:
            source_token = opaque.group(1)[:120]
    if not source_token:
        source_token = hashlib.sha256(resolved_url.encode("utf-8")).hexdigest()[:32]

    if not name and not query_text and coords is None:
        raise GoogleMapsImportError(
            "Esse link não traz nome ou coordenadas suficientes. Abra o estabelecimento no Google Maps e use Compartilhar > Copiar link."
        )

    return ParsedGoogleMapsLink(
        resolved_url=resolved_url,
        name=name,
        query_text=query_text,
        latitude=coords[0] if coords else None,
        longitude=coords[1] if coords else None,
        source_id=f"gmaps:{source_token}"[:160],
    )


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def _candidate_score(item: dict[str, object], parsed: ParsedGoogleMapsLink) -> float:
    score = 0.0
    candidate_name = _clean_text(item.get("name"), 160)
    if parsed.name and candidate_name:
        expected = _normalized(parsed.name)
        actual = _normalized(candidate_name)
        if expected == actual:
            score += 50
        elif expected in actual or actual in expected:
            score += 32
        else:
            expected_parts = {part for part in expected.split() if len(part) > 2}
            actual_parts = {part for part in actual.split() if len(part) > 2}
            if expected_parts:
                score += 20 * len(expected_parts & actual_parts) / len(expected_parts)
    if parsed.latitude is not None and parsed.longitude is not None:
        try:
            distance = _distance_m(parsed.latitude, parsed.longitude, float(item.get("lat")), float(item.get("lon")))
        except (TypeError, ValueError):
            distance = 999999
        if distance <= 100:
            score += 45
        elif distance <= 500:
            score += 35
        elif distance <= 1500:
            score += 20
        elif distance <= 5000:
            score += 5
        else:
            score -= 25
    result_type = _clean_text(item.get("result_type"), 40)
    if result_type in {"amenity", "building", "street", "postcode"}:
        score += 2
    return score


def _geoapify_lookup(parsed: ParsedGoogleMapsLink) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    try:
        provider = GeoapifyProvider()
    except ProviderConfigurationError:
        return {}, ["Geoapify não está configurado; preenchemos apenas o que foi possível extrair do link."]

    search_text = parsed.name or parsed.query_text
    selected: dict[str, object] = {}
    if search_text:
        params: dict[str, object] = {
            "text": search_text,
            "format": "json",
            "lang": "pt",
            "limit": 6,
            "filter": "countrycode:br",
            "apiKey": provider.api_key,
        }
        if parsed.latitude is not None and parsed.longitude is not None:
            params["bias"] = f"proximity:{parsed.longitude:.6f},{parsed.latitude:.6f}"
        response = provider._request_json("/v1/geocode/search", params, timeout=min(provider.timeout, 6.0))
        if isinstance(response, dict) and isinstance(response.get("results"), list):
            candidates = [item for item in response["results"] if isinstance(item, dict)]
            if candidates:
                selected = max(candidates, key=lambda item: _candidate_score(item, parsed))
                if _candidate_score(selected, parsed) < 20:
                    selected = {}

    if not selected and parsed.latitude is not None and parsed.longitude is not None:
        response = provider._request_json(
            "/v1/geocode/reverse",
            {
                "lat": parsed.latitude,
                "lon": parsed.longitude,
                "format": "json",
                "lang": "pt",
                "limit": 1,
                "apiKey": provider.api_key,
            },
            timeout=min(provider.timeout, 6.0),
        )
        if isinstance(response, dict) and isinstance(response.get("results"), list) and response["results"]:
            first = response["results"][0]
            if isinstance(first, dict):
                selected = first
                warnings.append("O estabelecimento não foi confirmado pelo nome; endereço e cidade vieram das coordenadas do link.")

    if not selected:
        return {}, ["Não conseguimos cruzar esse link com a base pública. Revise os campos antes de salvar."]

    place_id = _clean_text(selected.get("place_id"), 220)
    details: dict[str, object] = {}
    if place_id:
        try:
            details = provider._details(place_id)
        except ProviderError as exc:
            logging.getLogger("scoutliq").info(
                "Radar google_maps_import_details_failed place=%s status=%s error=%s",
                place_id[:18],
                exc.status_code,
                type(exc).__name__,
            )
    merged = {**selected, **details}
    return merged, warnings


def import_google_maps_link(raw_url: str) -> dict[str, object]:
    resolved = resolve_google_maps_url(raw_url)
    parsed = parse_google_maps_url(resolved)
    warnings: list[str] = []
    try:
        matched, upstream_warnings = _geoapify_lookup(parsed)
        warnings.extend(upstream_warnings)
    except ProviderTimeout as exc:
        matched = {}
        warnings.append("A fonte de enriquecimento demorou para responder; usamos apenas os dados do link.")
        logging.getLogger("scoutliq").info("Radar google_maps_import_geoapify_timeout error=%s", type(exc).__name__)
    except ProviderError as exc:
        matched = {}
        warnings.append("A fonte de enriquecimento está indisponível; usamos apenas os dados do link.")
        logging.getLogger("scoutliq").info(
            "Radar google_maps_import_geoapify_failed status=%s error=%s", exc.status_code, type(exc).__name__
        )

    try:
        latitude = float(matched.get("lat")) if matched.get("lat") is not None else parsed.latitude
        longitude = float(matched.get("lon")) if matched.get("lon") is not None else parsed.longitude
    except (TypeError, ValueError):
        latitude, longitude = parsed.latitude, parsed.longitude

    matched_name = _clean_text(matched.get("name"), 160)
    name = matched_name or parsed.name or parsed.query_text
    city = _clean_text(matched.get("city") or matched.get("municipality") or matched.get("county"), 100)
    country_code = _clean_text(matched.get("country_code"), 4).upper() or "BR"
    address = _clean_text(matched.get("formatted"), 250)
    category = _geoapify_category(matched.get("categories")) if matched else "Estabelecimento"
    website = _contact_website(matched) if matched else ""
    instagram = _contact_instagram(matched) if matched else ""
    phone = _contact_phone(matched) if matched else ""
    whatsapp = _contact_whatsapp(matched) if matched else ""

    if not name:
        warnings.append("Nome não identificado automaticamente.")
    if not city:
        warnings.append("Cidade não identificada automaticamente.")
    if latitude is None or longitude is None:
        warnings.append("Coordenadas não identificadas automaticamente.")

    note = "Importado a partir de um link público do Google Maps. Revise os dados antes de salvar."
    return {
        "source": "google_maps",
        "source_id": parsed.source_id,
        "resolved_url": parsed.resolved_url,
        "warnings": list(dict.fromkeys(warnings)),
        "lead": {
            "name": name[:160],
            "category": category[:80] if category else "Estabelecimento",
            "city": city[:100],
            "country": country_code[:2] if len(country_code) == 2 else "BR",
            "address": address[:250],
            "latitude": latitude,
            "longitude": longitude,
            "rating": None,
            "reviews": None,
            "website": website,
            "website_status": "unknown",
            "instagram": instagram,
            "instagram_active": False,
            "phone": phone,
            "whatsapp": whatsapp,
            "contact": "",
            "potential_cents": 0,
            "notes": note,
        },
    }
