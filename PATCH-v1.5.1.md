# ScoutLIQ v1.5.1 — Alembic migration convergence

Hotfix for the v1.5 audit upgrade chain.

## Cause
Two consecutive v1.5 patches each introduced an Alembic migration with `revision = '007'`:
- `007_site_audit.py`
- `007_deep_site_audit.py`

When both files were present after applying patches cumulatively, Alembic detected a duplicate revision and `upgrade head` aborted at startup.

## Fix
- Keeps `007_site_audit.py` as the canonical revision `007`.
- Rewrites the existing `007_deep_site_audit.py` path as revision `008`, depending on `007`.
- Revision `008` converges both historical audit schemas into the current deep-audit schema.
- The migration is defensive and also succeeds when a database had already applied either historical `007` schema.

The filename `007_deep_site_audit.py` is intentionally retained in the patch so copying the patch over an existing project overwrites the conflicting file. No manual file deletion is required.

No application API, frontend, auth, scoring or business logic changes are included in this hotfix.
