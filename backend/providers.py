"""Discovery providers for Radar. The map renderer is deliberately independent."""
from __future__ import annotations

import json
import logging
import math
import os
import re
import socket
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from .consumption import metered, submit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import ORIGIN, PRODUCTION
from .schemas import LeadInput
from .search_location import SearchLocation


from .discovery_contract import DiscoveryQuery


class DiscoveryResult(BaseModel):
    source_id: str = Field(min_length=2, max_length=160)
    lead: LeadInput


class DiscoveryBatch(BaseModel):
    provider: str
    location_label: str
    results: list[DiscoveryResult]
    complete: bool = True
    scanned: int = 0
    result_limit: int | None = None
    scope: str = "region"


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ProviderTimeout(ProviderError):
    pass


class ProviderConfigurationError(ProviderError):
    pass


class LocationNotFound(ProviderError):
    pass


class EstablishmentProvider(Protocol):
    name: str

    def search(self, query: DiscoveryQuery) -> DiscoveryBatch: ...


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _clean_text(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:max_length]


def _safe_url(value: object) -> str:
    raw = _clean_text(value, 500)
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    elif "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username:
        return ""
    return raw[:500]


def _instagram_url(value: object) -> str:
    raw = _clean_text(value, 500)
    if not raw:
        return ""
    if "instagram.com" in raw or raw.startswith(("http://", "https://")):
        return _safe_url(raw)
    handle = raw.strip().lstrip("@").strip("/")
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", handle):
        return ""
    return f"https://www.instagram.com/{handle}/"


def _whatsapp(value: object) -> str:
    raw = _clean_text(value, 100)
    if not raw:
        return ""
    digits = "".join(re.findall(r"\d", raw))
    return digits if 8 <= len(digits) <= 15 else ""


CATEGORY_LABELS = {
    ("shop", "hairdresser"): "Barbearia / salão",
    ("amenity", "restaurant"): "Restaurante",
    ("amenity", "cafe"): "Cafeteria",
    ("amenity", "fast_food"): "Lanchonete",
    ("amenity", "bar"): "Bar",
    ("amenity", "pub"): "Bar",
    ("leisure", "fitness_centre"): "Academia",
    ("shop", "pet"): "Pet shop",
    ("amenity", "veterinary"): "Veterinária",
    ("healthcare", "clinic"): "Clínica",
    ("amenity", "clinic"): "Clínica",
    ("amenity", "dentist"): "Dentista",
    ("healthcare", "dentist"): "Dentista",
    ("office", "lawyer"): "Advocacia",
    ("office", "accountant"): "Contabilidade",
    ("office", "it"): "Tecnologia / software",
    ("office", "estate_agent"): "Imobiliária",
    ("shop", "car_repair"): "Oficina automotiva",
    ("shop", "car"): "Concessionária",
    ("shop", "beauty"): "Beleza",
    ("shop", "clothes"): "Loja de roupas",
    ("shop", "bakery"): "Padaria",
    ("amenity", "pharmacy"): "Farmácia",
    ("shop", "supermarket"): "Supermercado",
    ("tourism", "hotel"): "Hotel",
}

NICHE_SELECTORS: list[tuple[tuple[str, ...], list[tuple[str, str]]]] = [
    (("barbearia", "barber", "cabeleireiro", "salao"), [("shop", "hairdresser")]),
    (("restaurante", "restaurant"), [("amenity", "restaurant")]),
    (("pizzaria", "pizza"), [("cuisine", "pizza")]),
    (("cafeteria", "cafe", "coffee"), [("amenity", "cafe")]),
    (("lanchonete", "fast food"), [("amenity", "fast_food")]),
    (("bar", "pub"), [("amenity", "bar"), ("amenity", "pub")]),
    (("academia", "fitness", "gym"), [("leisure", "fitness_centre")]),
    (("pet shop", "petshop"), [("shop", "pet")]),
    (("veterinaria", "veterinario"), [("amenity", "veterinary")]),
    (("clinica", "clinic"), [("healthcare", "clinic"), ("amenity", "clinic")]),
    (("dentista", "odontologia", "dentist"), [("amenity", "dentist"), ("healthcare", "dentist")]),
    (("advogado", "advocacia", "lawyer"), [("office", "lawyer")]),
    (("contabilidade", "contador", "accountant"), [("office", "accountant")]),
    (("imobiliaria", "estate agent"), [("office", "estate_agent")]),
    (("oficina", "mecanica", "car repair"), [("shop", "car_repair")]),
    (("concessionaria",), [("shop", "car")]),
    (("beleza", "estetica"), [("shop", "beauty")]),
    (("roupa", "moda"), [("shop", "clothes")]),
    (("padaria", "bakery"), [("shop", "bakery")]),
    (("farmacia", "pharmacy"), [("amenity", "pharmacy")]),
    (("supermercado", "mercado"), [("shop", "supermarket")]),
    (("hotel", "pousada"), [("tourism", "hotel"), ("tourism", "guest_house")]),
]

BROAD_KEYS = ("shop", "amenity", "office", "craft", "tourism", "healthcare")

# A broad Radar search used to ask Overpass for every named shop/amenity/office/etc.
# In dense cities that can touch tens of thousands of OSM objects before the output
# limit is applied, which is exactly the kind of query public Overpass instances
# time out on. Keep the no-niche search broad enough for ScoutLIQ, but constrain it
# to the business categories the product can currently classify and score.
DEFAULT_DISCOVERY_SELECTORS = tuple(
    dict.fromkeys(
        selector
        for _aliases, selectors in NICHE_SELECTORS
        for selector in selectors
    )
)


