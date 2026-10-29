"""Provider-neutral discovery geometry and historical selection criteria."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from .search_location import SearchLocation

class DiscoveryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    location: str = Field(min_length=2, max_length=160)
    country: str = Field(default="", pattern=r"^(?:[A-Z]{2})?$")
    category: str = Field(default="", max_length=80)
    radius_km: int = Field(default=5, ge=1, le=25)
    scope: Literal["region", "radius", "bounds", "polygon"] = "region"
    municipality_id: str = Field(default="", max_length=16, pattern=r"^\d{0,16}$")
    city_name: str = Field(default="", max_length=100)
    state: str = Field(default="", max_length=100)
    state_code: str = Field(default="", max_length=12, pattern=r"^[A-Z0-9-]{0,12}$")
    center_lat: float | None = Field(default=None, ge=-85, le=85, allow_inf_nan=False)
    center_lng: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    bounds: list[float] = Field(default_factory=list, max_length=4)
    polygon: list[list[float]] = Field(default_factory=list, max_length=32)
    resolved_location: SearchLocation | None = None

    @model_validator(mode="after")
    def validate_territory(self):
        if self.resolved_location and self.scope != 'region':
            raise ValueError('Local administrativo não pode ser substituído por raio ou área desenhada')
        if self.scope in {"bounds", "polygon"}:
            if self.center_lat is None or self.center_lng is None:
                raise ValueError("Centro da área é obrigatório")
            if len(self.bounds) != 4:
                raise ValueError("Limites da área são obrigatórios")
            west, south, east, north = self.bounds
            if not (-180 <= west < east <= 180 and -85 <= south < north <= 85):
                raise ValueError("Limites da área inválidos")
        if self.scope == "polygon" and len(self.polygon) < 3:
            raise ValueError("O território precisa de pelo menos 3 pontos")
        if self.scope != "polygon" and self.polygon:
            raise ValueError("Polígono só pode ser usado no modo polygon")
        return self


class LegacySearch(DiscoveryQuery):
    """Lossless input adapter for saved queries predating structured intent."""
    problem_keys: list[str] = Field(default_factory=list, max_length=8)
    min_score: int = Field(default=0, ge=0, le=100)
    min_rating: float = Field(default=0, ge=0, le=5, allow_inf_nan=False)
    min_reviews: int = Field(default=0, ge=0, le=10000000)
    contact_filter: Literal['','any','phone','whatsapp','instagram'] = ''
    min_confidence: int = Field(default=0, ge=0, le=100)
    min_timing: int = Field(default=0, ge=0, le=100)
    service_key: str = Field(default='', max_length=50, pattern=r'^[a-z0-9_]{0,50}$')
    min_service_score: int = Field(default=0, ge=0, le=100)

    @field_validator('problem_keys')
    @classmethod
    def problems(cls, value):
        allowed={'no_site','website_issues','booking_gap','menu_gap','catalog_gap','ecommerce_gap','weak_digital','competitive_gap'}
        if any(key not in allowed for key in value): raise ValueError('Filtro de oportunidade inválido')
        return list(dict.fromkeys(value))

    @model_validator(mode='after')
    def exact_area(self):
        if self.scope in ('bounds','polygon'):
            from .search_location import SearchArea
            SearchArea(kind=self.scope,bounds=self.bounds,polygon=self.polygon)
            # Validate without rewriting the historical provider center/radius.
        return self

    def discovery(self):
        return DiscoveryQuery.model_validate(self.model_dump(include=set(DiscoveryQuery.model_fields)))
