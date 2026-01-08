document.addEventListener('DOMContentLoaded', () => {
  // -----------------------------
  // Helpers
  // -----------------------------
  const $ = (id) => document.getElementById(id);
  const backendReady = () => window.pywebview && window.pywebview.api;

  function fmtUSD(x) {
    const n = Number(x || 0);
    return n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
  }
  function fmtUSD2(x) {
    const n = Number(x || 0);
    return n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
  }

  function setDot(el, on) {
    if (!el) return;
    el.classList.remove('green', 'red');
    el.classList.add(on ? 'green' : 'red');
  }

  // -----------------------------
  // Sidebar navigation
  // -----------------------------
  const navItems = document.querySelectorAll('.nav-item');
  const sections = {
    dashboard: $('section-dashboard'),
    portfolio: $('section-portfolio'),
    connections: $('section-connections'),
    engine: $('section-engine'),
    settings: $('section-settings'),
  };

  function showSection(name) {
    Object.keys(sections).forEach(k => {
      if (sections[k]) sections[k].classList.toggle('hidden', k !== name);
    });
  }

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      navItems.forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      showSection(item.getAttribute('data-section') || 'dashboard');
    });
  });

  // Logout -> return to license screen
  const btnLogout = $('btn-logout');
  if (btnLogout) {
    btnLogout.addEventListener('click', async () => {
      try {
        if (backendReady() && window.pywebview.api.logout) {
          await window.pywebview.api.logout();
        }
      } catch(e) {}
      // python side will reload license.html in logout()
    });
  }

  // -----------------------------
  // Equity chart (canvas)
  // -----------------------------
  const canvas = $('equity-canvas');
  const ctx = canvas ? canvas.getContext('2d') : null;

  function drawEquityCurve(points) {
    if (!canvas || !ctx) return;

    // Resize to container width
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(rect.width * dpr);
    canvas.height = Math.floor(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const w = rect.width;
    const h = rect.height;

    // background
    ctx.clearRect(0, 0, w, h);

    // No data
    if (!points || points.length < 2) {
      ctx.globalAlpha = 0.9;
      ctx.font = "700 14px system-ui";
      ctx.fillStyle = "rgba(233,238,247,.70)";
      ctx.fillText("Equity curve will appear here once KAQT records daily snapshots.", 14, 32);
      return;
    }

    // Extract Y values
    const ys = points.map(p => Number(p.equity || 0));
    let minY = Math.min(...ys);
    let maxY = Math.max(...ys);
    if (minY === maxY) { maxY = minY + 1; }

    // padding
    const pad = 14;
    const innerW = w - pad * 2;
    const innerH = h - pad * 2;

    function xAt(i) {
      return pad + (i / (points.length - 1)) * innerW;
    }
    function yAt(val) {
      const t = (val - minY) / (maxY - minY);
      return pad + (1 - t) * innerH;
    }

    // grid
    ctx.strokeStyle = "rgba(255,255,255,.06)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const yy = pad + (i / 4) * innerH;
      ctx.beginPath();
      ctx.moveTo(pad, yy);
      ctx.lineTo(pad + innerW, yy);
      ctx.stroke();
    }

    // line (green-ish)
    ctx.strokeStyle = "rgba(81,214,138,.95)";
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.moveTo(xAt(0), yAt(ys[0]));
    for (let i = 1; i < ys.length; i++) ctx.lineTo(xAt(i), yAt(ys[i]));
    ctx.stroke();

    // fill
    ctx.fillStyle = "rgba(81,214,138,.12)";
    ctx.lineTo(xAt(ys.length - 1), pad + innerH);
    ctx.lineTo(xAt(0), pad + innerH);
    ctx.closePath();
    ctx.fill();
  }

  // -----------------------------
  // Render tables
  // -----------------------------
  const positionsBody = $('positions-body');
  const tradesBody = $('trades-body');

  function renderPositions(list) {
    if (!positionsBody) return;
    positionsBody.innerHTML = "";

    if (!list || list.length === 0) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td colspan="4" class="muted">No open positions.</td>`;
      positionsBody.appendChild(tr);
      return;
    }

    list.forEach(p => {
      const qty = Number(p.quantity ?? p.size ?? 0);
      const side = qty > 0 ? "LONG" : qty < 0 ? "SHORT" : "FLAT";
      const avg = Number(p.avg_price ?? p.avgPrice ?? p.avgCost ?? 0);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${p.symbol || "?"}</td>
        <td>${side}</td>
        <td>${Math.abs(qty)}</td>
        <td>${avg ? avg.toFixed(2) : "—"}</td>
      `;
      positionsBody.appendChild(tr);
    });
  }

  function renderTrades(list) {
    if (!tradesBody) return;
    tradesBody.innerHTML = "";

    if (!list || list.length === 0) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td colspan="5" class="muted">No trades yet.</td>`;
      tradesBody.appendChild(tr);
      return;
    }

    list.slice(-50).reverse().forEach(t => {
      const ts = Number(t.timestamp || (Date.now() / 1000));
      const timeStr = new Date(ts * 1000).toLocaleString();
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${timeStr}</td>
        <td>${t.symbol || "?"}</td>
        <td>${t.side || "?"}</td>
        <td>${t.quantity ?? t.qty ?? "—"}</td>
        <td>${t.price ? Number(t.price).toFixed(2) : "—"}</td>
      `;
      tradesBody.appendChild(tr);
    });
  }

  // -----------------------------
  // Status + UI wiring
  // -----------------------------
  async function refreshAll() {
    if (!backendReady()) return;

    const s = await window.pywebview.api.get_status();

    // Top metrics
    $('top-cash').textContent = fmtUSD(s.cash || 0);
    $('top-equity').textContent = fmtUSD(s.account_balance || 0);

    const pct = Number(s.equity_pct ?? 0);
    $('top-equity-pct').textContent = (isFinite(pct) && pct !== 0) ? `${pct > 0 ? "▲" : "▼"} ${(pct*100).toFixed(2)}%` : "—";

    $('top-last-decision').textContent = s.last_decision_human || "—";
    $('top-engine').textContent = s.engine_active ? "ACTIVE" : "INACTIVE";
    setDot($('engine-dot'), !!s.engine_active);

    // Dashboard blocks
    $('conn-status').textContent = s.connection_status || "—";
    $('snap-cash').textContent = fmtUSD2(s.cash || 0);
    $('snap-equity').textContent = fmtUSD2(s.account_balance || 0);
    $('snap-signal').textContent = s.signal_state || "—";
    $('snap-last').textContent = s.last_decision_human || "—";

    // Engine box
    $('engine-status-text').textContent = s.engine_active ? "ACTIVE" : "INACTIVE";
    setDot($('engine-dot-2'), !!s.engine_active);
    $('engine-next-run').textContent = s.next_run_human || "—";
    $('engine-signal').textContent = s.signal_state || "—";

    $('engine-status-2').textContent = s.engine_active ? "ACTIVE" : "INACTIVE";
    $('engine-signal-2').textContent = s.signal_state || "—";
    $('engine-last-2').textContent = s.last_decision_human || "—";
    $('engine-next-2').textContent = s.next_run_human || "—";

    // Start button lock
    const startBtns = [$('btn-start'), $('btn-start-2')].filter(Boolean);
    startBtns.forEach(b => b.disabled = !!s.engine_active);

    // Current position panel
    $('pos-symbol').textContent = s.current_symbol || "—";
    $('pos-size').textContent = s.current_size != null ? String(s.current_size) : "—";
    $('pos-avg').textContent = s.current_avg_price ? `$${Number(s.current_avg_price).toFixed(2)}` : "—";
    $('pos-exposure').textContent = s.signal_state === "LONG" ? "LONG (100%)" : "FLAT (0%)";
    $('pos-cash').textContent = fmtUSD2(s.cash || 0);

    // Mini stats (based on equity history)
    $('mini-return').textContent = (s.live_return != null) ? `${(Number(s.live_return)*100).toFixed(2)}%` : "—";
    $('mini-mdd').textContent = (s.live_max_dd != null) ? `${(Number(s.live_max_dd)*100).toFixed(2)}%` : "—";
    $('mini-exposure').textContent = s.signal_state || "—";

    // Tables
    const pos = await window.pywebview.api.get_positions();
    const trd = await window.pywebview.api.get_trades();
    renderPositions(pos);
    renderTrades(trd);

    // Equity curve
    const curve = await window.pywebview.api.get_equity_curve();
    drawEquityCurve(curve);
  }

  // Buttons
  $('btn-refresh')?.addEventListener('click', () => refreshAll().catch(console.error));

  async function startEngine() {
    if (!backendReady()) return alert("Backend not ready.");
    const r = await window.pywebview.api.start_engine();
    alert(r.message || (r.ok ? "Engine started" : "Failed"));
    await refreshAll();
  }

  async function stopEngine() {
    if (!backendReady()) return alert("Backend not ready.");
    const r = await window.pywebview.api.stop_engine();
    alert(r.message || (r.ok ? "Engine stopped" : "Failed"));
    await refreshAll();
  }

  $('btn-start')?.addEventListener('click', () => startEngine().catch(e => alert(String(e))));
  $('btn-start-2')?.addEventListener('click', () => startEngine().catch(e => alert(String(e))));
  $('btn-stop')?.addEventListener('click', () => stopEngine().catch(e => alert(String(e))));
  $('btn-stop-2')?.addEventListener('click', () => stopEngine().catch(e => alert(String(e))));

  // Connections
  $('btn-save-conn')?.addEventListener('click', async () => {
    const payload = {
      broker: "ibkr",
      mode: $('ibkr-mode').value,
      account_id: $('ibkr-account').value.trim(),
      ibkr_host: $('ibkr-host').value.trim(),
      ibkr_port: Number($('ibkr-port').value || 0),
      ibkr_client_id: Number($('ibkr-client-id').value || 0),
    };
    const r = await window.pywebview.api.save_broker_config(payload);
    alert(r.message || "Saved");
  });

  $('btn-test-conn')?.addEventListener('click', async () => {
    const r = await window.pywebview.api.test_broker_connection();
    alert(r.message || (r.ok ? "Connection OK" : "Failed"));
    await refreshAll();
  });

  // Settings scheduler
  $('btn-save-sched')?.addEventListener('click', async () => {
    const hour = Number($('sched-hour').value || 0);
    const minute = Number($('sched-minute').value || 0);
    const r = await window.pywebview.api.set_scheduler_time({ hour, minute });
    alert(r.message || "Saved");
    await refreshAll();
  });

  // Initial load
  refreshAll().catch(console.error);
  setInterval(() => refreshAll().catch(() => {}), 3000);
});