def _selectors(category: str) -> list[tuple[str, str]] | None:
    needle = _normalized(category)
    if not needle:
        return None
    for aliases, selectors in NICHE_SELECTORS:
        if any(alias in needle for alias in aliases):
            return selectors
    return []


def _category(tags: dict[str, object]) -> str:
    for key in ("shop", "amenity", "office", "craft", "tourism", "healthcare", "leisure"):
        value = _clean_text(tags.get(key), 80)
        if not value:
            continue
        if (key, value) in CATEGORY_LABELS:
            return CATEGORY_LABELS[(key, value)]
        return value.replace("_", " ").strip().title()[:80]
    return "Estabelecimento"


def _matches_unknown_category(category: str, name: str, tags: dict[str, object]) -> bool:
    needle = _normalized(category)
    if not needle:
        return True
    haystack = " ".join(
        [name, _category(tags)]
        + [_clean_text(tags.get(k), 100) for k in (*BROAD_KEYS, "leisure", "cuisine", "description")]
    )
    return needle in _normalized(haystack)



GEOAPIFY_NICHES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("hamburguer", "burger"), ("catering.fast_food.burger", "catering.restaurant.burger")),
    (("barbearia", "barber", "cabeleireiro", "salao"), ("service.beauty.hairdresser",)),
    (("restaurante", "restaurant"), ("catering.restaurant",)),
    (("pizzaria", "pizza"), ("catering.restaurant.pizza", "catering.fast_food.pizza")),
    (("cafeteria", "cafe", "coffee"), ("catering.cafe",)),
    (("lanchonete", "fast food"), ("catering.fast_food",)),
    (("bar", "pub"), ("catering.bar", "catering.pub")),
    (("academia", "fitness", "gym"), ("sport.fitness",)),
    (("pet shop", "petshop"), ("pet.shop",)),
    (("veterinaria", "veterinario"), ("pet.veterinary",)),
    (("clinica", "clinic"), ("healthcare.clinic_or_praxis",)),
    (("dentista", "odontologia", "dentist"), ("healthcare.dentist",)),
    (("advogado", "advocacia", "lawyer"), ("office.lawyer",)),
    (("contabilidade", "contador", "accountant"), ("office.accountant",)),
    (("imobiliaria", "estate agent"), ("office.estate_agent", "service.estate_agent")),
    (("oficina", "mecanica", "car repair"), ("service.vehicle.repair.car",)),
    (("concessionaria",), ("commercial.vehicle",)),
    (("beleza", "estetica"), ("service.beauty",)),
    (("roupa", "moda"), ("commercial.clothing",)),
    (("padaria", "bakery"), ("commercial.food_and_drink.bakery",)),
    (("farmacia", "pharmacy"), ("healthcare.pharmacy", "commercial.health_and_beauty.pharmacy")),
    (("supermercado", "mercado"), ("commercial.supermarket",)),
    (("hotel", "pousada"), ("accommodation.hotel", "accommodation.guest_house")),
]

GEOAPIFY_DEFAULT_CATEGORIES = tuple(
    dict.fromkeys(category for _aliases, categories in GEOAPIFY_NICHES for category in categories)
)

GEOAPIFY_CATEGORY_LABELS: tuple[tuple[str, str], ...] = (
    ("catering.fast_food.burger", "Hamburgueria"),
    ("catering.restaurant.burger", "Hamburgueria"),
    ("service.beauty.hairdresser", "Barbearia / salão"),
    ("catering.restaurant.pizza", "Pizzaria"),
    ("catering.fast_food.pizza", "Pizzaria"),
    ("catering.restaurant", "Restaurante"),
    ("catering.cafe", "Cafeteria"),
    ("catering.fast_food", "Lanchonete"),
    ("catering.bar", "Bar"),
    ("catering.pub", "Bar"),
    ("sport.fitness", "Academia"),
    ("pet.shop", "Pet shop"),
    ("pet.veterinary", "Veterinária"),
    ("healthcare.dentist", "Dentista"),
    ("healthcare.clinic_or_praxis", "Clínica"),
    ("office.lawyer", "Advocacia"),
    ("office.accountant", "Contabilidade"),
    ("office.estate_agent", "Imobiliária"),
    ("service.estate_agent", "Imobiliária"),
    ("service.vehicle.repair.car", "Oficina automotiva"),
    ("commercial.vehicle", "Concessionária / automotivo"),
    ("service.beauty", "Beleza"),
    ("commercial.clothing", "Loja de roupas"),
    ("commercial.food_and_drink.bakery", "Padaria"),
    ("healthcare.pharmacy", "Farmácia"),
    ("commercial.health_and_beauty.pharmacy", "Farmácia"),
    ("commercial.supermarket", "Supermercado"),
    ("accommodation.hotel", "Hotel"),
    ("accommodation.guest_house", "Pousada"),
)


def _geoapify_categories(category: str) -> tuple[str, ...] | None:
    needle = _normalized(category)
    if not needle:
        return None
    for aliases, categories in GEOAPIFY_NICHES:
        if any(alias in needle for alias in aliases):
            return categories
    return ()


