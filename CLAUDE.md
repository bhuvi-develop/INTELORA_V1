# INTELORA — Working Agreement

INTELORA is an **Enterprise AIOT Intelligence Platform**. It is not an admin
dashboard, not a CRUD app, and not a demo. Every change should move it toward
software a Fortune 500 buyer would pay for.

## Read this first

The Single Source of Truth is **[`docs/INTELORA_MASTER_REFERENCE.md`](docs/INTELORA_MASTER_REFERENCE.md)**.
Read it before writing code. Where code and that document disagree, the
document is correct. Where this file and that document disagree, that document
is correct — this file is a summary for fast orientation.

## Non-negotiables

- **Extend, never destroy.** Do not delete files, rename folders, replace the
  architecture, or regenerate whole files unless explicitly asked. Make the
  smallest change that does the job.
- **Branding is fixed.** Always `INTELORA`, never abbreviated, never restyled.
  The splash sequence is part of the brand and must not be replaced.
- **Stack is fixed.** Frontend: React + TypeScript + Vite + Tailwind +
  shadcn/ui + Framer Motion + Apache ECharts + Lucide + React Router + React
  Query. Backend: Python + FastAPI only. Database: PostgreSQL + TimescaleDB
  via SQLAlchemy and Alembic. No other framework, in either tier.
- **No placeholders.** No `TODO` comments, no stub functions, no fabricated
  data. Everything committed must compile and run.

## Architecture

Six layers, strictly ordered. Every module belongs to exactly one.

```
Device  →  Telemetry  →  Intelligence  →  Business Intelligence  →  Presentation
           (validate,     (6 AI layers)    (cost, efficiency,        (frontend)
            normalise)                      business score)
```

The frontend renders; it never computes business logic. The frontend never
talks to the database — only to FastAPI. No component may know where its data
originated.

### The two-model rule

This is the most important design decision in the platform.

- **Telemetry model** — asset-specific and genuinely divergent. Air
  conditioners report three-way power decomposition and relay state; mobile
  chargers report neither power factor, frequency, nor energy.
- **Business model** — identical for every asset type: health, status, power,
  temperature, energy, cost, efficiency, alerts, business score.

**Dashboard surfaces bind to the business model, never to telemetry shape.**
A new asset type integrates by satisfying the business contract. Missing
values degrade gracefully; they never break layout.

### Health is derived, never reported

Data sources emit measurements only. The **Health Engine**
(`backend/app/services/health_engine.py`) computes the score and state during
normalisation, from the electrical channels, against each asset category's own
envelope. Never accept a health value from a source, and never assign a health
state anywhere else.

Two rules follow, and both have already been violated once:

- **Grade penalties, don't step them.** A model that stays at 100 until a hard
  limit trips makes every asset read exactly 100 and nothing rankable.
- **Judge load-dependent channels against commanded output**, not their own
  rolling mean. Duty-cycled assets swing to near-zero by design; comparing to a
  mean reports every idle charger as a power loss.

### The three-dimension status model

Never collapse these into one field.

| Dimension | Values |
|---|---|
| Health | `healthy` · `warning` · `critical` |
| Operational | `running` · `idle` · `maintenance` |
| Connectivity | `online` · `offline` · `unknown` |

An asset is always all three at once. Alert severity (`critical` · `warning` ·
`information`) is a separate scale that shares colour semantics only.

## Layout

```
frontend/   React presentation layer     backend/    FastAPI, twin, intelligence
database/   init SQL and migrations      docs/       the SSOT
docker/     images and nginx config      assets/     brand source material
```

`frontend/src/` is fixed by the SSOT: `assets components layouts pages hooks
services context types utils animations charts constants styles routes`.
There is no `lib/` — `cn()` lives in `utils/`. Charts and animations are
top-level, not nested under `components/`.

## Design system

Dark is the default theme. Both themes are first-class and must always work.

| Token | Dark | Light |
|---|---|---|
| Background | `#030712` | `#F8FAFC` |
| Surface | `#111827` | `#FFFFFF` |
| Primary | `#00E5FF` | `#2563EB` |

Semantic: healthy `#22C55E`, warning `#F59E0B`, critical `#EF4444` — shifted
darker in light theme for contrast. **Never hardcode a colour**; always use a
token. Light theme is not dark theme with swapped colours: its depth comes
from elevation and crisp borders, not glow and blur.

Fixed dimensions: navbar `72px`, sidebar `280px` (collapsed `76px`), card
radius `20px`, spacing on an 8px grid.

### Effect hierarchy

Do not apply premium effects uniformly — that is what makes a UI look like a
template. Tier them:

| Level | Treatment |
|---|---|
| Primary (hero verdict, KPI cards, asset cards) | full: lift, glow, depth, count-up |
| Secondary (charts, summary tiles, nav) | subtle: fade, slide |
| Tables and forms | minimal: colour and opacity transitions only |

Honour `prefers-reduced-motion` everywhere, including the splash.

**The dashboard must breathe.** Generous whitespace, vertical sections, at
most two charts per row. Never crowd a page. The Cockpit carries executive
information only; detail belongs in the modules it links to.

## Time-series storage

120 devices at 1 Hz is ~10.4 million rows a day. Telemetry is read through
three tiers — raw hypertable up to ~6 hours, `telemetry_1m` up to ~3 days,
`telemetry_1h` beyond — selected by window in
`backend/app/services/history_service.py`. Never query the raw hypertable for a
long range. Nothing is ever deleted; old chunks compress instead.

## Current state

Phases 1 and 2 are complete: frontend, backend, database, a 120-asset Digital
Twin with battery and thermostat physics, the Health Engine, six intelligence
layers, storage tiers and live WebSocket streaming, running together.

The platform observes and advises; it does not control devices. Keep the seam
open for future actuation, but do not implement it.

**The UI is frozen.** Phase 2 was backend work. Do not change layout, CSS,
animations, branding, the splash screen, navigation or responsive behaviour
without explicit instruction.

Run with `docker compose up --build`, or see [`README.md`](README.md) for
local development.
