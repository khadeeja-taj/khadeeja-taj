# HaqFlow — Backend & Eligibility Engine

**Member 2 deliverable — Python Backend / Database / Rules Engineer**

The stable Python backend that the rest of the HaqFlow team plugs into:
predictable APIs, clean data models, and a **deterministic** eligibility engine.

> Core principle: the LLM may *extract* a person's facts, but this Python code
> *decides* whether each published condition is **matched**, **failed**, or
> still **unknown**. No eligibility threshold is ever invented at runtime — every
> threshold comes from a program's rule data with a cited source.

---

## Tech stack

- **FastAPI** + **Pydantic v2** — API and request/response validation
- **SQLAlchemy 2.0** — ORM (one consistent pattern everywhere)
- **SQLite** by default (zero setup); point `DATABASE_URL` at **Supabase/Postgres**
  for the shared team DB — nothing else changes
- **pytest** — unit + endpoint tests

## Project layout

```
backend/
  app/
    api/         # thin route handlers: validate -> service -> schema
    schemas/     # Pydantic request/response models (the shared contract)
    models/      # SQLAlchemy tables + shared enums
    services/    # all DB access and business logic lives here
    rules/       # deterministic eligibility engine + operators
    utils/       # consistent error envelope
    seed/        # curated Pakistan program pack (programs.json)
    config.py    # env-driven settings
    database.py  # engine / session / Base
    main.py      # FastAPI app + startup (create tables, seed programs)
  tests/         # eligibility unit tests + endpoint happy/failure paths
```

## Run it

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
# Interactive docs: http://localhost:8000/docs
```

On startup the app creates tables and seeds the curated program pack
(8 Pakistan programs). To use Supabase/Postgres, copy `.env.example` to `.env`
and set `DATABASE_URL`.

## Test it

```bash
pytest            # 18 tests: eligibility engine + all endpoints
```

---

## API contract

Base URL: `/`   ·   All errors share one envelope (see below).

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `POST` | `/cases` | Create a case (optionally with a situation) |
| `GET` | `/cases` | List cases |
| `GET` | `/cases/{id}` | Full case (situation, matches, tasks, documents) |
| `PUT` | `/cases/{id}/situation` | Create/replace structured facts |
| `GET` | `/programs` | List programs (`?country=&category=`) |
| `GET` | `/programs/{id}` | One program |
| `POST` | `/programs` | Add a program |
| `POST` | `/cases/{id}/match` | **Run the eligibility engine** over all programs |
| `GET` | `/cases/{id}/matches` | Stored match results (best-first) |
| `POST` | `/cases/{id}/tasks` | Create an action-plan task |
| `GET` | `/cases/{id}/tasks` | List tasks |
| `PATCH` | `/tasks/{id}` | Update task status/fields |
| `POST` | `/cases/{id}/documents` | Store a document/evidence result |
| `GET` | `/cases/{id}/documents` | List documents |

### Situation facts (what the eligibility engine reads)

Send named columns and/or a free-form `facts` bag; they are merged before
matching. Facts the seed programs use:

`pmt_score`, `has_cnic`, `gender`, `monthly_income`, `province`,
`children_in_school`, `has_pregnant_member`, `has_disability`, `age`,
`eobi_registered`, `insured_years`, `has_bank_account`.

### Eligibility rule shape (Program `eligibility_rules[]`)

```json
{
  "field": "pmt_score",
  "operator": "lte",
  "value": 32,
  "label": "NSER poverty (PMT) score is 32 or below",
  "required": true
}
```

Operators: `eq ne lt lte gt gte in not_in contains between is_true is_false`.

### MatchResult (per program)

```json
{
  "match_level": "eligible",
  "score": 1.0,
  "matched_conditions": [ ... ],
  "failed_conditions":  [ ... ],
  "missing_conditions": [ ... ]
}
```

`match_level` values:

| Level | Meaning |
| --- | --- |
| `eligible` | Every required condition matched |
| `likely` | Required matched; some optional condition unknown/failed |
| `needs_info` | A required fact is still unknown |
| `not_eligible` | A required condition failed |

> The engine never claims *official* eligibility — only how the person's facts
> line up with a program's **published** criteria. UI language should say
> "may qualify" / "matches the published criteria".

### Error envelope (every error)

```json
{ "error": { "code": "not_found", "message": "Case 'x' not found.", "details": null } }
```

Codes: `not_found` (404), `conflict` (409), `validation_error` (422),
`http_error`, `internal_error` (500).

### Shared enums

- **TaskStatus**: `pending in_progress blocked completed cancelled`
- **TaskPriority**: `low medium high urgent`
- **DocumentStatus**: `received processed needs_review rejected`
- **CaseStatus**: `open in_progress escalated resolved closed`

---

## Interfaces with the team

- **Member 1/3 (AI/agent):** call `PUT /cases/{id}/situation` with extracted
  `facts`, then `POST /cases/{id}/match`. The engine — not the prompt — decides
  eligibility.
- **Member 3 (Program data):** program JSON + rule shape are documented above;
  add programs via `POST /programs` or extend `app/seed/programs.json`.
- **Member 4 (Frontend):** consume the documented schemas at `/docs`; every
  response is a typed Pydantic model, never an ad-hoc dict.
- **Member 5 (Follow-up):** `TaskStatus` values and the `PATCH /tasks/{id}`
  status-update endpoint are the persistence points for the action plan.

Program facts carry `source_url`, `source_date` and `effective_date` for the
trust/auditability requirement.
