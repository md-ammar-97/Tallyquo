// Minimal app-shell service worker. Deliberately does NOT cache API
// responses -- this is a financial app, and serving a stale invoice or
// payment figure from a cache while offline is worse than no data at
// all. Only same-origin static assets (the built JS/CSS/icons) get
// cached, cache-first with a network fallback; navigations and every
// cross-origin request (the API, on a different host) always go to the
// network untouched.

const CACHE_NAME = 'tallyquo-shell-v1'

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  if (request.method !== 'GET' || url.origin !== self.location.origin) return
  // Navigations (the SPA shell HTML) always go to the network -- a stale
  // cached index.html could point at assets from a build that no longer
  // exists once a new deploy ships.
  if (request.mode === 'navigate') return
  if (!url.pathname.startsWith('/assets/') && !/\.(svg|png|ico|webmanifest)$/.test(url.pathname)) return

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(request)
      if (cached) return cached
      const response = await fetch(request)
      if (response.ok) cache.put(request, response.clone())
      return response
    })
  )
})
