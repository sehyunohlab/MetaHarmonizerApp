# Backend project structure

The FastAPI backend is organised in layers, one top-level package per layer.

```
backend/
├── app/
│   ├── main.py              # composition root: app factory, middleware wiring, router mounting
│   ├── core/                # cross-cutting: settings, security, errors, logging, middleware,
│   │                        #   rate limits, Redis, storage, metrics, federation signing
│   ├── db/                  # SQLAlchemy base, session, ORM models, optimistic locking
│   ├── repositories/        # data access: all SQL/ORM, one module per aggregate
│   ├── schemas/             # Pydantic request/response DTOs, one module per API area
│   ├── services/            # business logic, incl. the engine-facing facades routers use
│   │                        #   (schema_catalog, engine_status, llm_rematch)
│   ├── workers/             # job dispatch (queue.py), harmonize task, arq worker, retention
│   ├── routers/             # HTTP only: one router per API area + deps.py (auth dependencies)
│   └── engine_adapter/      # ★ ONLY place that imports `metaharmonizer` (ADR 0001)
├── alembic/                 # migrations; alembic.ini at backend/
├── data/                    # METAHARMONIZER_DATA_DIR target (schema registry, value dicts, uploads)
├── scripts/                 # operational CLIs, run as `python -m scripts.<name>` from backend/
├── benchmarks/              # versioned benchmark sets + regression policies
├── tests/
│   ├── unit/                # MockEngineAdapter — fast, no torch/network; includes the layering guard
│   ├── contract/            # API contracts against Postgres + Redis
│   ├── integration/         # real engine / external validators (opt-in)
│   └── perf/                # dataset-size performance checks
├── vendor/                  # pinned metaharmonizer wheel
└── requirements.txt
```

## Layering rules

Each package may import only the packages listed for it (plus itself):

| Package          | May import                                                 |
|------------------|------------------------------------------------------------|
| `core`           | nothing app-specific                                       |
| `db`             | `core`                                                     |
| `schemas`        | `core`                                                     |
| `engine_adapter` | `core`                                                     |
| `repositories`   | `core`, `db`                                               |
| `services`       | `core`, `db`, `repositories`, `schemas`, `engine_adapter`  |
| `workers`        | `core`, `db`, `repositories`, `schemas`, `services`, `engine_adapter` |
| `routers`        | `core`, `db`, `repositories`, `schemas`, `services`, `workers` |
| `main.py`        | anything (composition root)                                |

- **routers**: parse/validate (schemas), call services — or repositories for plain CRUD —
  and shape responses. No SQL; ORM classes only for typing and the session dependency.
  Engine features go through services; background work is enqueued via `workers.queue`.
- **services**: business logic. No raw SQL (use repositories). Services and workers are the
  only callers of `engine_adapter`.
- **repositories**: all SQL/ORM. No engine.
- **workers**: run the engine via the adapter; write results via repositories.
- **engine_adapter**: the only importer of the upstream wheel (ADR 0001).
- **core**: depended on by everyone; depends on nothing app-specific. App-specific behaviour
  is injected from `main.py` — e.g. `install_limits(app, api_token_owner=...)` and
  `EngineReadinessMiddleware(readiness_error=...)`.

One documented exception: `engine_adapter/metaharmonizer_impl.py` falls back to the
dashboard's dictionary mapper in `services/harmonizer.py` (see the FAQ in
[`app/engine_adapter/README.md`](app/engine_adapter/README.md)).

Enforced by [`tests/unit/test_layering.py`](tests/unit/test_layering.py), which checks every
import in `app/` (including function-level imports), and by the engine-boundary CI check.

## Running locally

**With Docker** (any machine that has it): `make up` → stack on `:8000` (API) / `:8080` (Caddy).

**Without Docker** (e.g. a machine without WSL2/admin): portable Postgres + Redis run from
`%LOCALAPPDATA%\mh-dev` via the helper script — no admin needed.

```powershell
./scripts/dev_services.ps1 start     # start portable Postgres (5433) + Redis (6380)
./scripts/dev_services.ps1 status    # check
# .env already points DATABASE_URL -> :5433 and REDIS_URL -> :6380
cd backend; .\.venv\Scripts\uvicorn.exe app.main:app --reload
./scripts/dev_services.ps1 stop      # when done
```

Both paths serve the same app and pass `/healthz` + `/readyz`.
