from backend import main
from backend.providers import (
    DiscoveryBatch,
    DiscoveryQuery,
    DiscoveryResult,
    LocationNotFound,
    ProviderError,
    ProviderTimeout,
)
from backend.schemas import LeadInput
from backend.db import SessionLocal
from backend.models import Lead
from sqlalchemy import select


def discovered(source_id: str, *, name="Empresa Radar", lat=-8.05, lon=-34.9, address="Rua A, 10, Recife", website="", instagram="", rating=None, reviews=None):
    return DiscoveryResult(
        source_id=source_id,
        lead=LeadInput(
            name=name,
            category="Barbearia / salão",
            city="Recife",
            country="BR",
            address=address,
            latitude=lat,
            longitude=lon,
            rating=rating,
            reviews=reviews,
            website=website,
            website_status="unknown",
            instagram=instagram,
            instagram_active=False,
            phone="+55 81 99999-9999",
        ),
    )


class FakeProvider:
    name = "openstreetmap"

    def __init__(self, batches):
        self.batches = list(batches)
        self.queries = []

    def search(self, query: DiscoveryQuery):
        self.queries.append(query)
        value = self.batches.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def batch(*items):
    return DiscoveryBatch(
        provider="openstreetmap",
        location_label="Recife, Pernambuco, Brasil",
        results=list(items),
    )


