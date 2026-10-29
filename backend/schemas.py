import re
from datetime import date
from uuid import UUID
from typing import Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, Field, ConfigDict, field_validator

Stage = Literal['discovered', 'contacted', 'replied', 'negotiating', 'won', 'lost']
Currency = Literal['BRL','USD']
Locale = Literal['pt-BR','en-US','es']
Money = int

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Login(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=256)

class EmailInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    email: str = Field(min_length=5, max_length=254)

class TokenInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    token: str = Field(min_length=20, max_length=500)

class ResetPasswordInput(TokenInput):
    password: str = Field(min_length=12, max_length=256)

class LeadInput(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=100)
    country: str = Field(default='BR', pattern=r'^[A-Z]{2}$')
    address: str = Field(default='', max_length=250)
    latitude: float = Field(ge=-85, le=85, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    rating: float | None = Field(default=None, ge=0, le=5, allow_inf_nan=False)
    reviews: int | None = Field(default=None, ge=0, le=10000000)
    website: str = Field(default='', max_length=500)
    website_status: Literal['unknown','none','good','poor'] = 'unknown'
    instagram: str = Field(default='', max_length=500)
    instagram_active: bool = False
    phone: str = Field(default='', max_length=30)
    whatsapp: str = Field(default='', max_length=20)
    contact: str = Field(default='', max_length=100)
    potential_cents: int = Field(default=0, ge=0, le=1000000000, strict=True)
    potential_currency: Currency = 'BRL'
    notes: str = Field(default='', max_length=5000)

    @field_validator('website', 'instagram')
    @classmethod
    def safe_url(cls, value):
        if value and (urlparse(value).scheme not in ('https','http') or not urlparse(value).hostname or urlparse(value).username):
            raise ValueError('Use uma URL http ou https valida')
        return value

    @field_validator('whatsapp')
    @classmethod
    def valid_phone(cls, value):
        if value and not re.fullmatch(r'\d{8,15}', value):
            raise ValueError('WhatsApp: codigo do pais e numero, apenas digitos')
        return value

class GoogleMapsImportInput(StrictModel):
    url: str = Field(min_length=10, max_length=2000)

class ImportedLeadInput(StrictModel):
    lead: LeadInput
    source: Literal['google_maps']
    source_id: str = Field(min_length=8, max_length=160)

class LeadUpdate(LeadInput):
    version: int = Field(ge=1)

class StageUpdate(StrictModel):
    stage: Stage
    version: int = Field(ge=1)

class NextActionUpdate(StrictModel):
    next_action: str = Field(default='', max_length=180)
    next_action_on: date | None = None
    version: int = Field(ge=1)

    @field_validator('next_action')
    @classmethod
    def normalize_action(cls, value):
        return ' '.join(value.split())


class LeadWatchUpdate(StrictModel):
    enabled: bool
    version: int = Field(ge=1)

class LeadActivityInput(StrictModel):
    kind: Literal['whatsapp','call','email','meeting','proposal','reply','note']
    body: str = Field(default='', max_length=1200)
    occurred_on: date | None = None
    channel: Literal['email','whatsapp','phone','meeting','other'] | None = None
    result: Literal['recorded','contacted','not_reached','interest','information_request','objection','refusal','opt_out','automatic_reply','insufficient','delivery_failure'] = 'recorded'
    request_id: UUID | None = None

    @field_validator('body')
    @classmethod
    def normalize_body(cls, value):
        return ' '.join(value.split())

RADAR_PROBLEM_KEYS = {
    'no_site','website_issues','booking_gap','menu_gap','catalog_gap',
    'ecommerce_gap','weak_digital','competitive_gap',
}

from .search_intent import Intent

class RadarSavedQuery(StrictModel):
    commercial_intent: Intent | None = None
    location: str = Field(min_length=2, max_length=160)
    category: str = Field(default='', max_length=80)
    radius_km: int = Field(default=5, ge=1, le=25)
    scope: Literal['region','radius','bounds','polygon'] = 'region'
    country: str = Field(default='', pattern=r'^(?:[A-Z]{2})?$')
    municipality_id: str = Field(default='', max_length=16, pattern=r'^\d{0,16}$')
    city_name: str = Field(default='', max_length=100)
    state: str = Field(default='', max_length=100)
    state_code: str = Field(default='', max_length=12, pattern=r'^[A-Z0-9-]{0,12}$')
    center_lat: float | None = Field(default=None, ge=-85, le=85, allow_inf_nan=False)
    center_lng: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    bounds: list[float] = Field(default_factory=list, max_length=4)
    polygon: list[list[float]] = Field(default_factory=list, max_length=32)
    problem_keys: list[str] = Field(default_factory=list, max_length=8)

    @field_validator('bounds')
    @classmethod
    def valid_bounds(cls, value):
        if not value:
            return []
        if len(value) != 4:
            raise ValueError('Área visível inválida')
        west, south, east, north = value
        if not (-180 <= west <= 180 and -180 <= east <= 180 and -85 <= south <= 85 and -85 <= north <= 85 and west < east and south < north):
            raise ValueError('Área visível inválida')
        return value

    @field_validator('polygon')
    @classmethod
    def valid_polygon(cls, value):
        if not value:
            return []
        if len(value) < 3:
            raise ValueError('O território precisa de pelo menos 3 pontos')
        cleaned=[]
        for point in value:
            if len(point) != 2:
                raise ValueError('Ponto do território inválido')
            lng, lat = point
            if not (-180 <= lng <= 180 and -85 <= lat <= 85):
                raise ValueError('Ponto do território inválido')
            cleaned.append([float(lng), float(lat)])
        return cleaned
    min_score: int = Field(default=0, ge=0, le=100)
    min_rating: float = Field(default=0, ge=0, le=5)
    min_reviews: int = Field(default=0, ge=0, le=10000000)
    contact_filter: Literal['','any','phone','whatsapp','instagram'] = ''
    min_confidence: int = Field(default=0, ge=0, le=100)
    min_timing: int = Field(default=0, ge=0, le=100)
    service_key: str = Field(default='', max_length=50, pattern=r'^[a-z0-9_]{0,50}$')
    min_service_score: int = Field(default=0, ge=0, le=100)

    @field_validator('problem_keys')
    @classmethod
    def valid_problem_keys(cls, value):
        unique=list(dict.fromkeys(value))
        if any(item not in RADAR_PROBLEM_KEYS for item in unique):
            raise ValueError('Filtro de oportunidade inválido')
        return unique

class RadarNaturalSearchInput(StrictModel):
    text: str = Field(min_length=3, max_length=280)
    fallback_location: str = Field(default='', max_length=160)
    fallback_country: str = Field(default='', pattern=r'^(?:[A-Z]{2})?$')

class RadarSavedSearchInput(StrictModel):
    name: str = Field(min_length=2, max_length=80)
    query: RadarSavedQuery
    result_ids: list[str] = Field(default_factory=list, max_length=2000)

    @field_validator('result_ids')
    @classmethod
    def valid_result_ids(cls, value):
        if len(set(value)) != len(value):
            raise ValueError('Remova resultados duplicados da busca salva')
        if any(not re.fullmatch(r'[0-9a-fA-F-]{36}', item or '') for item in value):
            raise ValueError('Resultado de busca inválido')
        return value


class RadarSavedSearchMonitorUpdate(StrictModel):
    enabled: bool
    interval: Literal['daily','weekly'] = 'daily'
    version: int = Field(ge=1)

class RadarSavedSearchResultsUpdate(StrictModel):
    result_ids: list[str] = Field(default_factory=list, max_length=2000)
    version: int = Field(ge=1)

    @field_validator('result_ids')
    @classmethod
    def valid_result_ids(cls, value):
        return RadarSavedSearchInput.valid_result_ids(value)

class SaleInput(StrictModel):
    lead_id: str = Field(max_length=36)
    campaign_id: str | None = Field(default=None, max_length=36, pattern=r'^[0-9a-fA-F-]{36}$')
    service: str = Field(min_length=2, max_length=160)
    amount_cents: int = Field(gt=0, le=1000000000, strict=True)
    currency: Currency = 'BRL'
    recurring_cents: int = Field(default=0, ge=0, le=1000000000, strict=True)
    sold_on: date
    due_on: date


class CampaignInput(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default='', max_length=2000)
    status: Literal['active','paused','finished'] = 'active'
    source_saved_search_id: str | None = Field(default=None, max_length=36, pattern=r'^[0-9a-fA-F-]{36}$')


class CampaignUpdate(CampaignInput):
    version: int = Field(ge=1)


class CampaignLeadsInput(StrictModel):
    lead_ids: list[str] = Field(min_length=1, max_length=500)
    source: Literal['manual','saved_search','similar','automation'] = 'manual'

    @field_validator('lead_ids')
    @classmethod
    def valid_campaign_leads(cls, value):
        unique = list(dict.fromkeys(value))
        if len(unique) != len(value):
            raise ValueError('Remova estabelecimentos duplicados')
        if any(not re.fullmatch(r'[0-9a-fA-F-]{36}', item or '') for item in value):
            raise ValueError('Lead inválido')
        return value

class ProjectUpdate(StrictModel):
    project_status: Literal['progress','active','finished']

class PaymentInput(StrictModel):
    amount_cents: int = Field(gt=0, le=1000000000, strict=True)
    currency: Currency = 'BRL'
    paid_on: date
    request_id: str = Field(pattern=r'^[0-9a-fA-F-]{36}$')

class ExpenseInput(StrictModel):
    description: str = Field(min_length=2, max_length=160)
    amount_cents: int = Field(gt=0, le=1000000000, strict=True)
    currency: Currency = 'BRL'
    incurred_on: date
    request_id: str = Field(pattern=r'^[0-9a-fA-F-]{36}$')

class SettingsInput(StrictModel):
    name: str = Field(min_length=2, max_length=80)
    accent: Literal['crimson','blue','green','purple','amber']
    motion: Literal['full','reduced']
    timezone: str = Field(max_length=64)
    locale: Locale = 'pt-BR'
    default_currency: Currency = 'BRL'

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Fuso horario invalido')
        return value

class PasswordInput(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)

class SiteInput(StrictModel):
    sale_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=2, max_length=160)
    url: str = Field(default='', max_length=500)
    domain: str = Field(default='', max_length=253, pattern=r'^[a-zA-Z0-9.\-]*$')
    domain_owner: str = Field(default='', max_length=160)
    renewal_on: date | None = None
    hosting: str = Field(default='', max_length=160)
    plan: str = Field(default='', max_length=160)
    maintenance: str = Field(default='', max_length=3000)
    monthly_revenue_cents: int = Field(default=0, ge=0, le=1000000000, strict=True)
    monthly_cost_cents: int = Field(default=0, ge=0, le=1000000000, strict=True)
    annual_domain_cost_cents: int = Field(default=0, ge=0, le=1000000000, strict=True)
    currency: Currency = 'BRL'
    ssl_status: Literal['unknown','valid','expiring','issue'] = 'unknown'
    ssl_expires_on: date | None = None
    analytics_url: str = Field(default='', max_length=500)
    repository_url: str = Field(default='', max_length=500)
    admin_url: str = Field(default='', max_length=500)
    status: Literal['building','active','paused','issue','archived'] = 'building'
    notes: str = Field(default='', max_length=5000)

    @field_validator('url','analytics_url','repository_url','admin_url')
    @classmethod
    def safe_url(cls, value):
        return LeadInput.safe_url(value)

