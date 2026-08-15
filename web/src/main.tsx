import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MotionConfig } from 'motion/react'
import '@fontsource-variable/manrope'
import '@fontsource-variable/inter'
import '@fontsource-variable/jetbrains-mono'
import './styles/tailwind.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* reducedMotion="user" makes every Motion-driven animation in the
        app (route transitions, tile entrance, count-ups, hover/press)
        auto-collapse to instant under the OS's prefers-reduced-motion
        setting -- the plain-CSS transitions have their own equivalent
        guard in styles/tailwind.css. */}
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
