# INTELORA

**Enterprise AIOT Intelligence Platform**

INTELORA turns raw electrical telemetry into business decisions. Six intelligence
layers sit between the device and the executive: anomaly detection, predictive
maintenance, preventive scheduling, prescriptive optimisation, asset performance
management, and overall equipment efficiency.

The authoritative specification is
[`docs/INTELORA_MASTER_REFERENCE.md`](docs/INTELORA_MASTER_REFERENCE.md). Where
code and that document disagree, the document is correct.

---

## Running it

### With Docker (recommended)

```bash
cp .env.example .env
docker compose up --build
```

| Service  | URL                            |
| -------- | ------------------------------ |
| Frontend | http://localhost:8080          |
| API docs | http://localhost:8000/docs     |
| Health   | http://localhost:8000/health   |
| Live     | ws://localhost:8000/ws/live    |
| Database | localhost:5432                 |

On first start the backend creates the schema, converts `telemetry` into a
TimescaleDB hypertable, provisions the asset registry, and starts the Digital
Twin Engine. Telemetry begins flowing within a second or two; the intelligence
layers complete their first pass shortly after.

### Local development

The database is easiest in Docker even when the rest runs on the host:

```bash
docker compose up -d database
```

**Backend** — requires Python 3.12 or newer:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
set POSTGRES_HOST=localhost     # the container publishes on the host
uvicorn app.main:app --reload
```

**Frontend**:

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

The dev server reads `VITE_API_BASE_URL` and `VITE_WS_URL`, defaulting to
`localhost:8000`.

---

## Layout

```
INTELORA/
├── frontend/          Presentation Layer — React 19, TypeScript, Vite
├── backend/           Telemetry, Intelligence and BI layers — FastAPI
├── database/          Extension bootstrap SQL
├── docs/              The Single Source of Truth
├── docker/            Images, nginx config, runtime entrypoint
└── assets/            Brand source material
```

### Backend

```
backend/app/
├── main.py            Wires the layers and owns their lifetimes
├── config/            Every environment variable, in one place
├── core/              Structured logging, error taxonomy
├── database/          Engine, sessions, schema bootstrap, column types
├── models/            SQLAlchemy tables
├── schemas/           Pydantic contracts — mirrored by frontend/src/types
├── digital_twin/      Virtual assets: profiles, scenarios, devices, engine
├── intelligence/      The six layers, plus shared context and the runner
├── services/          Telemetry pipeline, business model, live state, dashboard
├── routers/           47 REST endpoints under /api/v1
├── websocket/         The single multiplexed /ws/live connection
└── utils/             Pure helpers
```

### Frontend

```
frontend/src/
├── main.tsx  App.tsx
├── assets/            Static assets
├── components/        ui · brand · boot · layout · common · cockpit · data
├── layouts/           AppShell
├── pages/             One per route
├── routes/            Lazy-loaded route table
├── hooks/             Context accessors and React Query hooks
├── services/          HTTP client, live stream, typed API surface
├── context/           Theme, sidebar, boot, live bridge
├── charts/            Tree-shaken ECharts wrapper and option builders
├── animations/        Shared motion vocabulary
├── constants/         Config, navigation registry, copy, query keys
├── types/             Mirrors backend/app/schemas
├── utils/             cn, formatting, status mapping
└── styles/            The token layer
```

---

## How it fits together

```
Digital Twin ──► Telemetry Service ──► PostgreSQL / TimescaleDB
                        │                        │
                        │                        ▼
                        │                 Intelligence Layers (×6)
                        │                        │
                        ▼                        ▼
                 WebSocket ◄──── Business Intelligence Layer
                        │
                        ▼
                 React Presentation Layer
```

The twin is constructed with the telemetry service as its sink. That single
seam is what lets a real sensor gateway replace it in a later phase without
anything above the Telemetry Layer changing.

### Three ideas worth knowing before you edit anything

**The two-model rule.** Asset categories genuinely differ — an air conditioner
reports three-way power decomposition and relay state; a mobile charger reports
neither power factor, frequency, nor energy. So there are two models: a
telemetry model that varies, and a **business model** that is identical for
every category. Dashboard surfaces bind to the business model. A value the
category does not report is `null` and renders as an em dash, never as zero.

**Three status dimensions.** Health (`healthy`/`warning`/`critical`), operation
(`running`/`idle`/`maintenance`) and connectivity (`online`/`offline`/`unknown`)
are independent. An asset is always all three at once. Never collapse them.

**Live data does not go through component state.** The WebSocket writes into the
React Query cache, so components use ordinary `useQuery` calls and receive live
updates without knowing a socket exists. Messages are coalesced and flushed on
an animation frame — at 1 Hz across a dozen charts, that is the difference
between smooth and stuttering.

---

## Configuration

All of it in `.env`; see `.env.example` for the annotated set. The ones you are
most likely to change:

| Variable                        | Default   | Purpose                                  |
| ------------------------------- | --------- | ---------------------------------------- |
| `TWIN_ENABLED`                  | `true`    | Master switch for the Digital Twin       |
| `TWIN_INTERVAL_SECONDS`         | `1.0`     | Telemetry cadence                        |
| `TWIN_LAPTOP_CHARGERS`          | `18`      | Virtual device count                     |
| `TWIN_MOBILE_CHARGERS`          | `24`      | Virtual device count                     |
| `TWIN_AIR_CONDITIONERS`         | `12`      | Virtual device count                     |
| `INTELLIGENCE_INTERVAL_SECONDS` | `15.0`    | How often the six layers recompute       |
| `ENERGY_TARIFF_PER_KWH`         | `0.14`    | Converts energy into cost                |

Raising a device count adds devices on the next start without disturbing
existing ones or their history.

No secret may ever go in a `VITE_*` variable — those are compiled into the
browser bundle. Container deployments get their API endpoints from `/config.js`,
written by the frontend entrypoint at container start, so one built image can be
promoted across environments.

---

## Scope

The platform **observes and advises**. It does not control devices: there is no
actuation endpoint anywhere in the API, and prescriptive output is
recommendations for humans. The architecture leaves room for future control
without implementing it.

Authentication, multi-tenant enforcement, and PDF/spreadsheet export are later
phases and are absent rather than stubbed.

---

## Verification

```bash
cd frontend && npm run typecheck && npm run build
cd backend  && python -m compileall -q app
```
