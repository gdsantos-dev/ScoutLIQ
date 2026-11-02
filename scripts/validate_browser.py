"""Canonical browser runner: critical PR coverage or complete opt-in regression."""
import validate_browser_v1388 as runner

runner.GROUPS['critical'] = [
    ('redesign', 'unified'), ('unified-search', 'unified'), ('investigation', 'unified'),
    ('planning', 'planning'), ('daily-operations', 'daily'), ('commercial-queue', 'unified'),
    ('workflow', 'unified'), ('communication', 'communication'),
]
runner.GROUPS['full'] = runner.GROUPS['complete'] + [
    ('commercial-queue', 'unified'), ('followup', 'unified'),
    ('operations', 'operations'), ('planning', 'planning'), ('daily-operations', 'daily'),
]

if __name__ == '__main__':
    runner.main()
