import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MotionConfig } from 'motion/react'
import '@fontsource-variable/manrope'
import '@fontsource-variable/inter'
import '@fontsource-variable/jetbrains-mono'
// Legacy Carbon stylesheet is pulled in from inside tailwind.css itself,
// wrapped in a low-priority @layer so it still styles every page not yet
// migrated to the Wise-inspired redesign (WI.B-WI.E2) without its plain
// unlayered selectors beating Tailwind's own utility classes -- see the
// comment at the top of tailwind.css for why layering (not import order)
// is what actually decides that. Deleted once the migration sweep is
// done (WI.G).
import './styles/tailwind.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* reducedMotion="user" makes every Motion-driven animation in the
        app (route transitions, tile entrance, count-ups, hover/press)
        auto-collapse to instant under the OS's prefers-reduced-motion
        setting -- the plain-CSS transitions have their own equivalent
        guard in index.css. */}
    <MotionConfig reducedMotion="user">
      <App />
    </MotionConfig>
  </StrictMode>,
)

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Installability/offline-shell polish only -- the app works fine
      // without it, so a registration failure is silent, not surfaced.
    })
  })
}
