# INTELORA Brand System

Source material for the INTELORA identity. Runtime assets live in
`frontend/public/`; this directory is the reference the platform is built
against.

---

## The name

**INTELORA.** Never abbreviated, never hyphenated, never set in lowercase in
product surfaces. The wordmark *is* the logo — there is no separate logotype to
pair it with.

## The wordmark

Implemented in [`frontend/src/components/brand/Wordmark.tsx`](../../frontend/src/components/brand/Wordmark.tsx),
in two forms:

| Variant | Where | Treatment |
| --- | --- | --- |
| `flat` | Navigation bar, sidebar | Sora, bold, `0.2em` tracking, single colour |
| `dimensional` | Splash sequence only | Extruded, metallic gradient, specular highlight, light sweep, glass reflection |

The dimensional form is built from stacked text layers under CSS perspective —
not WebGL. That is a specification requirement, and it means the brand moment
paints on the first frame and adds nothing to the bundle.

### Safe area

Clear space around the wordmark is **half the cap height** on every side. No
other element — icon, rule, badge or edge — may enter it.

```
┌─────────────────────────────┐
│         ½ cap height        │
│   ┌─────────────────────┐   │
│ ½ │      INTELORA       │ ½ │
│   └─────────────────────┘   │
│         ½ cap height        │
└─────────────────────────────┘
```

### Minimum size

`14px` cap height flat, `40px` dimensional. Below the dimensional minimum the
extrusion muddies and the flat variant should be used instead.

## The mark

A hexagonal aperture with a signal core, in
[`Wordmark.tsx`](../../frontend/src/components/brand/Wordmark.tsx) as `LogoMark`
and as SVG in `frontend/public/favicon.svg` and `app-icon.svg`.

Deliberately abstract — it represents a monitored node, not a charger or an air
conditioner, so it stays valid as the platform grows into pumps, motors, UPS
systems and solar.

## Colour

| Token | Dark | Light |
| --- | --- | --- |
| Background | `#030712` | `#F8FAFC` |
| Surface | `#111827` | `#FFFFFF` |
| Primary | `#00E5FF` | `#2563EB` |
| Healthy | `#22C55E` | `#16A34A` |
| Warning | `#F59E0B` | `#D97706` |
| Critical | `#EF4444` | `#DC2626` |

**Primary changes between themes.** Nothing may hardcode cyan — every accent
resolves through a token, or it will be wrong in half the product.

The splash screen is the one deliberate exception: it is locked to `#030712`
with the cyan glow in both themes, because the brand moment should be identical
for every viewer.

## Typography

**Sora** — display, the wordmark, headings, KPI numerals.
**Inter** — interface and body text.

Tabular figures on every numeral that sits in a column or animates, so digits do
not jitter as values change.

## Spacing

8px grid throughout: 8, 16, 24, 32, 40, 48, 64. Navbar `72px`, sidebar `280px`
(collapsed `76px`), card radius `20px`.

## Motion

The startup sequence runs 4–5 seconds: particles fade in, the wordmark resolves
from blur, light sweeps across it, the camera pushes in, and the dashboard —
already mounted behind — is revealed as the logo clears.

No loading text, no percentage, no progress bar, no spinner. The logo is the
loading experience.

## Usage rules

**Do**

- Use the wordmark as supplied, in Sora
- Keep the safe area clear
- Resolve every colour through a design token
- Honour `prefers-reduced-motion`, including in the splash

**Do not**

- Abbreviate, translate or transliterate the name
- Recolour, outline, rotate, skew or add effects to the wordmark
- Place the dimensional variant on a light background
- Replace the startup sequence
- Pair the mark with a second logotype
