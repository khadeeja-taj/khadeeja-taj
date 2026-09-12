# HaqFlow Backend — quick share pack

Two files, the whole backend. Everyone on the team can run this in ~2 minutes.

## Files in this folder
- **`app.py`** — the entire backend in one file (models, schemas, deterministic
  eligibility engine, all API routes, and the seeded Pakistan program pack).
- **`requirements.txt`** — Python dependencies.

## Run it

```bash
# 1. (recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. install
pip install -r requirements.txt

# 3. start the server
uvicorn app:app --reload
#   ...or:  python app.py
```

Then open **http://localhost:8000/docs** — interactive API docs where anyone can
try every endpoint in the browser.

On first run it auto-creates a local SQLite database (`haqflow.db`) and seeds
8 Pakistan support programs. **No database setup needed to get started.**

## Use the shared team database (Supabase / Postgres) instead
```bash
pip install psycopg2-binary
export DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:5432/DBNAME"
uvicorn app:app --reload
```
(Windows PowerShell: `setx DATABASE_URL "..."` then reopen the terminal.)

## The endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Is the server up? |
| POST | `/cases` | Create a case (optionally with a situation) |
| GET | `/cases` · `/cases/{id}` | List / get a full case |
| PUT | `/cases/{id}/situation` | Save the AI-extracted structured facts |
| GET/POST | `/programs` · `/programs/{id}` | List / add / get programs |
| POST | `/cases/{id}/match` | **Run the eligibility engine** over all programs |
| GET | `/cases/{id}/matches` | Stored match results (best first) |
| POST/GET | `/cases/{id}/tasks` | Create / list action-plan tasks |
| PATCH | `/tasks/{id}` | Update a task's status |
| POST/GET | `/cases/{id}/documents` | Store / list document (evidence) results |

## Who plugs in where
- **AI/agent teammate:** `PUT /cases/{id}/situation` with the extracted `facts`,
  then `POST /cases/{id}/match`. The Python engine — not the prompt — decides
  eligibility.
- **Program-data teammate:** add programs via `POST /programs`, or edit the
  `SEED_PROGRAMS` list at the top of `app.py`.
- **Frontend teammate:** every response shape is visible and testable at `/docs`.
- **Follow-up teammate:** task status values live in the `TaskStatus` enum;
  update them via `PATCH /tasks/{id}`.

## Eligibility rule shape (how a program decides who qualifies)
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

A match result reports `match_level` (`eligible` / `likely` / `needs_info` /
`not_eligible`), a `score`, and the exact lists of matched / failed / missing
conditions — so the UI can always explain *why*.

## Example (paste into `/docs`, endpoint `POST /cases`)
```json
{
  "raw_text": "My father lost his daily-wage job. We are six people. My sister is in school and my mother is pregnant.",
  "situation": {
    "household_size": 6,
    "monthly_income": 15000,
    "province": "Punjab",
    "facts": { "pmt_score": 18, "has_cnic": true, "gender": "female", "children_in_school": 1, "has_pregnant_member": true }
  }
}
```
Copy the returned `id`, then call `POST /cases/{id}/match` to see the matched
programs.

> Note: the full modular version of this backend (separate `api/`, `models/`,
> `services/`, `rules/` folders + tests) lives one level up in `backend/`.
> This single-file pack is just the easy way to share and start.
