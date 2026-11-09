// Service worker do FaceCheck. Necessário para o Chrome oferecer "Instalar aplicativo".
// Não guarda páginas nem dados em cache: tudo vem sempre do servidor (versão atual, presença em tempo real).
// Sem conexão, as telas mostram um aviso em vez da página de erro do navegador.
const OFFLINE_HTML = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>FaceCheck · sem conexão</title>
<style>html,body{height:100%;margin:0}body{display:grid;place-items:center;background:#0a0a0a;color:#e5e5e5;
font:16px/1.5 system-ui,sans-serif;text-align:center;padding:24px}button{margin-top:16px;padding:12px 22px;border:0;
border-radius:14px;background:#c81e25;color:#fff;font:600 16px system-ui}p{color:#a3a3a3;max-width:320px}</style></head>
<body><div><h1 style="font-size:22px;margin:0 0 8px">Sem conexão com o servidor</h1>
<p>Confira o Wi-Fi ou os dados móveis do aparelho. O FaceCheck precisa do servidor para reconhecer e registrar presença.</p>
<button onclick="location.reload()">Tentar de novo</button></div></body></html>`;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', event => {
  // só as navegações (abrir uma tela) ganham o aviso de sem conexão; o resto segue direto para a rede
  if (event.request.mode !== 'navigate') return;
  event.respondWith(
    fetch(event.request).catch(() => new Response(OFFLINE_HTML, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }))
  );
});
