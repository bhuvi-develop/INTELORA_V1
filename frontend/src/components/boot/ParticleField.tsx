import { useEffect, useMemo, useRef } from 'react'

import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

/**
 * Ambient particle field for the splash.
 *
 * The brand specification asks for particles that are "very soft, almost
 * invisible" and a screen that "should never look busy" — so this is
 * deliberately restrained: few particles, low opacity, slow drift.
 *
 * Rendered to a canvas rather than as DOM nodes. Sixty animated elements each
 * with their own compositor layer is a measurable cost at the exact moment the
 * application is also mounting the dashboard behind the splash; one canvas is
 * a single layer and leaves the main thread free for React.
 */

interface Particle {
  x: number
  y: number
  radius: number
  drift: number
  speed: number
  opacity: number
  phase: number
}

const PARTICLE_COUNT = 46

export function ParticleField({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const frameRef = useRef<number | null>(null)
  const reducedMotion = usePrefersReducedMotion()

  // Positions are generated once. Regenerating them on re-render would make
  // the field visibly jump.
  const seeds = useMemo<Particle[]>(
    () =>
      Array.from({ length: PARTICLE_COUNT }, () => ({
        x: Math.random(),
        y: Math.random(),
        radius: 0.6 + Math.random() * 1.7,
        drift: (Math.random() - 0.5) * 0.00008,
        speed: 0.000018 + Math.random() * 0.000042,
        opacity: 0.12 + Math.random() * 0.3,
        phase: Math.random() * Math.PI * 2,
      })),
    [],
  )

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const context = canvas.getContext('2d')
    if (!context) return

    let width = 0
    let height = 0
    const ratio = Math.min(window.devicePixelRatio || 1, 2)

    const resize = () => {
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = Math.floor(width * ratio)
      canvas.height = Math.floor(height * ratio)
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
    }

    resize()
    window.addEventListener('resize', resize)

    const draw = (elapsed: number) => {
      context.clearRect(0, 0, width, height)

      for (const particle of seeds) {
        // Slow vertical rise with a gentle horizontal sway, wrapping at the
        // edges so the field never empties.
        const y = (particle.y - elapsed * particle.speed) % 1
        const wrappedY = y < 0 ? y + 1 : y
        const sway = Math.sin(elapsed * 0.0004 + particle.phase) * 14
        const x = ((particle.x + elapsed * particle.drift) % 1 + 1) % 1

        const px = x * width + sway
        const py = wrappedY * height

        const glow = context.createRadialGradient(px, py, 0, px, py, particle.radius * 5)
        glow.addColorStop(0, `rgba(0, 229, 255, ${particle.opacity})`)
        glow.addColorStop(1, 'rgba(0, 229, 255, 0)')

        context.fillStyle = glow
        context.beginPath()
        context.arc(px, py, particle.radius * 5, 0, Math.PI * 2)
        context.fill()

        context.fillStyle = `rgba(226, 245, 255, ${particle.opacity * 0.85})`
        context.beginPath()
        context.arc(px, py, particle.radius, 0, Math.PI * 2)
        context.fill()
      }
    }

    if (reducedMotion) {
      // A single static frame: the field is still present, simply not moving.
      draw(0)
      return () => window.removeEventListener('resize', resize)
    }

    const start = performance.now()
    const loop = (now: number) => {
      draw(now - start)
      frameRef.current = requestAnimationFrame(loop)
    }
    frameRef.current = requestAnimationFrame(loop)

    return () => {
      window.removeEventListener('resize', resize)
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    }
  }, [seeds, reducedMotion])

  return <canvas ref={canvasRef} className={className} aria-hidden />
}
