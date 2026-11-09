// Cabeçalho, drawer lateral, fullscreen, toast, modais e confirmação — compartilhados pelas páginas.

// ---- ícones (traço, 24x24) ----
const PATHS = {
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  fs: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
  fsExit: '<path d="M8 3v3a2 2 0 0 1-2 2H3M21 8h-3a2 2 0 0 1-2-2V3M3 16h3a2 2 0 0 1 2 2v3M16 21v-3a2 2 0 0 1 2-2h3"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="10" r="3"/><path d="M7 17.5c1-2 3-3 5-3s4 1 5 3"/>',
  user: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  admin: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  camera: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  chevron: '<path d="m9 18 6-6-6-6"/>',
  trash: '<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4M12 17h.01"/>',
  face: '<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  // ícones dos avisos (monocromáticos, no lugar de emojis)
  turnLeft: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  turnRight: '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
  arrowLeft: '<path d="M19 12H5M12 19l-7-7 7-7"/>',
  arrowRight: '<path d="M5 12h14M12 5l7 7-7 7"/>',
  arrows: '<path d="M18 8l4 4-4 4M6 8l-4 4 4 4M2 12h20"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  bulb: '<path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7V17h8v-2.3A7 7 0 0 0 12 2z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  contrast: '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" stroke="none"/>',
  hand: '<path d="M18 11V6a2 2 0 0 0-4 0v5"/><path d="M14 10V4a2 2 0 0 0-4 0v6"/><path d="M10 10.5V6a2 2 0 0 0-4 0v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-6-2.4l-3.6-3.6a2 2 0 0 1 2.8-2.8L7 15"/>',
  ban: '<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
  glasses: '<circle cx="6" cy="15" r="4"/><circle cx="18" cy="15" r="4"/><path d="M14 15a2 2 0 0 0-4 0M2.5 13 5 7c.7-1.3 1.4-2 3-2M21.5 13 19 7c-.7-1.3-1.5-2-3-2"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  level: '<path d="M3 12h18"/><path d="M7 8l-4 4 4 4M17 8l4 4-4 4"/>',
  ruler: '<path d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.4 2.4 0 0 1 0-3.4l2.6-2.6a2.4 2.4 0 0 1 3.4 0Z"/><path d="m14.5 12.5 2-2M11.5 9.5l2-2M8.5 6.5l2-2M17.5 15.5l2-2"/>',
  loader: '<path d="M21 12a9 9 0 1 1-6.2-8.6"/>',
  pause: '<path d="M9 5v14M15 5v14"/>',
  volume: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/>',
  mute: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="m22 9-6 6M16 9l6 6"/>',
  mirror: '<path d="M12 3v18"/><path d="M8 7 3 12l5 5V7z"/><path d="m16 7 5 5-5 5V7z"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  cameraOff: '<path d="m2 2 20 20"/><path d="M7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16"/><path d="M9.5 4h5L17 7h3a2 2 0 0 1 2 2v7.5"/><path d="M14.1 14.1A3 3 0 1 1 9.9 9.9"/>',
};
function icon(name, size = 20, sw = 2) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || ''}</svg>`;
}
const ICONS = {
  menu: icon('menu', 22), close: icon('close', 22), fs: icon('fs', 22), fsExit: icon('fsExit', 22),
  scan: icon('scan'), user: icon('user'), admin: icon('admin'), check: icon('check', 28, 3), camera: icon('camera', 26),
  logo: `<span class="inline-grid place-items-center w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 text-white shadow-lg shadow-indigo-500/30">${icon('scan', 18, 2.2)}</span>`,
};

const UI = {
  // active: 'checkin' | 'cadastro' | 'admin'; controls: HTML extra dentro do drawer; headerRight: HTML à direita do header
  mount({ active, title, controls = '', headerRight = '' }) {
    const links = [
      { id: 'checkin', href: '/', label: 'Check-in', icon: ICONS.scan },
      { id: 'cadastro', href: '/cadastro', label: 'Cadastro', icon: ICONS.user },
      { id: 'admin', href: '/admin', label: 'Admin', icon: ICONS.admin },
    ];
    document.body.insertAdjacentHTML('afterbegin', `
<header id="appHeader" class="h-14 shrink-0 flex items-center gap-2 px-2 sm:px-4 border-b border-white/10 bg-slate-950/70 backdrop-blur-md z-30 relative">
  <button id="menuBtn" class="btn btn-ghost btn-icon" aria-label="Menu">${ICONS.menu}</button>
  <a href="/" class="flex items-center gap-2 pl-1">${ICONS.logo}<span class="font-semibold tracking-tight">FaceCheck</span></a>
  <span class="text-slate-500 hidden sm:inline">/</span><span class="text-slate-300 hidden sm:inline">${title}</span>
  <div class="flex-1"></div>
  <div id="headerRight" class="flex items-center gap-2">${headerRight}
    <button class="btn btn-ghost btn-icon" data-fs aria-label="Tela cheia">${ICONS.fs}</button>
  </div>