def test_radar_search_persists_dedupes_homonyms_and_adds_pipeline(auth, monkeypatch):
    first = discovered("N101", instagram="https://instagram.com/empresa")
    second = discovered(
        "W202",
        name="Empresa Radar",
        lat=-8.061,
        lon=-34.912,
        address="Rua B, 20, Recife",
        website="https://empresa.example",
    )
    provider = FakeProvider([batch(first, second), batch(first, second)])
    monkeypatch.setattr(main, "radar_provider", provider)

    payload = {"location": "Recife", "category": "barbearia", "radius_km": 5, "country": "BR"}
    response = auth.post("/api/radar/search", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["count"] == 2 and data["created"] == 2
    assert len({item["id"] for item in data["results"]}) == 2
    assert all(item["name"] == "Empresa Radar" for item in data["results"])
    assert any(r["key"] == "website_unlisted" for r in data["results"][0]["score"]["reasons"])
    assert provider.queries[0].category == "barbearia"

    repeat = auth.post("/api/radar/search", json=payload)
    assert repeat.status_code == 200
    assert repeat.json()["created"] == 0
    with SessionLocal() as db:
        assert len(db.scalars(select(Lead)).all()) == 2

    lead = repeat.json()["results"][0]
    moved = auth.patch(
        f"/api/leads/{lead['id']}/stage",
        json={"stage": "discovered", "version": lead["version"]},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["in_pipeline"] is True


def test_radar_empty_result_is_success(auth, monkeypatch):
    monkeypatch.setattr(main, "radar_provider", FakeProvider([batch()]))
    response = auth.post(
        "/api/radar/search",
        json={"location": "Recife", "category": "dentista", "radius_km": 2, "country": "BR"},
    )
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["count"] == 0


def test_radar_external_errors_are_safe(auth, monkeypatch):
    cases = [
        (LocationNotFound("not found"), 422, "região"),
        (ProviderTimeout("timeout"), 504, "demorou"),
        (ProviderError("upstream exploded", status_code=500), 503, "indisponível"),
        (ProviderError("rate", status_code=429), 503, "limite"),
    ]
    for error, status, text in cases:
        monkeypatch.setattr(main, "radar_provider", FakeProvider([error]))
        response = auth.post(
            "/api/radar/search",
            json={"location": "Recife", "category": "", "radius_km": 5, "country": "BR"},
        )
        assert response.status_code == status
        assert text in response.json()["detail"].lower()
        assert "upstream exploded" not in response.text


def test_radar_validation_rejects_bad_params(auth, monkeypatch):
    monkeypatch.setattr(main, "radar_provider", FakeProvider([batch()]))
    for payload in [
        {"location": "R", "category": "", "radius_km": 5, "country": "BR"},
        {"location": "Recife", "category": "", "radius_km": 0, "country": "BR"},
        {"location": "Recife", "category": "", "radius_km": 26, "country": "BR"},
        {"location": "Recife", "category": "", "radius_km": 5, "country": "BRA"},
        {"location": "Recife", "category": "", "radius_km": 5, "country": "BR", "scope": "polygon"},
        {"location": "Recife", "category": "", "radius_km": 5, "country": "BR", "admin": True},
    ]:
        assert auth.post("/api/radar/search", json=payload).status_code == 422


def test_osm_provider_serializes_public_fields_without_inventing_signals(monkeypatch):
    from backend.providers import OpenStreetMapProvider

    provider = OpenStreetMapProvider()
    monkeypatch.setattr(
        provider,
        "_geocode",
        lambda query: {
            "lat": "-8.05",
            "lon": "-34.90",
            "display_name": "Recife, Pernambuco, Brasil",
            "address": {"city": "Recife"},
        },
    )
    captured = {}

    def fake_request(url, *, data=None, timeout=None):
        captured["payload"] = data.decode("utf-8") if data else ""
        return {
            "elements": [
                {
                    "type": "node",
                    "id": 123,
                    "lat": -8.051,
                    "lon": -34.901,
                    "tags": {
                        "name": "Barbearia Fonte",
                        "shop": "hairdresser",
                        "addr:street": "Rua Teste",
                        "addr:housenumber": "9",
                        "website": "barbearia.example",
                        "contact:instagram": "@barbeariafonte",
                        "contact:phone": "+55 81 3333-4444",
                        "contact:whatsapp": "+55 81 99999-8888",
                    },
                }
            ]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request)
    result = provider.search(
        DiscoveryQuery(location="Recife", category="barbearia", radius_km=5, country="BR")
    )
    assert result.provider == "openstreetmap"
    assert len(result.results) == 1
    item = result.results[0]
    assert item.source_id == "N123"
    assert item.lead.website == "https://barbearia.example"
    assert item.lead.instagram == "https://www.instagram.com/barbeariafonte/"
    assert item.lead.instagram_active is False
    assert item.lead.rating is None and item.lead.reviews is None
    assert item.lead.website_status == "unknown"
    assert "shop%22%3D%22hairdresser" in captured["payload"]


def test_osm_broad_search_uses_curated_selectors_instead_of_all_business_keys(monkeypatch):
    from backend.providers import OpenStreetMapProvider

    provider = OpenStreetMapProvider()
    monkeypatch.setattr(
        provider,
        "_geocode",
        lambda query: {
            "lat": "-8.05",
            "lon": "-34.90",
            "display_name": "Recife, Pernambuco, Brasil",
            "address": {"city": "Recife"},
        },
    )
    captured = {}

    def fake_request(url, *, data=None, timeout=None):
        captured["payload"] = data.decode("utf-8") if data else ""
        return {"elements": []}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    provider.search(DiscoveryQuery(location="Recife", category="", radius_km=10, country="BR"))
    payload = captured["payload"]
    assert "hairdresser" in payload
    assert "restaurant" in payload
    assert "%5B%22shop%22%5D%3B" not in payload
    assert "%5B%22amenity%22%5D%3B" not in payload


def test_osm_overpass_falls_back_after_timeout(monkeypatch):
    from backend.providers import OpenStreetMapProvider

    provider = OpenStreetMapProvider()
    provider.overpass_urls = [
        "https://first.example/api/interpreter",
        "https://second.example/api/interpreter",
    ]
    calls = []

    def fake_request(url, *, data=None, timeout=None):
        calls.append(url)
        if "first.example" in url:
            raise ProviderTimeout("slow")
        return {"elements": []}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    result = provider._request_overpass(b"data=test")
    assert result == {"elements": []}
    assert calls == provider.overpass_urls


def test_geoapify_provider_serializes_and_enriches_without_inventing_reviews(monkeypatch):
    from backend.providers import GeoapifyProvider

    monkeypatch.setenv("RADAR_GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setenv("RADAR_ENRICH_LIMIT", "1")
    provider = GeoapifyProvider()
    monkeypatch.setattr(
        provider,
        "_geocode",
        lambda query: {
            "lat": -8.05,
            "lon": -34.90,
            "city": "Recife",
            "formatted": "Recife, Pernambuco, Brasil",
            "place_id": "city-recife",
        },
    )
    calls = []

    def fake_request(path, params, *, max_bytes=5_000_000, timeout=None):
        calls.append((path, params, timeout))
        if path == "/v2/places":
            return {
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-34.901, -8.051]},
                        "properties": {
                            "name": "Barbearia Geo",
                            "place_id": "geo-123",
                            "city": "Recife",
                            "formatted": "Rua Teste, 9, Recife - PE",
                            "lat": -8.051,
                            "lon": -34.901,
                            "categories": ["service.beauty.hairdresser"],
                            "datasource": {"raw": {"phone": "+55 81 3333-4444"}},
                        },
                    }
                ]
            }
        if path == "/v2/place-details":
            return {
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "feature_type": "details",
                            "website": "barbearia.example",
                            "contact": {
                                "phone": "+55 81 3333-4444",
                                "instagram": "@barbeariageo",
                                "whatsapp": "+55 81 99999-8888",
                            },
                        },
                    }
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(provider, "_request_json", fake_request)
    result = provider.search(
        DiscoveryQuery(location="Recife, PE, Brasil", category="barbearia", radius_km=5, country="BR")
    )
    assert result.provider == "geoapify"
    assert result.location_label == "Recife, Pernambuco, Brasil"
    assert len(result.results) == 1
    lead = result.results[0].lead
    assert result.results[0].source_id == "geo-123"
    assert lead.category == "Barbearia / salão"
    assert lead.website == "https://barbearia.example"
    assert lead.instagram == "https://www.instagram.com/barbeariageo/"
    assert lead.whatsapp == "5581999998888"
    assert lead.rating is None and lead.reviews is None
    assert lead.instagram_active is False
    places_call = next(call for call in calls if call[0] == "/v2/places")
    assert "service.beauty.hairdresser" in places_call[1]["categories"]
    assert places_call[1]["filter"] == "place:city-recife"
    assert places_call[1]["limit"] == provider.region_page_size
    assert places_call[1]["offset"] == 0
    details_call = next(call for call in calls if call[0] == "/v2/place-details")
    assert details_call[2] == provider.detail_timeout