class SiteUpdate(SiteInput):
    version: int = Field(ge=1)



AutomationTrigger = Literal['pipeline_added','stage_changed','watch_change','enriched','score_changed','manual']
AutomationConditionField = Literal[
    'score','confidence','timing','stage','in_pipeline','watchlisted',
    'has_phone','has_whatsapp','has_instagram','website_status','service_score','combined_signal'
]
AutomationOperator = Literal['eq','neq','gte','lte','gt','lt','truthy','falsy','contains']
AutomationActionType = Literal['add_pipeline','set_next_action','add_watchlist','add_note']

class AutomationCondition(StrictModel):
    field: AutomationConditionField
    operator: AutomationOperator = 'eq'
    value: str | int | bool | None = None
    service_key: str = Field(default='', max_length=50, pattern=r'^[a-z0-9_]{0,50}$')

class AutomationAction(StrictModel):
    type: AutomationActionType
    text: str = Field(default='', max_length=500)
    due_days: int = Field(default=0, ge=0, le=365)

    @field_validator('text')
    @classmethod
    def normalize_text(cls, value):
        return ' '.join(value.split())

class AutomationStop(StrictModel):
    stages: list[Stage] = Field(default_factory=lambda: ['won','lost'], max_length=6)
    max_runs_per_lead: int = Field(default=3, ge=1, le=50)
    stop_if_next_action_exists: bool = False

    @field_validator('stages')
    @classmethod
    def unique_stages(cls, value):
        return list(dict.fromkeys(value))

class AutomationRuleInput(StrictModel):
    name: str = Field(min_length=2, max_length=100)
    enabled: bool = True
    trigger: AutomationTrigger
    conditions: list[AutomationCondition] = Field(default_factory=list, max_length=8)
    actions: list[AutomationAction] = Field(min_length=1, max_length=8)
    stop: AutomationStop = Field(default_factory=AutomationStop)

class AutomationRuleUpdate(AutomationRuleInput):
    version: int = Field(ge=1)

class AutomationToggleInput(StrictModel):
    enabled: bool
    version: int = Field(ge=1)

class ResearchBatchInput(StrictModel):
    lead_ids: list[str] = Field(min_length=1, max_length=25)
    mode: Literal['web','deep'] = 'deep'
    stale_days: int = Field(default=30, ge=0, le=365)

    @field_validator('lead_ids')
    @classmethod
    def valid_lead_ids(cls, value):
        if len(set(value)) != len(value):
            raise ValueError('Remova estabelecimentos duplicados da fila')
        if any(not re.fullmatch(r'[0-9a-fA-F-]{36}', item or '') for item in value):
            raise ValueError('Lead inválido')
        return value
