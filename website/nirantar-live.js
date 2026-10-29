(() => {
  const $ = id => document.getElementById(id);
  const allowed = ['bronze-tinsel-n8pb.here.now', '127.0.0.1', 'localhost'];
  let site = 'https://bronze-tinsel-n8pb.here.now/';
  try {
    const candidate = new URL(new URLSearchParams(location.search).get('site') || site);
    if (['https:', 'http:'].includes(candidate.protocol) && allowed.includes(candidate.hostname)) site = candidate.href;
  } catch {}
  $('nirantar-site').src = site;
  $('direct-site').href = site;

  const examples = [
    {title: 'Tatkal requests are entering a short queue', detail: 'In this example, new bookings are admitted in batches while active checkouts finish. The queue and wait estimate are illustrative.', kind: 'warning'},
    {title: 'Booking confirmations are slower than usual', detail: 'In this example, passengers should wait for a final transaction status before retrying payment.', kind: 'warning'},
    {title: 'Booking flow is being admitted normally', detail: 'This example shows a follow-up notice after a queue clears. No live Nirantar recovery is inferred.', kind: 'recovery'}
  ];
  const phaseNotices = {
    RESULT_RUSH: ['A crowd arrives at once', 'Scenario users rise while measured IEMCRP requests test the portal. This Nirantar overlay shows how a passenger warning could look.'],
    SATURATION: ['The demo database is overloaded', 'Measured requests compete for a limited connection pool. PortalPulse is checking latency, errors, and DB pressure.'],
    ANOMALY_DETECTION: ['The models are investigating', 'M2 forecasts demand, M3 scores the anomaly, and M4 traces the likely cause using current demo telemetry.'],
    POLICY_ACTION: ['A response is being evaluated', 'M5 ranks actions and M6 checks safety. An M7 card appears only if the simulator actually applies an action.'],
    CONTROLLED_RECOVERY: ['Pressure is easing', 'The fault is cleared and PortalPulse compares later measurements with the earlier request window.'],
    RATE_LIMIT_PRESSURE: ['Refresh requests are being limited', 'The demo ingress cap produces measured HTTP 429 responses. Active requests are protected while excess retries are rejected.'],
    GATEWAY_FAILURE: ['A dependency has failed', 'The simulator injects HTTP 503 responses so PortalPulse can test detection and response.'],
    SECOND_WAVE: ['A second crowd is arriving', 'The demo tests whether the portal remains stable after its first recovery.'],
    NORMAL: ['The scenario is settling', 'Generated demand returns toward baseline. Check the measured result before calling recovery verified.']
  };
  let exampleIndex = 0;
  let lastPhase = '';
  let runActive = false;
  const seen = new Set();

  function card({title, detail, kind = 'warning', source = 'EXAMPLE · OVERLAY', footer = '', id}) {
    if (id && seen.has(id)) return;
    if (id) {
      seen.add(id);
      if (seen.size > 80) seen.delete(seen.values().next().value);
    }
    const node = document.createElement('article');
    node.className = 'notice ' + kind;
    const close = document.createElement('button');
    close.textContent = '×';
    close.setAttribute('aria-label', 'Dismiss notice');
    close.onclick = () => node.remove();
    const label = document.createElement('small');
    label.textContent = source;
    const heading = document.createElement('strong');
    heading.textContent = title;
    const body = document.createElement('p');
    body.textContent = detail;
    const foot = document.createElement('footer');
    foot.textContent = footer || new Date().toLocaleTimeString();
    if (kind === 'action') {
      const bot = document.createElement('img');
      bot.src = '/static/assets/portalpulse-guide-robot.svg';
      bot.alt = 'PulseBot';
      node.append(bot);
    }
    node.append(close, label, heading, body, foot);
    $('notice-stack').prepend(node);
    while ($('notice-stack').children.length > 3) $('notice-stack').lastElementChild.remove();
  }

  function setReadout(traffic) {
    runActive = Boolean(traffic.is_running);
    $('pulse-phase').textContent = runActive ? String(traffic.phase || 'Running').replaceAll('_', ' ') : 'Idle';
    $('pulse-users').textContent = Number(traffic.virtual_users ?? traffic.current_vus ?? 0).toLocaleString();
    $('pulse-rps').textContent = `${Number(traffic.rps ?? traffic.real_requests_per_sec ?? 0).toFixed(1)}/s`;
    $('pulse-errors').textContent = `${Number(traffic.error_rate ?? traffic.failure_rate ?? 0).toFixed(1)}%`;
    $('bridge-state').textContent = runActive ? '● Live IEMCRP scenario mirror' : 'PortalPulse demo idle';
    $('run-linked-demo').disabled = runActive;
    $('stop-linked-demo').disabled = !runActive;
  }

  async function refresh() {
    try {
      const response = await fetch('/api/v1/live-demo/snapshot');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const snapshot = await response.json();
      setReadout(snapshot.traffic);
    } catch {
      $('bridge-state').textContent = 'PortalPulse connection unavailable';
    }
  }

  $('preview-notice').onclick = () => card(examples[exampleIndex++ % examples.length]);
  $('run-linked-demo').onclick = async () => {
    $('run-linked-demo').disabled = true;
    try {
      const response = await fetch('/api/v1/live-demo/start', {method: 'POST'});
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }
      lastPhase = '';
      card({kind: 'action', source: 'PULSEBOT · SCENARIO STARTED', title: 'Watch the crowd and the response', detail: 'PortalPulse has started the capped IEMCRP demo. The cards here will follow its measured traffic, model decisions, M7 actions, and recovery.', footer: 'Maximum 6 workers · 12 real requests/s · automatic stop within 100 seconds'});
      await refresh();
    } catch (error) {
      card({kind: 'warning', source: 'DEMO CONTROL', title: 'The scenario did not start', detail: String(error.message || error), footer: 'The safety limit or restart cooldown may be active.'});
      await refresh();
    }
  };
  $('stop-linked-demo').onclick = async () => {
    await fetch('/api/v1/live-demo/stop', {method: 'POST'}).catch(() => {});
    await refresh();
  };

  const stream = new EventSource('/api/v1/stream/events');
  stream.addEventListener('traffic', event => {
    try {
      const item = JSON.parse(event.data);
      if (item.scenario !== 'IEMCRP_RESULT_DAY_LIVE_DEMO') return;
      setReadout(item);
      if (!item.is_running || item.is_paused || item.phase === lastPhase) return;
      lastPhase = item.phase;
      const notice = phaseNotices[item.phase];
      if (notice) card({kind: ['CONTROLLED_RECOVERY', 'NORMAL'].includes(item.phase) ? 'recovery' : 'warning', source: 'LIVE IEMCRP SCENARIO · NIRANTAR OVERLAY', title: notice[0], detail: notice[1], footer: `${Number(item.virtual_users || 0).toLocaleString()} scenario users · ${Number(item.rps || 0).toFixed(1)} measured req/s`});
    } catch (error) { console.error(error); }
  });
  stream.addEventListener('actuation', event => {
    try {
      const item = JSON.parse(event.data);
      if (item.portal_id !== 'college_portal' || !['EXECUTED', 'SUCCESS'].includes(item.status)) return;
      card({kind: 'action', source: 'PULSEBOT · M7 APPLIED ON IEMCRP DEMO', title: `PortalPulse applied ${String(item.action || 'an action').replaceAll('_', ' ')}`, detail: 'The safety-approved actuator changed the simulated IEMCRP portal. PortalPulse is now checking later request measurements; this did not change Nirantar.', footer: `Cycle ${item.cycle_id || '—'} · verification pending`, id: `action:${item.cycle_id}`});
    } catch (error) { console.error(error); }
  });
  for (const type of ['warning', 'recovery']) stream.addEventListener(type, event => {
    try {
      const item = JSON.parse(event.data);
      if (!['college_portal', 'nirantar'].includes(item.portal_id)) return;
      if (item.portal_id === 'college_portal' && !runActive) return;
      const native = item.portal_id === 'nirantar';
      const verified = item.is_recovered && item.verification_status === 'RECOVERY_VERIFIED';
      card({
        kind: type === 'warning' ? 'warning' : verified ? 'action' : 'recovery',
        source: native ? 'LIVE NIRANTAR PROTOTYPE EVENT' : verified ? 'PULSEBOT · VERIFIED DEMO RECOVERY' : `LIVE IEMCRP ${type.toUpperCase()} · OVERLAY`,
        title: item.title || item.id || 'Portal status update',
        detail: native ? item.why_it_happened || item.message || 'Nirantar prototype update.' : `${item.why_it_happened || item.what_happened || item.message || 'Measured demo condition.'} ${item.what_portalpulse_did || (verified ? 'M7 action verified by the next M1 sample.' : 'PortalPulse continues to monitor.')}`,
        footer: `${native ? 'Nirantar prototype' : 'IEMCRP demo portal'} · ${new Date().toLocaleTimeString()}`,
        id: `${type}:${item.id || item.cycle_id || item.timestamp}`
      });
    } catch (error) { console.error(error); }
  });
  stream.addEventListener('demo_reset', () => {lastPhase = ''; seen.clear(); $('notice-stack').replaceChildren(); refresh();});
  stream.addEventListener('demo_stopped', () => {runActive = false; refresh(); card({kind: 'action', source: 'PULSEBOT · LOAD STOPPED', title: 'Generated requests have stopped', detail: 'The scenario workers are stopped. Earlier graph samples remain available on PortalPulse Traffic and AI Models.', footer: 'No new demo load is being generated.'});});
  stream.onerror = () => {$('bridge-state').textContent = 'Reconnecting to PortalPulse…';};
  refresh();
})();
