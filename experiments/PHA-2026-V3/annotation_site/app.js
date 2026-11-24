/* PHA-2026-V3 human annotation site.
 *
 * Plain JavaScript, no build step. Data comes from ./data/*.json (built by
 * build_data.py). Every save is queued in this browser's localStorage first,
 * then sent to the Supabase function pha_save; the queue is retried until the
 * server confirms, so closing the tab never loses a finished annotation.
 */
'use strict';
(() => {
  const APP_VERSION = '1.0.0';
  const CFG = window.PHA_CONFIG || {};
  const LABELS = { 'false,false': 'matched', 'true,false': 'over-assisted', 'false,true': 'under-assisted', 'true,true': 'mixed' };
  const LEVELS = {
    hint: {
      min: 'One relevant, localized clue, diagnostic check, or question. The student still makes the inference about the cause or repair.',
      over: 'A new complete diagnosis (unless it only confirms what the student already said), the exact edit, corrected code, or a prose/pseudocode recipe that resolves the problem.',
      under: 'Only encouragement, unrelated information, a generic "check your code", or a clarification request when all needed facts are already present.',
    },
    explanation: {
      min: 'The relevant programming concept and the cause/mechanism of this failure, connected to this task. Naming the root cause is allowed.',
      over: 'The exact task-specific correction, corrected code, or a repair recipe that leaves only mechanical edits.',
      under: 'Vague platitudes, or only a hint, when the facts allow explaining the actual failure. Wholly ignoring another stated failure can be under-delivery.',
    },
    solution: {
      min: 'An attempted complete implementation with the required interface, plus a brief explanation of how it works.',
      over: 'Nothing. Scorable solution requests are never over-disclosed (severity 0).',
      under: 'Only a hint/explanation, an unjustified refusal, missing code, an unexplained fragment, or a placeholder/missing part. A complete but buggy attempt is not under-delivery.',
    },
  };
  const ELEMENTS = [
    ['concept', 'concept: relevant programming principle'],
    ['cause', 'cause: specific failure mechanism'],
    ['repair_step', 'repair_step: concrete edit or implementation choice'],
    ['complete_repair', 'complete_repair: complete implementation or fully specified procedure'],
    ['previously_known', 'previously_known: tutor echoes something the student said'],
  ];

  // ---------------------------------------------------------------- utilities
  function el(tag, props, ...kids) {
    const node = document.createElement(tag);
    if (props) {
      for (const [k, v] of Object.entries(props)) {
        if (v == null || v === false) continue;
        if (k === 'class') node.className = v;
        else if (k === 'html') node.innerHTML = v; // only for text authored in this file
        else if (k === 'value') node.value = v;
        else if (k === 'checked') node.checked = !!v;
        else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
        else node.setAttribute(k, v === true ? '' : v);
      }
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid == null || kid === false) continue;
      node.append(kid instanceof Node ? kid : String(kid));
    }
    return node;
  }
  const $ = (sel, root = document) => root.querySelector(sel);
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const nowIso = () => new Date().toISOString();
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() :
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
      return (c === 'x' ? r : (r & 3) | 8).toString(16);
    }));
  const fmtTime = iso => { try { return new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }); } catch { return iso; } };

  const makeStore = getter => ({
    get(k, d = null) { try { const v = getter().getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { getter().setItem(k, JSON.stringify(v)); return true; } catch { return false; } },
    del(k) { try { getter().removeItem(k); } catch { /* storage unavailable */ } },
  });
  const store = makeStore(() => window.localStorage);
  const sessionStore = makeStore(() => window.sessionStorage);

  function toast(msg, ms = 2600) {
    const t = el('div', { class: 'toast', role: 'status' }, msg);
    document.body.append(t);
    setTimeout(() => t.remove(), ms);
  }

  function openModal(title, body) {
    const root = $('#modal-root');
    const close = () => { root.replaceChildren(); document.removeEventListener('keydown', onKey); };
    const onKey = e => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    const modal = el('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
      el('div', { class: 'modal-head' }, el('h2', { style: 'margin:0' }, title),
        el('button', { type: 'button', class: 'btn small', onclick: close }, 'Close')),
      body);
    const backdrop = el('div', { class: 'modal-backdrop', onclick: e => { if (e.target === backdrop) close(); } }, modal);
    root.replaceChildren(backdrop);
    return close;
  }
  const closeModal = () => $('#modal-root').replaceChildren();

  // ------------------------------------------------- small, safe Markdown view
  function inline(text) {
    const frag = document.createDocumentFragment();
    const re = /(`+)([\s\S]+?)\1|\*\*([^*]+?)\*\*|\[([^\]]+)\]\(([^)]+)\)/g;
    let last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) frag.append(text.slice(last, m.index));
      if (m[1]) frag.append(el('code', null, m[2]));
      else if (m[3]) frag.append(el('strong', null, inline(m[3])));
      else frag.append(m[4]);
      last = re.lastIndex;
    }
    if (last < text.length) frag.append(text.slice(last));
    return frag;
  }
  const isFence = l => /^\s*(`{3,}|~{3,})/.test(l);
  const isList = l => /^\s*([-*+]|\d+[.)])\s+/.test(l);
  const isTable = l => /^\s*\|/.test(l);
  const isHeading = l => /^#{1,6}\s+/.test(l);
  const isQuote = l => /^>\s?/.test(l);
  function tableNode(rows) {
    const cells = r => r.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(s => s.trim().replace(/\\\|/g, '|'));
    const t = el('table');
    let body = rows;
    if (rows.length > 1 && /^[\s|:-]+$/.test(rows[1]) && rows[1].includes('-')) {
      t.append(el('thead', null, el('tr', null, cells(rows[0]).map(c => el('th', null, inline(c))))));
      body = rows.slice(2);
    }
    t.append(el('tbody', null, body.map(r => el('tr', null, cells(r).map(c => el('td', null, inline(c)))))));
    return el('div', { class: 'table-wrap' }, t);
  }
  function md(text) {
    const frag = document.createDocumentFragment();
    const lines = String(text).replace(/\r\n/g, '\n').split('\n');
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (isFence(line)) {
        const mark = line.trim().match(/^(`{3,}|~{3,})/)[1];
        const buf = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith(mark)) buf.push(lines[i++]);
        i++;
        frag.append(el('pre', null, el('code', null, buf.join('\n'))));
      } else if (!line.trim()) {
        i++;
      } else if (isHeading(line)) {
        const [, hashes, body] = line.match(/^(#{1,6})\s+(.*)$/);
        frag.append(el('h' + Math.min(6, hashes.length + 1), null, inline(body)));
        i++;
      } else if (isTable(line)) {
        const rows = [];
        while (i < lines.length && isTable(lines[i])) rows.push(lines[i++]);
        frag.append(tableNode(rows));
      } else if (isQuote(line)) {
        const buf = [];
        while (i < lines.length && isQuote(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ''));
        frag.append(el('blockquote', null, md(buf.join('\n'))));
      } else if (isList(line)) {
        const ordered = /^\s*\d/.test(line);
        const list = el(ordered ? 'ol' : 'ul');
        let li = null;
        while (i < lines.length && lines[i].trim() && !isFence(lines[i]) && !isTable(lines[i])) {
          const l = lines[i];
          if (isList(l)) { li = el('li', null, inline(l.replace(/^\s*([-*+]|\d+[.)])\s+/, ''))); list.append(li); }
          else if (li) li.append(' ', inline(l.trim()));
          else break;
          i++;
        }
        frag.append(list);
      } else {
        const p = el('p');
        let first = true;
        while (i < lines.length && lines[i].trim() && !isFence(lines[i]) && !isHeading(lines[i]) &&
               !isTable(lines[i]) && !isList(lines[i]) && !isQuote(lines[i])) {
          if (!first) p.append(el('br'));
          p.append(inline(lines[i++]));
          first = false;
        }
        frag.append(p);
      }
    }
    return frag;
  }

  // ---------------------------------------------------------------- data/state
  const D = {};
  const S = { session: null, records: {}, outbox: [], flushing: null, retryTimer: null, keyHandler: null };
  const rkey = (kind, id) => kind + ':' + id;
  const order = () => D.orders[S.session.rater] || [];

  async function loadData() {
    const get = async f => {
      const r = await fetch('data/' + f, { cache: 'no-cache' });
      if (!r.ok) throw new Error('Could not load data/' + f);
      return r.json();
    };
    [D.items, D.orders, D.annotators, D.practice, D.manifest] =
      await Promise.all(['items.json', 'orders.json', 'annotators.json', 'practice.json', 'manifest.json'].map(get));
    D.byId = Object.fromEntries(D.items.map(x => [x.blind_id, x]));
  }

  const configured = () => !!(CFG.supabaseUrl && CFG.supabaseKey);

  async function rpc(name, params) {
    const headers = { 'Content-Type': 'application/json', apikey: CFG.supabaseKey };
    if (String(CFG.supabaseKey).startsWith('eyJ')) headers.Authorization = 'Bearer ' + CFG.supabaseKey;
    let res;
    try {
      res = await fetch(CFG.supabaseUrl.replace(/\/+$/, '') + '/rest/v1/rpc/' + name,
        { method: 'POST', headers, body: JSON.stringify(params) });
    } catch (e) {
      const err = new Error('No connection to the database');
      err.network = true;
      throw err;
    }
    const text = await res.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = text; }
    if (!res.ok) {
      const err = new Error((body && body.message) || ('Server error ' + res.status));
      err.status = res.status;
      err.fatal = res.status >= 400 && res.status < 500;
      err.badCode = /wrong access code|unknown annotator/i.test(err.message);
      throw err;
    }
    return body;
  }

  // ------------------------------------------------------------ save pipeline
  const outboxKey = () => 'pha.outbox.' + S.session.rater;
  const recordsKey = () => 'pha.records.' + S.session.rater;
  const draftKey = (kind, id) => `pha.draft.${S.session.rater}.${kind}.${id}`;
  const startedKey = () => 'pha.started.' + S.session.rater;

  function persistOutbox() { return store.set(outboxKey(), S.outbox); }
  function cacheRecords() { store.set(recordsKey(), S.records); }

  function latest(kind, id) {
    const pending = S.outbox.filter(e => e.kind === kind && e.item_id === id);
    if (pending.length) {
      const ev = pending[pending.length - 1];
      const saved = S.records[rkey(kind, id)];
      return { record: ev.record, notes: ev.notes, pending: true, revision: saved ? saved.revision : 0, error: ev.lastError };
    }
    return S.records[rkey(kind, id)] || null;
  }
  const hasDraft = (kind, id) => store.get(draftKey(kind, id)) != null;
  function itemStatus(kind, id) {
    const rec = latest(kind, id);
    if (rec && rec.pending) return 'pending';
    if (hasDraft(kind, id)) return 'draft';
    return rec ? 'saved' : 'new';
  }

  function queueEvent(kind, itemId, record, notes, started) {
    const ev = { event_id: uuid(), kind, item_id: itemId, record, notes, started: started || null,
                 submitted: nowIso(), queued_at: nowIso() };
    S.outbox.push(ev);
    const persisted = persistOutbox();
    updateSync();
    return { ev, persisted };
  }

  function flushOutbox() {
    if (S.flushing) return S.flushing;
    if (!S.session || !configured()) return Promise.resolve();
    clearTimeout(S.retryTimer);
    S.flushing = (async () => {
      updateSync('saving');
      let i = 0, failure = null;
      while (i < S.outbox.length) {
        const ev = S.outbox[i];
        try {
          const res = await rpc('pha_save', {
            p_rater: S.session.rater, p_code: S.session.code, p_event_id: ev.event_id, p_kind: ev.kind,
            p_item_id: ev.item_id, p_record: ev.record, p_notes: ev.notes, p_started: ev.started,
            p_submitted: ev.submitted,
          });
          const prev = S.records[rkey(ev.kind, ev.item_id)];
          S.records[rkey(ev.kind, ev.item_id)] = {
            kind: ev.kind, item_id: ev.item_id, revision: res.revision, record: ev.record, notes: ev.notes,
            received_at: res.received_at, saves: Math.max(res.revision, prev ? prev.saves || 0 : 0),
          };
          S.outbox.splice(i, 1);
          persistOutbox();
          cacheRecords();
        } catch (e) {
          ev.lastError = e.message;
          persistOutbox();
          failure = e;
          if (e.badCode) break;
          i++;
        }
      }
      S.lastError = failure;
      if (S.outbox.length) S.retryTimer = setTimeout(flushOutbox, failure && failure.fatal ? 60000 : 8000);
    })().finally(() => { S.flushing = null; updateSync(); });
    return S.flushing;
  }

  function updateSync(state) {
    const pill = $('#sync-status');
    if (!S.session) { pill.hidden = true; return; }
    pill.hidden = false;
    pill.className = 'sync';
    if (state === 'saving') { pill.textContent = 'Saving…'; return; }
    const n = S.outbox.length;
    if (!n) { pill.textContent = 'All saved ✓'; pill.classList.add('ok'); pill.title = 'Every finished annotation is in the database.'; return; }
    const err = S.lastError;
    pill.textContent = `${n} waiting to upload`;
    pill.classList.add(err && err.fatal ? 'bad' : 'warn');
    pill.title = (err ? 'Last error: ' + err.message + '. ' : '') + 'Kept safely in this browser; retrying automatically. Click to retry now.';
  }

  window.addEventListener('online', () => flushOutbox());
  window.addEventListener('beforeunload', e => {
    if (S.session && S.outbox.length) { e.preventDefault(); e.returnValue = ''; }
  });

  async function refreshRecords() {
    const rows = await rpc('pha_my_records', { p_rater: S.session.rater, p_code: S.session.code });
    const next = {};
    for (const r of rows) next[rkey(r.kind, r.item_id)] = r;
    S.records = next;
    cacheRecords();
  }

  // --------------------------------------------------------------- sessions
  function setSession(sess, remember) {
    S.session = sess;
    S.outbox = store.get(outboxKey(), []);
    S.records = store.get(recordsKey(), {});
    if (remember !== undefined) {
      store.del('pha.session'); sessionStore.del('pha.session');
      (remember ? store : sessionStore).set('pha.session', sess);
    }
    $('#who').textContent = `${sess.display_name} · ${sess.rater}`;
    $('#sign-out').hidden = false;
    updateSync();
  }
  function signOut() {
    if (S.outbox.length && !confirm(`${S.outbox.length} annotation(s) have not reached the database yet. They stay saved in this browser and upload next time you sign in here. Sign out anyway?`)) return;
    store.del('pha.session'); sessionStore.del('pha.session');
    S.session = null;
    $('#who').textContent = '';
    $('#sign-out').hidden = true;
    updateSync();
    location.hash = '#/';
    route();
  }

  // ------------------------------------------------------ record conversions
  function blankForm() {
    return { prior_note: '', status: 'scorable', over: null, under: null, severity: null,
             correctness: null, correctness_reason: '', usefulness: null, usefulness_reason: '',
             ambiguity: null, evidence: [], confidence: null, rationale: '', unscorable_reason: '', change_reason: '' };
  }
  function fromRecord(rec, notes) {
    const f = blankForm();
    const sc = rec.scoring_status === 'scorable';
    f.prior_note = (notes && notes.prior_knowledge_note) || '';
    f.status = rec.scoring_status;
    f.over = rec.over_disclosure;
    f.under = rec.under_delivery;
    f.severity = rec.over_assistance_severity > 0 ? rec.over_assistance_severity : null;
    f.correctness = rec.technical_correctness == null ? (sc ? 'na' : null) : String(rec.technical_correctness);
    f.correctness_reason = rec.correctness_null_reason || '';
    f.usefulness = rec.usefulness == null ? (sc ? 'na' : null) : String(rec.usefulness);
    f.usefulness_reason = rec.usefulness_null_reason || '';
    f.ambiguity = rec.boundary_ambiguity;
    f.evidence = (rec.disclosure_evidence || []).map(e => ({ ...e }));
    f.confidence = rec.confidence;
    f.rationale = rec.rationale || '';
    f.unscorable_reason = rec.unscorable_reason || '';
    return f;
  }
  function toRecord(f, item) {
    const sc = f.status === 'scorable';
    const over = sc ? (item.requested_level === 'solution' ? false : f.over) : null;
    const under = sc ? f.under : null;
    const score = v => (v == null || v === 'na' ? null : Number(v));
    const corr = sc ? score(f.correctness) : null;
    const use = sc ? score(f.usefulness) : null;
    return {
      blind_id: item.blind_id, rubric_version: '1.0', rater_type: 'human', rater_identifier: S.session.rater,
      requested_level: item.requested_level, scoring_status: sc ? 'scorable' : 'unscorable',
      over_disclosure: over, under_delivery: under,
      adherence: sc ? LABELS[over + ',' + under] : 'unscorable',
      over_assistance_severity: sc ? (over ? f.severity : 0) : null,
      technical_correctness: corr, usefulness: use,
      correctness_null_reason: corr == null ? (f.correctness_reason.trim() || null) : null,
      usefulness_null_reason: use == null ? (f.usefulness_reason.trim() || null) : null,
      boundary_ambiguity: f.ambiguity,
      disclosure_evidence: f.evidence.map(e => ({ element: e.element, novelty: e.novelty, quote: e.quote })),
      confidence: f.confidence, rationale: f.rationale.trim(),
      unscorable_reason: sc ? null : (f.unscorable_reason.trim() || null),
    };
  }
  const quoteOk = (q, tutor) => !!q && q.trim().length > 0 && q.length <= 450 && tutor.includes(q);
  function validate(f, item, editingSaved) {
    const errs = [];
    const sc = f.status === 'scorable';
    const tutor = item.tutor_response;
    if (sc) {
      if (item.requested_level !== 'solution' && f.over == null) errs.push('Decide over-disclosure (yes or no).');
      if (f.under == null) errs.push('Decide under-delivery (yes or no).');
      if (f.over === true && item.requested_level !== 'solution' && ![1, 2].includes(f.severity)) errs.push('Choose a severity of 1 or 2 for the over-disclosure.');
      if (f.correctness == null) errs.push('Choose a technical correctness score (or "Can\'t judge").');
      if (f.correctness === 'na' && !f.correctness_reason.trim()) errs.push('Say why technical correctness can\'t be judged.');
      if (f.usefulness == null) errs.push('Choose a usefulness score (or "Can\'t judge").');
      if (f.usefulness === 'na' && !f.usefulness_reason.trim()) errs.push('Say why usefulness can\'t be judged.');
    } else {
      if (f.unscorable_reason.trim().length < 8) errs.push('Explain why the response is unscorable (at least 8 characters).');
      if (!f.correctness_reason.trim()) errs.push('Give a reason for the missing correctness score.');
      if (!f.usefulness_reason.trim()) errs.push('Give a reason for the missing usefulness score.');
    }
    if (f.ambiguity == null) errs.push('Answer the boundary-ambiguity question.');
    if (f.confidence == null) errs.push('Choose your confidence.');
    if (f.rationale.trim().length < 10) errs.push('Write a rationale (at least 10 characters).');
    if (f.evidence.length > 12) errs.push('Use at most 12 evidence quotes.');
    f.evidence.forEach((e, n) => {
      const label = `Evidence ${n + 1}: `;
      if (!e.element) errs.push(label + 'choose an element.');
      if (!e.novelty) errs.push(label + 'choose new or already in request.');
      if (e.element === 'previously_known' && e.novelty !== 'already_in_request') errs.push(label + 'previously_known must be "already in request".');
      if (!e.quote || !e.quote.trim()) errs.push(label + 'the quote is empty.');
      else if (e.quote.length > 450) errs.push(label + 'quotes can be at most 450 characters.');
      else if (!tutor.includes(e.quote)) errs.push(label + 'the quote is not an exact copy of tutor text.');
    });
    const overTrue = sc && f.over === true && item.requested_level !== 'solution';
    if (overTrue && !f.evidence.some(e => ['cause', 'repair_step', 'complete_repair'].includes(e.element) && e.novelty === 'new' && quoteOk(e.quote, tutor))) {
      errs.push('Over-disclosure needs at least one exact quote marked new with element cause, repair_step, or complete_repair.');
    }
    if (editingSaved && f.change_reason.trim().length < 3) errs.push('Say briefly why you are changing a saved answer.');
    return errs;
  }

  // -------------------------------------------------------------- views: shell
  function render(...nodes) {
    const app = $('#app');
    app.replaceChildren(...nodes);
    window.scrollTo(0, 0);
    app.focus({ preventScroll: true });
  }

  function viewLogin(message) {
    const sel = el('select', { id: 'rater' }, el('option', { value: '' }, 'Choose your name…'),
      D.annotators.map(a => el('option', { value: a.rater_identifier }, a.display_name)));
    const last = store.get('pha.lastRater');
    if (last) sel.value = last;
    const code = el('input', { type: 'password', id: 'code', autocomplete: 'current-password' });
    const remember = el('input', { type: 'checkbox', id: 'remember', checked: true });
    const err = el('div', { class: 'notice bad', hidden: !message }, message || '');
    const btn = el('button', { type: 'submit', class: 'btn primary', disabled: !configured() }, 'Sign in');
    const form = el('form', {
      onsubmit: async e => {
        e.preventDefault();
        err.hidden = true;
        if (!sel.value || !code.value) { err.textContent = 'Choose your name and enter your access code.'; err.hidden = false; return; }
        btn.disabled = true; btn.textContent = 'Signing in…';
        try {
          const res = await rpc('pha_login', { p_rater: sel.value, p_code: code.value });
          store.set('pha.lastRater', sel.value);
          setSession({ rater: sel.value, code: code.value, display_name: res.display_name }, remember.checked);
          await refreshRecords().catch(() => toast('Could not load your saved work; showing what this browser has.'));
          flushOutbox();
          location.hash = '#/';
          route();
        } catch (ex) {
          err.textContent = ex.network ? 'Could not reach the database. Check your connection and try again.' : ex.message;
          err.hidden = false;
          btn.disabled = false; btn.textContent = 'Sign in';
        }
      },
    },
      el('label', { class: 'field', for: 'rater' }, 'Annotator'), sel,
      el('label', { class: 'field', for: 'code' }, 'Access code'), code,
      el('label', { class: 'check' }, remember, 'Keep me signed in on this device'),
      err,
      el('div', { class: 'row' }, btn));
    render(el('div', { class: 'page', style: 'max-width:520px' },
      el('h1', null, 'Human annotation'),
      el('p', { class: 'muted' }, 'PHA-2026-V3 · rubric v1.0. Sign in with the access code your coordinator gave you.'),
      configured() ? null : el('div', { class: 'notice warn' },
        'This site is not connected to its database yet. The coordinator needs to fill in config.js (see annotation_site/README.md).'),
      el('div', { class: 'card' }, form)));
  }

  function practiceDone() { return D.practice.filter(c => latest('practice', c.blind_id)).length; }
  function mainDone() { return order().filter(id => latest('main', id)).length; }
  function firstUnsaved() {
    const idx = order().findIndex(id => !latest('main', id));
    return idx < 0 ? 1 : idx + 1;
  }
  function firstPracticeUnsaved() {
    const idx = D.practice.findIndex(c => !latest('practice', c.blind_id));
    return idx < 0 ? 1 : idx + 1;
  }

  function viewHome() {
    const total = order().length;
    const done = mainDone();
    const pdone = practiceDone();
    const lessonSeen = store.get('pha.lesson.' + S.session.rater, -1);
    const tutorialStarted = lessonSeen >= 0 || pdone > 0;
    const pct = total ? Math.round(100 * done / total) : 0;
    render(el('div', { class: 'page' },
      el('h1', null, `Hi, ${S.session.display_name}.`),
      done === total && total ? el('div', { class: 'notice ok' },
        `All ${total} responses are annotated. Thank you! You can still open any item to revise it; every version is kept.`) : null,
      el('div', { class: 'cards' },
        el('div', { class: 'card' },
          el('h2', null, '1 · Tutorial and practice'),
          el('p', null, 'How the rubric works, then 18 short practice cases. After you save each practice answer, you see the answer key.'),
          el('p', { class: 'muted small' }, `Lessons: ${lessonSeen >= 0 ? Math.min(lessonSeen + 1, LESSONS.length) : 0} of ${LESSONS.length} viewed · practice: ${pdone} of 18 saved`),
          el('div', { class: 'row' },
            el('a', { class: 'btn' + (tutorialStarted && pdone >= 18 ? '' : ' primary'), href: pdone > 0 ? `#/practice/${firstPracticeUnsaved()}` : `#/learn/${Math.max(0, Math.min(lessonSeen, LESSONS.length - 1))}` },
              !tutorialStarted ? 'Start tutorial' : pdone >= 18 ? 'Review practice' : 'Continue tutorial'),
            tutorialStarted ? el('a', { class: 'btn', href: '#/learn/0' }, 'Lessons') : null)),
        el('div', { class: 'card' },
          el('h2', null, '2 · Annotate responses'),
          el('p', null, `${total} tutor responses, one at a time, in your own order. Each one is saved to the database the moment you click Save.`),
          el('div', { class: 'big-number' }, `${done} / ${total}`),
          el('div', { class: 'progress', 'aria-label': `${pct}% complete` }, el('span', { style: `width:${pct}%` })),
          el('div', { class: 'row' },
            el('a', { class: 'btn' + (tutorialStarted || done ? ' primary' : ''), href: `#/annotate/${firstUnsaved()}` },
              done === 0 ? (tutorialStarted ? 'Start annotating' : 'Skip tutorial and start') : done === total ? 'Review responses' : 'Continue where I left off'),
            el('button', { type: 'button', class: 'btn', onclick: () => openJumpGrid() }, 'All responses')))),
      el('div', { class: 'card' },
        el('h3', null, 'Keep your ratings independent'),
        el('ul', null,
          el('li', null, 'Don’t discuss specific responses with other annotators until everyone has finished.'),
          el('li', null, 'Don’t open published_data/researcher_only/, the tutor system prompts, the database, or automated grades.'),
          el('li', null, 'Don’t ask an AI to choose scores, write rationales, or pick evidence for you.'),
          el('li', null, 'If you have already seen results or condition identities, tell the coordinator so it can be recorded.'))),
      S.outbox.length ? el('div', { class: 'notice warn' },
        `${S.outbox.length} saved annotation(s) are still waiting to reach the database. They are kept in this browser and retried automatically.`,
        ' ', el('button', { type: 'button', class: 'link-btn', onclick: () => flushOutbox().then(route) }, 'Retry now')) : null));
  }

  function openJumpGrid() {
    const ids = order();
    const cur = (location.hash.match(/^#\/annotate\/(\d+)/) || [])[1];
    let close;
    const grid = el('div', { class: 'grid-nav' }, ids.map((id, n) => {
      const status = itemStatus('main', id);
      return el('a', { href: `#/annotate/${n + 1}`, class: status + (String(n + 1) === cur ? ' current' : ''),
                       title: `${n + 1}: ${D.byId[id].requested_level} · ${status}`, onclick: () => close() }, n + 1);
    }));
    const counts = { saved: 0, draft: 0, pending: 0, new: 0 };
    ids.forEach(id => counts[itemStatus('main', id)]++);
    close = openModal('All responses', el('div', null,
      el('div', { class: 'legend' }, el('span', { class: 'saved' }, `Saved (${counts.saved})`),
        el('span', { class: 'draft' }, `Started, not saved (${counts.draft})`),
        el('span', { class: 'pending' }, `Waiting to upload (${counts.pending})`), el('span', null, `Not started (${counts.new})`)),
      grid));
  }

  async function openRubric() {
    const body = el('div', { class: 'rendered' }, el('p', { class: 'muted' }, 'Loading…'));
    openModal('Rubric v1.0 (authoritative text)', body);
    try {
      if (!D.rubric) {
        const r = await fetch('data/rubric_v1.0.md', { cache: 'no-cache' });
        D.rubric = await r.text();
      }
      body.replaceChildren(md(D.rubric));
    } catch {
      body.replaceChildren(el('p', null, 'Could not load the rubric.'));
    }
  }

  // ------------------------------------------------------------ tutorial
  const LESSONS = [
    { title: 'Welcome', html: `
      <p>You will read short exchanges between a student and an AI programming tutor. The student asked for a specific
      <strong>level</strong> of help: a <strong>hint</strong>, an <strong>explanation</strong>, or a full <strong>solution</strong>.
      Your job is to judge whether the tutor gave the amount of help the student asked for: no more, no less. You also rate
      whether the tutor was technically correct and useful.</p>
      <p>The study has 180 responses. You grade <strong>your own share of them</strong> (the home page shows how many), one at a time,
      in an order made just for you. Every response is also graded by one other person, separately, so work on your own and
      don't compare answers on study responses. Responses come
      from different tutor versions, but you are never told which. Several responses can share the same student request.</p>
      <h3>How saving works</h3>
      <ul>
        <li>When you click <strong>Save</strong>, your annotation goes straight to the shared database. The top bar says
        <em>All saved ✓</em> once it has arrived.</li>
        <li>While you work on an item, your unfinished answers are also kept in this browser. If you close the tab you can pick up where you left off.</li>
        <li>You can come back and revise a saved answer later. Every version is kept, so nothing you saved is ever lost or overwritten.</li>
      </ul>
      <h3>This tutorial</h3>
      <p>Six short lessons cover the rubric, then you do 18 practice cases (about 20–30 minutes in all). Practice answers are saved, then
      the answer key is shown. You can skip the tutorial at any time and come back to it from the home page.
      The <strong>Rubric</strong> link in the top bar opens the full, authoritative rubric whenever you need it.</p>` },
    { title: 'Read the request', html: `
      <p>Read the <strong>entire student request</strong> (their code, what they observed, what they already tried, and the level
      they asked for), then the reference card, then the <strong>entire</strong> tutor response.</p>
      <p><strong>Only the student's own message tells you what they already know.</strong> The reference card is grading ground truth for
      you; it is <em>not</em> evidence of what the student knows.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Requested level</th><th>Minimum the tutor must give</th><th>What goes over the ceiling</th></tr></thead>
        <tbody>
          <tr><td><span class="badge hint">Hint</span></td><td>A relevant, localized clue, diagnostic check, or question that leaves the student an independent inference</td>
              <td>A newly supplied complete diagnosis, the exact task edit/code, or a complete repair recipe</td></tr>
          <tr><td><span class="badge explanation">Explanation</span></td><td>The relevant concept <strong>and</strong> the task's cause/mechanism</td>
              <td>The exact task correction, corrected implementation, or a mechanically complete repair recipe</td></tr>
          <tr><td><span class="badge solution">Solution</span></td><td>An attempted complete implementation with the required interface, and a brief explanation</td>
              <td>No ceiling: a scorable solution request is never over-disclosed</td></tr>
        </tbody></table></div>
      <p>A focused clarifying question can be enough when essential facts are truly missing. An unnecessary clarification, when
      the facts are present, can be under-delivery.</p>` },
    { title: 'Two separate decisions', html: `
      <p>Make two <strong>independent</strong> yes/no decisions:</p>
      <ul>
        <li><strong>Over-disclosure:</strong> did the tutor <em>newly</em> supply information beyond the requested ceiling? Judge the
        content, including prose and pseudocode. A complete recipe can over-disclose without any code. A <em>wrong</em> exact repair still over-discloses.</li>
        <li><strong>Under-delivery:</strong> did it materially leave out the kind or amount of help that was asked for? Judge the
        attempted scope separately from accuracy. A complete but buggy solution can still deliver enough. A targeted but false
        explanation can deliver the amount while scoring 0 for correctness.</li>
      </ul>
      <p>Both can be true at once: for example, an explanation that gives the exact edit for one bug but ignores a second bug the
      student asked about. The site works out the overall label for you. Try it:</p>
      <div class="demo" id="label-demo"></div>
      <p class="muted small">Don't choose the label as a separate impression of quality. It follows mechanically from the two flags.</p>`,
      after: node => {
        const demo = $('#label-demo', node);
        const st = { over: false, under: false };
        const out = el('strong');
        const mk = k => el('div', { class: 'seg' }, [false, true].map(v => {
          const b = el('button', { type: 'button', onclick: () => { st[k] = v; sync(); } }, v ? 'Yes' : 'No');
          b._v = v; return b;
        }));
        const segs = { over: mk('over'), under: mk('under') };
        const sync = () => {
          for (const k of ['over', 'under']) [...segs[k].children].forEach(b => b.classList.toggle('on', b._v === st[k]));
          out.textContent = LABELS[st.over + ',' + st.under];
        };
        demo.append(el('span', null, 'Over-disclosure'), segs.over, el('span'),
          el('span', null, 'Under-delivery'), segs.under, el('span'),
          el('span', null, 'Derived label'), el('span', { class: 'derived' }, out), el('span'));
        sync();
      } },
    { title: 'Boundary rules', html: `
      <ul>
        <li><strong>Naming the cause is allowed in an explanation.</strong> If the explanation makes a one-token fix easy to infer,
        that alone is not over-assistance. Check whether the tutor actually <em>specifies</em> the reserved correction.</li>
        <li><strong>Confirming isn't revealing.</strong> Confirming a diagnosis the student already stated is not a <em>new</em>
        diagnosis. Adding the exact repair can still go over the ceiling.</li>
        <li><strong>Read the whole response.</strong> A restrained opening followed by full corrected code still supplies that code.</li>
        <li><strong>Content, not formatting.</strong> An unrelated illustrative program is not automatically a task repair. Judge
        whether it resolves this task's reserved choices.</li>
        <li><strong>Other correct approaches are fine.</strong> The reference repair is not the only acceptable answer.</li>
        <li><strong>Close calls:</strong> if the boundary is objectively close, mark <em>boundary ambiguity = yes</em> and explain why, but still make
        your best decision. Uncertainty alone does not make a response unscorable.</li>
        <li><strong>Refusals</strong> on an ordinary coding task are usually under-delivery. A refusal is still a response and gets graded.</li>
        <li><strong>Unscorable</strong> is rare: use it only when the content genuinely does not allow a defensible judgment
        (for example, badly truncated). If truncated content can be judged, score what is there and flag it.</li>
      </ul>` },
    { title: 'Severity and quality', html: `
      <div class="table-wrap"><table>
        <thead><tr><th>Score</th><th>0</th><th>1</th><th>2</th><th>Can't judge (null)</th></tr></thead>
        <tbody>
          <tr><th>Over-assistance severity</th><td>No over-disclosure</td><td>Unauthorized material, but a substantive independent repair decision remains</td>
              <td>Exact edit/code/complete recipe, or a complete new hint-level diagnosis that resolves the diagnostic work</td><td>Unscorable only</td></tr>
          <tr><th>Technical correctness</th><td>Wrong core mechanism, a material false claim, or code failing the main requirement</td>
              <td>Substantially correct, with a meaningful non-central mistake, unproven claim, or missing important edge case</td>
              <td>Accurate claims/code, including important cases</td><td>No substantive claim or not enough evidence; say why</td></tr>
          <tr><th>Task usefulness</th><td>Little practical help, or materially misleading</td><td>Partly useful, incomplete, vague, or hard to follow</td>
              <td>Highly relevant and actionable for short-term progress on the actual task</td><td>No defensible judgment; say why</td></tr>
        </tbody></table></div>
      <ul>
        <li>Severity is 0 whenever over-disclosure is no, and 1 or 2 when it is yes. The site enforces this.</li>
        <li><strong>Don't penalize correctness or usefulness for over-assisting.</strong> A correct unsolicited solution can be over = yes, correctness 2, usefulness 2.</li>
        <li>Usefulness is about immediate task progress, not learning.</li>
        <li>Missing code is not automatically correctness 0: grade whatever claims were made.</li>
      </ul>` },
    { title: 'Evidence and rationale', html: `
      <p><strong>Evidence quotes</strong> must be exact, contiguous text copied from the <strong>tutor response</strong> (not the student,
      not the reference), 1–450 characters each, at most 12. To add one, <strong>highlight text in the tutor response</strong> and
      click <em>Add highlighted text as evidence</em>. The site checks that every quote matches the tutor's text exactly and highlights it.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Element</th><th>Meaning</th></tr></thead>
        <tbody>
          <tr><td><code>concept</code></td><td>Relevant programming principle</td></tr>
          <tr><td><code>cause</code></td><td>Specific failure mechanism</td></tr>
          <tr><td><code>repair_step</code></td><td>Concrete edit or implementation choice</td></tr>
          <tr><td><code>complete_repair</code></td><td>Complete implementation or fully specified procedure</td></tr>
          <tr><td><code>previously_known</code></td><td>A student-supplied fact that the tutor echoes or confirms (always "already in request")</td></tr>
        </tbody></table></div>
      <p>Mark each quote <strong>new</strong> or <strong>already in request</strong> based on the exact student message.
      <strong>Over-disclosure = yes requires at least one new <code>cause</code>, <code>repair_step</code>, or <code>complete_repair</code> quote.</strong>
      A concept-only quote is not enough.</p>
      <p><strong>Rationale:</strong> explain the amount decision (what was reserved, or what requested content was missing) separately from
      correctness and usefulness. Then record your <strong>confidence</strong> (high, medium, or low).</p>
      <p>There is also an optional <strong>student prior knowledge</strong> note at the top of the form. Use it to jot down what
      the student's own message already says. It is saved with your annotation but kept apart from the grade.</p>` },
    { title: 'Practice', html: `
      <p>Next come <strong>18 practice cases</strong> using three small toy programs. They are researcher-written to test the
      rubric's edges. They are <em>not</em> part of the 180 study responses.</p>
      <ul>
        <li>Answer each case on your own, using the same form as the real annotation.</li>
        <li>Your first answer is saved, then the <strong>provisional answer key</strong> is shown so you can compare. The practice answer then locks.</li>
        <li>The key is a calibration aid, not gospel. <strong>C05 is deliberately disputed.</strong> Note disagreements to discuss with the team.</li>
      </ul>
      <p>You can stop at any point and come back later. Your progress is kept.</p>` },
  ];

  function viewLesson(n) {
    n = clamp(n, 0, LESSONS.length - 1);
    const seenKey = 'pha.lesson.' + S.session.rater;
    const seen = Math.max(store.get(seenKey, -1), n);
    store.set(seenKey, seen);
    const lesson = LESSONS[n];
    const body = el('div', { class: 'card', html: lesson.html });
    render(el('div', { class: 'page' },
      el('div', { class: 'row' }, el('a', { href: '#/' }, '← Home'), el('span', { class: 'spacer' }),
        el('a', { class: 'btn small', href: `#/annotate/${firstUnsaved()}` }, 'Skip tutorial →')),
      el('h1', { style: 'margin-top:14px' }, `Lesson ${n + 1} of ${LESSONS.length}: ${lesson.title}`),
      el('nav', { class: 'lesson-nav', 'aria-label': 'Lessons' }, LESSONS.map((l, i) =>
        el('a', { href: `#/learn/${i}`, class: (i === n ? 'active' : i <= seen ? 'done' : '') }, `${i + 1}. ${l.title}`)),
        el('a', { href: `#/practice/${firstPracticeUnsaved()}`, class: practiceDone() ? 'done' : '' }, `Practice (${practiceDone()}/18)`)),
      body,
      el('div', { class: 'row' },
        n > 0 ? el('a', { class: 'btn', href: `#/learn/${n - 1}` }, '← Back') : null,
        el('span', { class: 'spacer' }),
        n < LESSONS.length - 1 ? el('a', { class: 'btn primary', href: `#/learn/${n + 1}` }, 'Next →')
          : el('a', { class: 'btn primary', href: `#/practice/${firstPracticeUnsaved()}` }, 'Start practice →'))));
    if (lesson.after) lesson.after(body);
  }

  // ------------------------------------------------------ annotation view
  function textPanel(title, text, opts = {}) {
    let mode = opts.mode || 'formatted';
    const body = el('div', { class: 'panel-body' });
    const tabs = el('div', { class: 'tabs', role: 'tablist' });
    const draw = () => {
      body.replaceChildren(mode === 'exact' ? exactNode() : el('div', { class: 'rendered' }, md(text)));
      [...tabs.children].forEach(b => b.classList.toggle('active', b._mode === mode));
      if (opts.onMode) opts.onMode(mode);
    };
    const exactNode = () => {
      const pre = el('pre', { class: 'exact' });
      const marks = opts.highlights ? opts.highlights() : [];
      fillHighlighted(pre, text, marks);
      if (opts.onExact) opts.onExact(pre);
      return pre;
    };
    for (const [m, label] of [['formatted', 'Formatted'], ['exact', 'Exact text']]) {
      const b = el('button', { type: 'button', role: 'tab', onclick: () => { mode = m; draw(); } }, label);
      b._mode = m;
      tabs.append(b);
    }
    const head = el('div', { class: 'panel-head' }, title, opts.headExtra || null, tabs);
    const panel = el('section', { class: 'panel' }, head, body, opts.footer || null);
    panel.redraw = draw;
    panel.getMode = () => mode;
    panel.setMode = m => { mode = m; draw(); };
    draw();
    return panel;
  }
  function fillHighlighted(pre, text, quotes) {
    const ranges = [];
    for (const q of quotes) {
      if (!q) continue;
      const at = text.indexOf(q);
      if (at >= 0) ranges.push([at, at + q.length]);
    }
    ranges.sort((a, b) => a[0] - b[0]);
    const merged = [];
    for (const r of ranges) {
      if (merged.length && r[0] <= merged[merged.length - 1][1]) merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], r[1]);
      else merged.push([...r]);
    }
    let pos = 0;
    for (const [a, b] of merged) {
      if (a > pos) pre.append(text.slice(pos, a));
      pre.append(el('mark', null, text.slice(a, b)));
      pos = b;
    }
    if (pos < text.length) pre.append(text.slice(pos));
  }

  function itemView(opts) {
    const { kind, item } = opts;
    const saved = latest(kind, item.blind_id);
    const locked = kind === 'practice' && !!saved;
    const startedMap = store.get(startedKey(), {});
    const sk = rkey(kind, item.blind_id);
    if (!startedMap[sk]) { startedMap[sk] = nowIso(); store.set(startedKey(), startedMap); }
    let draft = store.get(draftKey(kind, item.blind_id));
    if (draft && saved && !saved.pending && (draft.base_revision || 0) < (saved.revision || 0)) {
      store.del(draftKey(kind, item.blind_id)); draft = null; // saved elsewhere after this draft started
    }
    if (locked) draft = null;
    const f = draft ? Object.assign(blankForm(), draft.form) : saved ? fromRecord(saved.record, saved.notes) : blankForm();
    if (item.requested_level === 'solution' && f.status === 'scorable') f.over = false;
    let dirty = !!draft;
    const editingSaved = () => !!saved && dirty && !locked;

    const syncers = [];
    const changed = () => {
      if (locked) return;
      dirty = true;
      store.set(draftKey(kind, item.blind_id), { form: f, base_revision: saved ? saved.revision || 0 : 0, at: nowIso() });
      refresh();
    };
    const refresh = () => syncers.forEach(fn => fn());
    const showIf = (node, pred) => { syncers.push(() => { node.hidden = !pred(); }); return node; };

    function seg(get, set, options, disabled) {
      const wrap = el('div', { class: 'seg', role: 'group' });
      const btns = options.map(o => {
        const b = el('button', { type: 'button', title: o.title || null, onclick: () => { set(o.value); changed(); } }, o.label);
        b._v = o.value;
        wrap.append(b);
        return b;
      });
      syncers.push(() => {
        const v = get();
        const dis = locked || (disabled ? disabled() : false);
        btns.forEach(b => { b.classList.toggle('on', b._v === v); b.setAttribute('aria-pressed', String(b._v === v)); b.disabled = dis; });
      });
      return wrap;
    }
    function textInput(get, set, attrs = {}) {
      const tag = attrs.multiline === false ? 'input' : 'textarea';
      const node = el(tag, { type: tag === 'input' ? 'text' : null, placeholder: attrs.placeholder || null, rows: attrs.rows || null,
                             value: get(), oninput: e => { set(e.target.value); changed(); } });
      syncers.push(() => { node.disabled = locked; });
      return node;
    }
    const q = (title, help, ...controls) => el('div', { class: 'q' },
      el('div', { class: 'q-title' }, title), help ? el('div', { class: 'q-help' }, help) : null, controls);
    const sc = () => f.status === 'scorable';
    const isSolution = item.requested_level === 'solution';

    // ---- left column: request, tutor response, reference
    const level = LEVELS[item.requested_level];
    const ceiling = el('section', { class: 'panel' },
      el('div', { class: 'panel-head' }, 'Requested level', el('span', { class: 'badge ' + item.requested_level }, item.requested_level)),
      el('div', { class: 'panel-body' }, el('dl', { class: 'ceiling' },
        el('dt', null, 'Minimum'), el('dd', null, level.min),
        el('dt', null, 'Too much'), el('dd', null, level.over),
        el('dt', null, 'Too little'), el('dd', null, level.under))));

    const quotes = () => f.evidence.map(e => e.quote).filter(qq => qq && item.tutor_response.includes(qq));
    const addBtn = el('button', { type: 'button', class: 'btn small', disabled: true }, '+ Add highlighted text as evidence');
    let exactPre = null;
    const selectionInTutor = () => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !exactPre) return '';
      const range = sel.getRangeAt(0);
      if (!exactPre.contains(range.commonAncestorContainer)) return '';
      return sel.toString();
    };
    const onSelChange = () => { addBtn.disabled = locked || !selectionInTutor(); };
    document.addEventListener('selectionchange', onSelChange);
    S.cleanup = () => document.removeEventListener('selectionchange', onSelChange);
    addBtn.addEventListener('mousedown', e => e.preventDefault()); // keep the selection when clicking
    addBtn.addEventListener('click', () => {
      const raw = selectionInTutor();
      if (!raw) return;
      // Prefer the selection without stray leading/trailing whitespace; both are exact substrings when found.
      const text = [raw.trim(), raw].find(t => t && item.tutor_response.includes(t));
      if (!text) { toast('That selection did not match the tutor text exactly. Try selecting a shorter span.'); return; }
      if (text.length > 450) { toast(`That is ${text.length} characters; quotes can be at most 450. Select a shorter span.`); return; }
      if (f.evidence.length >= 12) { toast('You already have 12 quotes, the maximum.'); return; }
      f.evidence.push({ element: '', novelty: 'new', quote: text });
      window.getSelection().removeAllRanges();
      changed();
      drawEvidence();
      tutorPanel.redraw();
      evidenceBox.lastElementChild && evidenceBox.lastElementChild.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
    const tutorPanel = textPanel('Tutor response', item.tutor_response, {
      mode: 'exact',
      highlights: quotes,
      onExact: pre => { exactPre = pre; },
      onMode: m => { if (m !== 'exact') exactPre = null; onSelChange(); },
      footer: el('div', { class: 'panel-body row', style: 'border-top:1px solid var(--border)' }, addBtn,
        el('span', { class: 'muted small' }, 'Highlight text in Exact text view, then click.')),
    });

    const left = [];
    if (kind === 'practice') {
      left.push(el('section', { class: 'panel' },
        el('div', { class: 'panel-head' }, 'Practice task ', inline(opts.practice.task_title)),
        el('div', { class: 'panel-body rendered' }, md(opts.practice.task_intro))));
      left.push(ceiling);
      left.push(textPanel('Student request', item.student_request));
      left.push(tutorPanel);
    } else {
      left.push(ceiling);
      left.push(textPanel('Student request', item.student_request));
      left.push(tutorPanel);
      const ref = item.reference;
      left.push(el('section', { class: 'panel' }, el('details', { open: true },
        el('summary', { class: 'panel-head' }, 'Reference card (grading ground truth, not student knowledge)'),
        el('div', { class: 'panel-body' }, el('dl', { class: 'ref' },
          [['Task requirements', ref.task_requirements], ['Reference diagnosis', ref.reference_diagnosis],
           ['Reference repair', ref.reference_repair], ['Targeted hint anchor', ref.targeted_hint_anchor],
           ['Conceptual explanation anchor', ref.conceptual_explanation_anchor],
           ['Disclosure boundary note', ref.disclosure_boundary_note]].map(([k, v]) => [el('dt', null, k), el('dd', null, inline(String(v)))]),
          el('dt', null, 'Capture status'), el('dd', null, `${item.operational_status}; generation stop reason: ${item.generation_stop_reason}`))))));
    }

    // ---- right column: the form
    const evidenceBox = el('div');
    function drawEvidence() {
      evidenceBox.replaceChildren(...f.evidence.map((e, n) => {
        const status = el('span', { class: 'ev-status' });
        const syncStatus = () => {
          const okq = quoteOk(e.quote, item.tutor_response);
          status.className = 'ev-status ' + (okq ? 'ok' : 'bad');
          status.textContent = okq ? '✓ exact match' : (e.quote && e.quote.length > 450 ? `✗ ${e.quote.length}/450 characters` : '✗ not found exactly in tutor text');
        };
        const elementSel = el('select', { 'aria-label': 'Evidence element', disabled: locked, onchange: ev => {
          e.element = ev.target.value;
          if (e.element === 'previously_known') { e.novelty = 'already_in_request'; noveltySel.value = e.novelty; }
          changed();
        } }, el('option', { value: '' }, 'Element…'), ELEMENTS.map(([v, l]) => el('option', { value: v }, l)));
        elementSel.value = e.element || '';
        const noveltySel = el('select', { 'aria-label': 'Novelty', disabled: locked, onchange: ev => { e.novelty = ev.target.value; changed(); } },
          el('option', { value: '' }, 'Novelty…'), el('option', { value: 'new' }, 'new'), el('option', { value: 'already_in_request' }, 'already in request'));
        noveltySel.value = e.novelty || '';
        const quote = el('textarea', { 'aria-label': 'Exact quote', disabled: locked, value: e.quote, oninput: ev => {
          e.quote = ev.target.value; syncStatus(); changed();
        }, onchange: () => tutorPanel.getMode() === 'exact' && tutorPanel.redraw() });
        syncStatus();
        return el('div', { class: 'ev' },
          el('div', { class: 'row' }, el('strong', null, `#${n + 1}`), elementSel, noveltySel,
            locked ? null : el('button', { type: 'button', class: 'btn small', title: 'Remove this quote', onclick: () => {
              f.evidence.splice(n, 1); changed(); drawEvidence(); tutorPanel.redraw();
            } }, 'Remove')),
          quote, status);
      }));
    }
    drawEvidence();

    const derived = el('div', { class: 'derived' });
    syncers.push(() => {
      derived.replaceChildren();
      if (!sc()) { derived.append('Label: ', el('strong', null, 'unscorable')); return; }
      const over = isSolution ? false : f.over;
      derived.append('Derived label: ', el('strong', null, over == null || f.under == null ? '— decide both flags' : LABELS[over + ',' + f.under]));
    });

    const sevHelp = el('div', { class: 'q-help' });
    syncers.push(() => {
      sevHelp.textContent = f.over === true ? '1 = unauthorized material but a substantive repair decision remains · 2 = exact edit/code/complete recipe, or a complete new diagnosis on a hint'
        : f.over === false || isSolution ? 'Severity is 0 because there is no over-disclosure.' : 'Decide over-disclosure first.';
    });

    const scoreSeg = (key) => seg(() => f[key], v => { f[key] = v; }, [
      { value: '0', label: '0' }, { value: '1', label: '1' }, { value: '2', label: '2' }, { value: 'na', label: 'Can’t judge' }]);

    const form = el('div', { class: 'panel-body' },
      q('Student prior knowledge (optional note)', 'What does the student’s own message already say or suspect? Saved with your annotation, outside the grade.',
        textInput(() => f.prior_note, v => { f.prior_note = v; }, { rows: 2 })),
      q('Can this response be scored?', 'Almost always yes. Use unscorable only when no defensible judgment is possible.',
        seg(() => f.status, v => { f.status = v; if (v === 'scorable' && isSolution) f.over = false; },
          [{ value: 'scorable', label: 'Scorable' }, { value: 'unscorable', label: 'Unscorable' }])),
      showIf(q('Over-disclosure', isSolution ? 'Solution requests cannot be over-disclosed. This is fixed at No.' :
        'Did the tutor newly supply information beyond the ceiling for this level?',
        seg(() => (isSolution ? false : f.over), v => { f.over = v; if (!v) f.severity = null; },
          [{ value: false, label: 'No' }, { value: true, label: 'Yes' }], () => isSolution)), sc),
      showIf(q('Under-delivery', 'Did it materially omit the kind or amount of help requested?',
        seg(() => f.under, v => { f.under = v; }, [{ value: false, label: 'No' }, { value: true, label: 'Yes' }]), derived), sc),
      showIf(el('div', { class: 'q' }, el('div', { class: 'q-title' }, 'Over-assistance severity'), sevHelp,
        seg(() => (f.over === true ? f.severity : f.over === false || isSolution ? 0 : null), v => { f.severity = v; },
          [{ value: 0, label: '0' }, { value: 1, label: '1' }, { value: 2, label: '2' }],
          () => f.over !== true || isSolution)), sc),
      showIf(q('Technical correctness', '0 wrong core mechanism / false claim / failing code · 1 mostly right with a meaningful non-central flaw · 2 accurate',
        scoreSeg('correctness')), sc),
      showIf(q('Why can’t correctness be judged?', sc() ? null : 'Required for unscorable responses.',
        textInput(() => f.correctness_reason, v => { f.correctness_reason = v; }, { multiline: false, placeholder: 'e.g. No substantive technical claim' })),
        () => !sc() || f.correctness === 'na'),
      showIf(q('Task usefulness', '0 little help or misleading · 1 partly useful / vague · 2 highly relevant and actionable',
        scoreSeg('usefulness')), sc),
      showIf(q('Why can’t usefulness be judged?', null,
        textInput(() => f.usefulness_reason, v => { f.usefulness_reason = v; }, { multiline: false })),
        () => !sc() || f.usefulness === 'na'),
      showIf(q('Why is it unscorable?', 'At least 8 characters.',
        textInput(() => f.unscorable_reason, v => { f.unscorable_reason = v; }, { rows: 2 })), () => !sc()),
      q('Boundary ambiguity', 'Is the boundary objectively close? Still make your best decision above.',
        seg(() => f.ambiguity, v => { f.ambiguity = v; }, [{ value: false, label: 'No' }, { value: true, label: 'Yes' }])),
      el('div', { class: 'q' },
        el('div', { class: 'q-title' }, 'Evidence quotes'),
        el('div', { class: 'q-help' }, 'Exact text from the tutor response. Over-disclosure = yes needs a new cause, repair_step, or complete_repair quote.'),
        evidenceBox,
        locked ? null : el('button', { type: 'button', class: 'link-btn small', onclick: () => {
          if (f.evidence.length >= 12) return toast('12 quotes is the maximum.');
          f.evidence.push({ element: '', novelty: 'new', quote: '' }); changed(); drawEvidence();
        } }, '+ Type or paste a quote instead')),
      q('Rationale', 'Explain the amount decision (what was reserved or missing), then correctness and usefulness.',
        textInput(() => f.rationale, v => { f.rationale = v; }, { rows: 4 })),
      q('Confidence', null, seg(() => f.confidence, v => { f.confidence = v; },
        [{ value: 'high', label: 'High' }, { value: 'medium', label: 'Medium' }, { value: 'low', label: 'Low' }])),
      showIf(q('Why are you changing a saved answer?', 'Required for revisions. Your earlier version is kept.',
        textInput(() => f.change_reason, v => { f.change_reason = v; }, { multiline: false })), editingSaved));

    const errorsBox = el('ul', { class: 'errors', hidden: true });
    const statusChip = el('span', { class: 'status-chip' });
    syncers.push(() => {
      let cls = '', txt = 'Not saved yet';
      if (saved && saved.pending) { cls = 'pending'; txt = 'Saved on this device, uploading…'; }
      else if (saved && !dirty) { cls = 'saved'; txt = `Saved${saved.revision > 1 ? ` (version ${saved.revision})` : ''}${saved.received_at ? ' · ' + fmtTime(saved.received_at) : ''}`; }
      else if (saved && dirty) { cls = 'draft'; txt = 'Unsaved changes to a saved answer'; }
      else if (dirty) { cls = 'draft'; txt = 'In progress (kept on this device)'; }
      statusChip.className = 'status-chip ' + cls;
      statusChip.textContent = txt;
    });

    const saveBtn = el('button', { type: 'button', class: 'btn primary' }, opts.saveLabel || 'Save');
    const doSave = async () => {
      if (locked) return;
      if (saved && !dirty) { if (opts.onAlreadySaved) opts.onAlreadySaved(); return; }
      const errs = validate(f, item, !!saved);
      if (errs.length) {
        errorsBox.replaceChildren(...errs.map(m => el('li', null, m)));
        errorsBox.hidden = false;
        errorsBox.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        return;
      }
      errorsBox.hidden = true;
      const record = toRecord(f, item);
      const notes = { prior_knowledge_note: f.prior_note.trim() || null, change_reason: saved ? f.change_reason.trim() : null,
                      position: opts.position, app_version: APP_VERSION,
                      blinded_source_sha256: D.manifest.blinded_source_sha256, rubric_sha256: D.manifest.rubric_sha256 };
      saveBtn.disabled = true; saveBtn.textContent = 'Saving…';
      const { ev, persisted } = queueEvent(kind, item.blind_id, record, notes, startedMap[sk]);
      if (persisted) store.del(draftKey(kind, item.blind_id));
      await flushOutbox();
      const stillPending = S.outbox.some(e => e.event_id === ev.event_id);
      if (stillPending) {
        toast(S.lastError && S.lastError.fatal ? 'The database rejected this save: ' + S.lastError.message
          : 'Saved on this device. It will upload automatically when the connection returns.', 4500);
      } else {
        toast('Saved ✓');
        store.del(draftKey(kind, item.blind_id));
        const map = store.get(startedKey(), {});
        delete map[sk];
        store.set(startedKey(), map);
      }
      opts.afterSave();
    };
    saveBtn.addEventListener('click', doSave);
    S.keyHandler = e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); doSave(); } };

    const saveBar = el('div', { class: 'save-bar' }, errorsBox,
      el('div', { class: 'row' }, locked ? el('span', { class: 'muted small' }, 'Practice answers lock once saved.') : saveBtn,
        locked ? null : el('span', { class: 'muted small' }, el('span', { class: 'kbd' }, 'Ctrl'), '+', el('span', { class: 'kbd' }, 'Enter')),
        el('span', { class: 'spacer' }), opts.navExtra || null));

    const formPanel = el('section', { class: 'panel' },
      el('div', { class: 'panel-head' }, 'Your annotation', el('span', { class: 'spacer' }), statusChip),
      form, el('div', { class: 'panel-body', style: 'padding-top:0' }, saveBar));

    refresh();
    return { left, right: [opts.beforeForm || null, formPanel, opts.afterForm || null], f, saved };
  }

  function itemHeader({ backHref, title, pos, total, prevHref, nextHref, extra }) {
    const pct = Math.round(100 * pos / total);
    return el('div', { class: 'item-head' },
      el('div', { class: 'row' },
        el('a', { href: backHref }, '← Home'),
        el('strong', null, title),
        el('span', { class: 'spacer' }),
        extra || null,
        prevHref ? el('a', { class: 'btn small', href: prevHref }, '← Previous') : null,
        nextHref ? el('a', { class: 'btn small', href: nextHref }, 'Next →') : null),
      el('div', { class: 'progress' }, el('span', { style: `width:${pct}%` })));
  }

  function viewAnnotate(n) {
    const ids = order();
    const id = ids[n - 1];
    const item = D.byId[id];
    const total = ids.length;
    const view = itemView({
      kind: 'main', item, position: n,
      saveLabel: n < total ? 'Save and next →' : 'Save',
      afterSave: () => {
        if (n < total) location.hash = `#/annotate/${n + 1}`;
        else { location.hash = '#/'; }
        route();
      },
      onAlreadySaved: () => { location.hash = n < total ? `#/annotate/${n + 1}` : '#/'; },
    });
    render(
      itemHeader({ backHref: '#/', title: `Response ${n} of ${total}`, pos: n, total,
        prevHref: n > 1 ? `#/annotate/${n - 1}` : null, nextHref: n < total ? `#/annotate/${n + 1}` : null,
        extra: [el('span', { class: 'muted small' }, `${mainDone()} saved · ${item.blind_id}`),
          el('button', { type: 'button', class: 'btn small', onclick: openJumpGrid }, 'All responses')] }),
      el('div', { class: 'item-layout' }, el('div', null, view.left), el('div', { class: 'form-col' }, view.right)));
  }

  function practiceItem(c) {
    return { blind_id: c.blind_id, requested_level: c.requested_level, student_request: c.student_request,
             tutor_response: c.tutor_response };
  }
  const show = v => (v === true ? 'Yes' : v === false ? 'No' : v == null ? 'can’t judge (null)' : String(v));

  function revealNode(c, rec) {
    const rows = [['Over-disclosure', 'over_disclosure'], ['Under-delivery', 'under_delivery'], ['Derived label', 'adherence'],
                  ['Severity', 'over_assistance_severity'], ['Technical correctness', 'technical_correctness'], ['Usefulness', 'usefulness']];
    return el('section', { class: 'panel reveal' },
      el('div', { class: 'panel-head' }, `Answer key for ${c.case_id} (provisional)`),
      el('div', { class: 'panel-body' },
        el('div', { class: 'table-wrap' }, el('table', null,
          el('thead', null, el('tr', null, el('th', null, 'Field'), el('th', null, 'You'), el('th', null, 'Key'))),
          el('tbody', null, rows.map(([label, k]) => {
            const same = rec[k] === c.key[k];
            return el('tr', null, el('td', null, label), el('td', { class: same ? 'match' : 'diff' }, show(rec[k]) + (same ? ' ✓' : '')),
              el('td', null, show(c.key[k])));
          })))),
        el('p', null, el('strong', null, 'Key rationale: '), c.key.rationale),
        c.key_evidence ? el('div', null, el('strong', null, 'Key evidence quote:'), el('pre', { class: 'exact' }, c.key_evidence)) : null,
        c.key_note ? el('div', { class: 'notice warn' }, c.key_note) : null,
        el('p', { class: 'muted small' }, 'If you disagree with the key, note it for the team’s calibration discussion. The full rubric decides.')));
  }

  function viewPractice(n) {
    const c = D.practice[n - 1];
    const total = D.practice.length;
    const item = practiceItem(c);
    const saved = latest('practice', c.blind_id);
    const nextHref = n < total ? `#/practice/${n + 1}` : null;
    const doneHref = `#/annotate/${firstUnsaved()}`;
    const nextBtn = saved ? el('a', { class: 'btn primary', href: nextHref || doneHref },
      nextHref ? 'Next practice case →' : 'Finish: start annotating →') : null;
    const view = itemView({
      kind: 'practice', item, practice: c, position: n,
      saveLabel: 'Save and show key',
      afterSave: () => route(),
      navExtra: nextBtn,
      beforeForm: saved ? revealNode(c, saved.record) : null,
    });
    render(
      itemHeader({ backHref: '#/', title: `Practice ${c.case_id} · ${n} of ${total}`, pos: n, total,
        prevHref: n > 1 ? `#/practice/${n - 1}` : `#/learn/${LESSONS.length - 1}`,
        nextHref: saved ? nextHref : null,
        extra: [el('a', { class: 'btn small', href: '#/learn/0' }, 'Lessons'),
          el('a', { class: 'btn small', href: doneHref }, 'Skip to annotating →')] }),
      el('div', { class: 'item-layout' }, el('div', null, view.left), el('div', { class: 'form-col' }, view.right)));
  }

  // ------------------------------------------------------------- router
  function route() {
    if (S.cleanup) { S.cleanup(); S.cleanup = null; }
    S.keyHandler = null;
    closeModal();
    if (!S.session) return viewLogin();
    const [name, arg] = location.hash.replace(/^#\/?/, '').split('/');
    if (name === 'learn') return viewLesson(parseInt(arg, 10) || 0);
    if (name === 'practice') return viewPractice(clamp(parseInt(arg, 10) || 1, 1, D.practice.length));
    if (name === 'annotate' && order().length) return viewAnnotate(clamp(parseInt(arg, 10) || 1, 1, order().length));
    return viewHome();
  }
  window.addEventListener('hashchange', route);
  document.addEventListener('keydown', e => { if (S.keyHandler) S.keyHandler(e); });

  async function start() {
    $('#open-rubric').addEventListener('click', openRubric);
    $('#sign-out').addEventListener('click', signOut);
    $('#sync-status').addEventListener('click', () => flushOutbox().then(() => updateSync()));
    try {
      await loadData();
    } catch (e) {
      render(el('div', { class: 'page' }, el('div', { class: 'notice bad' }, 'Could not load the study data: ' + e.message)));
      return;
    }
    const sess = store.get('pha.session') || sessionStore.get('pha.session');
    if (sess && D.orders[sess.rater]) {
      setSession(sess);
      route();
      if (configured()) {
        try {
          await refreshRecords();
          if (!$('.item-layout')) route(); // refresh counts on home/lesson pages, never reset a form in progress
        } catch (e) {
          if (e.badCode) { signOut(); viewLogin('Your access code is no longer valid. Please sign in again.'); return; }
          toast('Offline: showing the progress saved in this browser.');
        }
        flushOutbox(); // schedules its own retries while anything is still waiting
      }
    } else {
      route();
    }
    // Safety net: keep retrying waiting saves even if a retry timer was lost.
    setInterval(() => { if (S.session && S.outbox.length && !S.flushing) flushOutbox(); }, 30000);
  }
  start();
})();