</header>
<div id="drawerOverlay" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 hidden"></div>
<aside id="drawer" class="fixed top-0 left-0 h-full w-80 max-w-[86vw] bg-slate-950/95 border-r border-white/10 z-50 -translate-x-full flex flex-col shadow-2xl">
  <div class="h-14 flex items-center gap-2 px-3 border-b border-white/10">
    ${ICONS.logo}<span class="font-semibold">FaceCheck</span>
    <div class="flex-1"></div>
    <button id="drawerClose" class="btn btn-ghost btn-icon" aria-label="Fechar">${ICONS.close}</button>
  </div>
  <nav class="p-3 flex flex-col gap-1">
    ${links.map(l => `<a class="nav-link ${l.id === active ? 'active' : ''}" href="${l.href}">${l.icon}<span>${l.label}</span></a>`).join('')}
  </nav>
  ${controls ? `<div class="p-4 border-t border-white/10 flex flex-col gap-4">${controls}</div>` : ''}
  <div class="flex-1"></div>
  <div class="p-3 border-t border-white/10 flex flex-col gap-2">
    <button class="btn btn-primary w-full hidden" id="installBtn">${icon('download', 20)}<span>Instalar aplicativo</span></button>
    <button class="btn w-full" data-fs>${ICONS.fs}<span data-fs-label>Tela cheia</span></button>
    <p class="text-[11px] text-slate-500 text-center">Protótipo · nenhuma imagem é guardada</p>
  </div>
