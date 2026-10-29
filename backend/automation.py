from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AutomationRule, AutomationRun, Lead, LeadActivity, User
from .scoring import score


def _decoded(value: str, fallback):
    try:
        parsed = json.loads(value or '')
        return parsed if isinstance(parsed, type(fallback)) else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


def rule_row(rule: AutomationRule) -> dict:
    return {
        'id': rule.id,
        'name': rule.name,
        'enabled': bool(rule.enabled),
        'trigger': rule.trigger,
        'conditions': _decoded(rule.conditions_json, []),
        'actions': _decoded(rule.actions_json, []),
        'stop': _decoded(rule.stop_json, {}),
        'last_run_at': rule.last_run_at,
        'created_at': rule.created_at,
        'updated_at': rule.updated_at,
        'version': rule.version,
    }


def run_row(run: AutomationRun) -> dict:
    return {
        'id': run.id,
        'rule_id': run.rule_id,
        'lead_id': run.lead_id,
        'trigger': run.trigger,
        'status': run.status,
        'reason': run.reason,
        'actions': _decoded(run.actions_json, []),
        'created_at': run.created_at,
    }


def _service_score(payload: dict, key: str) -> int:
    for item in payload.get('service_scores') or []:
        if isinstance(item, dict) and item.get('key') == key:
            try:
                return int(item.get('value') or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def _condition_value(lead: Lead, condition: dict):
    field = str(condition.get('field') or '')
    if field in {'score', 'confidence', 'timing', 'service_score', 'combined_signal'}:
        payload = score(lead)
        if field == 'score':
            return int(payload.get('value') or 0)
        if field == 'confidence':
            confidence = payload.get('confidence') or {}
            return int(confidence.get('value') or 0)
        if field == 'timing':
            timing = payload.get('timing') or {}
            return int(timing.get('value') or 0)
        if field == 'service_score':
            return _service_score(payload, str(condition.get('service_key') or ''))
        return [str(item.get('key') or '') for item in payload.get('combined_signals') or [] if isinstance(item, dict)]
    if field == 'stage':
        return lead.stage
    if field == 'in_pipeline':
        return bool(lead.in_pipeline)
    if field == 'watchlisted':
        return bool(getattr(lead, 'watchlisted', False))
    if field == 'has_phone':
        return bool(lead.phone)
    if field == 'has_whatsapp':
        return bool(lead.whatsapp)
    if field == 'has_instagram':
        return bool(lead.instagram)
    if field == 'website_status':
        return lead.website_status
    return None


def _as_number(value):
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def condition_matches(lead: Lead, condition: dict) -> bool:
    actual = _condition_value(lead, condition)
    operator = str(condition.get('operator') or 'eq')
    expected = condition.get('value')
    if operator == 'truthy':
        return bool(actual)
    if operator == 'falsy':
        return not bool(actual)
    if operator == 'contains':
        if isinstance(actual, (list, tuple, set)):
            return str(expected or '') in {str(item) for item in actual}
        return str(expected or '') in str(actual or '')
    if operator in {'gte', 'lte', 'gt', 'lt'}:
        left = _as_number(actual)
        right = _as_number(expected)
        if left is None or right is None:
            return False
        return {
            'gte': left >= right,
            'lte': left <= right,
            'gt': left > right,
            'lt': left < right,
        }[operator]
    if isinstance(actual, bool):
        if isinstance(expected, str):
            expected = expected.strip().lower() in {'1', 'true', 'yes', 'sim'}
        expected = bool(expected)
    if operator == 'neq':
        return actual != expected
    return actual == expected


def _add_activity(db: Session, lead: Lead, kind: str, body: str, rule: AutomationRule, metadata: dict | None = None) -> None:
    payload = {'automation_rule_id': rule.id, 'automation_rule_name': rule.name, **(metadata or {})}
    db.add(LeadActivity(
        user_id=lead.user_id,
        lead_id=lead.id,
        kind=kind,
        body=body[:1200],
        metadata_json=json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
        created_at=int(time.time()),
    ))


def _local_date(user: User | None, due_days: int) -> str:
    timezone = getattr(user, 'timezone', '') or 'America/Sao_Paulo'
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo('UTC')
    return (datetime.now(zone).date() + timedelta(days=max(0, due_days))).isoformat()


def _stop_reason(db: Session, rule: AutomationRule, lead: Lead, stop: dict) -> str:
    stages = stop.get('stages') if isinstance(stop.get('stages'), list) else ['won', 'lost']
    if lead.stage in stages:
        return f'stage:{lead.stage}'
    if bool(stop.get('stop_if_next_action_exists')) and bool(lead.next_action):
        return 'next_action_exists'
    max_runs = int(stop.get('max_runs_per_lead') or 3)
    executed = db.scalar(
        select(func.count()).select_from(AutomationRun).where(
            AutomationRun.rule_id == rule.id,
            AutomationRun.lead_id == lead.id,
            AutomationRun.status == 'executed',
        )
    ) or 0
    if executed >= max(1, min(max_runs, 50)):
        return 'max_runs'
    return ''


def _apply_action(db: Session, rule: AutomationRule, lead: Lead, action: dict, user: User | None, now: int) -> dict:
    action_type = str(action.get('type') or '')
    if action_type == 'add_pipeline':
        if lead.stage in {'won', 'lost'}:
            return {'type': action_type, 'status': 'skipped', 'reason': 'closed_stage'}
        if not lead.in_pipeline:
            lead.in_pipeline = True
            lead.pipeline_added_at = lead.pipeline_added_at or now
            _add_activity(db, lead, 'pipeline_added', '', rule, {'stage': lead.stage})
            return {'type': action_type, 'status': 'done'}
        return {'type': action_type, 'status': 'skipped', 'reason': 'already_in_pipeline'}

    if action_type == 'set_next_action':
        if lead.stage in {'won', 'lost'}:
            return {'type': action_type, 'status': 'skipped', 'reason': 'closed_stage'}
        text = ' '.join(str(action.get('text') or '').split())[:180]
        if not text:
            return {'type': action_type, 'status': 'skipped', 'reason': 'empty_text'}
        due_days = max(0, min(int(action.get('due_days') or 0), 365))
        lead.next_action = text
        lead.next_action_on = _local_date(user, due_days)
        _add_activity(db, lead, 'next_action', text, rule, {'due_on': lead.next_action_on})
        return {'type': action_type, 'status': 'done', 'due_on': lead.next_action_on}

    if action_type == 'add_watchlist':
        if not bool(getattr(lead, 'watchlisted', False)):
            lead.watchlisted = True
            lead.watch_started_at = lead.watch_started_at or now
            _add_activity(db, lead, 'note', 'Empresa adicionada à Watchlist por automação.', rule)
            return {'type': action_type, 'status': 'done'}
        return {'type': action_type, 'status': 'skipped', 'reason': 'already_watchlisted'}

    if action_type == 'add_note':
        text = ' '.join(str(action.get('text') or '').split())[:1200]
        if not text:
            return {'type': action_type, 'status': 'skipped', 'reason': 'empty_text'}
        _add_activity(db, lead, 'note', text, rule)
        return {'type': action_type, 'status': 'done'}

    return {'type': action_type or 'unknown', 'status': 'skipped', 'reason': 'unsupported_action'}


def execute_rule(db: Session, rule: AutomationRule, lead: Lead, trigger: str, *, force: bool = False) -> AutomationRun | None:
    if not rule.enabled and not force:
        return None
    if rule.trigger != trigger and not force:
        return None
    conditions = _decoded(rule.conditions_json, [])
    if not all(condition_matches(lead, item) for item in conditions if isinstance(item, dict)):
        return None

    now = int(time.time())
    stop = _decoded(rule.stop_json, {})
    reason = _stop_reason(db, rule, lead, stop)
    if reason:
        run = AutomationRun(
            user_id=lead.user_id,
            rule_id=rule.id,
            lead_id=lead.id,
            trigger=trigger,
            status='stopped',
            reason=reason,
            actions_json='[]',
            created_at=now,
        )
        db.add(run)
        rule.last_run_at = now
        rule.updated_at = now
        return run

    user = db.get(User, lead.user_id)
    actions = _decoded(rule.actions_json, [])
    applied = [_apply_action(db, rule, lead, item, user, now) for item in actions if isinstance(item, dict)]
    run = AutomationRun(
        user_id=lead.user_id,
        rule_id=rule.id,
        lead_id=lead.id,
        trigger=trigger,
        status='executed',
        reason='',
        actions_json=json.dumps(applied, ensure_ascii=False, separators=(',', ':')),
        created_at=now,
    )
    db.add(run)
    rule.last_run_at = now
    rule.updated_at = now
    return run


def run_automation_event(db: Session, lead: Lead, trigger: str, metadata: dict | None = None) -> list[AutomationRun]:
    rules = db.scalars(
        select(AutomationRule).where(
            AutomationRule.user_id == lead.user_id,
            AutomationRule.enabled.is_(True),
            AutomationRule.trigger == trigger,
        ).order_by(AutomationRule.created_at.asc())
    ).all()
    runs: list[AutomationRun] = []
    for rule in rules:
        run = execute_rule(db, rule, lead, trigger)
        if run is not None:
            runs.append(run)
    return runs