def _geoapify_category(values: object) -> str:
    categories = [str(value) for value in values] if isinstance(values, list) else []
    for prefix, label in GEOAPIFY_CATEGORY_LABELS:
        if any(value == prefix or value.startswith(prefix + ".") for value in categories):
            return label
    for value in categories:
        if value and value.split(".", 1)[0] in {
            "commercial", "catering", "service", "healthcare", "office", "sport", "pet", "accommodation"
        }:
            return value.rsplit(".", 1)[-1].replace("_", " ").strip().title()[:80]
    return "Estabelecimento"


def _geoapify_raw(properties: dict[str, object]) -> dict[str, object]:
    datasource = properties.get("datasource")
    if not isinstance(datasource, dict):
        return {}
    raw = datasource.get("raw")
    return raw if isinstance(raw, dict) else {}


def _contact_phone(properties: dict[str, object]) -> str:
    contact = properties.get("contact")
    if isinstance(contact, dict):
        value = contact.get("phone")
        if isinstance(value, list):
            value = value[0] if value else ""
        phone = _clean_text(value, 30)
        if phone:
            return phone
    raw = _geoapify_raw(properties)
    return _clean_text(raw.get("contact:phone") or raw.get("phone") or raw.get("mobile"), 30)


def _contact_whatsapp(properties: dict[str, object]) -> str:
    contact = properties.get("contact")
    if isinstance(contact, dict):
        value = contact.get("whatsapp")
        if value:
            parsed = _whatsapp(value)
            if parsed:
                return parsed
    raw = _geoapify_raw(properties)
    return _whatsapp(raw.get("contact:whatsapp") or raw.get("whatsapp"))


def _contact_instagram(properties: dict[str, object]) -> str:
    contact = properties.get("contact")
    if isinstance(contact, dict):
        value = contact.get("instagram")
        if value:
            parsed = _instagram_url(value)
            if parsed:
                return parsed
    raw = _geoapify_raw(properties)
    return _instagram_url(raw.get("contact:instagram") or raw.get("instagram"))


def _contact_website(properties: dict[str, object]) -> str:
    value = properties.get("website")
    if isinstance(value, list):
        value = value[0] if value else ""
    website = _safe_url(value)
    if website:
        return website
    raw = _geoapify_raw(properties)
    return _safe_url(raw.get("contact:website") or raw.get("website") or raw.get("url"))


def _state_code(value: object) -> str:
    code = _clean_text(value, 12).upper()
    return code.rsplit("-", 1)[-1] if code else ""


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def _candidate_priority(item: DiscoveryResult, center: tuple[float, float], radius_m: float) -> float:
    lead = item.lead
    points = 0.0
    if not lead.website:
        points += 24
    if lead.instagram:
        points += 12
    if lead.whatsapp:
        points += 14
    if lead.phone:
        points += 9
    if lead.address:
        points += 4
    if lead.category != "Estabelecimento":
        points += 3
    distance = _distance_m(center[0], center[1], float(lead.latitude), float(lead.longitude))
    if radius_m > 0:
        points += max(0.0, 6.0 * (1.0 - distance / radius_m))
    return points