def test_radar_locations_returns_catalog_and_catalog_error_is_safe(auth, monkeypatch):
    sample = [
        {"id": "2611606", "name": "Recife", "uf": "PE", "state": "Pernambuco"},
        {"id": "2607901", "name": "Jaboatão dos Guararapes", "uf": "PE", "state": "Pernambuco"},
    ]
    monkeypatch.setattr(main, "brazil_municipalities", lambda: sample)
    response = auth.get("/api/radar/locations")
    assert response.status_code == 200
    assert response.json() == sample

    from backend.locations import LocationCatalogError

    def failed():
        raise LocationCatalogError("upstream details must stay private")

    monkeypatch.setattr(main, "brazil_municipalities", failed)
    response = auth.get("/api/radar/locations")
    assert response.status_code == 503
    assert "sugestões" in response.json()["detail"].lower()
    assert "upstream details" not in response.text


def test_radar_provider_configuration_error_is_safe(auth, monkeypatch):
    from backend.providers import ProviderConfigurationError

    monkeypatch.setattr(
        main,
        "radar_provider",
        FakeProvider([ProviderConfigurationError("secret key details")]),
    )
    response = auth.post(
        "/api/radar/search",
        json={"location": "Recife", "category": "", "radius_km": 5, "country": "BR"},
    )
    assert response.status_code == 503
    assert "configurada" in response.json()["detail"].lower()
    assert "secret key details" not in response.text


