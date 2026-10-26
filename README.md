# Setu: Commercial Decision Engine for EU-India B2B Teams

Setu turns commercial signals into a short, ranked queue of decisions for revenue leaders selling across the EU-India corridor. Each decision comes with evidence, counter-signals, a confidence score and an audit trail. A human approves, adjusts or rejects it, and the engine learns from the verdict.

See `ENGINE_BRIEF.md` for a summary of what the engine does.

> **Status:** working prototype on fictional demo data (nine accounts, five deals, 28 signals). No live customers or CRM connection: approved actions go to a write-back outbox. Built with Claude Code as build partner. Setu is a product of AIA Stakeholder Intelligence.

## Redesign (October 2026, designed, not yet built)

The running app still uses the original interface. The redesign puts an owner on every call, sends it to a deputy when that person is away, and shows exactly what changes in the CRM before anyone approves. Screens use the engine's own demo output. More in [`docs/design`](docs/design).

| Decision queue | Decision detail | Engine |
|---|---|---|
| [![Decision queue](docs/design/1-decision-queue.png)](docs/design/1-decision-queue.png) | [![Decision detail](docs/design/2-decision-detail.png)](docs/design/2-decision-detail.png) | [![Agent weights](docs/design/3-engine-weights.png)](docs/design/3-engine-weights.png) |

## Run it

Requires Python 3.10 or later. No packages to install.

```bash
python run.py            # http://127.0.0.1:8000, loads demo data on first start
python run.py --reset    # reload the EU-India demo data
python -m unittest discover tests
```

## Run with Docker

With Docker Desktop running, start the app from this folder:

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. The database is stored in a named Docker volume and
persists across container restarts. Stop the app with `Ctrl+C`; use
`docker compose down` to remove the container while keeping the database.

Optional: set `ANTHROPIC_API_KEY` to have Claude write the executive briefing (model set by `SETU_MODEL`). Without a key, a template briefing is used. `SETU_EUR_INR` overrides the illustrative exchange rate.

## Project layout

| Path | Purpose |
|---|---|
| `engine/ingest.py` | Observe and Understand: ingestion, entity resolution, classification |
| `engine/agents.py` | Reason: the seven specialist agents plus the Manager agent |
| `engine/corridor.py` | EU-India knowledge: FX, holiday windows, Indian fiscal year, regulation, buyer norms |
| `engine/prioritise.py` | Prioritise: scoring and queue selection |
| `engine/pipeline.py` | One engine run end to end, plus the Executive agent briefing |
| `engine/review.py` | Human review, CRM and Slack write-back, learning loop |
| `engine/accounts.py` | ICP discovery, account plans, buying committees, outreach plays |
| `engine/meddpicc.py` | MEDDPICC deal inspection |
| `engine/llm.py` | Optional Claude call for the briefing |
| `engine/seed.py` | Fictional demo tenant |
| `server.py`, `run.py` | JSON API and web server |
| `web/` | Browser interface |
| `tests/` | End-to-end tests of the workflow |

## API

| Method | Path | Does |
|---|---|---|
| GET | `/api/summary` | Headline numbers and the latest briefing |
| GET | `/api/decisions?status=pending` | Decision queue with expanded evidence |
| POST | `/api/decisions/{id}/review` | `{"verdict": "approve" \| "adjust" \| "reject", "note": "...", "value": "..."}` |
| POST | `/api/run` | Run the engine |
| GET, POST | `/api/events` | Read the signal feed, or ingest `{"source", "text", "email"?, "account"?}` |
| POST | `/api/simulate` | Inject a realistic live signal |
| GET | `/api/accounts`, `/api/accounts/{id}` | Account list and living account plan |
| GET | `/api/icp` | Ranked target accounts |
| GET | `/api/opportunities/{id}/meddpicc` | MEDDPICC inspection |
| GET | `/api/audit`, `/api/outbox` | Audit trail and write-back queue |
| GET | `/api/agents` | Agent weights and recent runs |

## Taking it to production

1. Replace the outbox with real connectors (HubSpot or Salesforce API, Slack webhooks) and pull signals from them on a schedule.
2. Swap SQLite for PostgreSQL and add role-based access per team.
3. Feed a live EUR/INR rate and a maintained holiday calendar into `corridor.py`.
4. Host in the EU and document GDPR and DPDP Act data flows before onboarding real customer data.
