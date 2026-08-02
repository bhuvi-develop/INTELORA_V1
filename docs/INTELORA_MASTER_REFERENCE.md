# INTELORA — Master Reference

**Unified AIOT Intelligence Platform · Single Source of Truth · Version 1.1**

This document is the authority for the INTELORA platform. Every developer, AI
session, designer, and future contributor must follow it. If generated code
conflicts with this document, the document is correct.

**Precedence:** this document → the Development Constitution (§12) → later
sections over earlier → more specific over more general.

---

## Table of contents

1. [Vision and business objective](#1-vision-and-business-objective)
2. [Product principles](#2-product-principles)
3. [Brand identity](#3-brand-identity)
4. [Layered architecture](#4-layered-architecture)
5. [Assets and the two-model rule](#5-assets-and-the-two-model-rule)
6. [The status model](#6-the-status-model)
7. [Intelligence layers](#7-intelligence-layers)
8. [Data architecture](#8-data-architecture)
9. [API architecture](#9-api-architecture)
10. [Design system](#10-design-system)
11. [Screen blueprint](#11-screen-blueprint)
12. [Development constitution](#12-development-constitution)
13. [Repository layout](#13-repository-layout)
14. [Roadmap](#14-roadmap)

---

## 1. Vision and business objective

INTELORA transforms raw electrical telemetry into business decisions. Unlike
traditional monitoring software it unifies artificial intelligence, asset
intelligence, predictive analytics, operational intelligence and business
intelligence into one platform, on one scalable architecture.

The value chain the platform exists to serve:

```
Raw electrical data → Device intelligence → Business intelligence → Executive decision
```

INTELORA answers questions such as: Which asset is unhealthy? Which is likely
to fail? What maintenance should be performed? Which asset costs the most?
Which building consumes the most energy? What is today's operational
efficiency? Which assets need immediate attention?

**Target industries:** commercial buildings, industrial plants, corporate
offices, hospitals, educational institutions, manufacturing, data centres,
energy companies, facility management, smart buildings.

**INTELORA is an observation platform.** It observes, analyses, generates
intelligence, and recommends actions. It does **not** control devices. The
architecture must remain open to future actuation (relay operations, remote
commands) without implementing it now.

---

## 2. Product principles

1. **Everything begins with data.** Without telemetry there is no intelligence.
2. **The system explains** what happened, why it happened, what will happen,
   and what should be done.
3. **One platform for every asset.** Adding an asset type must never require
   rewriting the platform.
4. **Device intelligence and business intelligence stay separated.**
5. **The interface communicates fast.** A user understands system status within
   five seconds of opening the dashboard.
6. **Every decision prioritises** scalability, maintainability, readability and
   performance.

---

## 3. Brand identity

The brand name is **INTELORA**. Never abbreviate it, never restyle the logo,
never substitute alternative branding. The wordmark *is* the logo.

**Personality:** professional, minimal, premium, intelligent, reliable, modern,
enterprise, global, elegant.

### Startup experience

The splash screen displays **only** the word INTELORA. No subtitle, no loading
text, no percentage, no progress bar, no spinner. The logo itself is the
loading experience.

**Sequence** (4–5 seconds total):

```
Dark screen → particles fade in → INTELORA appears → letters extrude into 3D
→ light sweeps across the logo → logo floats → camera zooms slightly
→ dashboard fades in behind → logo disappears → dashboard becomes interactive
```

**Treatment:** background `#030712`, 3D extruded text via CSS perspective and
Framer Motion (never WebGL), glass material, metallic reflection, soft cyan
glow, depth, very soft almost-invisible floating particles. No gaming effects,
no RGB, no fire.

The splash plays on application launch and on browser refresh. It must **not**
replay during in-app navigation. The dashboard mounts behind it; interaction is
suppressed until the sequence completes.

### Brand system

The brand includes logo, favicon, application icon, colours, typography,
spacing rules, iconography, logo safe area, usage rules and the startup
animation. All are consistent on every page.

---

## 4. Layered architecture

```
Device Layer
    ↓
Telemetry Layer        ingest · validate · normalise · store · broadcast
    ↓
Intelligence Layer     the six AI layers
    ↓
Business Intelligence  cost · efficiency · business score · cross-layer rollup
    ↓
Presentation Layer     the INTELORA frontend
```

Every module belongs to exactly one layer and must not violate the separation.

- All assets pass through one **common telemetry pipeline** before entering the
  intelligence layers.
- **No dashboard logic may depend on asset-specific implementations.**
- The frontend renders; it never computes business logic.
- The frontend never touches the database. `Frontend → FastAPI → Database`.
- The dashboard must never know where data originated.

### Data sources

Real MIKOS sensor · Digital Twin Engine · simulator · REST API · future MQTT.
Every source passes through the same telemetry service and satisfies the same
contract. The Digital Twin Engine is the primary source during development
until real sensors are connected.

### Future AI capability

The architecture must accommodate machine learning, deep learning, large
language models, digital twin analytics, forecasting, optimisation, root cause
analysis and recommendation engines without redesign.

---

## 5. Assets and the two-model rule

**Version 1 assets:** laptop charger, mobile charger, air conditioner.

**Future assets** must integrate without architectural change: water pumps,
water heaters, compressors, motors, UPS systems, solar systems, generators,
HVAC, industrial machines.

### Telemetry model — asset-specific

The three asset types genuinely differ:

| Channel | Laptop charger | Mobile charger | Air conditioner |
|---|---|---|---|
| Voltage, current | ✓ | ✓ | ✓ |
| Power | single | single | active / reactive / apparent |
| Temperature | ✓ | ✓ | ✓ |
| Power factor | ✓ | — | ✓ |
| Frequency | ✓ | — | ✓ |
| Energy | ✓ | — | ✓ |
| Relay status, operations | — | — | ✓ |
| Type-specific | — | charging status | — |

Each asset type declares its capabilities in a registry. Nothing is hardcoded.

### Business model — unified

Every asset, regardless of type, exposes exactly this:

```
health · status · power · temperature · energy · cost · efficiency
· alerts · business score
```

**Dashboard surfaces bind to the business model, never to telemetry shape.**
Where a device does not naturally expose a value, the system handles its
absence gracefully without breaking layout or architecture. Cost, efficiency
and business score are Business Intelligence Layer outputs, not telemetry.

### Fault taxonomies

Asset-specific, declared alongside capabilities.

- **Laptop charger:** adapter failure, overheating, voltage drop, power loss
- **Mobile charger:** cable failure, fast charging, overheating, power drop
- **Air conditioner:** high current, voltage drop, compressor wear, dirty
  filter, overheating, power loss

---

## 6. The status model

Three **independent** dimensions. Never collapse them into one field.

| Dimension | Values |
|---|---|
| **Health state** | `healthy` · `warning` · `critical` |
| **Operational state** | `running` · `idle` · `maintenance` |
| **Connectivity state** | `online` · `offline` · `unknown` |

An asset is always all three simultaneously — for example *running · warning ·
online*. Health is derived from the numeric health score.

*Failure* and *recovery* are Digital Twin **scenarios**, not asset states; they
manifest as transitions into and out of `critical`.

**Alert severity** is a separate scale: `critical` · `warning` · `information`.
**Alert lifecycle** is separate again: `active` → `acknowledged` → `resolved`.
Severity and lifecycle are orthogonal — an alert can be critical *and*
acknowledged.

---

## 6a. The Health Engine

Health is **computed by the platform, never reported by a source**. A physical
charger has no opinion about its own condition; it reports volts, amps, watts
and degrees. If a source could declare its health, the platform would be
displaying that source's conclusion rather than reaching one, and every
intelligence layer above would inherit the assertion instead of the evidence.

The engine scores every reading during normalisation, as a weighted penalty
model over six channels — temperature, voltage, current, power, power factor,
frequency — each judged against **the asset category's own envelope**. A
charger at 55 °C is in trouble; a compressor at 55 °C is working normally.

Two properties matter:

- **Penalties are graded, not binary.** A gentle slope begins well before each
  hard limit. A model that holds at 100 until a threshold trips produces a
  fleet where every asset reads exactly 100 and nothing can be ranked or
  watched trending — which is most of what a health index is for.
- **Load-dependent channels are judged against commanded output**, not against
  their own rolling average. A duty-cycled asset swings from near-zero to full
  by design: an unplugged charger, one tapering towards a full battery, and an
  air conditioner between compressor cycles all sit far below their mean while
  behaving perfectly.

The same rule governs anomaly detection. Statistical z-score detection applies
only to channels with a stable expected value (voltage, temperature, power
factor, frequency); power and current are checked against commanded load
instead.

The three health states are thresholds on the resulting score — `critical`
below 52, `warning` below 78 — and are assigned nowhere else in the platform.

## 7. Intelligence layers

Six layers. Each is independent, each enriches the previous, none duplicates or
overwrites another's work.

| # | Layer | Inputs | Outputs |
|---|---|---|---|
| 1 | **Anomaly detection** | voltage, current, power, temperature, frequency, power factor, relay status | anomaly score, severity, fault type, confidence, **alert** |
| 2 | **Predictive maintenance** | telemetry, anomaly results, historical trends | failure probability, remaining useful life, predicted failure date, confidence, risk level |
| 3 | **Preventive maintenance** | predictive results, operating hours, maintenance history | maintenance due, service schedule, priority, window |
| 4 | **Prescriptive optimisation** | predictive, preventive, business rules | recommended action, energy saving, **cost saving**, operational advice |
| 5 | **Asset performance management** | all prior layers, telemetry | health index, health score, MTBF, MTTR, availability, reliability, maintainability, criticality, lifecycle stage, cost exposure, maintenance cost, maintenance ROI, risk score, asset ranking, repair-vs-replace, business value |
| 6 | **Overall equipment efficiency** | availability, performance, quality, asset health | OEE and factors, rolled up by department, building, fleet, enterprise |

### Page mapping

| Page | Layer |
|---|---|
| Enterprise Cockpit | all layers |
| Anomaly | 1 |
| Predictive | 2 |
| APM | 5 |
| OEE | 6 |
| Alerts | 1 |
| Reports | all layers |

**Layers 3 and 4 have no page of their own.** They surface as outputs within
other screens: Layer 3 answers "which devices need maintenance" on the
Predictive and APM pages; Layer 4 is the source of the Cockpit's *Today's cost
saving* KPI.

### Naming caution

`Quality` means two unrelated things. Keep them distinct in code:
**data quality** (a telemetry field) and **OEE quality** (a Layer 6 factor).

---

## 8. Data architecture

**PostgreSQL** for business data, **TimescaleDB** for telemetry. SQLAlchemy
ORM, Alembic migrations, Pydantic validation.

**Hierarchy:** organisation → location → asset group → asset. One organisation
must never access another's data.

**Core tables:** `organizations`, `locations`, `asset_groups`, `assets`,
`telemetry`, `anomaly_results`, `predictive_results`, `preventive_results`,
`prescriptive_results`, `apm_results`, `oee_results`, `alerts`, `users`,
`roles`, `notifications`, `maintenance_logs`, `audit_logs`, `system_settings`.

**Telemetry fields.** Common to every category: timestamp, asset id, voltage,
current, power, energy, temperature, frequency, power factor, **runtime
hours**, **load percent**, source, quality, created time. Category-specific:
relay status and operations plus **indoor temperature** for air conditioners;
**charging state**, **battery percent**, **charge cycles** and **fast charging**
for the two charger categories.

**Health is never stored by a source.** Data sources report measurements only.
The Health Engine (§9a) derives the score and state during normalisation, and
those derived fields are written alongside the reading.

### Storage tiers

At 120 devices and 1 Hz the platform writes roughly 10.4 million rows a day.
Raw retention is correct for writes and unusable for long reads, so telemetry
is served through three tiers:

| Window | Source |
|---|---|
| Up to ~6 hours | raw hypertable |
| Up to ~3 days | `telemetry_1m` continuous aggregate |
| Beyond that | `telemetry_1h` continuous aggregate |

Chunks are two hours wide and compress after six, segmented by `asset_id`.
Nothing is discarded — every packet remains in the raw hypertable. A query
whose tier has not yet materialised falls through to the next finer one, within
a bounded row budget, so a young deployment never shows an empty chart while
data exists.

**Source types:** `REAL_SENSOR`, `SIMULATOR`, `MOCK_LIVE`, `REST_API`, `MQTT`.

**Integrity chain — no orphan records:**

```
telemetry → references an asset
AI result → references telemetry
alert     → references an AI result
```

This makes alert-to-evidence drill-through a structural capability: every alert
traces back through its AI result to the telemetry window that produced it.

**Roles:** admin, executive, facility manager, maintenance engineer, operator,
viewer.

**Retention is unlimited.** No component may assume a bounded dataset:
pagination and explicit time ranges are mandatory, never optional.

---

## 9. API architecture

REST-first, versioned under `/api/v1/`, with real-time updates over WebSocket.
Every endpoint is RESTful, stateless, typed and documented via OpenAPI.

### Response envelope

```json
{ "status": true, "message": "Success", "timestamp": "...", "data": {}, "errors": [] }
```

`status` is a boolean **inside the body** — a `200` response can carry
`status: false`. Clients must unwrap the envelope and treat `status: false` as
a failure, or errors will surface as empty data. Error responses additionally
carry an error code. Stack traces are never returned to the frontend.

### Endpoints

| Group | Endpoints |
|---|---|
| Dashboard | `GET /dashboard/overview` `/kpi` `/charts` `/recent` |
| Assets | `GET /assets` `GET /assets/{id}` `POST` `PUT` `DELETE` |
| Telemetry | `GET /telemetry` `/telemetry/live` `/telemetry/history` `/telemetry/ranges` `POST /telemetry` |
| Digital Twin | `POST /twin/start` `/stop` `/reset` · `GET /twin/status` |
| Anomaly | `GET /anomaly` `GET /anomaly/{assetId}` `POST /anomaly/analyze` |
| Predictive | `GET /predictive` `POST /predictive/run` |
| Preventive | `GET /preventive` `POST /preventive/generate` |
| Prescriptive | `GET /prescriptive` `POST /prescriptive/recommend` |
| APM | `GET /apm` `/apm/assets` `/apm/health` `/apm/ranking` |
| OEE | `GET /oee` `/oee/overview` `/oee/history` |
| Alerts | `GET /alerts` `GET /alerts/{id}` `PUT /alerts/{id}` `DELETE /alerts/{id}` |
| Reports | `GET /reports` `POST /reports/export` |
| Settings | `GET /settings` `PUT /settings` |

### WebSocket

A **single multiplexed connection** at `/ws/live` carries live KPIs, charts,
telemetry, alerts and device status. Not one socket per feature. The frontend
never polls.

Because telemetry is generated at 1 Hz per device, the client must coalesce
inbound messages and flush on an animation frame; charts update by incremental
append rather than full option replacement.

### Security

Authentication is a future phase: JWT, OAuth2, refresh tokens, role-based
access control. The API client is built with an interceptor chain so this slots
in without touching call sites. Secrets live in `.env`, never in code — and
never in a `VITE_*` variable, which ships to the browser.

---

## 10. Design system

### Colour

| Token | Dark | Light |
|---|---|---|
| Background | `#030712` | `#F8FAFC` |
| Surface | `#111827` | `#FFFFFF` |
| Primary | `#00E5FF` | `#2563EB` |
| Healthy | `#22C55E` | `#16A34A` |
| Warning | `#F59E0B` | `#D97706` |
| Critical | `#EF4444` | `#DC2626` |

**Dark is the default theme.** Both are first-class; switching is instant with
no reload and the preference persists. Never hardcode a colour — always use a
token, so that a theme-dependent primary resolves correctly.

Light theme is **not** dark theme with swapped colours. Glassmorphism and glow
do not survive a near-white background; light theme takes its premium quality
from elevation, crisp borders and layered soft shadows.

### Typography

**Sora** for display, the wordmark and KPI numerals. **Inter** for UI and body
text. Tabular figures for all numerals in KPIs and tables.

### Spacing and dimension

8px grid — 8, 16, 24, 32, 40, 48, 64. No arbitrary values.
Navbar `72px` · sidebar `280px` (collapsed `76px`) · card radius `20px`.

### Effect hierarchy

Premium effects are **tiered, never uniform**. Applying everything everywhere
is what makes an interface look like a template.

| Level | Applies to | Treatment |
|---|---|---|
| Primary | hero verdict, KPI cards, asset cards | full: lift, glow, depth, count-up |
| Secondary | charts, summary tiles, navigation | subtle: fade, slide |
| Minimal | tables, forms | colour and opacity transitions only |

Honour `prefers-reduced-motion` throughout, including the splash.

### Layout philosophy

**The dashboard must breathe.** Generous whitespace, large spacing, clear
hierarchy, professional alignment. Vertical sections the user scrolls through
naturally, each fading in. Never place fifteen charts, twenty KPI cards or
fifty tables on one page. **At most two charts per row.** The user must never
feel overwhelmed.

### Components

Icons are **Lucide only** — never emoji, never a second icon pack.
Charts are **Apache ECharts only**, animated, responsive, interactive.
Loading is **skeleton only** — never a spinner.
Empty states carry an illustration, a meaningful message and a call to action.
Error states are friendly and offer retry; raw errors are never shown.
Buttons: gradient, glow, hover lift, ripple, rounded. Never a bare HTML button.
Inputs: rounded, focus glow, soft border, animated label.

### Accessibility

Keyboard navigation, visible focus states, semantic HTML, screen-reader
support, adequate contrast in both themes.

### Reference points

Apple, Apple VisionOS, Tesla, Azure Portal, Microsoft Fabric, Datadog, Grafana
Cloud, Stripe, Linear, Notion, Siemens, Schneider Electric, ABB.
**Never** Bootstrap admin, AdminLTE, Material Dashboard, CoreUI, or any
template aesthetic.

---

## 11. Screen blueprint

### Shell

Every page: navbar, sidebar, breadcrumb, page title, content, footer,
responsive layout.

**Navbar** (72px, fixed, glass, blurred): logo, global search, theme toggle,
notifications, profile, current time, organisation name, quick actions.

**Sidebar** (280px, collapsible, glass, hover glow, active indicator):
Enterprise Cockpit · Anomaly Detection · Predictive Maintenance · Overall
Equipment Efficiency · Asset Performance Management · Alerts · Reports ·
Settings · Future Modules.

### Enterprise Cockpit — Mission Control

The landing page. It aggregates every intelligence layer into one executive
screen and carries **executive information only**; detail lives in the modules
it links to.

| Section | Content |
|---|---|
| 1 | Welcome — organisation, system status verdict, live indicator, date, time |
| 2 | KPI cards — total assets, healthy, warning, critical, average health, average OEE, today's energy, today's cost saving, active alerts |
| 3 | Asset overview — three premium cards on the unified business model |
| 4 | Intelligence summary — anomaly, predictive, APM and OEE headline verdicts |
| 5 | Charts — a curated executive set, at most two per row |
| 6 | Alerts summary — recent alerts with severity breakdown |
| 7 | Activity feed — live and animated |

### Everything meaningful is clickable

Every KPI card is an entry point.

```
KPI card    → its module or a filtered asset view
Asset card  → that asset type's module
Chart       → expanded analytics
Alert       → alert detail
```

### Module pages

**Anomaly** — today's anomalies, critical, warning, resolved; anomaly timeline,
heatmap, distribution; recent anomalies table filtered by severity, asset, time.

**Predictive** — failure probability, remaining useful life, confidence;
prediction, failure and health trends; asset table. Carries Layer 3 maintenance
output.

**OEE** — large OEE gauge with availability, performance and quality; trend,
historical comparison, department and asset comparison.

**APM** — the most premium page. Health, risk, criticality, MTBF, MTTR,
lifecycle, cost exposure, maintenance cost, availability, reliability; radar,
treemap, health trend, risk matrix, asset ranking. Reliability-engineering
metrics and business metrics are visually separated, per principle 4.

**Alerts** — professional notification centre. Severity and lifecycle filters,
search, acknowledge / resolve / assign, detail route.

**Reports** — energy, health, maintenance and OEE reports; export to PDF, Excel
and CSV.

**Settings** — theme, language, organisation, notifications, preferences,
profile. Reserves extensible space for asset management, user management and
Digital Twin control.

### Chart inventory

Line, area, bar, gauge, donut/pie, treemap, heatmap, radar, timeline, risk
matrix, sunburst. Each is a reusable primitive; pages compose them.

---

## 12. Development constitution

### Ownership

The engineer working on INTELORA is lead architect, lead designer, lead
frontend engineer, lead backend engineer and database architect, and is
responsible for consistency across the whole platform.

### Rules

- **Extend, never destroy.** Never delete files, rename folders, replace the
  architecture, rewrite components, or break navigation, styling, animation or
  responsiveness. Never regenerate a whole file unless asked.
- **When modifying:** read existing files, understand the architecture, change
  the minimum, and preserve style, naming, design and responsiveness.
- **When creating:** explain why the file exists, where it belongs, how it
  connects, its dependencies and its usage.
- **No placeholder code, no TODO comments, no fake backends, no dummy
  architecture.** Everything must compile and run.
- **Consistency.** One design system across every page. No page feels
  different.
- **Code quality.** Small, readable, reusable, typed, documented functions. No
  long functions, no duplicated logic.
- **Performance.** Lazy loading, code splitting, memoisation, no unnecessary
  re-renders. ECharts must be tree-shaken — never import the full bundle.
- **Python standards.** PEP 8, type hints, docstrings, async, modular services,
  dependency injection where appropriate.
- **Git.** Small commits, meaningful messages, never commit broken code.
- **Testing.** A future phase, but the architecture must permit unit,
  integration, API and UI testing — which means logic stays out of components.

### Module development order

Enterprise Cockpit → Digital Twin Engine → Telemetry → Anomaly → Predictive →
Preventive → Prescriptive → APM → OEE → Alerts → Reports.

Never skip architecture. Never start a phase before the current one is
complete.

---

## 13. Repository layout

```
INTELORA/
├── frontend/     Presentation Layer (React)
├── backend/      Telemetry, Intelligence and BI layers (FastAPI)
├── database/     Extension bootstrap and migration SQL
├── docs/         This document
├── docker/       Images, nginx config, runtime entrypoints
└── assets/       Brand source material
```

`frontend/src/` is fixed:

```
assets  components  layouts  pages  hooks  services  context  types
utils   animations  charts   constants  styles  routes
```

There is no `lib/` — `cn()` lives in `utils/`. `charts/` and `animations/` are
top-level, not nested under `components/`. Never create folders outside this
structure.

`backend/app/` mirrors the layer model:

```
config  database  models  schemas  routers  services
digital_twin  intelligence  websocket  core  utils
```

---

## 14. Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Branding, design system, frontend, backend, database, Digital Twin Engine, live dashboard | **Complete** |
| 2 | 120-asset fleet, battery and thermostat physics, Health Engine, storage tiers, named history ranges | **Complete** |
| 3 | Authentication, RBAC, multi-tenant enforcement | Planned |
| 3 | Anomaly detection models | Planned |
| 4 | Predictive maintenance models | Planned |
| 5 | Preventive maintenance | Planned |
| 6 | Prescriptive optimisation | Planned |
| 7 | Asset performance management depth | Planned |
| 8 | OEE depth and rollups | Planned |
| 9 | Alerts, reports, notifications | Planned |
| 10 | MQTT, real MIKOS sensors, deployment | Planned |

Phase 1 as delivered merges what earlier drafts sequenced as separate frontend,
backend, twin and telemetry phases, at the project owner's direction.

---

## Final principle

INTELORA is not a dashboard. It is an Enterprise AIOT Intelligence Platform.
Every design decision, every API, every table, every animation, every
component, every chart, every page and every module must reinforce that.