def test_geoapify_selected_city_uses_structured_geocode_and_place_boundary(monkeypatch):
    from backend.providers import GeoapifyProvider

    monkeypatch.setenv("RADAR_GEOAPIFY_API_KEY", "test-key")
    provider = GeoapifyProvider()
    calls = []

    def fake_request(path, params, **kwargs):
        calls.append((path, dict(params)))
        if path == "/v1/geocode/search":
            assert params.get("city") == "Recife"
            assert params.get("state") == "Pernambuco"
            assert "text" not in params
            return {
                "results": [
                    {
                        "name": "Recife",
                        "city": "Recife",
                        "state": "Pernambuco",
                        "state_code": "PE",
                        "country_code": "br",
                        "lat": -8.05428,
                        "lon": -34.8813,
                        "formatted": "Recife, PE, Brasil",
                        "place_id": "recife-place-id",
                    }
                ]
            }
        if path == "/v2/places":
            assert params["filter"] == "place:recife-place-id"
            assert params["offset"] == 0
            return {"features": []}
        raise AssertionError(path)

    monkeypatch.setattr(provider, "_request_json", fake_request)
    provider.enrich_limit = 0
    result = provider.search(
        DiscoveryQuery(
            location="Recife, PE, Brasil",
            category="barbearia",
            radius_km=5,
            country="BR",
            municipality_id="2611606",
            city_name="Recife",
            state="Pernambuco",
            state_code="PE",
        )
    )
    assert result.location_label == "Recife, PE, Brasil"
    assert [call[0] for call in calls] == ["/v1/geocode/search", "/v2/places"]


def test_geoapify_rejects_cross_state_and_shared_fit_excludes_chain(monkeypatch):
    from backend.providers import GeoapifyProvider

    monkeypatch.setenv("RADAR_GEOAPIFY_API_KEY", "test-key")
    provider = GeoapifyProvider()
    provider.enrich_limit = 0
    monkeypatch.setattr(
        provider,
        "_geocode",
        lambda query: {
            "lat": -8.05428,
            "lon": -34.8813,
            "city": "Recife",
            "state": "Pernambuco",
            "state_code": "PE",
            "formatted": "Recife, PE, Brasil",
            "place_id": "recife-place-id",
        },
    )

    def feature(name, place_id, lat, lon, state_code="PE", city="Recife"):
        return {
            "type": "Feature",
            "properties": {
                "name": name,
                "place_id": place_id,
                "lat": lat,
                "lon": lon,
                "city": city,
                "state_code": state_code,
                "country_code": "br",
                "formatted": f"{name}, {city}",
                "categories": ["service.beauty.hairdresser"],
            },
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        }

    monkeypatch.setattr(
        provider,
        "_request_json",
        lambda path, params, **kwargs: {
            "features": [
                feature("McDonald's Boa Vista", "chain", -8.055, -34.882),
                feature("Barbearia Local", "local", -8.056, -34.883),
                feature("Empresa PB", "pb", -8.057, -34.884, state_code="PB", city="João Pessoa"),
                feature("Muito longe", "far", -7.12, -34.86),
            ]
        },
    )
    result = provider.search(
        DiscoveryQuery(
            location="Recife, PE, Brasil",
            category="barbearia",
            radius_km=5,
            country="BR",
            city_name="Recife",
            state="Pernambuco",
            state_code="PE",
        )
    )
    assert [item.lead.name for item in result.results] == ["McDonald's Boa Vista", "Barbearia Local", "Muito longe"]
    from backend.commercial_fit import assess
    assert assess(result.results[0].lead)['status'] == 'incompatible'
    assert assess(result.results[1].lead)['status'] == 'compatible' 
    assert result.results[0].lead.city == "Recife"


