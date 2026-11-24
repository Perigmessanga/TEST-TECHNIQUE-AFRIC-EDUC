const CACHE='passage-v1';
self.addEventListener('install', event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(['/','/static/app.css','/static/app.js','/static/manifest.webmanifest']))));
self.addEventListener('fetch', event=>event.respondWith(fetch(event.request).catch(()=>caches.match(event.request).then(r=>r||new Response('Mode hors ligne', {status:503})))));
