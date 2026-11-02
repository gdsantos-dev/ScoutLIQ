"""Bounded operational events; no exception messages, payloads or connection URLs."""
import json
import logging


def event(name, *, component, state, retryable=False):
    logging.getLogger('scoutliq.operations').warning(json.dumps({
        'event': name, 'component': component, 'state': state, 'retryable': retryable,
    }, ensure_ascii=True, sort_keys=True))
