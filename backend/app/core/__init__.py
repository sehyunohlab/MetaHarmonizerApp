"""
Core cross-cutting concerns (no business logic, no engine imports).

Houses what every layer depends on, and imports nothing app-specific — app
behaviour is injected from app/main.py. Includes settings, security (passwords,
JWT, API tokens), federation signing, errors + the unified envelope, logging,
HTTP middleware, rate limits/idempotency, Redis + the job bus (progress,
cancellation, WebSocket tickets), storage, uploads, metrics, pagination, email,
and Sentry.
"""