def _diversify_results(items: list[DiscoveryResult], limit: int) -> list[DiscoveryResult]:
    if len(items) <= limit:
        return items
    selected: list[DiscoveryResult] = []
    counts: dict[str, int] = {}
    # First pass prevents a broad search from becoming 20 restaurants/fast-food rows.
    per_category = max(2, min(5, limit // 4 or 2))
    for item in items:
        key = item.lead.category
        if counts.get(key, 0) >= per_category:
            continue
        counts[key] = counts.get(key, 0) + 1
        selected.append(item)
        if len(selected) >= limit:
            return selected
    chosen = {item.source_id for item in selected}
    for item in items:
        if item.source_id in chosen:
            continue
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


class GeoapifyProvider:
    name = "geoapify"
    _geocode_cache_lock = Lock()
    _geocode_cache: dict[tuple[str, ...], tuple[float, dict[str, object]]] = {}

    def __init__(self) -> None:
        self.api_key = os.getenv("RADAR_GEOAPIFY_API_KEY", "").strip()
        if not self.api_key:
            raise ProviderConfigurationError("RADAR_GEOAPIFY_API_KEY ausente.")
        self.base_url = os.getenv("RADAR_GEOAPIFY_URL", "https://api.geoapify.com").rstrip("/")
        self.timeout = max(4.0, min(float(os.getenv("RADAR_HTTP_TIMEOUT", "8")), 15.0))
        self.max_results = max(5, min(int(os.getenv("RADAR_MAX_RESULTS", "24")), 60))
        self.candidate_limit = max(
            self.max_results,
            min(int(os.getenv("RADAR_CANDIDATE_LIMIT", str(self.max_results * 3))), 100),
        )
        self.enrich_limit = max(
            0,
            min(int(os.getenv("RADAR_ENRICH_LIMIT", "12")), 100),
        )
        # Region-wide discovery uses Geoapify's administrative place boundary
        # plus offset pagination. The previous proximity query only sampled the
        # city centre and made large cities look artificially small.
        self.region_page_size = max(20, min(int(os.getenv("RADAR_REGION_PAGE_SIZE", "500")), 500))
        self.region_max_results = max(
            self.region_page_size,
            min(int(os.getenv("RADAR_REGION_MAX_RESULTS", "2000")), 2000),
        )
        self.region_scan_limit = max(
            self.region_max_results,
            min(int(os.getenv("RADAR_REGION_SCAN_LIMIT", "5000")), 10000),
        )
        self.detail_workers = max(1, min(int(os.getenv("RADAR_DETAIL_WORKERS", "2")), 4))
        self.detail_timeout = max(2.0, min(float(os.getenv("RADAR_DETAIL_TIMEOUT", "4")), 8.0))
        self.user_agent = os.getenv("RADAR_USER_AGENT", f"ScoutLIQ/1.0 (+{ORIGIN})")[:250]

    @metered('geoapify')
    def _request_json(
        self,
        path: str,
        params: dict[str, object],
        *,
        max_bytes: int = 5_000_000,
        timeout: float | None = None,
    ) -> object:
        query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
        url = f"{self.base_url}{path}?{query}"
        request = Request(
            url,
            headers={"Accept": "application/json", "User-Agent": self.user_agent},
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout or self.timeout) as response:
                payload = response.read(max_bytes + 1)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise ProviderConfigurationError("A chave Geoapify foi recusada.", status_code=exc.code) from exc
            raise ProviderError("A fonte externa recusou a consulta.", status_code=exc.code) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ProviderTimeout("A fonte externa demorou além do limite.") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise ProviderTimeout("A fonte externa demorou além do limite.") from exc
            raise ProviderError("Não foi possível conectar à fonte externa.") from exc
        if len(payload) > max_bytes:
            raise ProviderError("A fonte externa retornou dados demais.")
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("A fonte externa retornou uma resposta inválida.") from exc

    def _geocode(self, query: DiscoveryQuery) -> dict[str, object]:
        key = (
            _normalized(query.location),
            query.country,
            _normalized(query.city_name),
            _normalized(query.state),
            query.state_code,
        )
        now = time.monotonic()
        with self._geocode_cache_lock:
            cached = self._geocode_cache.get(key)
            if cached and cached[0] > now - 86400:
                return cached[1]

        if query.city_name:
            params: dict[str, object] = {
                "city": query.city_name,
                "type": "city",
                "format": "json",
                "lang": "en",
                "limit": 5,
                "apiKey": self.api_key,
            }
            if query.country:
                params["filter"] = f"countrycode:{query.country.lower()}"
            if query.state:
                params["state"] = query.state
        else:
            params = {
                "text": query.location,
                "type": "locality",
                "format": "json",
                "lang": "en",
                "limit": 5,
                "apiKey": self.api_key,
            }
            if query.country:
                params["filter"] = f"countrycode:{query.country.lower()}"

        response = self._request_json("/v1/geocode/search", params)
        if not isinstance(response, dict) or not isinstance(response.get("results"), list) or not response["results"]:
            raise LocationNotFound("Região não encontrada.")

        candidates = [item for item in response["results"] if isinstance(item, dict)]
        first: dict[str, object] | None = None
        if query.city_name:
            expected_city = _normalized(query.city_name)
            expected_state = query.state_code.upper()
            for item in candidates:
                country_code = _clean_text(item.get("country_code"), 4).upper()
                city = _normalized(_clean_text(item.get("city") or item.get("name"), 100))
                state_code = _state_code(item.get("state_code"))
                if query.country and country_code and country_code != query.country:
                    continue
                if city != expected_city:
                    continue
                if expected_state and state_code and state_code != expected_state:
                    continue
                first = item
                break
            if first is None:
                raise LocationNotFound("Município selecionado não pôde ser confirmado pela fonte externa.")
        else:
            first = candidates[0] if candidates else None

        if not first:
            raise LocationNotFound("Região não encontrada.")
        try:
            float(first["lat"])
            float(first["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("A geocodificação não retornou coordenadas válidas.") from exc
        with self._geocode_cache_lock:
            self._geocode_cache[key] = (time.monotonic(), first)
        return first

    def _place_to_result(
        self,
        feature: dict[str, object],
        fallback_city: str,
        query: DiscoveryQuery,
        unknown_filter: str,
        center: tuple[float, float],
        *,
        enforce_radius: bool = True,
    ) -> DiscoveryResult | None:
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            return None
        name = _clean_text(properties.get("name"), 160)
        place_id = _clean_text(properties.get("place_id"), 160)
        if len(name) < 2 or len(place_id) < 2:
            return None
        try:
            latitude = float(properties.get("lat"))
            longitude = float(properties.get("lon"))
        except (TypeError, ValueError):
            geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
            coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
            if not isinstance(coordinates, list) or len(coordinates) < 2:
                return None
            try:
                longitude, latitude = float(coordinates[0]), float(coordinates[1])
            except (TypeError, ValueError):
                return None
        # Geoapify should already enforce the spatial filter. Re-check distance and
        # administrative metadata locally so a malformed/stale upstream record can
        # never turn a Recife query into João Pessoa or another state.
        if enforce_radius and _distance_m(center[0], center[1], latitude, longitude) > query.radius_km * 1000 + 250:
            return None
        country_code = _clean_text(properties.get("country_code"), 4).upper()
        # A map rectangle cannot establish the city/country of a result.
        # Do not turn a missing provider field into an invented Brazilian lead.
        if query.scope in {'bounds','polygon'} and (
            not re.fullmatch(r'[A-Z]{2}',country_code) or
            not _clean_text(properties.get('city') or properties.get('municipality'),100)
        ):
            return None
        if query.country and country_code and country_code != query.country:
            return None
        result_state_code = _state_code(properties.get("state_code"))
        if query.state_code and result_state_code and result_state_code != query.state_code:
            return None

        category = _geoapify_category(properties.get("categories"))
        if unknown_filter:
            haystack = _normalized(" ".join([name, category, *[str(v) for v in properties.get("categories", []) if isinstance(v, str)]]))
            if _normalized(unknown_filter) not in haystack:
                return None
        city = (
            query.city_name[:100]
            if query.city_name
            else _clean_text(properties.get("city") or properties.get("municipality") or fallback_city, 100)
        ) or fallback_city[:100] or "Região pesquisada"
        address = _clean_text(properties.get("formatted"), 250)
        if not address:
            line1 = _clean_text(properties.get("address_line1"), 160)
            line2 = _clean_text(properties.get("address_line2"), 160)
            address = ", ".join(part for part in (line1, line2) if part)[:250]
        lead = LeadInput(
            name=name,
            category=category,
            city=city,
            country=country_code or query.country or "BR",
            address=address,
            latitude=latitude,
            longitude=longitude,
            rating=None,
            reviews=None,
            website=_contact_website(properties),
            website_status="unknown",
            instagram=_contact_instagram(properties),
            instagram_active=False,
            phone=_contact_phone(properties),
            whatsapp=_contact_whatsapp(properties),
            contact="",
            potential_cents=0,
            notes="",
        )
        return DiscoveryResult(source_id=place_id, lead=lead)

    def _details(self, place_id: str) -> dict[str, object]:
        response = self._request_json(
            "/v2/place-details",
            {"id": place_id, "features": "details", "lang": "pt", "apiKey": self.api_key},
            timeout=self.detail_timeout,
        )
        if not isinstance(response, dict) or not isinstance(response.get("features"), list):
            raise ProviderError("A fonte externa retornou detalhes inválidos.")
        for feature in response["features"]:
            if not isinstance(feature, dict):
                continue
            properties = feature.get("properties")
            if isinstance(properties, dict) and properties.get("feature_type") == "details":
                return properties
        return {}

    def _enrich(self, item: DiscoveryResult, properties: dict[str, object]) -> DiscoveryResult:
        if not properties:
            return item
        data = item.lead.model_dump()
        website = _contact_website(properties)
        instagram = _contact_instagram(properties)
        phone = _contact_phone(properties)
        whatsapp = _contact_whatsapp(properties)
        if website:
            data["website"] = website
        if instagram:
            data["instagram"] = instagram
        if phone:
            data["phone"] = phone
        if whatsapp:
            data["whatsapp"] = whatsapp
        return DiscoveryResult(source_id=item.source_id, lead=LeadInput(**data))

    def enrich_existing(self, source_id: str, lead: LeadInput) -> LeadInput:
        """Fetch provider details for one already-known business without running a new area search."""
        if not source_id:
            return lead
        details = self._details(source_id)
        return self._enrich(DiscoveryResult(source_id=source_id, lead=lead), details).lead

    def search(self, query: DiscoveryQuery) -> DiscoveryBatch:
        if query.resolved_location:
            location = query.resolved_location
            if location.source != 'geoapify' or location.latitude is None or query.scope != 'region':
                raise ProviderConfigurationError('A fonte não suporta o território selecionado.')
            place = {'place_id': location.id, 'lat': location.latitude, 'lon': location.longitude,
                     'country_code': location.country_code, 'city': location.city, 'formatted': location.formatted}
        elif query.scope in {"bounds", "polygon"} and query.center_lat is not None and query.center_lng is not None:
            place = {"lat": query.center_lat, "lon": query.center_lng, "country_code": query.country or "BR", "formatted": query.location}
        else:
            place = self._geocode(query)
        resolved_country = (query.country if query.scope in {"bounds", "polygon"} else _clean_text(place.get("country_code"), 4).upper()[:2] or query.country or "BR")
        query = query.model_copy(update={"country": resolved_country})
        latitude, longitude = float(place["lat"]), float(place["lon"])
        center = (latitude, longitude)
        fallback_city = _clean_text(
            query.city_name or place.get("city") or place.get("municipality") or query.location,
            100,
        )
        selected = _geoapify_categories(query.category)
        categories = selected if selected else GEOAPIFY_DEFAULT_CATEGORIES
        place_id = _clean_text(place.get("place_id"), 220)

        # A resolved city/district/postcode is searched by its full Geoapify
        # administrative boundary. Radius is retained only as a defensive
        # fallback for ambiguous free-text locations without a place boundary.
        region_mode = bool(place_id) and query.scope == "region"
        place_filter = (
            f"place:{place_id}"
            if region_mode
            else f"circle:{longitude:.6f},{latitude:.6f},{query.radius_km * 1000}"
        )
        page_size = self.region_page_size if region_mode else self.candidate_limit
        result_limit = self.region_max_results if region_mode else self.max_results
        unknown_filter = query.category if selected == () else ""

        items: list[DiscoveryResult] = []
        seen: set[str] = set()
        offset = getattr(self, '_smart_offset', 0)
        scanned = 0
        complete = True

        while len(items) < result_limit and (not region_mode or scanned < self.region_scan_limit):
            request_limit = min(page_size, result_limit - len(items))
            if region_mode:
                request_limit = min(request_limit, self.region_scan_limit - scanned)
            if request_limit <= 0:
                complete = False
                break
            response = self._request_json(
                "/v2/places",
                {
                    "categories": ",".join(categories),
                    "filter": place_filter,
                    "bias": f"proximity:{longitude:.6f},{latitude:.6f}",
                    "limit": request_limit,
                    "offset": offset if region_mode or hasattr(self, '_smart_offset') else 0,
                    "lang": "pt",
                    "apiKey": self.api_key,
                },
                max_bytes=12_000_000 if region_mode else 5_000_000,
            )
            if not isinstance(response, dict) or not isinstance(response.get("features"), list):
                raise ProviderError("A fonte externa retornou uma resposta inválida.")
            features = [feature for feature in response["features"] if isinstance(feature, dict)]
            scanned += len(features)
            if not features:
                break

            for feature in features:
                item = self._place_to_result(
                    feature,
                    fallback_city,
                    query,
                    unknown_filter,
                    center,
                    enforce_radius=not region_mode,
                )
                if item and item.source_id not in seen:
                    seen.add(item.source_id)
                    items.append(item)
                    if len(items) >= result_limit:
                        break

            if hasattr(self, '_smart_offset'):
                complete = len(features) < request_limit
                break
            if not region_mode or len(features) < request_limit:
                break
            offset += request_limit
            if len(items) >= result_limit:
                complete = False
                break
            if region_mode and scanned >= self.region_scan_limit:
                complete = False
                break

        radius_m = 0.0 if region_mode else query.radius_km * 1000.0
        items.sort(key=lambda item: _candidate_priority(item, center, radius_m), reverse=True)

        if items and self.enrich_limit:
            logger = logging.getLogger("scoutliq")
            enriched = list(items)
            enrich_count = min(self.enrich_limit, len(enriched))
            lookup = {item.source_id: index for index, item in enumerate(enriched[:enrich_count])}
            with ThreadPoolExecutor(max_workers=self.detail_workers) as executor:
                futures = {submit(executor, self._details, detail_place_id): detail_place_id for detail_place_id in lookup}
                for future in as_completed(futures):
                    detail_place_id = futures[future]
                    try:
                        details = future.result()
                    except ProviderError as exc:
                        logger.info(
                            "Radar geoapify_detail_failed place=%s status=%s error=%s",
                            detail_place_id[:18],
                            exc.status_code,
                            type(exc).__name__,
                        )
                        continue
                    index = lookup[detail_place_id]
                    enriched[index] = self._enrich(enriched[index], details)
            items = enriched
            items.sort(key=lambda item: _candidate_priority(item, center, radius_m), reverse=True)

        label = _clean_text(place.get("formatted"), 220) or query.location
        return DiscoveryBatch(
            provider=self.name,
            location_label=label,
            results=items,
            complete=complete,
            scanned=scanned,
            result_limit=result_limit,
            scope="region" if region_mode else "radius",
        )

class OpenStreetMapProvider:
    name = "openstreetmap"
    _geocode_lock = Lock()
    _geocode_cache_lock = Lock()
    _last_geocode_at = 0.0
    _geocode_cache: dict[tuple[str, str], tuple[float, dict[str, object]]] = {}

    def __init__(self) -> None:
        self.nominatim_url = os.getenv("RADAR_NOMINATIM_URL", "https://nominatim.openstreetmap.org").rstrip("/")
        default_overpass = [
            "https://overpass.private.coffee/api/interpreter",
            "https://overpass-api.de/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        ]
        configured_many = os.getenv("RADAR_OVERPASS_URLS", "").strip()
        configured_one = os.getenv("RADAR_OVERPASS_URL", "").strip()
        if configured_many:
            candidates = [item.strip() for item in configured_many.split(",") if item.strip()]
        elif configured_one:
            candidates = [configured_one, *default_overpass]
        else:
            candidates = default_overpass
        self.overpass_urls = list(dict.fromkeys(item.rstrip("/") for item in candidates))[:3]
        if not self.overpass_urls:
            raise RuntimeError("Nenhum endpoint Overpass configurado para o Radar.")
        # Keep individual attempts short enough to allow a fallback within the UI request budget.
        self.timeout = max(4.0, min(float(os.getenv("RADAR_HTTP_TIMEOUT", "8")), 12.0))
        self.max_results = max(10, min(int(os.getenv("RADAR_MAX_RESULTS", "60")), 100))
        self.user_agent = os.getenv("RADAR_USER_AGENT", f"ScoutLIQ/1.0 (+{ORIGIN})")[:250]

    @metered('openstreetmap')
    def _request_json(self, url: str, *, data: bytes | None = None, timeout: float | None = None) -> object:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if ORIGIN.startswith(("http://", "https://")):
            headers["Referer"] = ORIGIN + "/"
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
        request = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
        try:
            with urlopen(request, timeout=timeout or self.timeout) as response:
                payload = response.read(2_000_001)
                if len(payload) > 2_000_000:
                    raise ProviderError("A fonte externa retornou dados demais.")
                return json.loads(payload.decode("utf-8"))
        except HTTPError as exc:
            raise ProviderError("A fonte externa recusou a consulta.", status_code=exc.code) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise ProviderTimeout("A fonte externa demorou além do limite.") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise ProviderTimeout("A fonte externa demorou além do limite.") from exc
            raise ProviderError("Não foi possível conectar à fonte externa.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("A fonte externa retornou uma resposta inválida.") from exc

    def _geocode(self, query: DiscoveryQuery) -> dict[str, object]:
        key = (_normalized(query.location), query.country)
        now = time.monotonic()
        with self._geocode_cache_lock:
            cached = self._geocode_cache.get(key)
            if cached and cached[0] > now - 86400:
                return cached[1]
        values = {
            "format": "jsonv2",
            "q": query.location,
            "limit": 1,
            "addressdetails": 1,
        }
        if query.country:
            values["countrycodes"] = query.country.lower()
        params = urlencode(values)
        # The public Nominatim policy caps applications at one request per second.
        with self._geocode_lock:
            delay = 1.0 - (time.monotonic() - self._last_geocode_at)
            if delay > 0:
                time.sleep(delay)
            data = self._request_json(f"{self.nominatim_url}/search?{params}")
            type(self)._last_geocode_at = time.monotonic()
        if not isinstance(data, list) or not data:
            raise LocationNotFound("Região não encontrada.")
        first = data[0]
        if not isinstance(first, dict):
            raise ProviderError("A geocodificação retornou uma resposta inválida.")
        try:
            float(first["lat"])
            float(first["lon"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("A geocodificação não retornou coordenadas válidas.") from exc
        with self._geocode_cache_lock:
            self._geocode_cache[key] = (time.monotonic(), first)
        return first

    def _overpass_query(self, query: DiscoveryQuery, latitude: float, longitude: float) -> str:
        radius = query.radius_km * 1000
        selected = _selectors(query.category)
        lines: list[str] = []
        if selected is None:
            # No niche: search only the supported commercial categories instead of every
            # amenity/shop in the radius. The old broad-key query regularly timed out in
            # dense cities such as Recife even though only 60 rows were returned.
            selectors = DEFAULT_DISCOVERY_SELECTORS
            for key, value in selectors:
                lines.append(
                    f'nwr(around:{radius},{latitude:.6f},{longitude:.6f})["name"]["{key}"="{value}"];'
                )
        elif selected:
            for key, value in selected:
                lines.append(
                    f'nwr(around:{radius},{latitude:.6f},{longitude:.6f})["name"]["{key}"="{value}"];'
                )
        else:
            # Unknown free-text niche: keep compatibility with V1 by fetching business-like
            # objects and filtering by name/category locally. This path may be heavier, but
            # it is only used when the niche is not one of the known selectors above.
            for key in BROAD_KEYS:
                lines.append(
                    f'nwr(around:{radius},{latitude:.6f},{longitude:.6f})["name"]["{key}"];'
                )
            lines.append(
                f'nwr(around:{radius},{latitude:.6f},{longitude:.6f})["name"]["leisure"="fitness_centre"];'
            )
        overpass_timeout = max(8, int(self.timeout) + 2)
        return "\n".join(
            [f"[out:json][timeout:{overpass_timeout}];", "(", *lines, ");", f"out tags center qt {self.max_results};"]
        )

    def _request_overpass(self, payload: bytes) -> object:
        last_error: ProviderError | None = None
        logger = logging.getLogger("scoutliq")
        for index, endpoint in enumerate(self.overpass_urls):
            try:
                return self._request_json(endpoint, data=payload, timeout=self.timeout)
            except ProviderError as exc:
                last_error = exc
                host = urlparse(endpoint).hostname or "unknown"
                logger.warning(
                    "Radar overpass_attempt_failed host=%s attempt=%s/%s status=%s error=%s",
                    host,
                    index + 1,
                    len(self.overpass_urls),
                    exc.status_code,
                    type(exc).__name__,
                )
                # 4xx responses other than temporary throttling indicate a bad query/config
                # and retrying the same payload against every public server only adds delay.
                if exc.status_code is not None and 400 <= exc.status_code < 500 and exc.status_code != 429:
                    raise
        if last_error is not None:
            raise last_error
        raise ProviderError("Nenhuma fonte Overpass está configurada.")

    def _lead_from_element(self, element: dict[str, object], fallback_city: str, country: str, unknown_filter: str) -> DiscoveryResult | None:
        tags = element.get("tags")
        if not isinstance(tags, dict):
            return None
        name = _clean_text(tags.get("name"), 160)
        if len(name) < 2:
            return None
        if unknown_filter and not _matches_unknown_category(unknown_filter, name, tags):
            return None
        osm_type = _clean_text(element.get("type"), 20)
        osm_id = element.get("id")
        if osm_type not in ("node", "way", "relation") or not isinstance(osm_id, int):
            return None
        if osm_type == "node":
            lat, lon = element.get("lat"), element.get("lon")
        else:
            center = element.get("center") if isinstance(element.get("center"), dict) else {}
            lat, lon = center.get("lat"), center.get("lon")
        try:
            latitude, longitude = float(lat), float(lon)
        except (TypeError, ValueError):
            return None
        city = _clean_text(tags.get("addr:city") or tags.get("addr:municipality") or fallback_city, 100)
        if len(city) < 2:
            city = fallback_city[:100] or "Região pesquisada"
        street = _clean_text(tags.get("addr:street") or tags.get("addr:place"), 160)
        number = _clean_text(tags.get("addr:housenumber"), 30)
        suburb = _clean_text(tags.get("addr:suburb") or tags.get("addr:neighbourhood"), 100)
        address_parts = [" ".join(x for x in (street, number) if x).strip(), suburb, city]
        address = ", ".join(dict.fromkeys(x for x in address_parts if x))[:250]
        website = _safe_url(tags.get("contact:website") or tags.get("website") or tags.get("url"))
        instagram = _instagram_url(tags.get("contact:instagram") or tags.get("instagram"))
        phone = _clean_text(tags.get("contact:phone") or tags.get("phone") or tags.get("mobile"), 30)
        whatsapp = _whatsapp(tags.get("contact:whatsapp") or tags.get("whatsapp"))
        lead = LeadInput(
            name=name,
            category=_category(tags),
            city=city,
            country=country,
            address=address,
            latitude=latitude,
            longitude=longitude,
            rating=None,
            reviews=None,
            website=website,
            website_status="unknown",
            instagram=instagram,
            instagram_active=False,
            phone=phone,
            whatsapp=whatsapp,
            contact="",
            potential_cents=0,
            notes="",
        )
        prefix = {"node": "N", "way": "W", "relation": "R"}[osm_type]
        return DiscoveryResult(source_id=f"{prefix}{osm_id}", lead=lead)

    def search(self, query: DiscoveryQuery) -> DiscoveryBatch:
        if query.resolved_location:
            raise ProviderConfigurationError('O adaptador OpenStreetMap não cobre este limite administrativo.')
        if query.scope in {"bounds", "polygon"} and query.center_lat is not None and query.center_lng is not None:
            place = {"lat": query.center_lat, "lon": query.center_lng, "address": {"country_code": (query.country or "BR").lower()}, "display_name": query.location}
        else:
            place = self._geocode(query)
        address = place.get("address") if isinstance(place.get("address"), dict) else {}
        resolved_country = _clean_text(address.get("country_code"), 4).upper()[:2] or query.country or "BR"
        query = query.model_copy(update={"country": resolved_country})
        latitude, longitude = float(place["lat"]), float(place["lon"])
        address = place.get("address") if isinstance(place.get("address"), dict) else {}
        fallback_city = _clean_text(
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("county")
            or query.location,
            100,
        )
        overpass_query = self._overpass_query(query, latitude, longitude)
        response = self._request_overpass(
            urlencode({"data": overpass_query}).encode("utf-8")
        )
        if not isinstance(response, dict) or not isinstance(response.get("elements"), list):
            raise ProviderError("A fonte externa retornou uma resposta inválida.")
        selected = _selectors(query.category)
        unknown_filter = query.category if selected == [] else ""
        items: list[DiscoveryResult] = []
        seen: set[str] = set()
        for element in response["elements"]:
            if not isinstance(element, dict):
                continue
            if query.scope in {'bounds','polygon'}:
                tags=element.get('tags')
                if not isinstance(tags,dict): continue
                observed_city=_clean_text(tags.get('addr:city') or tags.get('addr:municipality'),100)
                observed_country=_clean_text(tags.get('addr:country'),4).upper()
                if len(observed_city)<2 or not re.fullmatch('[A-Z]{2}',observed_country): continue
                item=self._lead_from_element(element,observed_city,observed_country,unknown_filter)
            else:
                item = self._lead_from_element(element, fallback_city, query.country, unknown_filter)
            if item and item.source_id not in seen:
                seen.add(item.source_id)
                items.append(item)
            if len(items) >= self.max_results:
                break
        label = _clean_text(place.get("display_name"), 220) or query.location
        return DiscoveryBatch(provider=self.name, location_label=label, results=items, scope="radius", scanned=len(response["elements"]), complete=len(response["elements"]) < self.max_results, result_limit=self.max_results)


class DemoProvider:
    name = "demo"

    def search(self, query: DiscoveryQuery) -> DiscoveryBatch:
        from .seed import demo_leads

        needle = query.location.casefold()
        results = [
            DiscoveryResult(source_id=f"demo:{i}", lead=item)
            for i, item in enumerate(demo_leads())
            if item.country == query.country
            and (not needle or needle in item.city.casefold())
            and (not query.category or query.category.casefold() in item.category.casefold())
        ]
        return DiscoveryBatch(provider=self.name, location_label=query.location, results=results, scope=query.scope)


class UnconfiguredProvider:
    name = "geoapify"

    def search(self, query: DiscoveryQuery) -> DiscoveryBatch:
        raise ProviderConfigurationError(
            "A fonte Geoapify não está configurada neste ambiente."
        )


def build_provider() -> EstablishmentProvider | None:
    provider = os.getenv("RADAR_PROVIDER", "auto").strip().lower()
    if provider in ("", "auto"):
        if os.getenv("RADAR_GEOAPIFY_API_KEY", "").strip():
            return GeoapifyProvider()
        # Do not silently depend on public Overpass in production. It is useful as
        # a zero-key development fallback, but it is not reliable enough to be the
        # primary production discovery service.
        return UnconfiguredProvider() if PRODUCTION else OpenStreetMapProvider()
    if provider in ("geo", "geoapify"):
        try:
            return GeoapifyProvider()
        except ProviderConfigurationError:
            return UnconfiguredProvider()
    if provider in ("osm", "openstreetmap"):
        return OpenStreetMapProvider()
    if provider == "demo":
        return DemoProvider()
    if provider == "disabled":
        return None
    raise RuntimeError(f"RADAR_PROVIDER desconhecido: {provider}")
