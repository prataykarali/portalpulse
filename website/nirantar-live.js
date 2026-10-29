(() => {
  const $ = id => document.getElementById(id);
  const allowed = ['bronze-tinsel-n8pb.here.now', '127.0.0.1', 'localhost'];
  let site = 'https://bronze-tinsel-n8pb.here.now/';
  try { const url = new URL(new URLSearchParams(location.search).get('site') || site); if (['http:', 'https:'].includes(url.protocol) && allowed.includes(url.hostname)) site = url.href; } catch {}
  $('nirantar-site').src = site;
  $('direct-site').href = site;
  const series = {};
  const charts = [
    ['rps', 'Measured requests', 'req/s', '#6c45f4', '#e9e0ff', 10],
    ['p95', 'p95 latency', 'ms', '#f28a27', '#fff0d9', 350],
    ['errors', 'Failed responses', '%', '#ef426a', '#ffe0e8', 100],
    ['forecast', 'M2 +5 min demand', 'req/s', '#b42bdc', '#f5e0fc', 16],
    ['anomaly', 'M3 anomaly score', '', '#02ad9a', '#d9f8f1', 1],
    ['confidence', 'M5 action confidence', '%', '#248ce3', '#ddecff', 100]
  ];
  for (const [key, label, unit, color, fill] of charts) {
    series[key] = [];
    const tile = document.createElement('article');
    tile.className = 'graph-card';
    tile.style.setProperty('--line', color);
    tile.style.setProperty('--fill', fill);
    tile.innerHTML = `<header><strong>${label}</strong><b id="value-${key}">—</b></header><svg viewBox="0 0 150 58" preserveAspectRatio="none" role="img" aria-label="${label} history"><line x1="0" y1="56" x2="150" y2="56"/><line x1="0" y1="29" x2="150" y2="29"/><path class="area"/><path class="line"/></svg>`;
    $('graph-grid').append(tile);
  }
  function plot(key, value, digits = 1) {
    const config = charts.find(item => item[0] === key);
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return;
    const data = series[key];
    data.push(numeric); if (data.length > 30) data.shift();
    const ceiling = Math.max(config[5], ...data) * 1.08;
    const xy = data.map((v, i) => `${(i / Math.max(1, data.length - 1) * 150).toFixed(1)},${(55 - Math.min(1, v / ceiling) * 50).toFixed(1)}`);
    const tile = $('value-' + key).closest('.graph-card');
    tile.querySelector('.line').setAttribute('d', `M ${xy.join(' L ')}`);
    tile.querySelector('.area').setAttribute('d', `M ${xy.join(' L ')} L 150,56 L 0,56 Z`);
    $('value-' + key).textContent = `${numeric.toFixed(digits)}${config[2] ? ' ' + config[2] : ''}`;
  }
  const phases = {
    'Tatkal arrival': ['A Tatkal crowd is arriving', 'The local Nirantar bridge is receiving a bounded burst. Watch measured requests rise while M2 predicts the next window.'],
    'Booking contention': ['Booking responses are slowing', 'The simulator adds local database delay. The p95 line shows what request latency actually does.'],
    'Gateway fault': ['Nirantar bridge gateway fault', 'A local 503 fault is injected for this phase. PortalPulse sees failed HTTP responses; M3 and M4 inspect the measured change.'],
    'Mitigation window': ['The response window is open', 'The fault is removed. M5 proposes a response, M6 checks it, and M7 applies only approved actions to the local bridge.'],
    'Recovery check': ['Checking for stable service', 'Requests continue while PortalPulse compares the latest measurement with the stressed window.'],
    'Second wave': ['A second Tatkal wave arrives', 'Demand rises again. The simulation loops through new conditions until you stop it.']
  };
  let running = false, lastPhase = '', latestSafety = '', latestAction = '', latestCause = '', stopBusy = false;
  const seen = new Set();
  function card({kind = 'warning', source = 'NIRANTAR SIMULATION', title, detail, footer = '', id}) {
    if (id && seen.has(id)) return;
    if (id) { seen.add(id); if (seen.size > 80) seen.delete(seen.values().next().value); }
    const node = document.createElement('article'); node.className = 'notice ' + kind;
    const close = document.createElement('button'); close.textContent = '×'; close.setAttribute('aria-label', 'Dismiss notice'); close.onclick = () => node.remove();
    if (kind === 'action') { const bot = document.createElement('img'); bot.src = '/static/assets/portalpulse-guide-robot.svg'; bot.alt = 'PulseBot'; node.append(bot); }
    const label = document.createElement('small'); label.textContent = source;
    const heading = document.createElement('strong'); heading.textContent = title;
    const body = document.createElement('p'); body.textContent = detail;
    const foot = document.createElement('footer'); foot.textContent = footer || new Date().toLocaleTimeString();
    node.append(close, label, heading, body, foot); $('notice-stack').prepend(node);
    while ($('notice-stack').children.length > 3) $('notice-stack').lastElementChild.remove();
  }
  function update(data) {
    const wasRunning = running;
    running = Boolean(data.running);
    $('run-linked-demo').disabled = running;
    $('stop-linked-demo').disabled = !running;
    $('bridge-state').textContent = running ? `● Simulation running · ${Math.floor(data.elapsed_seconds || 0)}s · Enter to stop` : 'Simulation idle';
    $('pulse-phase').textContent = data.phase || 'Idle';
    $('pulse-rps').textContent = `${Number(data.rps || 0).toFixed(1)}/s`;
    $('pulse-errors').textContent = `${Number(data.error_rate || 0).toFixed(0)}%`;
    if (running || wasRunning) {
      plot('rps', data.rps || 0); plot('p95', data.p95_ms || 0); plot('errors', data.error_rate || 0);
    }
    if (running && data.phase !== lastPhase) {
      lastPhase = data.phase;
      const notice = phases[data.phase];
      if (notice) card({kind: ['Recovery check', 'Mitigation window'].includes(data.phase) || (data.phase === 'Gateway fault' && data.circuit_breaker_active) ? 'recovery' : 'warning', title: data.phase === 'Gateway fault' && data.circuit_breaker_active ? 'Circuit breaker is protecting journeys' : notice[0], detail: data.phase === 'Gateway fault' && data.circuit_breaker_active ? 'The injected gateway fault is still present, but M7 enabled a cached fallback on the local bridge. Watch the measured failure line to see whether protection holds.' : notice[1], footer: `${Number(data.rps || 0).toFixed(1)} measured req/s · local bridge`, id: `phase:${data.phase}:${Math.floor((data.elapsed_seconds || 0) / 30)}`});
    }
    if (wasRunning && !running) card({kind: 'action', source: 'PULSEBOT · MANUAL STOP', title: 'Simulation stopped', detail: 'Local generated requests ended. The deployed Nirantar site remains open and untouched.', footer: data.stop_reason || 'Stopped by operator', id: 'manual-stop'});
  }
  async function refresh() { try { const response = await fetch('/api/v1/nirantar-simulation/status', {cache: 'no-store'}); if (!response.ok) throw Error(`HTTP ${response.status}`); update(await response.json()); } catch { $('bridge-state').textContent = 'Simulator connection unavailable'; } }
  $('run-linked-demo').onclick = async () => {
    $('run-linked-demo').disabled = true;
    try {
      const response = await fetch('/api/v1/nirantar-simulation/start', {method: 'POST'});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      seen.delete('manual-stop'); lastPhase = '';
      $('last-m7-action').textContent = 'None in this run';
      update(await response.json());
      $('stop-linked-demo').focus();
      card({kind: 'action', source: 'PULSEBOT · NIRANTAR SIMULATION', title: 'Simulation is running until you stop it', detail: 'Bounded requests now exercise the local Nirantar bridge. The measured and model graphs update here. Press Enter or Stop to finish.', footer: 'Maximum 4 in-flight requests · 10 requests/s · no story timer'});
    } catch (error) { card({title: 'Simulation could not start', detail: String(error), footer: 'Check PortalPulse availability.'}); await refresh(); }
  };
  async function stop() { if (!running || stopBusy) return; stopBusy = true; try { const response = await fetch('/api/v1/nirantar-simulation/stop', {method: 'POST'}); if (!response.ok) throw Error(`HTTP ${response.status}`); update(await response.json()); } catch (error) { card({title: 'Stop request failed', detail: String(error)}); } finally { stopBusy = false; } }
  $('stop-linked-demo').onclick = stop;
  document.addEventListener('keydown', event => { if (event.key === 'Enter' && running) { event.preventDefault(); stop(); } });
  $('toggle-panel').onclick = () => { const panel = $('model-panel'); panel.classList.toggle('collapsed'); $('toggle-panel').textContent = panel.classList.contains('collapsed') ? '+' : '−'; };
  $('preview-notice').onclick = () => card({kind: 'warning', source: 'PREVIEW · NIRANTAR', title: 'Tatkal arrivals are queuing', detail: 'This preview illustrates the passenger message. Use Run simulation to generate measured local bridge traffic and model responses.', footer: 'Preview only · no live traffic inferred'});
  const stream = new EventSource('/api/v1/stream/events');
  function listen(type, handler) { stream.addEventListener(type, event => { try { const item = JSON.parse(event.data); if (item.portal_id === 'nirantar' && running) handler(item); } catch (error) { console.error(error); } }); }
  stream.addEventListener('nirantar_simulation', event => { try { update(JSON.parse(event.data)); } catch (error) { console.error(error); } });
  listen('forecast', item => { const horizon = item.horizons?.['5m']; const val = Number(typeof horizon === 'object' ? horizon?.requests_per_sec : horizon); if (Number.isFinite(val)) plot('forecast', val); });
  listen('anomaly', item => plot('anomaly', item.anomaly_score || 0, 3));
  listen('rca', item => { latestCause = String(item.root_cause || 'Unknown').replaceAll('_', ' '); $('model-cause').textContent = `${latestCause} · ${Math.round(Number(item.confidence || 0) * 100)}% confidence`; });
  listen('action', item => { latestAction = String(item.action || 'NO_OP').replaceAll('_', ' '); plot('confidence', Number(item.confidence || 0) * 100); $('model-action').textContent = `${latestAction} → ${latestSafety || 'checking safety'}`; });
  listen('safety', item => { latestSafety = item.decision || 'Unknown'; $('model-action').textContent = `${latestAction || 'NO OP'} → ${latestSafety}`; });
  listen('actuation', item => { $('model-action').textContent = `${String(item.action || 'NO_OP').replaceAll('_', ' ')} → ${latestSafety} → ${item.status}`; if (item.status === 'EXECUTED') { $('last-m7-action').textContent = `${String(item.action).replaceAll('_', ' ')} · ${new Date().toLocaleTimeString()}`; card({kind: 'action', source: 'PULSEBOT · M7 LOCAL ACTION', title: `PortalPulse applied ${String(item.action).replaceAll('_', ' ')}`, detail: `M6 approved the action and M7 changed the local Nirantar bridge. Cause: ${latestCause || item.why || 'under investigation'}. A later measured cycle will check whether requests improved.`, footer: `Cycle ${item.cycle_id} · deployed Nirantar unchanged`, id: `action:${item.cycle_id}`}); } });
  listen('warning', item => card({kind: 'warning', source: 'NIRANTAR BRIDGE · DETECTED', title: item.title || 'Local bridge warning', detail: item.why_it_happened || item.message || 'Measured conditions crossed a threshold.', footer: `Cycle ${item.cycle_id || '—'} · local simulation`, id: `warning:${item.id}:${item.cycle_id}`}));
  listen('recovery', item => card({kind: 'recovery', source: 'NIRANTAR BRIDGE · RECOVERY CHECK', title: item.title || 'Condition easing', detail: item.current_result || item.message || 'The observed trigger has cleared. Monitoring continues.', footer: item.verification_status || 'Metric normalized', id: `recovery:${item.id}:${item.cycle_id}`}));
  stream.onerror = () => { $('bridge-state').textContent = 'Reconnecting to PortalPulse…'; };
  refresh(); setInterval(() => { if (!document.hidden) refresh(); }, 5000);
})();
