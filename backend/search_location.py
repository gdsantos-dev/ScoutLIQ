"""Resolved administrative geography shared by search, saved searches and routines.

Coordinates and bounding boxes describe the selection; a bounding box is never
claimed to be its administrative boundary. Providers must declare support.
"""
from typing import Literal
import math
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SearchArea(BaseModel):
    """Explicit map geometry; never an inferred administrative boundary."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    kind: Literal['bounds', 'polygon']
    bounds: list[float] = Field(min_length=4, max_length=4)
    polygon: list[tuple[float, float]] = Field(default_factory=list, max_length=32)

    @property
    def label(self):
        return 'Território desenhado' if self.kind == 'polygon' else 'Área visível do mapa'

    @property
    def center(self):
        w,s,e,n = self.bounds
        return ((s+n)/2, (w+e)/2)

    @property
    def radius_km(self):
        w,s,e,n = self.bounds
        lat,_ = self.center
        return max(1, math.ceil(math.hypot((n-s)*111.32/2, (e-w)*111.32*max(.2,math.cos(math.radians(lat)))/2)))

    @model_validator(mode='after')
    def geometry(self):
        w,s,e,n = self.bounds
        if not (-180 <= w < e <= 180 and -85 <= s < n <= 85):
            raise ValueError('Limites da área inválidos')
        if self.radius_km > 25:
            raise ValueError('Aproxime o mapa; a área excede 25 km a partir do centro')
        if self.kind == 'bounds':
            if self.polygon: raise ValueError('Polígono não pertence à área retangular')
            return self
        points = self.polygon
        if len(points) < 3 or len(set(points)) != len(points):
            raise ValueError('Polígono exige pelo menos três pontos distintos')
        if any(not(w <= x <= e and s <= y <= n) for x,y in points):
            raise ValueError('Polígono fora dos limites informados')
        actual=[min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)]
        if any(abs(a-b)>1e-7 for a,b in zip(actual,self.bounds)):
            raise ValueError('Limites não correspondem ao polígono')
        edges=list(zip(points,points[1:]+points[:1]))
        if abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in edges)) < 1e-12:
            raise ValueError('Polígono sem área')
        def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        def intersects(a,b,c,d):
            if max(a[0],b[0]) < min(c[0],d[0]) or max(c[0],d[0]) < min(a[0],b[0]): return False
            if max(a[1],b[1]) < min(c[1],d[1]) or max(c[1],d[1]) < min(a[1],b[1]): return False
            return cross(a,b,c)*cross(a,b,d)<=0 and cross(c,d,a)*cross(c,d,b)<=0
        for i,(a,b) in enumerate(edges):
            for j,(c,d) in enumerate(edges):
                if j <= i+1 or (i==0 and j==len(edges)-1): continue
                if intersects(a,b,c,d): raise ValueError('Polígono com cruzamento de segmentos')
        return self


class SearchLocation(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=220, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=2, max_length=100)
    formatted: str = Field(min_length=2, max_length=220)
    administrative_type: Literal['district', 'city', 'county', 'state', 'country']
    subdivision: str = Field(default='', max_length=100)
    city: str = Field(default='', max_length=100)
    state: str = Field(default='', max_length=100)
    state_code: str = Field(default='', max_length=12)
    country: str = Field(default='', max_length=100)
    country_code: str = Field(pattern=r'^[A-Z]{2}$')
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    bbox: list[float] = Field(default_factory=list, max_length=4)
    source: Literal['geoapify', 'ibge']
    resolved_at: int = Field(ge=1)

    @model_validator(mode='after')
    def geometry(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Coordenadas incompletas')
        if self.bbox:
            if len(self.bbox) != 4:
                raise ValueError('Limites incompletos')
            west, south, east, north = self.bbox
            if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
                raise ValueError('Limites inválidos')
        return self


class LocationSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=220, pattern=r'^[a-zA-Z0-9_-]+$')
    query: str = Field(min_length=2, max_length=160)
    country: str = Field(default='', pattern=r'^([A-Z]{2})?$')


def resolve_selection(selection: LocationSelection, user_id):
    # Re-read the configured catalog. Client labels/coordinates never become
    # authoritative facts, and no arbitrary first result resolves homonyms.
    from .locations import LocationCatalogError
    from .location_budget import search
    for item in search(user_id,selection.query, selection.country, 'pt', administrative=True):
        location = item.get('resolved')
        if location and location['id'] == selection.id:
            return SearchLocation.model_validate(location)
    raise LocationCatalogError('Selected location is no longer available')
