/* Toza Gilam — gilam yuvish xizmati uchun buyurtmalar boshqaruvi.
   Ma'lumotlar brauzerning localStorage'ida saqlanadi. */
(() => {
  'use strict';

  // ---------- Konstantalar ----------
  const STATUSES = [
    { id: 'new',   label: 'Qabul qilindi', color: 'var(--s-new)' },
    { id: 'wash',  label: 'Yuvilmoqda',    color: 'var(--s-wash)' },
    { id: 'dry',   label: 'Quritilmoqda',  color: 'var(--s-dry)' },
    { id: 'ready', label: 'Tayyor',        color: 'var(--s-ready)' },
    { id: 'done',  label: 'Topshirildi',   color: 'var(--s-done)' },
  ];
  const STATUS = Object.fromEntries(STATUSES.map(s => [s.id, s]));

  const DEFAULT_SETTINGS = {
    companyName: 'Toza Gilam',
    companyPhone: '',
    deliveryFee: 30000,
    services: [
      { id: 'oddiy',  name: 'Oddiy gilam', price: 12000 },
      { id: 'junli',  name: 'Junli gilam', price: 18000 },
      { id: 'palos',  name: 'Palos',       price: 15000 },
      { id: 'kovro',  name: 'Kovrolin',    price: 10000 },
    ],
  };

  const KEY_ORDERS = 'tozagilam.orders.v1';
  const KEY_SETTINGS = 'tozagilam.settings.v1';

  // ---------- Saqlash ----------
  const load = (key, fallback) => {
    try { const v = JSON.parse(localStorage.getItem(key)); return v ?? fallback; }
    catch { return fallback; }
  };
  const save = (key, value) => {
    try { localStorage.setItem(key, JSON.stringify(value)); }
    catch { toast('Saqlab bo\'lmadi: xotira mavjud emas'); }
  };

  let orders = load(KEY_ORDERS, []);
  let settings = { ...DEFAULT_SETTINGS, ...load(KEY_SETTINGS, {}) };
  const persistOrders = () => save(KEY_ORDERS, orders);
  const persistSettings = () => save(KEY_SETTINGS, settings);

  // ---------- Yordamchilar ----------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const money = n => Math.round(n || 0).toLocaleString('ru-RU').replace(/,/g, ' ') + ' so\'m';
  const num = v => { const n = parseFloat(String(v).replace(',', '.')); return isFinite(n) && n > 0 ? n : 0; };
  const area = it => +(num(it.w) * num(it.l)).toFixed(2);
  const fmtDate = ts => new Date(ts).toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const fmtDateTime = ts => new Date(ts).toLocaleString('uz-UZ', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  const nextNum = () => orders.reduce((m, o) => Math.max(m, o.num || 0), 0) + 1;

  function orderTotal(o) {
    const items = o.items.reduce((s, it) => s + area(it) * (it.price || 0), 0);
    return items + (o.delivery ? (o.deliveryFee || 0) : 0) - (o.discount || 0);
  }
  const orderArea = o => o.items.reduce((s, it) => s + area(it), 0);

  function badge(statusId) {
    const s = STATUS[statusId] || STATUSES[0];
    return `<span class="badge" style="--c:${s.color}">${s.label}</span>`;
  }

  // Sahifa ichidagi tasdiqlash oynasi (brauzer confirm() o'rniga)
  function ask(message, okLabel = 'Ha', danger = false) {
    const d = $('#ask'), ok = $('#askOk'), no = $('#askNo');
    $('#askText').textContent = message;
    ok.textContent = okLabel; ok.className = 'btn ' + (danger ? 'btn-danger-solid' : 'btn-primary');
    return new Promise(resolve => {
      const done = v => { d.close(); ok.onclick = no.onclick = null; resolve(v); };
      ok.onclick = () => done(true); no.onclick = () => done(false);
      d.oncancel = e => { e.preventDefault(); done(false); };
      d.showModal(); no.focus();
    });
  }

  async function copyText(text, okMsg) {
    try { await navigator.clipboard.writeText(text); toast(okMsg); return; } catch {}
    const ta = document.createElement('textarea');
    ta.value = text; ta.setAttribute('readonly', ''); ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch {}
    ta.parentNode.removeChild(ta);
    toast(ok ? okMsg : 'Nusxalab bo\'lmadi');
  }

  let toastTimer;
  function toast(msg) {
    const t = $('#toast'); t.textContent = msg; t.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
  }

  // ---------- Router ----------
  const view = $('#view');
  let ordersFilter = 'active';
  let ordersQuery = '';
  let editingId = null;

  function route() {
    const name = location.hash.slice(1) || 'bosh';
    $$('.bottomnav a').forEach(a => a.classList.toggle('active', a.dataset.tab === name));
    window.scrollTo(0, 0);
    if (name === 'buyurtmalar') return renderOrders();
    if (name === 'yangi') return renderForm(null);
    if (name === 'tahrir') {
      const o = orders.find(x => x.id === editingId);
      if (o) return renderForm(o);
      location.hash = 'buyurtmalar'; return;
    }
    if (name === 'sozlamalar') return renderSettings();
    return renderHome();
  }
  window.addEventListener('hashchange', route);
  document.addEventListener('click', e => {
    const go = e.target.closest('[data-go]');
    if (go) { location.hash = go.dataset.go; }
  });

  // ---------- Bosh sahifa ----------
  function renderHome() {
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const monthStart = new Date(today.getFullYear(), today.getMonth(), 1).getTime();
    const todayOrders = orders.filter(o => o.createdAt >= today.getTime());
    const active = orders.filter(o => o.status !== 'done');
    const ready = orders.filter(o => o.status === 'ready');
    const monthRevenue = orders.filter(o => o.paid && (o.paidAt || o.createdAt) >= monthStart).reduce((s, o) => s + orderTotal(o), 0);
    const debt = orders.filter(o => !o.paid).reduce((s, o) => s + orderTotal(o), 0);

    const counts = STATUSES.slice(0, 4).map(s =>
      `<button class="chip" data-filter="${s.id}">${s.label}: <b>${orders.filter(o => o.status === s.id).length}</b></button>`).join('');

    view.innerHTML = `
      <h1>Bosh sahifa</h1>
      ${orders.length ? '' : `<div class="card welcome">
        <b>Xush kelibsiz!</b> Bu yerda gilam buyurtmalarini qabul qilasiz, holatini kuzatasiz va to'lovlarni hisoblaysiz.
        <div class="actions"><button class="btn btn-primary" data-go="yangi">+ Birinchi buyurtma</button>
        <button class="btn" id="tryDemo">Namuna bilan ko'rish</button></div></div><br>`}
      <div class="grid-stats">
        <div class="card stat"><div class="label">Bugungi buyurtmalar</div><div class="value">${todayOrders.length}</div></div>
        <div class="card stat"><div class="label">Jarayonda</div><div class="value">${active.length}</div></div>
        <div class="card stat"><div class="label">Shu oy tushum</div><div class="value">${money(monthRevenue).replace(' so\'m', '')}</div><div class="label">so'm</div></div>
        <div class="card stat"><div class="label">To'lanmagan</div><div class="value">${money(debt).replace(' so\'m', '')}</div><div class="label">so'm</div></div>
      </div>
      <h2>Holat bo'yicha</h2>
      <div class="status-row">${counts}</div>
      <h2>Topshirishga tayyor (${ready.length})</h2>
      ${listHtml(ready, 'Tayyor buyurtmalar yo\'q')}
      <h2>So'nggi buyurtmalar</h2>
      ${listHtml([...orders].sort((a, b) => b.createdAt - a.createdAt).slice(0, 5), 'Hali buyurtma yo\'q. Yuqoridagi “+ Buyurtma” tugmasini bosing.')}
    `;
    $('#tryDemo', view)?.addEventListener('click', addDemo);
    $$('[data-filter]', view).forEach(b => b.onclick = () => { ordersFilter = b.dataset.filter; location.hash = 'buyurtmalar'; });
    bindList();
  }

  function listHtml(list, emptyText) {
    if (!list.length) return `<div class="card empty">${esc(emptyText)}</div>`;
    return `<div class="order-list">${list.map(o => `
      <div class="card order" data-open="${o.id}" tabindex="0" role="button">
        <div><span class="name">#${o.num} · ${esc(o.customer.name)}</span>${o.demo ? ' <span class="muted small">(namuna)</span>' : ''}</div>
        <div class="sum">${money(orderTotal(o))}</div>
        <div class="meta">${esc(o.customer.phone)} · ${o.items.length} dona · ${orderArea(o).toFixed(1)} m² · ${fmtDate(o.createdAt)}</div>
        <div style="text-align:right">${o.paid ? '' : '<span class="badge unpaid">To\'lanmagan</span> '}${badge(o.status)}</div>
      </div>`).join('')}</div>`;
  }
  function bindList() {
    $$('[data-open]', view).forEach(el => {
      el.onclick = () => openOrder(el.dataset.open);
      el.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openOrder(el.dataset.open); } };
    });
  }

  // ---------- Buyurtmalar ro'yxati ----------
  function renderOrders() {
    const filters = [
      { id: 'active', label: 'Jarayonda' }, { id: 'all', label: 'Hammasi' },
      ...STATUSES.map(s => ({ id: s.id, label: s.label })), { id: 'unpaid', label: 'To\'lanmagan' },
    ];
    view.innerHTML = `
      <h1>Buyurtmalar</h1>
      <div class="field"><input id="q" type="search" placeholder="Ism, telefon yoki № bo'yicha qidirish" value="${esc(ordersQuery)}"></div>
      <div class="status-row" style="margin:10px 0 14px">${filters.map(f =>
        `<button class="chip ${f.id === ordersFilter ? 'active' : ''}" data-f="${f.id}">${f.label}</button>`).join('')}</div>
      <div id="list"></div>`;
    const draw = () => {
      const q = ordersQuery.trim().toLowerCase();
      const list = orders.filter(o => {
        if (ordersFilter === 'active' && o.status === 'done') return false;
        if (ordersFilter === 'unpaid' && o.paid) return false;
        if (STATUS[ordersFilter] && o.status !== ordersFilter) return false;
        if (!q) return true;
        return [o.customer.name, o.customer.phone, o.customer.address, '#' + o.num, String(o.num)]
          .some(v => String(v || '').toLowerCase().includes(q));
      }).sort((a, b) => b.createdAt - a.createdAt);
      $('#list', view).innerHTML = listHtml(list, 'Hech narsa topilmadi');
      bindList();
    };
    $('#q', view).oninput = e => { ordersQuery = e.target.value; draw(); };
    $$('[data-f]', view).forEach(b => b.onclick = () => {
      ordersFilter = b.dataset.f;
      $$('[data-f]', view).forEach(x => x.classList.toggle('active', x === b));
      draw();
    });
    draw();
  }

  // ---------- Buyurtma formasi ----------
  function renderForm(existing) {
    const o = existing ? structuredClone(existing) : {
      customer: { name: '', phone: '+998 ', address: '' },
      items: [{ service: settings.services[0]?.id, price: settings.services[0]?.price || 0, w: '', l: '' }],
      delivery: false, deliveryFee: settings.deliveryFee, discount: 0, note: '',
    };
    const serviceOptions = sel => settings.services.map(s =>
      `<option value="${s.id}" ${s.id === sel ? 'selected' : ''}>${esc(s.name)} — ${money(s.price)}/m²</option>`).join('');

    view.innerHTML = `
      <h1>${existing ? `Buyurtma #${existing.num} ni tahrirlash` : 'Yangi buyurtma'}</h1>
      <form id="f" class="card" autocomplete="off" novalidate>
        <div class="field"><label for="name">Mijoz ismi *</label><input id="name" required value="${esc(o.customer.name)}"></div>
        <div class="field"><label for="phone">Telefon *</label><input id="phone" type="tel" inputmode="tel" required value="${esc(o.customer.phone)}"></div>
        <div class="field"><label for="addr">Manzil</label><input id="addr" value="${esc(o.customer.address)}" placeholder="Mahalla, ko'cha, uy"></div>

        <h2>Gilamlar</h2>
        <div class="item-row muted small" style="margin-bottom:2px"><span>Turi</span><span>Eni (m)</span><span>Bo'yi (m)</span><span></span></div>
        <div id="items"></div>
        <button type="button" class="btn btn-sm" id="addItem">+ Gilam qo'shish</button>

        <h2>Qo'shimcha</h2>
        <label class="check"><input type="checkbox" id="delivery" ${o.delivery ? 'checked' : ''}> Olib ketish / yetkazib berish</label>
        <div class="row2" style="margin-top:10px">
          <div class="field"><label for="dfee">Yetkazish narxi</label><input id="dfee" type="number" min="0" step="1000" value="${o.deliveryFee || 0}"></div>
          <div class="field"><label for="disc">Chegirma (so'm)</label><input id="disc" type="number" min="0" step="1000" value="${o.discount || 0}"></div>
        </div>
        <div class="field"><label for="note">Izoh</label><textarea id="note" rows="2" placeholder="Masalan: dog'i bor, juda iflos">${esc(o.note)}</textarea></div>

        <div class="total-box"><span>Jami</span><span class="v" id="total">0 so'm</span></div>
        <div class="actions">
          <button class="btn btn-primary" type="submit" style="flex:1">${existing ? 'Saqlash' : 'Buyurtmani qabul qilish'}</button>
          <button class="btn" type="button" data-go="${existing ? 'buyurtmalar' : 'bosh'}">Bekor qilish</button>
        </div>
      </form>`;

    const itemsEl = $('#items', view);
    const drawItems = () => {
      itemsEl.innerHTML = o.items.map((it, i) => `
        <div class="item-row" data-i="${i}">
          <select data-k="service" aria-label="Gilam turi">${serviceOptions(it.service)}</select>
          <input data-k="w" type="number" inputmode="decimal" min="0" step="0.1" placeholder="2" value="${esc(it.w)}" aria-label="Eni">
          <input data-k="l" type="number" inputmode="decimal" min="0" step="0.1" placeholder="3" value="${esc(it.l)}" aria-label="Bo'yi">
          <button type="button" class="btn btn-icon" data-del aria-label="O'chirish" ${o.items.length < 2 ? 'disabled' : ''}>✕</button>
          <div class="area" data-area></div>
        </div>`).join('');
      updateTotals();
    };
    const updateTotals = () => {
      $$('.item-row[data-i]', itemsEl).forEach(row => {
        const it = o.items[+row.dataset.i];
        const a = area(it);
        $('[data-area]', row).textContent = a ? `${a} m² × ${money(it.price)} = ${money(a * it.price)}` : 'O\'lchamlarni kiriting';
      });
      o.delivery = $('#delivery', view).checked;
      o.deliveryFee = num($('#dfee', view).value);
      o.discount = num($('#disc', view).value);
      $('#total', view).textContent = money(Math.max(0, orderTotal(o)));
    };
    itemsEl.addEventListener('input', e => {
      const row = e.target.closest('[data-i]'); if (!row) return;
      const it = o.items[+row.dataset.i]; const k = e.target.dataset.k;
      if (k === 'service') {
        it.service = e.target.value;
        it.price = settings.services.find(s => s.id === it.service)?.price || 0;
      } else if (k) it[k] = e.target.value;
      updateTotals();
    });
    itemsEl.addEventListener('click', e => {
      if (!e.target.closest('[data-del]')) return;
      o.items.splice(+e.target.closest('[data-i]').dataset.i, 1); drawItems();
    });
    $('#addItem', view).onclick = () => {
      const last = o.items[o.items.length - 1];
      o.items.push({ service: last?.service || settings.services[0]?.id, price: last?.price || settings.services[0]?.price || 0, w: '', l: '' });
      drawItems();
      $$('.item-row[data-i]', itemsEl).at(-1).querySelector('[data-k="w"]').focus();
    };
    ['delivery', 'dfee', 'disc'].forEach(id => $('#' + id, view).addEventListener('input', updateTotals));
    drawItems();

    $('#f', view).onsubmit = e => {
      e.preventDefault();
      const name = $('#name', view).value.trim();
      const phone = $('#phone', view).value.trim();
      if (!name) { toast('Mijoz ismini kiriting'); return $('#name', view).focus(); }
      if (phone.replace(/\D/g, '').length < 7) { toast('Telefon raqamini to\'g\'ri kiriting'); return $('#phone', view).focus(); }
      const items = o.items.filter(it => area(it) > 0);
      if (!items.length) { toast('Kamida bitta gilam o\'lchamini kiriting'); return; }
      updateTotals();
      const data = {
        ...o, items,
        customer: { name, phone, address: $('#addr', view).value.trim() },
        note: $('#note', view).value.trim(),
      };
      if (existing) {
        Object.assign(existing, data, { updatedAt: Date.now() });
        persistOrders(); toast('Saqlandi'); location.hash = 'buyurtmalar'; openOrder(existing.id);
      } else {
        const created = { ...data, id: uid(), num: nextNum(), createdAt: Date.now(), status: 'new', paid: false, history: [{ status: 'new', at: Date.now() }] };
        orders.push(created); persistOrders();
        toast(`Buyurtma #${created.num} qabul qilindi`);
        location.hash = 'buyurtmalar'; openOrder(created.id);
      }
    };
  }

  // ---------- Buyurtma tafsilotlari ----------
  const modal = $('#modal');
  const modalBody = $('#modalBody');
  modal.addEventListener('click', e => { if (e.target === modal) modal.close(); });

  function openOrder(id) {
    const o = orders.find(x => x.id === id); if (!o) return;
    const idx = STATUSES.findIndex(s => s.id === o.status);
    const svcName = sid => settings.services.find(s => s.id === sid)?.name || 'Gilam';
    const tel = o.customer.phone.replace(/[^\d+]/g, '');

    modalBody.innerHTML = `
      <div class="modal-head">
        <div>
          <div class="muted small">${esc(settings.companyName)}${settings.companyPhone ? ' · ' + esc(settings.companyPhone) : ''}</div>
          <h1 style="margin:2px 0">Buyurtma #${o.num}</h1>
          <div class="muted small">${fmtDateTime(o.createdAt)}</div>
        </div>
        <button class="btn btn-icon no-print" data-close aria-label="Yopish">✕</button>
      </div>
      <p style="margin:12px 0 4px"><b>${esc(o.customer.name)}</b><br>
        <a href="tel:${esc(tel)}">${esc(o.customer.phone)}</a>${o.customer.address ? '<br>' + esc(o.customer.address) : ''}</p>

      <div class="steps no-print">${STATUSES.map((s, i) =>
        `<button data-status="${s.id}" class="${i < idx ? 'done' : i === idx ? 'current' : ''}">${s.label}</button>`).join('')}</div>

      <table style="margin-top:12px">
        <thead><tr><th>Gilam</th><th class="num">O'lcham</th><th class="num">m²</th><th class="num">Summa</th></tr></thead>
        <tbody>
          ${o.items.map(it => `<tr><td>${esc(svcName(it.service))}</td><td class="num">${num(it.w)}×${num(it.l)}</td><td class="num">${area(it)}</td><td class="num">${money(area(it) * it.price)}</td></tr>`).join('')}
          ${o.delivery ? `<tr><td colspan="3">Yetkazib berish</td><td class="num">${money(o.deliveryFee)}</td></tr>` : ''}
          ${o.discount ? `<tr><td colspan="3">Chegirma</td><td class="num">−${money(o.discount)}</td></tr>` : ''}
        </tbody>
      </table>
      <div class="total-box"><span>Jami · ${orderArea(o).toFixed(2)} m²</span><span class="v">${money(Math.max(0, orderTotal(o)))}</span></div>
      <div>Holat: ${badge(o.status)} &nbsp; To'lov: ${o.paid ? '<span class="badge paid">To\'langan</span>' : '<span class="badge unpaid">To\'lanmagan</span>'}</div>
      ${o.note ? `<p class="muted small">Izoh: ${esc(o.note)}</p>` : ''}

      <div class="actions no-print">
        ${idx < STATUSES.length - 1 ? `<button class="btn btn-primary" data-next>→ ${STATUSES[idx + 1].label}</button>` : ''}
        <button class="btn" data-paid>${o.paid ? 'To\'lovni bekor qilish' : '✓ To\'landi'}</button>
        <a class="btn" href="tel:${esc(tel)}">📞 Qo'ng'iroq</a>
        <button class="btn" data-sms>✉️ SMS</button>
        <button class="btn" data-receipt>📄 Chekni nusxalash</button>
        <button class="btn" data-edit>✎ Tahrirlash</button>
        <button class="btn btn-danger" data-delete>O'chirish</button>
      </div>`;

    const setStatus = sid => {
      o.status = sid; (o.history ||= []).push({ status: sid, at: Date.now() });
      persistOrders(); toast(`#${o.num}: ${STATUS[sid].label}`); route(); openOrder(o.id);
    };
    $('[data-close]', modalBody).onclick = () => modal.close();
    $$('[data-status]', modalBody).forEach(b => b.onclick = () => setStatus(b.dataset.status));
    $('[data-next]', modalBody)?.addEventListener('click', () => setStatus(STATUSES[idx + 1].id));
    $('[data-paid]', modalBody).onclick = () => {
      o.paid = !o.paid; o.paidAt = o.paid ? Date.now() : null;
      persistOrders(); toast(o.paid ? 'To\'lov qayd etildi' : 'To\'lov bekor qilindi'); route(); openOrder(o.id);
    };
    $('[data-sms]', modalBody).onclick = () => {
      const text = o.status === 'ready'
        ? `Assalomu alaykum, ${o.customer.name}! Gilamlaringiz tayyor (buyurtma #${o.num}). Jami: ${money(orderTotal(o))}. ${settings.companyName}`
        : `Assalomu alaykum, ${o.customer.name}! Buyurtma #${o.num} holati: ${STATUS[o.status].label}. ${settings.companyName}`;
      location.href = `sms:${tel}?body=${encodeURIComponent(text)}`;
    };
    $('[data-receipt]', modalBody).onclick = () => {
      const lines = [
        `${settings.companyName}${settings.companyPhone ? ' · ' + settings.companyPhone : ''}`,
        `Buyurtma #${o.num} · ${fmtDateTime(o.createdAt)}`,
        `Mijoz: ${o.customer.name}, ${o.customer.phone}`, '',
        ...o.items.map(it => `${svcName(it.service)} ${num(it.w)}×${num(it.l)} = ${area(it)} m² — ${money(area(it) * it.price)}`),
        ...(o.delivery ? [`Yetkazib berish — ${money(o.deliveryFee)}`] : []),
        ...(o.discount ? [`Chegirma — −${money(o.discount)}`] : []),
        '', `JAMI: ${money(Math.max(0, orderTotal(o)))}`,
        `Holat: ${STATUS[o.status].label} · ${o.paid ? 'To\'langan' : 'To\'lanmagan'}`,
      ];
      copyText(lines.join('\n'), 'Chek nusxalandi — Telegramga joylashingiz mumkin');
    };
    $('[data-edit]', modalBody).onclick = () => { modal.close(); editingId = o.id; location.hash = 'tahrir'; };
    $('[data-delete]', modalBody).onclick = async () => {
      if (!await ask(`Buyurtma #${o.num} butunlay o'chirilsinmi?`, 'O\'chirish', true)) return;
      orders = orders.filter(x => x.id !== o.id); persistOrders(); modal.close(); toast('O\'chirildi'); route();
    };
    if (!modal.open) modal.showModal();
  }

  // ---------- Sozlamalar ----------
  function renderSettings() {
    view.innerHTML = `
      <h1>Sozlamalar</h1>
      <form id="sf" class="card">
        <div class="row2">
          <div class="field"><label for="cn">Korxona nomi</label><input id="cn" value="${esc(settings.companyName)}"></div>
          <div class="field"><label for="cp">Telefon</label><input id="cp" type="tel" value="${esc(settings.companyPhone)}"></div>
        </div>
        <div class="field"><label for="df">Yetkazib berish narxi (standart)</label><input id="df" type="number" min="0" step="1000" value="${settings.deliveryFee}"></div>
        <h2>Xizmatlar va narxlar (1 m² uchun)</h2>
        <div id="svc"></div>
        <button type="button" class="btn btn-sm" id="addSvc">+ Xizmat qo'shish</button>
        <div class="actions"><button class="btn btn-primary" type="submit">Saqlash</button></div>
      </form>
      <h2>Ma'lumotlar</h2>
      <div class="card">
        <p class="muted small" style="margin-top:0">Ma'lumotlar shu qurilmada saqlanadi. Zaxira nusxa olib turing.</p>
        <div class="actions" style="margin-top:0">
          <button class="btn" id="exp">📋 Zaxirani nusxalash</button>
          <button class="btn" id="csv">📊 Excel uchun nusxalash</button>
          <label class="btn" for="imp">⬆ Fayldan tiklash</label><input id="imp" type="file" accept="application/json,.json" hidden>
          <button class="btn" id="demo">Namuna qo'shish</button>
          ${orders.some(o => o.demo) ? '<button class="btn btn-danger" id="demoDel">Namunalarni o\'chirish</button>' : ''}
        </div>
        <div class="field" style="margin-top:14px"><label for="paste">Zaxira matnini joylab tiklash</label>
          <textarea id="paste" rows="3" placeholder="Nusxalangan zaxira matnini shu yerga joylang"></textarea></div>
        <div class="actions" style="margin-top:0"><button class="btn" id="pasteGo">Tiklash</button>
        </div>
      </div>`;

    let svcs = structuredClone(settings.services);
    const drawSvc = () => {
      $('#svc', view).innerHTML = svcs.map((s, i) => `
        <div class="item-row" style="grid-template-columns:1.6fr 1fr auto" data-i="${i}">
          <input data-k="name" value="${esc(s.name)}" aria-label="Xizmat nomi">
          <input data-k="price" type="number" min="0" step="500" value="${s.price}" aria-label="Narx">
          <button type="button" class="btn btn-icon" data-del aria-label="O'chirish" ${svcs.length < 2 ? 'disabled' : ''}>✕</button>
        </div>`).join('');
    };
    $('#svc', view).addEventListener('input', e => {
      const i = +e.target.closest('[data-i]').dataset.i; const k = e.target.dataset.k;
      svcs[i][k] = k === 'price' ? num(e.target.value) : e.target.value;
    });
    $('#svc', view).addEventListener('click', e => {
      if (e.target.closest('[data-del]')) { svcs.splice(+e.target.closest('[data-i]').dataset.i, 1); drawSvc(); }
    });
    $('#addSvc', view).onclick = () => { svcs.push({ id: uid(), name: '', price: 0 }); drawSvc(); };
    drawSvc();

    $('#sf', view).onsubmit = e => {
      e.preventDefault();
      settings = {
        ...settings,
        companyName: $('#cn', view).value.trim() || 'Toza Gilam',
        companyPhone: $('#cp', view).value.trim(),
        deliveryFee: num($('#df', view).value),
        services: svcs.filter(s => s.name.trim()).map(s => ({ ...s, name: s.name.trim() })),
      };
      if (!settings.services.length) settings.services = DEFAULT_SETTINGS.services;
      persistSettings(); toast('Sozlamalar saqlandi'); renderSettings();
    };

    $('#exp', view).onclick = () => copyText(JSON.stringify({ orders, settings }), 'Zaxira nusxalandi. Uni xavfsiz joyga saqlang (masalan, Telegram "Saqlangan xabarlar").');
    $('#csv', view).onclick = () => {
      const rows = [['№', 'Sana', 'Mijoz', 'Telefon', 'Manzil', 'Soni', 'm²', 'Summa', 'Holat', 'To\'langan']]
        .concat(orders.map(o => [o.num, fmtDate(o.createdAt), o.customer.name, o.customer.phone, o.customer.address,
          o.items.length, orderArea(o).toFixed(2), Math.round(orderTotal(o)), STATUS[o.status]?.label, o.paid ? 'Ha' : 'Yo\'q']));
      copyText(rows.map(r => r.map(c => String(c ?? '').replace(/[\t\n]/g, ' ')).join('\t')).join('\n'), 'Jadval nusxalandi — Excelga joylang (Ctrl+V)');
    };
    const restore = async text => {
      let data;
      try { data = JSON.parse(text); if (!Array.isArray(data.orders)) throw 0; }
      catch { return toast('Zaxira noto\'g\'ri: Toza Gilam zaxirasini joylang'); }
      if (!await ask(`${data.orders.length} ta buyurtma tiklansinmi? Hozirgi ma'lumotlar almashtiriladi.`, 'Tiklash', true)) return;
      orders = data.orders; if (data.settings) settings = { ...DEFAULT_SETTINGS, ...data.settings };
      persistOrders(); persistSettings(); toast('Tiklandi'); renderSettings();
    };
    $('#imp', view).onchange = async e => { const f = e.target.files[0]; if (f) restore(await f.text()); e.target.value = ''; };
    $('#pasteGo', view).onclick = () => restore($('#paste', view).value);
    $('#demoDel', view)?.addEventListener('click', async () => {
      if (!await ask('Namuna buyurtmalar o\'chirilsinmi? Sizning buyurtmalaringiz qoladi.', 'O\'chirish', true)) return;
      orders = orders.filter(o => !o.demo); persistOrders(); toast('Namunalar o\'chirildi'); renderSettings();
    });
    $('#demo', view).onclick = () => addDemo();
  }

  function addDemo() {
    {
      const names = [['Dilnoza Karimova', '+998 90 123 45 67', 'Chilonzor 9-kvartal, 12-uy'], ['Sardor Aliyev', '+998 93 555 11 22', 'Yunusobod 4-mavze'],
        ['Malika Rahimova', '+998 97 700 80 90', 'Sergeli, Yangi hayot'], ['Jasur Toshmatov', '+998 99 321 65 43', ''], ['Nodira Usmonova', '+998 91 444 22 33', 'Mirzo Ulug\'bek, 7-uy']];
      const st = ['new', 'wash', 'dry', 'ready', 'done'];
      names.forEach(([name, phone, address], i) => {
        const s1 = settings.services[i % settings.services.length], s2 = settings.services[(i + 1) % settings.services.length];
        orders.push({
          id: uid(), demo: true, num: nextNum(), createdAt: Date.now() - i * 86400000 * 1.3, status: st[i], paid: i === 4 || i === 2,
          paidAt: Date.now(), customer: { name, phone, address },
          items: [{ service: s1.id, price: s1.price, w: 2 + i % 2, l: 3 }, ...(i % 2 ? [] : [{ service: s2.id, price: s2.price, w: 1.5, l: 2.5 }])],
          delivery: i % 2 === 0, deliveryFee: settings.deliveryFee, discount: 0, note: '', history: [],
        });
      });
      persistOrders(); toast('Namuna ma\'lumot qo\'shildi'); if (location.hash === '#bosh') route(); else location.hash = 'bosh';
    };
  }

  route();
})();