</aside>
<div id="toast"></div>`);

    const drawer = document.getElementById('drawer');
    const overlay = document.getElementById('drawerOverlay');
    const open = () => { drawer.classList.add('open'); overlay.classList.remove('hidden'); UI.drawerOpen = true; };
    const close = () => { drawer.classList.remove('open'); overlay.classList.add('hidden'); UI.drawerOpen = false; };
    document.getElementById('menuBtn').onclick = open;
    document.getElementById('drawerClose').onclick = close;
    overlay.onclick = close;
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
    document.querySelectorAll('[data-menu]').forEach(b => b.onclick = open);
    document.querySelectorAll('[data-fs]').forEach(b => b.onclick = () => UI.toggleFullscreen());
    document.addEventListener('fullscreenchange', () => UI._syncFs());
    // toque longo / botão direito: sem menu de contexto fora dos campos de texto
    const editable = t => t.closest && t.closest('input, textarea, [contenteditable="true"], .selectable');
    document.addEventListener('contextmenu', e => { if (!editable(e.target)) e.preventDefault(); });
    // limpa qualquer seleção que escape (ex.: toque duplo em texto)
    document.addEventListener('selectstart', e => { if (!editable(e.target)) e.preventDefault(); });
    this.open = open; this.close = close;
    PWA.syncButton();
  },

  async toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen({ navigationUI: 'hide' });
    } catch (e) { UI.toast('Tela cheia indisponível neste navegador'); }
  },

  _syncFs() {
    const fs = !!document.fullscreenElement;
    document.documentElement.classList.toggle('is-fs', fs);
    document.querySelectorAll('[data-fs-label]').forEach(l => l.textContent = fs ? 'Sair da tela cheia' : 'Tela cheia');
    document.querySelectorAll('[data-fs]').forEach(b => {
      const svg = b.querySelector('svg'); if (svg) svg.outerHTML = fs ? ICONS.fsExit : ICONS.fs;
    });
  },

  toast(msg, ms = 2500) {
    const t = document.getElementById('toast');
    // modais ficam na "top layer": o toast precisa estar dentro do modal aberto para aparecer por cima
    const host = [...document.querySelectorAll('dialog.modal[open]')].pop() || document.body;
    if (t.parentElement !== host) host.appendChild(t);
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), ms);
  },

  // Modal com <dialog>: no celular vira "folha" que sobe de baixo.
  // body/footer: string HTML. Retorna { el, close, $, $$, setTitle, setBody }.
  dialog({ title = '', body = '', footer = '', size = 'md', onClose } = {}) {
    const widths = { sm: '26rem', md: '36rem', lg: '50rem', xl: '64rem' };
    const d = document.createElement('dialog');
    d.className = 'modal';
    d.innerHTML = `
      <div class="modal-panel" style="--w:${widths[size] || widths.md}">
        ${title !== null ? `<div class="modal-head"><div class="min-w-0 flex-1" data-title>${title}</div>
          <button class="btn btn-ghost btn-icon shrink-0" data-close aria-label="Fechar">${ICONS.close}</button></div>` : ''}
        <div class="modal-body" data-body>${body}</div>
        ${footer ? `<div class="modal-foot" data-foot>${footer}</div>` : ''}
      </div>`;
    document.body.appendChild(d);
    document.documentElement.classList.add('modal-open');
    const close = () => { if (d.open) d.close(); };
    // clique fora do painel (no próprio <dialog>) ou em [data-close] fecha
    d.addEventListener('mousedown', e => { d._downOutside = e.target === d; });
    d.addEventListener('click', e => {
      if ((e.target === d && d._downOutside) || e.target.closest('[data-close]')) close();
    });
    d.addEventListener('close', () => {
      const t = d.querySelector('#toast');
      if (t) ([...document.querySelectorAll('dialog.modal[open]')].filter(x => x !== d).pop() || document.body).appendChild(t);
      d.remove();
      if (!document.querySelector('dialog.modal[open]')) document.documentElement.classList.remove('modal-open');
      onClose && onClose();
    });
    d.showModal();
    return {
      el: d, close,
      $: s => d.querySelector(s), $$: s => d.querySelectorAll(s),
      setTitle: h => { const t = d.querySelector('[data-title]'); if (t) t.innerHTML = h; },
      setBody: h => { d.querySelector('[data-body]').innerHTML = h; },
    };
  },

  // Confirmação própria (o confirm() do navegador trava a página e é feio no celular).
  confirm({ title = 'Tem certeza?', message = '', confirmText = 'Confirmar', cancelText = 'Cancelar', danger = false } = {}) {
    return new Promise(resolve => {
      let ok = false;
      const dlg = UI.dialog({
        size: 'sm', title: null,
        body: `<div class="px-6 pt-7 pb-5 flex flex-col items-center text-center gap-3">
          <div class="w-14 h-14 rounded-full grid place-items-center ${danger ? 'bg-red-500/15 text-red-300 ring-1 ring-red-400/30' : 'bg-indigo-500/15 text-indigo-300 ring-1 ring-indigo-400/30'}">
            ${icon(danger ? 'trash' : 'info', 26)}</div>
          <h3 class="text-lg font-bold leading-snug">${title}</h3>
          ${message ? `<p class="text-slate-400 text-sm leading-relaxed">${message}</p>` : ''}
        </div>`,
        footer: `<button class="btn flex-1" data-close>${cancelText}</button>
                 <button class="btn ${danger ? 'btn-danger-solid' : 'btn-primary'} flex-1" data-ok>${confirmText}</button>`,
        onClose: () => resolve(ok),
      });
      dlg.$('[data-ok]').onclick = () => { ok = true; dlg.close(); };
      setTimeout(() => dlg.$(danger ? '[data-close]' : '[data-ok]').focus(), 30);
    });
  },
};

// ---- utilitários ----
async function api(path, opts = {}) {
  const o = { ...opts };
  if (o.json !== undefined) {
    o.body = JSON.stringify(o.json);
    o.headers = { 'Content-Type': 'application/json', ...(o.headers || {}) };
    delete o.json;
  }
  const r = await fetch(path, o);
  if (!r.ok) {
    let msg = 'HTTP ' + r.status;
    try { const j = await r.json(); if (j.detail) msg = typeof j.detail === 'string' ? j.detail : 'dados inválidos'; } catch (_) {}
    throw new Error(msg);
  }
  return r.status === 204 ? null : r.json();
}
function fmtTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}
function fmtDateTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function fmtDate(d) {
  if (!d) return '';
  const [y, m, dd] = String(d).slice(0, 10).split('-');
  return `${dd}/${m}/${y}`;
}
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const WEEKDAYS = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];
function todayISO() { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); }
function weekday(iso) { const [y, m, d] = iso.split('-').map(Number); return WEEKDAYS[new Date(y, m - 1, d).getDay()]; }
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
function initials(name) {
  const p = String(name || '?').trim().split(/\s+/);
  return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
}
function avatar(name, size = 40) {
  let h = 0; for (const c of String(name)) h = (h * 31 + c.charCodeAt(0)) % 360;
  return `<span class="avatar" style="width:${size}px;height:${size}px;font-size:${Math.round(size * .36)}px;background:linear-gradient(135deg,hsl(${h} 65% 48%),hsl(${(h + 40) % 360} 70% 38%))">${esc(initials(name))}</span>`;
}
function debounce(fn, ms = 250) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

// ---- aplicativo instalável (PWA) ----
// O Chrome dispara "beforeinstallprompt" quando o site pode ser instalado; guardamos o evento e mostramos
// "Instalar aplicativo" no menu. Instalado, o FaceCheck abre sempre em tela cheia, sem a barra do navegador.
const PWA = {
  prompt: null,
  installed: window.matchMedia('(display-mode: fullscreen), (display-mode: standalone)').matches || navigator.standalone === true,
  syncButton() {
    const b = document.getElementById('installBtn'); if (!b) return;
    b.classList.toggle('hidden', !this.prompt || this.installed);
    b.onclick = async () => {
      if (!this.prompt) return;
      this.prompt.prompt();
      const choice = await this.prompt.userChoice.catch(() => null);
      if (choice && choice.outcome === 'accepted') UI.toast('Instalando… procure o ícone FaceCheck na tela inicial');
      this.prompt = null; this.syncButton();
    };
  },
};
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); PWA.prompt = e; PWA.syncButton(); });
window.addEventListener('appinstalled', () => { PWA.installed = true; PWA.prompt = null; PWA.syncButton(); });
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {}));
}
