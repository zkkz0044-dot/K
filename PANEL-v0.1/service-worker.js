const VERSION='k-mobile-v1-20260914-sensors2';
const SHELL=['/','/mobile.css','/mobile.js','/manifest.webmanifest','/icon-180.png','/icon-192.png','/icon-512.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(VERSION).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET') return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin||url.pathname.startsWith('/api/')) return;
  event.respondWith((async()=>{
    try{
      const res=await fetch(req,{cache:'no-store'});
      if(res.ok){const cache=await caches.open(VERSION);cache.put(req,res.clone())}
      return res;
    }catch(_e){
      return (await caches.match(req)) || (req.mode==='navigate'?await caches.match('/'):null) || new Response('K offline',{status:503,headers:{'Content-Type':'text/plain; charset=utf-8'}});
    }
  })());
});
