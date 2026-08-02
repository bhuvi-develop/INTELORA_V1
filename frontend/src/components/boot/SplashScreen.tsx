import { AnimatePresence, motion } from 'framer-motion'

import { splash } from '@/animations/variants'
import { Wordmark } from '@/components/brand/Wordmark'
import { useBoot } from '@/hooks/useAppContext'
import { ParticleField } from './ParticleField'

/**
 * The INTELORA startup sequence.
 *
 * Displays the wordmark and nothing else — no subtitle, no percentage, no
 * progress bar, no spinner. The logo is the loading experience.
 *
 * It is an **overlay, not a route gate**. The dashboard mounts, fetches and
 * paints underneath while this plays, so when the wordmark clears there is a
 * populated Cockpit behind it rather than an empty page beginning to load.
 * That is what makes the hand-off read as cinematic.
 *
 * The sequence runs on launch and on refresh, never on in-app navigation,
 * because the provider that owns it sits above the router and mounts once per
 * page load.
 *
 * Background is locked to `#030712` regardless of theme: the splash sits
 * outside the theme system by design, so the brand moment is identical for
 * every viewer. The overlay fades rather than cutting, which absorbs the
 * transition into a light-theme dashboard without a flash.
 */
export function SplashScreen() {
  const { booting } = useBoot()

  return (
    <AnimatePresence>
      {booting ? (
        <motion.div
          key="intelora-splash"
          className="fixed inset-0 z-[100] flex items-center justify-center overflow-hidden"
          style={{ backgroundColor: '#030712' }}
          variants={splash.curtain}
          initial="initial"
          exit="exit"
          // Announced to assistive technology so the sequence is not silent
          // dead air for a screen reader user.
          role="status"
          aria-label="INTELORA is starting"
        >
          {/* A single soft radial bloom. The specification is explicit that the
              screen must not look busy, so there is one light source, not a
              gradient mesh. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                'radial-gradient(ellipse 60% 45% at 50% 48%, rgb(0 229 255 / 0.09), transparent 70%)',
            }}
          />

          <motion.div
            className="pointer-events-none absolute inset-0"
            variants={splash.particles}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <ParticleField className="size-full" />
          </motion.div>

          {/* Camera push. Applied to a wrapper so the zoom is independent of
              the wordmark's own reveal and float. */}
          <motion.div
            className="relative flex items-center justify-center"
            variants={splash.camera}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <motion.div variants={splash.float} animate="animate">
              <motion.div
                variants={splash.wordmark}
                initial="initial"
                animate="animate"
                exit="exit"
              >
                <Wordmark
                  variant="dimensional"
                  size="text-[clamp(2.4rem,11vw,7rem)]"
                />
              </motion.div>
            </motion.div>
          </motion.div>

          {/* Vignette, to keep attention centred. */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                'radial-gradient(ellipse 90% 80% at 50% 50%, transparent 42%, rgb(3 7 18 / 0.85) 100%)',
            }}
          />
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
