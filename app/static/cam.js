// Helper de câmera compartilhado pelas páginas de check-in e cadastro.
const Cam = {
  stream: null,

  async list() {
    const devs = await navigator.mediaDevices.enumerateDevices();
    return devs.filter(d => d.kind === 'videoinput');
  },

  async start(video, deviceId) {
    this.stop();
    const constraints = {
      audio: false,
      video: deviceId ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
                      : { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }
    };
    try {
      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
    } catch (e) {
      // câmera salva não existe mais (ex.: celular usado como webcam desligado) → cai para a padrão
      if (!deviceId || !['OverconstrainedError', 'NotFoundError'].includes(e.name)) throw e;
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } } });
    }
    video.srcObject = this.stream;
    await video.play();
    return this.stream;
  },

  stop() {
    if (this.stream) { this.stream.getTracks().forEach(t => t.stop()); this.stream = null; }
  },

  // Captura um frame do <video> como JPEG, limitando a largura (padrão 640px).
  // Retorna { blob, width, height } nas dimensões do frame enviado.
  grab(video, maxW = 640, quality = 0.85) {
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) return Promise.resolve(null);
    const scale = Math.min(1, maxW / vw);
    const w = Math.round(vw * scale), h = Math.round(vh * scale);
    const c = Cam._canvas || (Cam._canvas = document.createElement('canvas'));
    c.width = w; c.height = h;
    c.getContext('2d').drawImage(video, 0, 0, w, h);
    return new Promise(res => c.toBlob(b => res({ blob: b, width: w, height: h }), 'image/jpeg', quality));
  },

  // Nome amigável: o Android manda "camera 1, facing front"; webcams vêm com "(046d:0825)" no fim.
  prettyLabels(cams) {
    const kind = l => /facing front|front|frontal|user/i.test(l) ? 'Câmera frontal'
      : /facing back|back|rear|traseira|environment/i.test(l) ? 'Câmera traseira' : null;
    const base = cams.map((c, i) => kind(c.label || '') || (c.label || '').replace(/\s*\([0-9a-f]{4}:[0-9a-f]{4}\)\s*$/i, '').trim() || `Câmera ${i + 1}`);
    const total = {}, seen = {};
    base.forEach(b => total[b] = (total[b] || 0) + 1);
    return base.map(b => total[b] > 1 ? `${b} ${(seen[b] = (seen[b] || 0) + 1)}` : b);
  },

  // Preenche um <select> com as câmeras disponíveis e restaura a escolha salva.
  async fillSelect(sel, storageKey) {
    const cams = await this.list();
    const names = this.prettyLabels(cams);
    sel.innerHTML = '';
    cams.forEach((c, i) => {
      const o = document.createElement('option');
      o.value = c.deviceId; o.textContent = c.label ? names[i] : ('Câmera ' + (i + 1));
      sel.appendChild(o);
    });
    const saved = localStorage.getItem(storageKey);
    if (saved && cams.some(c => c.deviceId === saved)) sel.value = saved;
    sel.onchange = () => localStorage.setItem(storageKey, sel.value);
    return cams;
  },

  // Traduz o erro do getUserMedia para algo que o operador entenda e saiba resolver.
  describeError(e) {
    const n = e && e.name;
    if (!window.isSecureContext || !navigator.mediaDevices)
      return { title: 'Câmera bloqueada neste endereço', text: 'O navegador só libera a câmera em HTTPS ou em localhost. Abra o sistema pelo endereço seguro.' };
    if (n === 'NotAllowedError' || n === 'SecurityError')
      return { title: 'Permissão da câmera negada', text: 'Toque no cadeado ao lado do endereço, permita o uso da câmera e tente de novo.' };
    if (n === 'NotFoundError' || n === 'OverconstrainedError' || n === 'DevicesNotFoundError')
      return { title: 'Nenhuma câmera encontrada', text: 'Conecte uma câmera ou escolha outra e tente de novo.' };
    if (n === 'NotReadableError' || n === 'TrackStartError' || n === 'AbortError')
      return { title: 'Câmera em uso', text: 'Outro aplicativo ou aba está usando a câmera. Feche e tente de novo.' };
    return { title: 'Câmera indisponível', text: 'Não foi possível abrir a câmera' + (e && e.message ? ` (${e.message})` : '') + '. Tente de novo.' };
  },

  // Painel "câmera indisponível" dentro de um container (mesmo visual no check-in e no cadastro).
  // onRetry: tentar abrir de novo; onPick: escolher outra câmera (só aparece se houver câmeras).
  async showError(container, err, { onRetry, onPick } = {}) {
    const info = this.describeError(err);
    let cams = [];
    try { cams = navigator.mediaDevices ? await this.list() : []; } catch (_) {}
    let el = container.querySelector('.cam-error');
    if (!el) { el = document.createElement('div'); el.className = 'cam-error'; container.appendChild(el); }
    el.innerHTML = `
      <div class="w-16 h-16 rounded-full grid place-items-center bg-white/5 border border-white/10 text-slate-300">${icon('cameraOff', 30)}</div>
      <div class="text-lg font-bold text-white">${esc(info.title)}</div>
      <p class="text-sm text-slate-400 max-w-xs leading-relaxed">${esc(info.text)}</p>
      <div class="flex flex-wrap justify-center gap-2 mt-1">
        <button class="btn btn-primary btn-sm" data-retry>${icon('refresh', 16)} Tentar de novo</button>
        ${cams.length > 1 ? `<button class="btn btn-sm" data-pick>${icon('camera', 16)} Escolher câmera</button>` : ''}
      </div>`;
    el.querySelector('[data-retry]').onclick = () => onRetry && onRetry();
    const pick = el.querySelector('[data-pick]');
    if (pick) pick.onclick = () => onPick && onPick();
    container.classList.add('cam-off');
  },

  hideError(container) {
    container.classList.remove('cam-off');
    const el = container.querySelector('.cam-error'); if (el) el.remove();
  },

  // id da câmera em uso
  currentId() {
    return this.stream ? this.stream.getVideoTracks()[0].getSettings().deviceId : null;
  },

  // Modal para escolher a câmera (usado no check-in e no cadastro; depende de ui.js).
  // onPick(deviceId, label) é chamado com a câmera escolhida.
  async openPicker({ onPick, storageKey = 'fc_camera' } = {}) {
    const cams = await this.list();
    const names = this.prettyLabels(cams);
    const current = this.currentId();
    const dlg = UI.dialog({
      size: 'sm',
      title: '<div class="font-bold text-lg">Escolher câmera</div>',
      body: `<div class="p-4 flex flex-col gap-2" data-list>${cams.length ? cams.map((c, i) => {
        const on = c.deviceId === current;
        const name = names[i];
        const hint = /traseira/i.test(name) ? 'desligue "Espelhar imagem" no menu' : '';
        return `<button class="row-item ${on ? '!border-indigo-500/60 !bg-indigo-500/10' : ''}" data-id="${esc(c.deviceId)}" data-label="${esc(name)}">
          <span class="w-11 h-11 rounded-xl grid place-items-center bg-white/5 text-slate-300 shrink-0">${icon('camera', 22)}</span>
          <div class="min-w-0 flex-1"><div class="font-semibold leading-snug line-clamp-2">${esc(name)}</div>
            ${hint || on ? `<div class="text-xs text-slate-400 mt-0.5">${[on ? 'em uso' : '', hint].filter(Boolean).join(' · ')}</div>` : ''}</div>
          ${on ? `<span class="text-indigo-400 shrink-0">${icon('check', 22, 2.6)}</span>` : ''}
        </button>`;
      }).join('') : `<div class="empty"><div class="ic">${icon('camera', 26)}</div><div>Nenhuma câmera encontrada. Confira a permissão do navegador.</div></div>`}</div>`,
    });
    dlg.$('[data-list]').onclick = e => {
      const b = e.target.closest('[data-id]'); if (!b) return;
      try { localStorage.setItem(storageKey, b.dataset.id); } catch (_) {}
      dlg.close();
      onPick && onPick(b.dataset.id, b.dataset.label);
    };
  },
};
