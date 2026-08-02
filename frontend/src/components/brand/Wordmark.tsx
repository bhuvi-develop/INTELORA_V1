import { cn } from '@/utils/cn'

/**
 * The INTELORA wordmark.
 *
 * The word *is* the logo, so this is the single most brand-critical component
 * in the platform. It renders in two forms:
 *
 * - `flat` — the navbar and sidebar lockup.
 * - `dimensional` — the splash sequence: extruded, metallic, with a glass
 *   reflection and a light sweep.
 *
 * The extrusion is built from stacked copies of the text offset along a
 * diagonal, each progressively darker, with CSS perspective applied to the
 * container. That is deliberately not WebGL — the SSOT specifies CSS
 * perspective and Framer Motion, and it means the brand moment costs no
 * additional bundle weight and paints on the very first frame.
 */

interface WordmarkProps {
  variant?: 'flat' | 'dimensional'
  className?: string
  /** Tailwind text-size class. Controls everything else proportionally. */
  size?: string
}

/** Depth layers for the extrusion. More reads as heavy; fewer as thin. */
const EXTRUSION_LAYERS = 7

export function Wordmark({
  variant = 'flat',
  className,
  size = 'text-xl',
}: WordmarkProps) {
  if (variant === 'flat') {
    return (
      <span
        className={cn(
          'font-display font-bold tracking-[0.2em] text-foreground select-none',
          size,
          className,
        )}
      >
        INTELORA
      </span>
    )
  }

  return (
    <div
      className={cn('relative select-none', className)}
      style={{ perspective: '900px', perspectiveOrigin: '50% 45%' }}
    >
      <div
        className="relative"
        style={{
          transformStyle: 'preserve-3d',
          transform: 'rotateX(9deg) rotateY(-3deg)',
        }}
      >
        {/* Extruded depth. Rendered behind the face, each layer stepped along
            the light direction and dimmed, which is what gives the letters
            physical thickness rather than a drop shadow. */}
        {Array.from({ length: EXTRUSION_LAYERS }).map((_, index) => {
          const depth = index + 1
          const fade = 1 - depth / (EXTRUSION_LAYERS + 3)
          return (
            <span
              key={depth}
              aria-hidden
              className={cn(
                'absolute inset-0 font-display font-extrabold tracking-[0.16em] whitespace-nowrap',
                size,
              )}
              style={{
                transform: `translate3d(${depth * 1.15}px, ${depth * 1.15}px, ${-depth * 2}px)`,
                color: `rgb(8 22 34 / ${0.9 * fade})`,
                WebkitTextStroke: '0.4px rgb(0 60 74 / 0.35)',
              }}
            >
              INTELORA
            </span>
          )
        })}

        {/* The face: a brushed-metal gradient with a cyan cast at the edges. */}
        <span
          className={cn(
            'relative block font-display font-extrabold tracking-[0.16em] whitespace-nowrap',
            size,
          )}
          style={{
            backgroundImage:
              'linear-gradient(168deg, #ffffff 2%, #cfefff 20%, #7fdcf0 38%, #ffffff 52%, #57c9e6 68%, #b9e9f7 84%, #ffffff 98%)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
            filter: 'drop-shadow(0 0 26px rgb(0 229 255 / 0.45))',
          }}
        >
          INTELORA
        </span>

        {/* Specular highlight along the upper edge of the glyphs. */}
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-0 font-display font-extrabold tracking-[0.16em] whitespace-nowrap',
            size,
          )}
          style={{
            backgroundImage:
              'linear-gradient(to bottom, rgb(255 255 255 / 0.95) 0%, rgb(255 255 255 / 0) 44%)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
          }}
        >
          INTELORA
        </span>

        {/* Light sweep. A narrow band travelling across the face, masked to the
            glyphs so it reads as light moving over metal rather than a bar
            crossing the screen. */}
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute inset-0 overflow-hidden font-display font-extrabold tracking-[0.16em] whitespace-nowrap',
            size,
          )}
          style={{
            WebkitMaskImage:
              'linear-gradient(to right, transparent, #000 20%, #000 80%, transparent)',
            maskImage:
              'linear-gradient(to right, transparent, #000 20%, #000 80%, transparent)',
          }}
        >
          <span
            className="absolute inset-y-0 -left-1/3 w-1/3"
            style={{
              background:
                'linear-gradient(100deg, transparent, rgb(255 255 255 / 0.55), transparent)',
              animation: 'sweep 3.2s ease-in-out 0.9s infinite',
            }}
          />
        </span>
      </div>

      {/* Glass reflection: a mirrored copy fading downward, as if the wordmark
          were resting on a polished surface. */}
      <div
        aria-hidden
        className="pointer-events-none absolute top-full left-0 w-full"
        style={{
          transform: 'scaleY(-1)',
          transformOrigin: 'top',
          opacity: 0.16,
          WebkitMaskImage: 'linear-gradient(to bottom, #000, transparent 62%)',
          maskImage: 'linear-gradient(to bottom, #000, transparent 62%)',
          filter: 'blur(1.4px)',
        }}
      >
        <span
          className={cn(
            'block font-display font-extrabold tracking-[0.16em] whitespace-nowrap',
            size,
          )}
          style={{
            backgroundImage:
              'linear-gradient(168deg, #ffffff, #7fdcf0 45%, #ffffff)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
          }}
        >
          INTELORA
        </span>
      </div>
    </div>
  )
}

/**
 * The compact mark for the collapsed sidebar and favicon lockup.
 *
 * A hexagonal aperture with a signal core — an abstraction of a monitored node
 * rather than a literal device, so it stays valid as the platform grows beyond
 * chargers and air conditioners.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      className={cn('size-9', className)}
      aria-hidden
    >
      <defs>
        <linearGradient id="intelora-mark" x1="6" y1="4" x2="34" y2="36">
          <stop offset="0%" stopColor="var(--intelora-primary)" />
          <stop offset="100%" stopColor="var(--intelora-primary)" stopOpacity="0.35" />
        </linearGradient>
      </defs>
      <path
        d="M20 2.8 34.6 11v18L20 37.2 5.4 29V11L20 2.8Z"
        stroke="url(#intelora-mark)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M20 11.5v9.2l6.4 3.7"
        stroke="var(--intelora-primary)"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="20" r="2.6" fill="var(--intelora-primary)" />
    </svg>
  )
}