def test_geoapify_broad_search_prioritizes_opportunity_signals_and_diversifies(monkeypatch):
    from backend.providers import GeoapifyProvider

    monkeypatch.setenv("RADAR_GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setenv("RADAR_MAX_RESULTS", "5")
    monkeypatch.setenv("RADAR_CANDIDATE_LIMIT", "15")
    provider = GeoapifyProvider()
    provider.enrich_limit = 0
    monkeypatch.setattr(
        provider,
        "_geocode",
        lambda query: {
            "lat": -8.05428,
            "lon": -34.8813,
            "city": "Recife",
            "state_code": "PE",
            "formatted": "Recife, PE, Brasil",
            "place_id": "recife-place-id",
        },
    )

    cats = [
        "catering.restaurant",
        "catering.restaurant",
        "catering.restaurant",
        "catering.restaurant",
        "service.beauty.hairdresser",
        "healthcare.dentist",
    ]
    features = []
    for i, cat in enumerate(cats):
        features.append({
            "type": "Feature",
            "properties": {
                "name": f"Local {i}",
                "place_id": f"p{i}",
                "lat": -8.054 + i * 0.0002,
                "lon": -34.881 + i * 0.0002,
                "city": "Recife",
                "state_code": "PE",
                "country_code": "br",
                "formatted": f"Rua {i}, Recife",
                "categories": [cat],
                "contact": {"phone": "+55 81 3333-0000"} if i >= 4 else {},
            },
            "geometry": {"type": "Point", "coordinates": [-34.881 + i * 0.0002, -8.054 + i * 0.0002]},
        })
    monkeypatch.setattr(provider, "_request_json", lambda path, params, **kwargs: {"features": features})
    result = provider.search(
        DiscoveryQuery(
            location="Recife, PE, Brasil",
            category="",
            radius_km=5,
            country="BR",
            city_name="Recife",
            state="Pernambuco",
            state_code="PE",
        )
    )
    names = [item.lead.name for item in result.results]
    assert "Local 4" in names and "Local 5" in names
    assert len({item.lead.category for item in result.results}) >= 3


def test_radar_map_config_exposes_only_maptiler_browser_key(auth, monkeypatch):
    monkeypatch.setenv("RADAR_MAPTILER_API_KEY", "browser-key")
    monkeypatch.setenv("RADAR_MAPTILER_STYLE_ID", "dataviz-v4-dark")
    monkeypatch.setenv("RADAR_GEOAPIFY_API_KEY", "server-secret-must-not-leak")
    response = auth.get("/api/radar/map-config")
    assert response.status_code == 200
    assert response.json() == {
        "provider": "maptiler",
        "api_key": "browser-key",
        "style_id": "dataviz-v4-dark",
    }
    assert "server-secret-must-not-leak" not in response.text


def test_radar_map_config_falls_back_to_open_map(auth, monkeypatch):
    monkeypatch.delenv("RADAR_MAPTILER_API_KEY", raising=False)
    monkeypatch.delenv("RADAR_MAPTILER_STYLE_ID", raising=False)
    response = auth.get("/api/radar/map-config")
    assert response.status_code == 200
    assert response.json() == {
        "provider": "open",
        "api_key": "",
        "style_id": "dataviz-v4-dark",
    }


def test_google_maps_link_parser_extracts_name_coords_and_stable_source():
    from backend.google_maps_import import parse_google_maps_url

    parsed = parse_google_maps_url(
        "https://www.google.com/maps/place/Via+Sul/@-8.168123,-34.918456,17z/data=!4m6!3m5!1s0x7ab:0x123!8m2!3d-8.168321!4d-34.918654"
    )
    assert parsed.name == "Via Sul"
    assert round(parsed.latitude or 0, 6) == -8.168321
    assert round(parsed.longitude or 0, 6) == -34.918654
    assert parsed.source_id.startswith("gmaps:")


def test_google_maps_import_rejects_non_google_url():
    from backend.google_maps_import import GoogleMapsImportError, parse_google_maps_url

    try:
        parse_google_maps_url("https://example.com/maps/place/Teste/@-8.0,-34.9,17z")
    except GoogleMapsImportError as exc:
        assert "Google Maps" in str(exc)
    else:
        raise AssertionError("non-Google URL should be rejected")


def test_google_maps_preview_endpoint_is_safe_and_does_not_persist(auth, monkeypatch):
    monkeypatch.setattr(
        main,
        "import_google_maps_link",
        lambda url: {
            "source": "google_maps",
            "source_id": "gmaps:test123",
            "resolved_url": url,
            "warnings": [],
            "lead": {
                "name": "Via Sul",
                "category": "Concessionária / automotivo",
                "city": "Jaboatão dos Guararapes",
                "country": "BR",
                "address": "Avenida Barreto de Menezes, 697",
                "latitude": -8.17,
                "longitude": -34.92,
                "rating": None,
                "reviews": None,
                "website": "https://example.com",
                "website_status": "unknown",
                "instagram": "",
                "instagram_active": False,
                "phone": "+55 81 3476-8500",
                "whatsapp": "",
                "contact": "",
                "potential_cents": 0,
                "notes": "Revise antes de salvar.",
            },
        },
    )
    response = auth.post(
        "/api/radar/import-google-maps",
        json={"url": "https://www.google.com/maps/place/Via+Sul/@-8.17,-34.92,17z"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["lead"]["name"] == "Via Sul"
    with SessionLocal() as db:
        assert db.scalar(select(Lead).where(Lead.name == "Via Sul")) is None



def test_imported_google_maps_lead_can_start_in_pipeline(auth):
    payload = {
        "source": "google_maps",
        "source_id": "gmaps:pipeline-import-1",
        "lead": {
            "name": "Lead Google Pipeline",
            "category": "Clínica",
            "city": "Recife",
            "country": "BR",
            "address": "Rua Teste, 10",
            "latitude": -8.05,
            "longitude": -34.9,
            "rating": None,
            "reviews": None,
            "website": "",
            "website_status": "unknown",
            "instagram": "",
            "instagram_active": False,
            "phone": "",
            "whatsapp": "",
            "contact": "",
            "potential_cents": 0,
            "notes": "Importado do Google Maps.",
        },
    }
    response = auth.post('/api/leads/imported?to_pipeline=true', json=payload)
    assert response.status_code == 201, response.text
    assert response.json()['in_pipeline'] is True
    assert response.json()['stage'] == 'discovered'

def test_imported_lead_persists_source_and_deduplicates(auth):
    payload = {
        "source": "google_maps",
        "source_id": "gmaps:via-sul-1",
        "lead": {
            "name": "Via Sul",
            "category": "Concessionária / automotivo",
            "city": "Jaboatão dos Guararapes",
            "country": "BR",
            "address": "Avenida Barreto de Menezes, 697",
            "latitude": -8.17,
            "longitude": -34.92,
            "rating": None,
            "reviews": None,
            "website": "",
            "website_status": "unknown",
            "instagram": "",
            "instagram_active": False,
            "phone": "+55 81 3476-8500",
            "whatsapp": "",
            "contact": "",
            "potential_cents": 0,
            "notes": "Importado do Google Maps.",
        },
    }
    created = auth.post("/api/leads/imported", json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["source"] == "google_maps"
    repeated = auth.post("/api/leads/imported", json=payload)
    assert repeated.status_code == 409

    same_identity = {**payload, "source_id": "gmaps:another-link", "lead": {**payload["lead"], "name": "  via SUL  "}}
    duplicate_identity = auth.post("/api/leads/imported", json=same_identity)
    assert duplicate_identity.status_code == 409


def test_geoapify_region_search_paginates_full_place_boundary(monkeypatch):
    from backend.providers import GeoapifyProvider

    monkeypatch.setenv("RADAR_GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setenv("RADAR_REGION_PAGE_SIZE", "20")
    monkeypatch.setenv("RADAR_REGION_MAX_RESULTS", "60")
    monkeypatch.setenv("RADAR_ENRICH_LIMIT", "0")
    provider = GeoapifyProvider()
    monkeypatch.setattr(
        provider,
        "_geocode",
        lambda query: {
            "lat": -8.05,
            "lon": -34.90,
            "city": "Recife",
            "formatted": "Recife, Pernambuco, Brasil",
            "country_code": "br",
            "place_id": "recife-boundary",
        },
    )
    calls = []

    def feature(index):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-34.9 + index * 0.0001, -8.05]},
            "properties": {
                "name": f"Empresa {index}",
                "place_id": f"poi-{index}",
                "city": "Recife",
                "country_code": "br",
                "formatted": f"Rua {index}, Recife",
                "lat": -8.05,
                "lon": -34.9 + index * 0.0001,
                "categories": ["catering.restaurant"],
            },
        }

    def fake_request(path, params, *, max_bytes=5_000_000, timeout=None):
        assert path == "/v2/places"
        calls.append(dict(params))
        offset = int(params.get("offset", 0))
        if offset == 0:
            return {"features": [feature(i) for i in range(20)]}
        if offset == 20:
            return {"features": [feature(i) for i in range(20, 27)]}
        return {"features": []}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    result = provider.search(DiscoveryQuery(location="Recife", category="restaurante", country="BR"))
    assert result.scope == "region"
    assert result.complete is True
    assert result.scanned == 27
    assert len(result.results) == 27
    assert [call["offset"] for call in calls] == [0, 20]
    assert all(call["filter"] == "place:recife-boundary" for call in calls)



def test_geoapify_radius_scope_uses_circle_even_with_resolved_boundary(monkeypatch):
    from backend.providers import GeoapifyProvider

    monkeypatch.setenv("RADAR_GEOAPIFY_API_KEY", "test-key")
    monkeypatch.setenv("RADAR_ENRICH_LIMIT", "0")
    provider = GeoapifyProvider()
    monkeypatch.setattr(
        provider,
        "_geocode",
        lambda query: {
            "lat": -8.05,
            "lon": -34.90,
            "city": "Recife",
            "formatted": "Recife, Pernambuco, Brasil",
            "country_code": "br",
            "place_id": "recife-boundary",
        },
    )
    calls = []

    def fake_request(path, params, *, max_bytes=5_000_000, timeout=None):
        assert path == "/v2/places"
        calls.append(dict(params))
        return {"features": []}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    result = provider.search(
        DiscoveryQuery(
            location="Recife",
            category="restaurante",
            country="BR",
            radius_km=10,
            scope="radius",
        )
    )
    assert result.scope == "radius"
    assert len(calls) == 1
    assert calls[0]["filter"] == "circle:-34.900000,-8.050000,10000"
    assert "offset" in calls[0] and calls[0]["offset"] == 0


def test_radar_reobservation_records_review_growth_for_timing(auth, monkeypatch):
    first = discovered("N-TIMING", rating=4.7, reviews=100)
    second = discovered("N-TIMING", rating=4.8, reviews=130)
    provider = FakeProvider([batch(first), batch(second)])
    monkeypatch.setattr(main, "radar_provider", provider)
    payload = {"location": "Recife", "category": "barbearia", "radius_km": 5, "country": "BR"}

    response = auth.post("/api/radar/search", json=payload)
    assert response.status_code == 200, response.text
    lead_id = response.json()["results"][0]["id"]

    response = auth.post("/api/radar/search", json=payload)
    assert response.status_code == 200, response.text
    item = response.json()["results"][0]
    assert item["id"] == lead_id
    assert item["reviews"] == 130
    keys = {signal["key"] for signal in item["score"]["timing"]["signals"]}
    assert "reviews_growth_strong" in keys

def test_radar_polygon_filters_results_to_drawn_territory(auth, monkeypatch):
    inside = discovered("N-POLY-IN", lat=-8.05, lon=-34.90, name="Dentro")
    outside = discovered("N-POLY-OUT", lat=-8.20, lon=-35.10, name="Fora")
    monkeypatch.setattr(main, "radar_provider", FakeProvider([batch(inside, outside)]))
    response = auth.post(
        "/api/radar/search",
        json={
            "location": "Território desenhado",
            "category": "barbearia",
            "radius_km": 20,
            "scope": "polygon",
            "country": "BR",
            "center_lat": -8.05,
            "center_lng": -34.90,
            "bounds": [-34.96, -8.11, -34.84, -7.99],
            "polygon": [
                [-34.96, -8.11],
                [-34.84, -8.11],
                [-34.84, -7.99],
                [-34.96, -7.99],
            ],
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["scope"] == "polygon"
    assert [item["name"] for item in data["results"]] == ["Dentro"]


def test_watchlist_records_relevant_change_detected_by_radar(auth, monkeypatch):
    first = discovered("N-WATCH", name="Empresa Watch", reviews=100, rating=4.5)
    second = discovered("N-WATCH", name="Empresa Watch", reviews=130, rating=4.5)
    provider = FakeProvider([batch(first), batch(second)])
    monkeypatch.setattr(main, "radar_provider", provider)
    payload = {"location": "Recife", "category": "barbearia", "radius_km": 5, "country": "BR"}

    created = auth.post("/api/radar/search", json=payload)
    lead = created.json()["results"][0]
    watched = auth.patch(
        f"/api/leads/{lead['id']}/watchlist",
        json={"enabled": True, "version": lead["version"]},
    )
    assert watched.status_code == 200, watched.text
    assert watched.json()["watchlisted"] is True

    refreshed = auth.post("/api/radar/search", json=payload)
    assert refreshed.status_code == 200, refreshed.text
    updated = refreshed.json()["results"][0]
    assert updated["reviews"] == 130
    assert updated["watch_last_checked_at"] is not None
    assert updated["watch_last_event_at"] is not None

    activities = auth.get(f"/api/leads/{lead['id']}/activities")
    assert activities.status_code == 200
    changes = [item for item in activities.json() if item["kind"] == "watch_change"]
    assert changes
    assert "avalia" in changes[0]["body"].lower()


def test_similar_leads_returns_ranked_workspace_matches(auth, monkeypatch):
    target = discovered("N-SIM-1", name="Barbearia Alfa", reviews=220, rating=4.7)
    close = discovered("N-SIM-2", name="Barbearia Beta", lat=-8.052, lon=-34.902, reviews=180, rating=4.6)
    farther = discovered("N-SIM-3", name="Barbearia Gama", lat=-8.12, lon=-34.98, reviews=15, rating=3.8)
    provider = FakeProvider([batch(target, close, farther), batch()])
    monkeypatch.setattr(main, "radar_provider", provider)
    payload = {"location": "Recife", "category": "barbearia", "radius_km": 5, "country": "BR"}
    created = auth.post("/api/radar/search", json=payload)
    assert created.status_code == 200
    source = next(item for item in created.json()["results"] if item["name"] == "Barbearia Alfa")

    result = auth.post(f"/api/leads/{source['id']}/similar")
    assert result.status_code == 200, result.text
    rows = result.json()["results"]
    assert rows
    assert rows[0]["name"] == "Barbearia Beta"
    assert rows[0]["similarity"] >= rows[-1]["similarity"]

def test_radar_visible_bounds_filters_results(auth, monkeypatch):
    inside = discovered("N-BOUNDS-IN", lat=-8.05, lon=-34.90, name="Dentro Bounds")
    outside = discovered("N-BOUNDS-OUT", lat=-8.30, lon=-35.20, name="Fora Bounds")
    monkeypatch.setattr(main, "radar_provider", FakeProvider([batch(inside, outside)]))
    response = auth.post(
        "/api/radar/search",
        json={
            "location": "Área visível do mapa",
            "category": "",
            "radius_km": 20,
            "scope": "bounds",
            "country": "BR",
            "center_lat": -8.05,
            "center_lng": -34.90,
            "bounds": [-34.97, -8.12, -34.83, -7.98],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["scope"] == "bounds"
    assert [item["name"] for item in response.json()["results"]] == ["Dentro Bounds"]
