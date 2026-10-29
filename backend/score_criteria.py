"""Validated configuration and replay of the existing Score 3.0 commercial dimensions."""
import json
from copy import deepcopy
from pydantic import Field, model_validator
from .schemas import StrictModel


class Weights(StrictModel):
    target_fit: int = Field(default=25, ge=5, le=50, strict=True)
    need: int = Field(default=25, ge=5, le=50, strict=True)
    impact: int = Field(default=20, ge=5, le=50, strict=True)
    viability: int = Field(default=20, ge=5, le=50, strict=True)
    activity: int = Field(default=10, ge=5, le=50, strict=True)

    @model_validator(mode='after')
    def total(self):
        if sum(self.model_dump().values()) != 100: raise ValueError('Os pesos devem somar 100.')
        return self


class Criteria(StrictModel):
    weights: Weights = Field(default_factory=Weights)
    minimum_coverage: int = Field(default=80, ge=80, le=100, strict=True)
    selection_threshold: int = Field(default=60, ge=60, le=95, strict=True)
    need_threshold: int = Field(default=65, ge=65, le=95, strict=True)


BASELINE = Criteria().model_dump()


def configuration(lead):
    raw = getattr(lead, 'score_criteria_json', '{}') or '{}'
    value = json.loads(raw)
    return Criteria.model_validate(value.get('criteria', BASELINE)).model_dump(), value.get('version', '3.0')


def commercial_priority(dimensions, fit, criteria=None):
    """Single computation for production and frozen-case replay. Evidence gates cannot be disabled."""
    cfg = Criteria.model_validate(criteria or BASELINE).model_dump()
    dims = deepcopy(dimensions)
    for key, weight in cfg['weights'].items(): dims[key]['weight'] = weight
    coverage = sum(d['weight'] for d in dims.values() if d['value'] is not None)
    value = round(sum(d['weight']*d['value'] for d in dims.values() if d['value'] is not None)/coverage) if coverage else 0
    need = dims['need']['value']
    blocked = dims['viability']['value'] == 0
    contact = dims['viability']['value'] is not None and not blocked
    contradictory = dims['need']['state'] == 'contradictory'
    sufficient = coverage >= cfg['minimum_coverage'] and dims['activity']['value'] is not None and need is not None and contact and fit['status'] == 'compatible' and not contradictory and not blocked
    state = ('qualified' if sufficient and value >= cfg['selection_threshold'] and need >= cfg['need_threshold']
             else 'evaluated' if sufficient else 'provisional' if coverage >= 40 else 'insufficient')
    if fit['status'] == 'incompatible' or blocked: value, state = 0, 'incompatible'
    elif not sufficient: value = min(value, 49)
    return {'value': value, 'status': state, 'coverage': coverage, 'commercial_dimensions': dims}
