(() => {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (v, n=1) => Number.isFinite(Number(v)) ? Number(v).toFixed(n) : '—';
  const kv = (label,value) => `<div class="kv"><span>${esc(label)}</span><b>${esc(value)}</b></div>`;
  const state = {snapshot:null,warnings:[],latestStage:'',cycleIds:[],scoreHistory:[],series:[],cycles:[],lastActuation:null,lastVerified:null,pinnedMitigation:null,pinnedVerified:null,runStartedAt:0,replayIndex:-1};
  try{const saved=JSON.parse(sessionStorage.getItem('portalpulse_demo_evidence')||'{}');if(Date.now()-Number(saved.savedAt||0)<60*60*1000){state.pinnedMitigation=saved.mitigation||null;state.pinnedVerified=saved.verified||null}}catch{}
  const base = location.origin;
  const phases = ['BASELINE','RAMP','RESULT_RUSH','SATURATION','ANOMALY_DETECTION','POLICY_ACTION','CONTROLLED_RECOVERY','RATE_LIMIT_PRESSURE','GATEWAY_FAILURE','SUSTAINED_LOAD','SECOND_WAVE','NORMAL'];
  const phaseStories = {
    BASELINE:['Baseline is being measured','PortalPulse learns the current request and latency shape.'],
    RAMP:['Demand is rising','Watch real requests and concurrent workers climb.'],
    RESULT_RUSH:['Results are opening','Students and staff are exercising the IEMCRP routes.'],
    SATURATION:['The database is under pressure','A local DB pool and latency fault is applied to the simulator.'],
    ANOMALY_DETECTION:['The models are investigating','The detector and root-cause classifier inspect measured telemetry.'],
    POLICY_ACTION:['A response is being checked','The neural policy recommends; capability and safety rules decide what can run.'],
    CONTROLLED_RECOVERY:['Post-action telemetry is arriving','The verifier compares measured portal behavior before and after.'],
    RATE_LIMIT_PRESSURE:['Refresh storm meets an ingress limit','Measured 429 responses show the portal throttling excess requests. Fast rejections can lower p95 while the failure line rises.'],
    GATEWAY_FAILURE:['A dependency is failing','Measured 503 responses test the detector and safety-gated response. A low response time with many failures is still a bad outcome.'],
    SUSTAINED_LOAD:['The injected faults have cleared','The portal serves real requests while the loop checks whether latency stays low.'],
    SECOND_WAVE:['A second crowd arrives','A new arrival wave tests whether the portal can keep serving after recovery.'],
    NORMAL:['The full journey is complete','Inspect the action and verification below; actual results are retained.']
  };
  const stages = [
    ['TRAFFIC',null,'♟','Generated portal requests'],['M1 TELEMETRY','M1','⌁','Measured metrics'],
    ['M2 FORECAST','M2','↗','Future demand'],['M3 ANOMALY','M3','◎','Outlier score'],
    ['M4 ROOT CAUSE','M4','◇','Likely cause'],['NETWORKX PATH',null,'◈','Causal path'],
    ['M5 NEURAL POLICY','M5','✧','Action probabilities'],['M6 SAFETY','M6','✓','Guardrail'],
    ['M7 ACTUATION','M7','⚙','Portal action'],['POST-ACTION','VERIFY','↻','Verification']
  ];
  let currentView = 'command';
  function navigate(view, updateHash=true) {
    if(view==='nirantar') view='guide';
    if(view==='policy') view='intelligence';
    if(view==='response') view='traffic';
    if (!document.querySelector(`[data-view-panel="${view}"]`)) view='command';
    currentView=view;
    document.querySelectorAll('[data-view-panel]').forEach(el=>el.classList.toggle('active',el.dataset.viewPanel===view));
    document.querySelectorAll('.page-nav [data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
    if(updateHash) history.replaceState(null,'',`#${view}`);if(view==='traffic')loadRecoveryHistory();
    window.scrollTo({top:0,behavior:'smooth'});
  }
  document.addEventListener('click',e=>{const target=e.target.closest('[data-view]');if(target)navigate(target.dataset.view)});
  const legacyViews={overview:'command',portals:'command',monitoring:'traffic',simulation:'traffic',incidents:'traffic',actions:'intelligence',integrations:'guide',settings:'guide'};
  const resolveView=hash=>hash.startsWith('/app/')?(legacyViews[hash.split('/')[2]]||'command'):(hash||'command');
  window.addEventListener('hashchange',()=>navigate(resolveView(location.hash.slice(1)),false));
  const initialHash=location.hash.slice(1);
  const initialView=resolveView(initialHash);
  navigate(initialView,false);
  if(initialHash.startsWith('/app/'))history.replaceState(null,'',`/website#${initialView}`);
  const requestedNirantar = new URLSearchParams(location.search).get('nirantar') || localStorage.getItem('portalpulse_nirantar_url');
  const defaultNirantar = 'https://bronze-tinsel-n8pb.here.now/';
  let currentNirantarURL='';
  const setNirantar = url => {try{const clean=new URL(url);if(!['https:','http:'].includes(clean.protocol))return;currentNirantarURL=clean.href;$('open-nirantar').href='/static/nirantar-live.html?site='+encodeURIComponent(clean.href);$('open-nirantar-direct').href=clean.href;$('nirantar-frame').src=clean.href}catch{}};
  setNirantar(requestedNirantar||defaultNirantar);
  async function api(path,method='GET',body){const res=await fetch(base+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});if(!res.ok)throw new Error(`${res.status} ${await res.text()}`);return res.json()}
  function drawSeries(el, values, color, maxHint=0, second) {
    if(!el)return;
    const nums=values.map(Number).filter(Number.isFinite);
    const max=Math.max(1,maxHint,...nums)*1.1;
    const left=39,right=628,top=17,bottom=211;
    const points=arr=>arr.map((v,i)=>[left+i/Math.max(1,arr.length-1)*(right-left),bottom-(Number(v)/max)*(bottom-top)]);
    const plot=arr=>points(arr).map(p=>p.join(',')).join(' ');
    const grid=[0,.25,.5,.75,1].map(n=>`<line x1="${left}" y1="${bottom-(bottom-top)*n}" x2="${right}" y2="${bottom-(bottom-top)*n}" stroke="#e9edfa" stroke-dasharray="4 5"/><text x="3" y="${bottom-(bottom-top)*n+3}" font-size="9" font-weight="700" fill="#91a0be">${fmt(max*n,0)}</text>`).join('');
    const fill=nums.length>1?`<polygon points="${left},${bottom} ${plot(nums)} ${right},${bottom}" fill="${color}" opacity=".13"/>`:'';
    const line=nums.length>1?`<path d="${smoothPath(points(nums))}" fill="none" stroke="${color}" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round"/>`:'';
    let extra='';
    if(second?.length>1){const mx=Math.max(1,...second.map(Number))*1.1;const pts=second.map((v,i)=>[left+i/Math.max(1,second.length-1)*(right-left),bottom-(Number(v)/mx)*(bottom-top)]);extra=`<path d="${smoothPath(pts)}" fill="none" stroke="#ea64a6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><text x="574" y="13" font-size="9" font-weight="800" fill="#d94c96">${fmt(mx,0)} ms</text><text x="596" y="226" font-size="9" font-weight="800" fill="#d94c96">0 ms</text>`}
    const dots=points(nums).map(([x,y],i)=>i%Math.max(1,Math.floor(nums.length/16))===0||i===nums.length-1?`<circle cx="${x}" cy="${y}" r="${i===nums.length-1?5:2.5}" fill="${color}" stroke="#fff" stroke-width="1.5"><title>Measured sample ${i+1} · ${fmt(nums[i],1)}</title></circle>`:'').join('');
    el.innerHTML=grid+fill+line+extra+dots+`<text x="${left}" y="226" font-size="9" fill="#7085ad">Earlier samples</text><text x="${right}" y="226" text-anchor="end" font-size="9" fill="#7085ad">Latest</text>`;
  }
  function ingestCycles(s){
    const old=state.cycles.at(-1),incoming=s.latest;
    const oldNumber=Number(old?.cycle_id?.split('_')[1]),newNumber=Number(incoming?.cycle_id?.split('_')[1]);
    const pin=state.pinnedMitigation||state.pinnedVerified,pinNumber=Number(pin?.cycle_id?.split('_')[1]);
    if(pin&&Number.isFinite(newNumber)&&Number.isFinite(pinNumber)&&newNumber<pinNumber&&Date.parse(incoming?.timestamp)>Date.parse(pin.timestamp)){state.pinnedMitigation=null;state.pinnedVerified=null;sessionStorage.removeItem('portalpulse_demo_evidence')}
    if(Number.isFinite(oldNumber)&&Number.isFinite(newNumber)&&newNumber<oldNumber&&Date.parse(incoming?.timestamp)>Date.parse(old?.timestamp)){
      state.cycles=[];state.series=[];state.pinnedMitigation=null;state.pinnedVerified=null;sessionStorage.removeItem('portalpulse_demo_evidence');
    }
    for(const cycle of s.history||[]){
      if(cycle.portal_id!=='college_portal'||!cycle.cycle_id||(state.runStartedAt&&Date.parse(cycle.timestamp)<state.runStartedAt))continue;
      const existing=state.cycles.findIndex(c=>c.cycle_id===cycle.cycle_id);
      if(existing>=0)state.cycles[existing]=cycle;
      else state.cycles.push(cycle);
    }
    rememberEvidence(state.cycles);
    state.cycles=state.cycles.slice(-90);
  }
  function rememberEvidence(cycles){
    let changed=false;
    for(const c of cycles){
      if(c.actuation?.status!=='SUCCESS')continue;
      if(c.verification_status==='RECOVERY_VERIFIED'&&Date.parse(c.timestamp)>Date.parse(state.pinnedVerified?.timestamp||0)){state.pinnedVerified=c;changed=true}
      if(!['SCALE_IN_WORKERS','NO_OP'].includes(c.recommended_action)&&Date.parse(c.timestamp)>Date.parse(state.pinnedMitigation?.timestamp||0)){state.pinnedMitigation=c;changed=true}
    }
    if(changed)try{sessionStorage.setItem('portalpulse_demo_evidence',JSON.stringify({mitigation:state.pinnedMitigation,verified:state.pinnedVerified,savedAt:Date.now()}))}catch{}
  }
  async function preloadCycleHistory(){
    try{
      const history=await api('/api/v1/control-loop/history?limit=100');
      if(!Array.isArray(history))return;
      const seen=new Set(state.cycles.map(c=>c.cycle_id));
      for(const c of history){if(c.portal_id==='college_portal'&&c.cycle_id&&!seen.has(c.cycle_id)&&(!state.runStartedAt||Date.parse(c.timestamp)>=state.runStartedAt)){state.cycles.push(c);seen.add(c.cycle_id)}}
      state.cycles.sort((a,b)=>Date.parse(a.timestamp)-Date.parse(b.timestamp));
      rememberEvidence(state.cycles);
      state.cycles=state.cycles.slice(-90);
      if(state.snapshot){renderModelTrends();renderActionImpact(state.snapshot);renderControlStory(state.snapshot)}
    }catch(e){console.warn('Recent cycle history unavailable',e)}
  }
  function linePoints(values,left,right,top,bottom,max){
    return values.map((v,i)=>`${(left+i/Math.max(1,values.length-1)*(right-left)).toFixed(1)},${(bottom-Math.max(0,Number(v)||0)/max*(bottom-top)).toFixed(1)}`).join(' ');
  }
  // Bezier segments interpolate only between measured samples; circles remain the actual readings.
  function smoothPath(points){
    if(!points.length)return '';
    if(points.length===1)return `M ${points[0][0]} ${points[0][1]}`;
    let d=`M ${points[0][0]} ${points[0][1]}`;
    for(let i=0;i<points.length-1;i++){
      const a=points[Math.max(0,i-1)],b=points[i],c=points[i+1],e=points[Math.min(points.length-1,i+2)];
      const dx=(c[0]-b[0])/6;
      const c1y=b[1]+(c[1]-a[1])/6,c2y=c[1]-(e[1]-b[1])/6;
      d+=` C ${b[0]+dx} ${c1y} ${c[0]-dx} ${c2y} ${c[0]} ${c[1]}`;
    }
    return d;
  }
  function renderControlStory(s){
    const cycles=state.cycles.slice(-48),freshLatest=!state.runStartedAt||Date.parse(s.latest?.timestamp)>=state.runStartedAt;
    const latest=freshLatest?(s.latest||{}):{},n=cycles.length;
    $('control-live-state').textContent=s.traffic.is_running?'● LIVE · '+s.traffic.phase.replaceAll('_',' '):'● DEMO STOPPED';
    $('control-chart-count').textContent=`${n} cycles · now ${fmt(cycles.at(-1)?.pre_metrics?.p95_ms,0)} ms / ${fmt(cycles.at(-1)?.pre_metrics?.db_connections,0)}% DB`;
    $('model-cycle-caption').textContent=latest.cycle_id?`Cycle ${latest.cycle_id.split('_')[1]} · ${new Date(latest.timestamp).toLocaleTimeString()} · ${s.traffic.is_running?'traffic running':'history paused — run a scenario for new points'}`:'No IEMCRP cycles yet · run a scenario for live model graphs';
    const svg=$('control-chart');
    if(!n){svg.innerHTML='<text x="400" y="130" text-anchor="middle" fill="#7385ae" font-size="16">Waiting for measured cycles…</text>';$('control-decision').innerHTML='<div class="control-decision-card"><small>Awaiting cycle</small><strong>Observing the portal</strong><p>The next model cycle will show its recommendation and safety decision here.</p></div>';$('control-outcome').innerHTML='<div class="control-outcome pending">No action in this run yet.</div>';return}
    const L=48,R=750,T=28,B=222;
    const latency=cycles.map(c=>Number(c.pre_metrics?.p95_ms??c.input_telemetry?.response_time??0));
    const db=cycles.map(c=>Number(c.pre_metrics?.db_connections??c.input_telemetry?.db_connections??0));
    const lm=Math.max(100,Math.ceil(Math.max(...latency,100)/100)*100),dm=Math.max(100,Math.ceil(Math.max(...db,100)/25)*25);
    const x=i=>L+i/Math.max(1,n-1)*(R-L),y=(v,max)=>B-Math.max(0,v)/max*(B-T);
    let marks='';
    cycles.forEach((c,i)=>{
      const applied=c.actuation?.status==='SUCCESS';
      const blocked=c.safety_decision==='REJECTED'&&!(cycles[i-1]?.safety_decision==='REJECTED'&&cycles[i-1]?.recommended_action===c.recommended_action);
      if(!applied&&!blocked)return;
      const color=applied?(c.verification_status==='RECOVERY_VERIFIED'?'#16a878':'#e99a20'):'#e25b75';
      marks+=`<line x1="${x(i)}" y1="${T}" x2="${x(i)}" y2="${B}" stroke="${color}" stroke-width="1.5" stroke-dasharray="5 5" opacity=".65"/><circle cx="${x(i)}" cy="${y(latency[i],lm)}" r="5" fill="${color}" stroke="#fff" stroke-width="2"><title>${esc((applied?'M7 applied · '+c.verification_status:'M6 blocked')+' · '+c.recommended_action)}</title></circle>`;
    });
    const grid=[0,.25,.5,.75,1].map(q=>`<line x1="${L}" y1="${B-q*(B-T)}" x2="${R}" y2="${B-q*(B-T)}" stroke="#dfebfa" stroke-dasharray="5 5"/><text x="4" y="${B-q*(B-T)+4}" fill="#6076a8" font-size="12">${Math.round(lm*q)} ms</text><text x="758" y="${B-q*(B-T)+4}" fill="#aa7a30" font-size="12">${Math.round(dm*q)}%</text>`).join('');
    const dbPts=linePoints(db,L,R,T,B,dm),latPts=linePoints(latency,L,R,T,B,lm);
    const lastX=x(n-1);
    const pointLabels=cycles.map((c,i)=>`<circle cx="${x(i)}" cy="${y(latency[i],lm)}" r="3" fill="#1e91ec" opacity=".8"><title>Cycle ${esc(c.cycle_id?.split('_')[1])} · M1 p95 ${fmt(latency[i],1)} ms · DB ${fmt(db[i],1)}% · ${esc(c.recommended_action)}</title></circle>`).join('');
    svg.innerHTML=grid+`<path d="${smoothPath(db.map((v,i)=>[x(i),y(v,dm)]))}" fill="none" stroke="#f3a329" stroke-width="3" stroke-linecap="round"/><path d="${smoothPath(latency.map((v,i)=>[x(i),y(v,lm)]))}" fill="none" stroke="#1e91ec" stroke-width="4" stroke-linecap="round"/>${pointLabels}${marks}<circle cx="${lastX}" cy="${y(latency.at(-1),lm)}" r="6" fill="#1e91ec" stroke="white" stroke-width="3"/><circle cx="${lastX}" cy="${y(db.at(-1),dm)}" r="5" fill="#f3a329" stroke="white" stroke-width="2"/>`;
    const recommendation=(latest.recommended_action||'NO_OP').replaceAll('_',' ');
    const reason=latest.safety_validation?.rejection_reasons?.[0];
    let status='Monitoring';
    if(latest.actuation?.status==='SUCCESS'&&latest.verification_status==='RECOVERY_VERIFIED')status='M7 applied · recovery verified';
    else if(latest.actuation?.status==='SUCCESS')status=latest.verification_status==='OBSERVING'?'M7 applied · checking next window':'M7 applied · recovery not verified';
    else if(latest.actuation_status==='FAILED')status='M7 execution failed';
    else if(latest.safety_decision==='REJECTED')status='M6 safety blocked action';
    else if(latest.safety_decision==='NO_ACTION_REQUIRED')status='No action required';
    $('control-decision').innerHTML=`<div class="control-decision-card ${latest.safety_decision==='REJECTED'?'blocked':latest.actuation?.status==='SUCCESS'?(latest.verification_status==='RECOVERY_VERIFIED'?'executed':'unverified'):''}"><small>${esc(status)}</small><strong>${esc(recommendation)}</strong><p>${esc(reason||latest.action_recommendation?.tactical_rationale||'The control loop is watching measured portal health.')}</p></div>`;
    const acted=[...state.cycles].reverse().find(c=>c.actuation?.status==='SUCCESS'||c.actuation_status==='FAILED');
    if(acted){
      const before=acted.pre_metrics||{},after=acted.post_metrics||{};
      const delta=Number(before.p95_ms)-Number(after.p95_ms);
      $('control-outcome').innerHTML=`<div class="control-outcome"><small>LAST M7 ATTEMPT · ${esc(acted.verification_status||'PENDING')}</small><b>${esc(acted.recommended_action.replaceAll('_',' '))}</b><div><span>Before <strong>${fmt(before.p95_ms,0)} ms</strong></span><span class="outcome-arrow">→</span><span>After <strong>${after.p95_ms===undefined?'Pending':fmt(after.p95_ms,0)+' ms'}</strong></span></div><p>${Number.isFinite(delta)?delta===0?'p95 unchanged after action':`${Math.abs(delta).toFixed(0)} ms ${delta>0?'lower':'higher'} p95 after action`:'Post-action sample pending'} · ${esc(acted.verification_status==='RECOVERY_VERIFIED'?'Recovery verified across full telemetry':acted.verification_status==='OBSERVING'?'Checking next measured window':'Recovery not verified')}</p></div>`;
    }else $('control-outcome').innerHTML='<div class="control-outcome pending">No M7 execution in the visible cycle history yet. Start the scenario or inject pressure to observe a decision.</div>';
  }
  function renderMetrics(s){
    const t=s.traffic,p=s.pool,lastCycle=state.cycles.at(-1),fresh=t.is_running?'measured now':'last control cycle',lastP95=lastCycle?.input_telemetry?.p95_ms??lastCycle?.pre_metrics?.p95_ms??t.p95,items=[
      ['Virtual users',t.current_vus,'scenario scale','#8158e3'],['Real requests / sec',fmt(t.real_requests_per_sec),fresh,'#19b7dc'],['p95 latency',fmt(t.is_running?t.p95:lastP95)+' ms',fresh,'#e85fab'],['Failure rate',fmt(t.failure_rate)+'%',fresh,'#ec7280'],['DB peak (3s)',fmt(p.recent_peak_utilization_percent??p.utilization_percent)+'%',fresh,'#f1a233'],['Control cycle',(s.latest?.cycle_id||'—').split('_').slice(0,2).join(' #'),t.is_running?'every 3 seconds':'generator stopped','#496bea']
    ];
    $('metrics').innerHTML=items.map(([label,value,note,color])=>`<div class="metric" style="--accent:${color}"><small>${esc(label)}</small><strong>${esc(value)}</strong><em>${esc(note)}</em></div>`).join('');
    const more=[['Generated workers',t.real_concurrency_workers],['In-flight requests',t.in_flight_requests],['DB waiting queries',p.waiting_queries],['p50 latency',fmt(t.p50)+' ms'],['p99 latency',fmt(t.p99)+' ms'],['Successful requests',fmt(t.success_rate)+'%']];
    $('traffic-metrics').innerHTML=more.map(([label,value])=>`<div class="metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`).join('');
  }
  function renderTraffic(s){
    const t=s.traffic,p=s.pool;
    const last=state.series.at(-1);
    const fresh={rps:Number(t.real_requests_per_sec||0),p95:Number(t.p95||0),db:Number(p.recent_peak_utilization_percent??p.utilization_percent??0),errors:Number(t.failure_rate||0),time:Date.now()};
    if(t.is_running&&(!last||fresh.time-last.time>=1000)){state.series.push(fresh);state.series=state.series.slice(-90)}
    const series=key=>state.series.map(x=>x[key]);
    drawSeries($('traffic-chart'),series('rps'),'#17b9e3');drawSeries($('latency-chart'),series('p95'),'#e765ac');drawSeries($('db-chart'),series('db'),'#f4ac38',100);drawSeries($('error-chart'),series('errors'),'#ee7180',100);
    drawSeries($('command-chart'),series('rps'),'#16bde3',0,series('p95'));
    $('rps-caption').textContent=fmt(t.real_requests_per_sec)+' req/s'+(t.is_running?'':' · last');$('latency-caption').textContent=fmt(t.p95)+' ms'+(t.is_running?'':' · last');$('db-caption').textContent=fmt(p.recent_peak_utilization_percent??p.utilization_percent)+'% · 3s observed peak'+(t.is_running?'':' · last');$('error-caption').textContent=fmt(t.failure_rate)+'%'+(t.is_running?'':' · last');$('chart-now').textContent=t.is_running?new Date().toLocaleTimeString():'Generator stopped';
    $('traffic-phase').textContent=t.phase.replaceAll('_',' ');
    $('scenario-elapsed').textContent=`${String(Math.floor((t.elapsed||0)/60)).padStart(2,'0')}:${String(Math.floor((t.elapsed||0)%60)).padStart(2,'0')}`;
    const idx=phases.indexOf(t.phase);$('phase-track').innerHTML=phases.map((ph,i)=>`<div class="phase-step ${i===idx?'current':i<idx?'done':''}"><i></i>${esc(ph.replaceAll('_',' '))}</div>`).join('');
    const story=phaseStories[t.phase]||['Monitoring traffic','Control loop active'];$('story-title').textContent=`Case ${Math.max(1,idx+1)} of ${phases.length} · ${story[0]}`;$('story-detail').textContent=`${story[1]} ${t.is_running?'Measured now':'Last request sample'}: ${fmt(t.real_requests_per_sec)} req/s, ${fmt(t.p95,0)} ms p95, ${fmt(t.failure_rate)}% failures.`;
    $('transactions').innerHTML=(s.transactions||[]).slice(-10).reverse().map(x=>`<span><b>${esc(x.persona)}</b><span>${esc(x.endpoint)}</span><b>${esc(x.status)} · ${fmt(x.latency)} ms</b></span>`).join('')||'<p>Transactions appear when traffic starts.</p>';
    document.querySelector('.model-live-note .live-chip').textContent=t.is_running?'● LIVE MODEL CYCLES':'● CONTROL CYCLES · GENERATOR STOPPED';
    $('command-chart').closest('.panel').querySelector('.live-chip').textContent=t.is_running?'● LIVE REQUESTS':'● LAST REQUEST SAMPLE';
  }
  function stageData(s,label,key){const c=s.latest||{};if(label==='TRAFFIC')return {status:s.traffic.is_running?'RUNNING':'IDLE',input_summary:{phase:s.traffic.phase},output_summary:{rps:s.traffic.real_requests_per_sec}};if(label==='NETWORKX PATH')return {status:c.cycle_id?'COMPLETE':'WAITING',output_summary:{path:c.causal_path||[]}};return c.models?.[key]}
  function stageSummary(label,d){if(!d)return 'Awaiting cycle';const o=d.output_summary||{};if(label==='TRAFFIC')return `${fmt(o.rps)} real req/s`;if(label==='NETWORKX PATH')return (o.path||[]).join(' → ')||'No path';if(label==='M2 FORECAST')return `+5m ${fmt(o.predicted_rps)} req/s`;if(label==='M3 ANOMALY')return `${fmt(o.anomaly_score,3)} · ${o.severity||'—'}`;if(label==='M4 ROOT CAUSE')return o.rca_class||'—';if(label==='M5 NEURAL POLICY')return o.selected_action||'—';if(label==='M6 SAFETY')return o.decision||'—';if(label==='M7 ACTUATION')return o.result||o.status||d.status||'—';if(label==='POST-ACTION')return o.status||d.status||'—';return d.status||'—'}
  function renderCommandArchitecture(s){
    const c=s.latest||{};
    $('arch-cycle').textContent=(c.cycle_id||'Awaiting cycle').split('_').slice(0,2).join(' #');
    const m7=c.actuation_status==='EXECUTED'?'applied the approved change':c.safety_decision==='REJECTED'?'held the change under the M6 safety rule':'continued monitoring without a portal change';
    $('command-sentence').textContent=c.cycle_id?`M1 measured ${fmt(c.input_telemetry?.requests_per_sec)} req/s. M5 proposed ${(c.recommended_action||'NO_OP').replaceAll('_',' ')}; M6 said ${(c.safety_decision||'WAITING').replaceAll('_',' ')}. M7 ${m7}. Open AI Models for the full causal path and proof.`:'The first control cycle will connect measured traffic, the model recommendation, safety decision, and action here.';
  }
  function renderPipeline(s){
    const c=s.latest||{};
    $('flow-cycle').textContent=c.cycle_id?`Cycle ${c.cycle_id.split('_')[1]} · ${new Date(c.timestamp).toLocaleTimeString()}`:'Awaiting first cycle';
    $('architecture-live').innerHTML=stages.map(([label,key,icon],i)=>{
      const d=stageData(s,label,key),rawStatus=d?.status||'WAITING',active=state.replayIndex===i||key&&state.latestStage===key;
      const held=key==='M7'&&rawStatus==='SKIPPED',awaiting=key==='VERIFY'&&rawStatus==='SKIPPED';
      const summary=held?(c.safety_decision==='REJECTED'?'Held by M6 safety':'No portal change'):awaiting?'Awaiting applied action':stageSummary(label,d);
      const status=held?(c.safety_decision==='REJECTED'?'SAFETY HOLD':'MONITORING'):awaiting?'NOT RUN':rawStatus;
      return `<div class="architecture-step ${active?'active':''} ${held?'held':''} ${key==='M7'&&c.actuation?.status==='SUCCESS'?'applied':''}"><span>${icon}</span><small>${esc(label)}</small><b>${esc(summary)}</b><em>${esc(status)}${d?.inference_time_ms?` · ${fmt(d.inference_time_ms,1)} ms`:''}</em></div>`;
    }).join('');
    $('cycle-history').innerHTML=(s.history||[]).slice(-12).map(x=>`<span>${esc(x.cycle_id)}</span>`).join('');
    renderAutomationExplanation(s);
    renderModelProof(s);
  }
  function renderAutomationExplanation(s){
    const c=s.latest||{},acted=state.pinnedMitigation||[...state.cycles].reverse().find(x=>x.actuation?.status==='SUCCESS'),pre=acted?.pre_metrics||{},post=acted?.post_metrics||{};
    const pressure=Number(s.pool?.utilization_percent||0),hot=s.traffic?.is_running&&(pressure>=85||Number(s.traffic?.failure_rate||0)>=8);
    const actionName=(acted?.recommended_action||'').replaceAll('_',' '),verified=acted?.verification_status==='RECOVERY_VERIFIED';
    const actionDetail=acted?`${actionMechanism(acted)} · ${new Date(acted.timestamp).toLocaleTimeString()}`:'M7 has not applied a change in the visible cycle history.';
    const result=acted?`p95 ${fmt(pre.p95_ms,0)} → ${fmt(post.p95_ms,0)} ms · DB ${fmt(pre.db_connections,0)} → ${fmt(post.db_connections,0)}%`:'The next applied action will add a measured before and after result here.';
    $('automation-explainer').innerHTML=`<div class="response-head"><span class="eyebrow">LIVE PRESSURE ↔ PORTAL CONTROL</span><h3>What is pushing the portal, and what actually pushed back?</h3><p>These are local measurements and recorded M7 actions, not a simulated animation of an action.</p></div><div class="response-arc"><div class="response-card pressure ${hot?'hot':''}"><small>01 · PRESSURE · ${s.traffic?.is_running?'LIVE':'LAST SAMPLE'}</small><strong>${fmt(pressure,0)}% DB pool</strong><span>${fmt(s.traffic?.p95,0)} ms p95 · ${fmt(s.traffic?.failure_rate,1)}% failures</span></div><div class="response-arc-arrow">↔</div><div class="response-card intervention ${acted?'did-act':''}"><small>02 · LAST RECORDED M7 INTERVENTION</small><strong>${esc(actionName||'Watching for an approved action')}</strong><span>${esc(actionDetail)}</span></div><div class="response-arc-arrow">→</div><div class="response-card outcome ${verified?'verified':acted?'unverified':''}"><small>03 · MEASURED OUTCOME</small><strong>${acted?verified?'Recovery verified across full telemetry':acted.verification_status==='OBSERVING'?'Checking next measured window':'Recovery not verified':'Awaiting action'}</strong><span>${esc(result)}</span></div></div><p class="response-status">Current cycle: M5 ${esc((c.recommended_action||'—').replaceAll('_',' '))} · M6 ${esc((c.safety_decision||'—').replaceAll('_',' '))}. ${c.safety_decision==='REJECTED'?'Safety is holding this cycle; no portal change is claimed.':''}</p>`;
  }
  function renderModelProof(s){
    const c=s.latest||{},m=s.models||{};
    const rows=[['M2 · XGBoost','m2_loaded','M2'],['M3 · Isolation Forest','m3_loaded','M3'],['M4 · RCA','m4_loaded','M4'],['M5 · PyTorch MLP','m5_loaded','M5']];
    $('model-proof').innerHTML=`<div><small>MODEL RUNTIME · CURRENT CYCLE</small><h4>Are the models actually running?</h4><p>Each badge combines the loaded checkpoint flag with the execution record from this cycle. A fallback is shown explicitly.</p></div><div class="proof-rows">${rows.map(([name,flag,key])=>{const r=c.models?.[key],loaded=Boolean(m[flag]),fallback=r?.model_version==='fallback-safe'||r?.status==='FALLBACK';return `<div><b>${name}</b><span class="${loaded&&!fallback&&r?.status==='COMPLETE'?'ok':'warn'}">${!loaded?'NOT LOADED':fallback?'FALLBACK':r?.status==='COMPLETE'?'INFERENCE COMPLETE':'AWAITING CYCLE'}</span><small>${esc(r?.model_version||'—')} · ${fmt(r?.inference_time_ms,1)} ms</small></div>`}).join('')}</div><p class="proof-scope">This is a local IEMCRP simulation: HTTP requests and measurements are local; model inference uses loaded files when available; M7 changes only the demo portal infrastructure. No production system is connected by this page.</p>`;
  }
  function renderForecastSvg(c){
    const horizons=['5m','10m','15m'];
    const values=[Number(c.input_telemetry?.requests_per_sec||0),...horizons.map(h=>Number(c.forecast?.[`${h}_forecast`]?.requests_per_sec||0))];
    const max=Math.max(10,...values)*1.15,L=45,R=376,T=17,B=103;
    const point=(v,i)=>[L+i*(R-L)/3,B-v/max*(B-T)];
    const points=values.map((v,i)=>point(v,i).join(',')).join(' ');
    const ticks=[0,.5,1].map(q=>`<line x1="${L}" y1="${B-q*(B-T)}" x2="${R}" y2="${B-q*(B-T)}" stroke="#dfe7f9" stroke-dasharray="4 4"/><text x="2" y="${B-q*(B-T)+3}" fill="#7387b1" font-size="9">${fmt(max*q,0)}</text>`).join('');
    $('forecast-chart').innerHTML=ticks+`<polygon points="${L},${B} ${points} ${R},${B}" fill="#8b5beb" opacity=".13"/><polyline points="${points}" fill="none" stroke="#8053e4" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>${values.map((v,i)=>{const [x,y]=point(v,i);return `<circle cx="${x}" cy="${y}" r="4.5" fill="${i?'#8053e4':'#1b9de5'}" stroke="#fff" stroke-width="2"/><text x="${x}" y="${Math.max(11,y-8)}" text-anchor="middle" fill="#5e4db0" font-size="9" font-weight="800">${fmt(v,0)}</text><text x="${x}" y="126" text-anchor="middle" fill="#687da8" font-size="9">${['Now','+5m','+10m','+15m'][i]}</text>`}).join('')}`;
  }
  function renderAnomalySvg(threshold){
    const cycles=state.cycles.slice(-30);
    const values=cycles.map(c=>Number(c.anomaly?.anomaly_score||0));
    const latencies=cycles.map(c=>Number(c.pre_metrics?.p95_ms??c.input_telemetry?.response_time??0));
    if(!cycles.length){$('anomaly-chart').innerHTML='<text x="200" y="70" text-anchor="middle" fill="#7184ad" font-size="12">Run a scenario to collect model cycles</text>';return}
    const L=36,R=380,T=16,B=105,max=1;
    const ty=B-Number(threshold||.45)*(B-T);
    const current=values.at(-1);
    const minLat=Math.min(...latencies),maxLat=Math.max(...latencies),latPad=Math.max(8,(maxLat-minLat)*.18),latLow=Math.max(0,minLat-latPad),latHigh=maxLat+latPad;
    const px=i=>L+i/Math.max(1,values.length-1)*(R-L);
    const py=v=>B-(v-latLow)/Math.max(.001,latHigh-latLow)*(B-T);
    const latencyLine=latencies.length>1?`<path d="${smoothPath(latencies.map((v,i)=>[px(i),py(v)]))}" fill="none" stroke="#168fe1" stroke-width="2.8" stroke-linecap="round"/>`:'';
    $('anomaly-chart').innerHTML=`<line x1="${L}" y1="${B}" x2="${R}" y2="${B}" stroke="#dfe7f9"/><line x1="${L}" y1="${ty}" x2="${R}" y2="${ty}" stroke="#ed637c" stroke-width="1.5" stroke-dasharray="5 5"/><text x="${L}" y="${Math.max(12,ty-5)}" fill="#cc536a" font-size="9">threshold ${fmt(threshold,2)}</text><text x="2" y="${B}" fill="#7387b1" font-size="9">0</text><text x="2" y="${T+3}" fill="#7387b1" font-size="9">1.0</text><text x="${R}" y="${T+3}" text-anchor="end" fill="#168fe1" font-size="9">p95 ${fmt(minLat,0)}–${fmt(maxLat,0)} ms · right scale</text>${values.length>1?`<path d="${smoothPath(values.map((v,i)=>[px(i),B-v*(B-T)]))}" fill="none" stroke="#0eaf9e" stroke-width="3.5" stroke-linecap="round"/>`:''}${latencyLine}${values.length?`<circle cx="${values.length>1?R:L}" cy="${B-current*(B-T)}" r="5" fill="${current>=threshold?'#ec6378':'#0eaf9e'}" stroke="#fff" stroke-width="2"/><text x="${R}" y="126" text-anchor="end" fill="#6378a6" font-size="9">${values.length} actual cycles · score ${fmt(current,3)}</text>`:''}`;
  }
  function renderCausalSvg(c,m){
    const positions={client:[48,110],cdn_edge:[145,110],api_gateway:[246,110],worker_backend:[350,110],postgresql_db:[447,58],redis_cache:[447,163]};
    const path=new Set(c.causal_path||[]),root=c.rca?.root_cause_tier;
    const edges=(m.topology_edges||[]).filter(([a,b])=>positions[a]&&positions[b]);
    const lines=edges.map(([a,b])=>{const [x1,y1]=positions[a],[x2,y2]=positions[b];return `<line x1="${x1+25}" y1="${y1}" x2="${x2-28}" y2="${y2}" stroke="${path.has(a)&&path.has(b)?'#ec9b19':'#8ba3d8'}" stroke-width="2.5" marker-end="url(#causal-arrow)"/>`}).join('');
    const nodes=Object.entries(positions).filter(([name])=>(m.topology_nodes||[]).includes(name)).map(([name,[x,y]])=>`<g><rect x="${x-29}" y="${y-22}" width="58" height="44" rx="13" fill="${name===root?'#fff0d8':path.has(name)?'#e5faf1':'#edf3ff'}" stroke="${name===root?'#ed9c20':path.has(name)?'#10ad80':'#b9c8ed'}" stroke-width="2"/><text x="${x}" y="${y+3}" text-anchor="middle" fill="#1d3977" font-size="16">${({client:'♟',cdn_edge:'◈',api_gateway:'⇄',worker_backend:'⚙',postgresql_db:'▤',redis_cache:'▣'})[name]}</text><text x="${x}" y="${y+37}" text-anchor="middle" fill="${name===root?'#ba740e':'#6076a4'}" font-size="9" font-weight="800">${esc(name.replaceAll('_',' '))}</text></g>`).join('');
    $('causal-svg').innerHTML=`<defs><marker id="causal-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#8ba3d8"/></marker></defs>${lines}${nodes}`;
  }
  function renderPolicySvg(c,m){
    const layers=m.m5_layers||[],policy=c.action_recommendation||{};
    if(!layers.length){$('policy-svg').innerHTML='';return}
    const xs=[34,113,192,271,350,430],ys=[34,54,74,94,114],dots=[];
    for(let col=0;col<layers.length;col++){
      for(let row=0;row<ys.length;row++)dots.push(`<circle cx="${xs[col]}" cy="${ys[row]}" r="${col===layers.length-1?5:4}" fill="${col===layers.length-1?'#e556aa':col===0?'#168fe1':'#8155e0'}" stroke="#fff" stroke-width="1.5"/>`);
    }
    const links=[];for(let col=0;col<layers.length-1;col++)for(let row=0;row<ys.length;row++)for(const next of [row,Math.min(ys.length-1,row+1)])links.push(`<line x1="${xs[col]+5}" y1="${ys[row]}" x2="${xs[col+1]-5}" y2="${ys[next]}" stroke="#a7b7e5" stroke-width="1" opacity=".55"/>`);
    $('policy-svg').innerHTML=links.join('')+dots.join('')+layers.map((n,i)=>`<text x="${xs[i]}" y="151" text-anchor="middle" fill="#5f70a7" font-size="10" font-weight="800">${esc(n)}</text>`).join('')+`<text x="250" y="175" text-anchor="middle" fill="#654bb9" font-size="12" font-weight="800">${esc((policy.selected_action||'Awaiting action').replaceAll('_',' '))} · ${fmt(Number(policy.confidence||0)*100)}%</text>`;
  }
  function renderTrend(id, rows, lines, unit='', independent=false){
    const svg=$(id),L=48,R=454,T=22,B=113;
    if(!rows.length){svg.innerHTML='<text x="250" y="75" text-anchor="middle" fill="#7184ad" font-size="13">Waiting for actual control cycles…</text>';return}
    const all=lines.flatMap(line=>rows.map(row=>Number(line.value(row))).filter(Number.isFinite));
    let low=Math.min(...all),high=Math.max(...all);
    const pad=Math.max(unit==='%'?2:unit==='score'?.025:2,(high-low)*.18);
    low=Math.max(0,low-pad);high=high+pad;if(high<=low)high=low+1;
    const x=i=>L+i/Math.max(1,rows.length-1)*(R-L),y=v=>B-(Number(v)-low)/(high-low)*(B-T);
    const grid=[0,.5,1].map(q=>`<line x1="${L}" y1="${B-q*(B-T)}" x2="${R}" y2="${B-q*(B-T)}" stroke="#e2eafa" stroke-dasharray="4 5"/>${independent?'':`<text x="3" y="${B-q*(B-T)+4}" fill="#7085ad" font-size="10">${fmt(low+(high-low)*q,unit==='score'?2:unit==='%'?0:1)}${unit==='%'?'%':''}</text>`}`).join('');
    const traces=lines.map((line,lineIndex)=>{
      const values=rows.map(row=>Number(line.value(row))||0);
      const min=Math.min(...values),max=Math.max(...values),range=max-min;
      const linePad=Math.max(line.unit==='ms'?8:line.unit==='%'?1.5:0.5,range*.16);
      const lineLow=Math.max(0,min-linePad),lineHigh=max+linePad;
      const lineY=v=>independent?B-(Number(v)-lineLow)/Math.max(.001,lineHigh-lineLow)*(B-T):y(v);
      const pts=rows.map((row,i)=>[x(i),lineY(values[i])]);
      const dots=rows.map((row,i)=>`<circle cx="${x(i)}" cy="${lineY(values[i])}" r="${i===rows.length-1?4:2.3}" fill="${line.color}" stroke="#fff" stroke-width="1"><title>${esc(row.cycle_id||'Cycle')} · ${esc(line.name)} ${fmt(values[i],1)}${esc(line.unit||unit)}${line.detail?' · '+esc(line.detail(row)):''}</title></circle>`).join('');
      const rangeLabel=independent?`<text x="${lineIndex===0?L:R}" y="${12+lineIndex*11}" text-anchor="${lineIndex===0?'start':'end'}" fill="${line.color}" font-size="9" font-weight="800">${esc(line.name)} ${fmt(min,1)}–${fmt(max,1)} ${esc(line.unit||unit)}</text>`:'';
      return `<path d="${smoothPath(pts)}" fill="none" stroke="${line.color}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>${dots}${rangeLabel}`;
    }).join('');
    svg.innerHTML=grid+traces+`<text x="${L}" y="142" fill="#7085ad" font-size="10">${rows.length} real cycles</text><text x="${R}" y="142" text-anchor="end" fill="#7085ad" font-size="10">${independent?'each line has its own scale':'latest · auto scale'}</text>`;
  }
  function renderModelTrends(){
    const rows=state.cycles.slice(-36);
    renderTrend('forecast-trend',rows,[{name:'M1 observed',color:'#139fdf',unit:'req/s',value:c=>c.input_telemetry?.requests_per_sec??0},{name:'M2 +5m',color:'#8053e4',unit:'req/s',value:c=>c.forecast?.['5m_forecast']?.requests_per_sec??0}],'req/s',true);
    renderTrend('rca-trend',rows,[{name:'M4 confidence',color:'#ed9b20',unit:'%',value:c=>Number(c.rca?.confidence??0)*100,detail:c=>c.rca?.rca_class||'—'},{name:'Measured DB pool',color:'#168fe1',unit:'%',value:c=>Number(c.pre_metrics?.db_connections??0)}],'%',true);
    renderTrend('policy-trend',rows,[{name:'M5 confidence',color:'#e451ad',unit:'%',value:c=>Number(c.action_recommendation?.confidence??0)*100,detail:c=>c.action_recommendation?.selected_action||'—'},{name:'M1 p95 latency',color:'#168fe1',unit:'ms',value:c=>Number(c.pre_metrics?.p95_ms??0)}],'%',true);
  }
  function actionMechanism(c){
    const action=c.recommended_action||'NO_OP',before=c.pre_metrics||{},after=c.post_metrics||{};
    const names={SCALE_OUT_WORKERS:'Adds portal workers to spread incoming requests',SCALE_IN_WORKERS:'Reduces workers after demand falls',ENABLE_WAITING_ROOM:'Meters new admissions so the portal can serve its queue',DIVERT_READS_TO_REPLICA:'Routes read traffic to a replica to ease the primary database',INCREASE_DB_POOL:'Raises the database connection pool limit',ACTIVATE_RATE_LIMIT:'Caps incoming requests to protect the portal',ENGAGE_CIRCUIT_BREAKER:'Stops calls to a failing downstream service',DRAIN_REQUEST_QUEUE:'Drains queued work',PURGE_REDIS_CACHE:'Clears cached entries',RESTART_DEGRADED_PODS:'Restarts unhealthy portal workers'};
    const detail=Number.isFinite(Number(before.service_instances))&&Number.isFinite(Number(after.service_instances))&&before.service_instances!==after.service_instances?` · workers ${before.service_instances} → ${after.service_instances}`:'';
    return (names[action]||action.replaceAll('_',' ').toLowerCase())+detail;
  }
  function renderActionImpact(s){
    const rows=state.cycles.slice(-90),latest=rows.at(-1),applied=[...rows].reverse().find(c=>c.actuation?.status==='SUCCESS')||state.pinnedMitigation,blocked=[...rows].reverse().find(c=>c.safety_decision==='REJECTED');
    const lastVerified=state.pinnedVerified||[...rows].reverse().find(c=>c.verification_status==='RECOVERY_VERIFIED'&&c.actuation?.status==='SUCCESS');
    $('impact-verified').innerHTML=lastVerified?`<span class="verified-mark">✓ VERIFIED RECOVERY · ${esc(new Date(lastVerified.timestamp).toLocaleTimeString())}</span><b>${esc((lastVerified.recommended_action||'').replaceAll('_',' '))}</b><span>Measured p95 ${fmt(lastVerified.pre_metrics?.p95_ms,0)} → ${fmt(lastVerified.post_metrics?.p95_ms,0)} ms · DB ${fmt(lastVerified.pre_metrics?.db_connections,0)} → ${fmt(lastVerified.post_metrics?.db_connections,0)}%</span><small>Verified in cycle ${esc(lastVerified.cycle_id?.split('_')[1]||'—')}; later decisions are listed below.</small>`:'<span class="verified-pending">No M7 recovery has been verified in the visible history yet.</span>';
    const focus=applied||blocked||latest||{},hasAction=focus.actuation?.status==='SUCCESS',verified=focus.verification_status==='RECOVERY_VERIFIED',fresh=s.traffic||{};
    const failed=hasAction&&focus.verification_status==='RECOVERY_FAILED';
    const status=hasAction?(verified?'RECOVERY VERIFIED':failed?'M7 RAN · RECOVERY FAILED':'ACTION APPLIED · NOT VERIFIED'):blocked?'SAFETY HOLD':'MONITORING';
    $('impact-status').textContent=status;
    $('impact-status').className='impact-status '+(verified?'verified':failed?'failed':hasAction?'unverified':blocked?'blocked':'');
    const m5=focus.action_recommendation||{},action=(focus.recommended_action||'NO_OP').replaceAll('_',' '),clock=focus.timestamp?new Date(focus.timestamp).toLocaleTimeString():'—';
    const steps=[[fresh.is_running?'01 · CROWD NOW':'01 · LAST TRAFFIC SAMPLE',`${Number(fresh.current_vus||0).toLocaleString()} virtual users`,`${fmt(fresh.real_requests_per_sec)} ${fresh.is_running?'measured':'last measured'} req/s · ${esc(fresh.phase||'—').replaceAll('_',' ')}`],['02 · MODEL · '+clock,`${esc(action)}`,`${fmt(Number(m5.confidence||0)*100)}% model confidence · ${esc(focus.rca?.rca_class||'no fault classified')}`],['03 · SAFETY + M7',hasAction?'Action applied':focus.safety_decision==='REJECTED'?'Blocked by guardrail':'No action applied',hasAction?actionMechanism(focus):esc(focus.safety_validation?.rejection_reasons?.[0]||focus.safety_decision||'Waiting for a decision')],['04 · VERIFY',verified?'Post-action check passed':hasAction?'Recovery not verified': 'Watching telemetry',hasAction?`${esc(focus.verification_status||'PENDING').replaceAll('_',' ')} · ${clock}`:'Next 3-second cycle checks portal health']];
    $('impact-flow').innerHTML=steps.map(([label,value,detail],i)=>`<div class="impact-step ${i===2&&hasAction?'applied':''} ${i===3&&verified?'verified':''}"><small>${label}</small><strong>${value}</strong><span>${detail}</span></div>`).join('<span class="impact-arrow" aria-hidden="true">→</span>');
    const before=focus.pre_metrics||{},after=focus.post_metrics||{};
    const focusIndex=rows.findIndex(c=>c.cycle_id===focus.cycle_id);
    const metric=(label,key,unit)=>`<div><span>${label}</span><b>${before[key]===undefined?'—':fmt(before[key],key==='queue_length'?0:1)}${unit} <i>→</i> ${after[key]===undefined?'Pending':fmt(after[key],key==='queue_length'?0:1)+unit}</b></div>`;
    $('impact-measurement').innerHTML=hasAction?`<small>ACTUAL M1 SAMPLE · CYCLE ${esc(focus.cycle_id?.split('_')[1]||'—')}</small><h4>${verified?'Portal recovery measured':failed?'M7 ran; recovery failed verification':'Action applied; outcome unverified'}</h4><p>${esc(actionMechanism(focus))}</p>${metric('p95 latency','p95_ms',' ms')}${metric('DB pool','db_connections','%')}${metric('Queue depth','queue_length','')}${metric('Throughput','rps',' req/s')}<footer>Applied ${esc(focus.actuation?.timestamp?new Date(focus.actuation.timestamp).toLocaleTimeString():clock)} · ${verified?'verified in this control cycle':'verification '+esc(focus.verification_status||'pending')} · ${focusIndex>=0?Math.max(0,rows.length-1-focusIndex):'90+'} later cycles observed</footer>`:`<small>MEASURED OUTCOME</small><h4>${blocked?'The guardrail held this cycle':'No M7 action yet'}</h4><p>${blocked?esc(focus.safety_validation?.rejection_reasons?.[0]||'Safety rejected the recommendation.'): 'Run the scenario or inject DB pressure to see an applied action and its measured before/after values.'}</p>`;
    if(latest?.pre_metrics){const later=hasAction&&latest.cycle_id!==focus.cycle_id;const improved=later&&Number(latest.pre_metrics.p95_ms)<Number(before.p95_ms)&&Number(latest.pre_metrics.db_connections)<Number(before.db_connections);$('impact-measurement').insertAdjacentHTML('beforeend',`<div class="impact-current"><span>LATEST M1 · ${esc(new Date(latest.timestamp).toLocaleTimeString())}</span><b>${fmt(latest.pre_metrics.p95_ms,0)} ms p95 · ${fmt(latest.pre_metrics.db_connections,0)}% DB</b>${improved&&!verified?'<em>Later readings eased; M7 recovery for this action was not verified.</em>':''}</div>`)}
    renderImpactChart(rows,focus);
    const events=[];
    const candidates=[...rows,...[state.pinnedMitigation,state.pinnedVerified].filter(c=>c&&!rows.some(row=>row.cycle_id===c.cycle_id))].sort((a,b)=>Date.parse(b.timestamp)-Date.parse(a.timestamp));
    for(const c of candidates){
      if(c.actuation?.status!=='SUCCESS'&&c.safety_decision!=='REJECTED')continue;
      const previous=events.at(-1);
      if(previous&&c.actuation?.status!=='SUCCESS'&&previous.actuation?.status!=='SUCCESS'&&previous.recommended_action===c.recommended_action&&previous.safety_decision===c.safety_decision)continue;
      events.push(c);
      if(events.length===(lastVerified?5:6))break;
    }
    if(lastVerified&&!events.some(c=>c.cycle_id===lastVerified.cycle_id))events.push(lastVerified);
    events.sort((a,b)=>Date.parse(b.timestamp)-Date.parse(a.timestamp));
    $('impact-table-body').innerHTML=events.length?events.map(c=>`<tr><td><b>${esc(c.cycle_id?.split('_')[1]||'—')}</b><small>${esc(new Date(c.timestamp).toLocaleTimeString())}</small></td><td>${esc((c.recommended_action||'NO_OP').replaceAll('_',' '))}<small>${fmt(Number(c.action_recommendation?.confidence||0)*100)}% confidence</small></td><td>${esc(c.safety_decision||'—')}<small>${c.actuation?.status==='SUCCESS'?'M7 applied':esc(c.actuation_status==='SKIPPED'?'held by safety':c.actuation_status||'not applied')}</small></td><td class="${c.verification_status==='RECOVERY_VERIFIED'?'good':c.verification_status==='RECOVERY_FAILED'?'bad':''}">${esc((c.verification_status||'—').replaceAll('_',' '))}<small>${c.post_metrics?`${fmt(c.pre_metrics?.p95_ms,0)} → ${fmt(c.post_metrics?.p95_ms,0)} ms p95`:'No post-action sample'}</small></td></tr>`).join(''):'<tr><td colspan="4">No action or safety block in this run yet. The model is observing live traffic.</td></tr>';
  }
  function renderImpactChart(rows,focus){
    const svg=$('impact-chart'),caption=$('impact-chart-caption');
    if(!rows.length){svg.innerHTML='<text x="400" y="120" text-anchor="middle" fill="#7385ae" font-size="16">Waiting for measured cycles…</text>';caption.innerHTML='<span>Actual cycle history appears here</span>';return}
    const L=48,R=750,T=28,B=206,n=rows.length,lat=rows.map(c=>Number(c.pre_metrics?.p95_ms??0)),db=rows.map(c=>Number(c.pre_metrics?.db_connections??0));
    const lm=Math.max(100,...lat)*1.12,dm=Math.max(100,...db)*1.05,x=i=>L+i/Math.max(1,n-1)*(R-L),yl=v=>B-v/lm*(B-T),yd=v=>B-v/dm*(B-T);
    const grid=[0,.5,1].map(q=>`<line x1="${L}" y1="${B-q*(B-T)}" x2="${R}" y2="${B-q*(B-T)}" stroke="#e4ebf9" stroke-dasharray="5 5"/><text x="2" y="${B-q*(B-T)+4}" fill="#6980a9" font-size="11">${fmt(lm*q,0)} ms</text><text x="757" y="${B-q*(B-T)+4}" fill="#b27b27" font-size="11">${fmt(dm*q,0)}%</text>`).join('');
    const marks=rows.map((c,i)=>{if(c.actuation?.status!=='SUCCESS')return '';const color=c.verification_status==='RECOVERY_VERIFIED'?'#14aa7a':'#eda026';const after=Number(c.post_metrics?.p95_ms);return `<line x1="${x(i)}" y1="${T}" x2="${x(i)}" y2="${B}" stroke="${color}" stroke-width="2" stroke-dasharray="5 5"/><circle cx="${x(i)}" cy="${yl(lat[i])}" r="6" fill="${color}" stroke="#fff" stroke-width="2"><title>${esc(c.recommended_action)} applied · ${esc(c.verification_status)}</title></circle>${Number.isFinite(after)?`<line x1="${x(i)}" y1="${yl(lat[i])}" x2="${x(i)}" y2="${yl(after)}" stroke="${color}" stroke-width="3"/><rect x="${x(i)-4}" y="${yl(after)-4}" width="8" height="8" fill="${color}"><title>Measured post-action p95 ${fmt(after,1)} ms</title></rect>`:''}`}).join('');
    svg.innerHTML=grid+`<path d="${smoothPath(db.map((v,i)=>[x(i),yd(v)]))}" fill="none" stroke="#efa22e" stroke-width="3.5"/><path d="${smoothPath(lat.map((v,i)=>[x(i),yl(v)]))}" fill="none" stroke="#238eed" stroke-width="3.5"/>${rows.map((c,i)=>`<circle cx="${x(i)}" cy="${yl(lat[i])}" r="2.8" fill="#238eed"><title>${esc(c.cycle_id)} · p95 ${fmt(lat[i])} ms · DB ${fmt(db[i])}%</title></circle>`).join('')}${marks}`;
    caption.innerHTML=`<span>${rows.length} real cycles</span><span>${focus.actuation?.status==='SUCCESS'?'Vertical line = M7 action · square = measured after':'Waiting for M7 action'}</span><span>Latest</span>`;
  }
  function renderModels(s){
    const c=s.latest||{},f=c.forecast||{},a=c.anomaly||{},r=c.rca||{},policy=c.action_recommendation||{},m=s.models||{};
    const previous=state.cycles.at(-2);
    const signed=(value,digits=1)=>`${value>=0?'+':''}${fmt(value,digits)}`;
    const modelState=c.cycle_id?(s.traffic.is_running?'LIVE':'LAST CYCLE'):'READY';
    $('m2-loaded').textContent=m.m2_loaded?`${modelState} · ${!c.cycle_id?'AWAITING DATA':previous?signed(Number(f['5m_forecast']?.requests_per_sec||0)-Number(previous.forecast?.['5m_forecast']?.requests_per_sec||0))+' req/s':'FORECASTING'}`:'UNAVAILABLE';
    $('m3-loaded').textContent=m.m3_loaded?`${modelState} · ${!c.cycle_id?'AWAITING DATA':previous?signed(Number(a.anomaly_score||0)-Number(previous.anomaly?.anomaly_score||0),3)+' score':'SCORING'}`:'UNAVAILABLE';
    $('m4-loaded').textContent=m.m4_loaded?`${modelState} · ${c.cycle_id?esc(r.rca_class||'—'):'AWAITING DATA'}`:'UNAVAILABLE';
    $('m5-loaded').textContent=m.m5_loaded?`${modelState} · ${c.cycle_id?fmt(Number(policy.confidence||0)*100)+'%':'AWAITING DATA'}`:'UNAVAILABLE';
    const horizons=['5m','10m','15m'];$('forecast').innerHTML=kv('M1 observed RPS',fmt(c.input_telemetry?.requests_per_sec))+horizons.map(h=>kv(`+${h} forecast`,fmt(f[`${h}_forecast`]?.requests_per_sec)+' req/s')).join('')+kv('Safe capacity',fmt(f.safe_capacity)+' req/s')+kv('Risk',f.risk_level);
    renderForecastSvg(c);
    $('anomaly').innerHTML=kv('Score',fmt(a.anomaly_score,3))+kv('Threshold',fmt(m.m3_threshold,3))+kv('Classification',c.cycle_id?(a.is_anomaly?'ANOMALY':'NOMINAL'):'AWAITING CYCLE')+kv('Severity',a.severity)+kv('Main contributor',a.contributing_features?.[0]?.metric||'—');
    renderAnomalySvg(m.m3_threshold);
    $('rca').innerHTML=kv('Predicted cause',r.rca_class)+kv('Confidence',fmt(Number(r.confidence||0)*100)+'%')+bars(r.probabilities||{});
    $('causal-graph').innerHTML=`<div class="path"><b>Current causal path</b>${(c.causal_path||[]).map(x=>`<span>${esc(x.replaceAll('_',' '))}</span>`).join('<span>→</span>')||'<span>Awaiting path</span>'}</div>`;
    renderCausalSvg(c,m);
    const vector=(m.m5_features||[]).map((name,i)=>`${name}: ${fmt(policy.input_feature_vector?.[i],2)}`).join(' · ');
    $('neural').innerHTML=`${kv('Selected model action',policy.selected_action)}${kv('Model confidence',fmt(Number(policy.confidence||0)*100)+'%')}${kv('Capability-safe action',c.safety_validation?.capability_mask?.effective_action||c.recommended_action)}${kv('M6 safety decision',c.safety_decision)}<details class="model-inputs"><summary>View 13 measured input features</summary><div class="input-vector">${esc(vector)}</div></details><div class="bars">${bars(policy.all_action_probabilities||{})}</div>`;
    renderPolicySvg(c,m);
    renderModelTrends();
    renderActionImpact(s);
    renderDecision(s);
  }
  function bars(values){return Object.entries(values).sort((x,y)=>Number(y[1])-Number(x[1])).map(([name,value])=>`<div class="bar"><label><span>${esc(name.replaceAll('_',' '))}</span><b>${fmt(Number(value)*100)}%</b></label><div class="bar-track"><i style="width:${Math.min(100,Math.max(0,Number(value)*100))}%"></i></div></div>`).join('')}
  function renderDecision(s){const c=s.latest||{},m=s.models||{},p=c.action_recommendation||{},mask=c.safety_validation?.capability_mask||{},m7Display=c.actuation_status==='SKIPPED'?(c.safety_decision==='REJECTED'?'HELD BY M6':'NO PORTAL CHANGE'):c.actuation_status||'—';$('policy-cycle').textContent=c.cycle_id||'—';$('safety-badge').textContent=c.safety_decision||'—';$('policy-network').innerHTML=(m.m5_layers||[]).map((n,i)=>`<div class="network-layer">${Array.from({length:Math.min(7,Math.max(3,Math.round(Math.log2(n||1))))},()=>'<i class="node"></i>').join('')}<b>${esc(n)}</b><small>${i===0?'input':i===(m.m5_layers||[]).length-1?'actions':'hidden'}</small></div>${i===(m.m5_layers||[]).length-1?'':'<span class="network-link">→</span>'}`).join('');$('policy-inputs').innerHTML=(m.m5_features||[]).map((name,i)=>`<span>${esc(name.replaceAll('_',' '))} <b>${fmt(p.input_feature_vector?.[i],1)}</b></span>`).join('');$('decision-summary').innerHTML=`<div class="decision-hero"><small>Latest model recommendation</small><strong>${esc(p.selected_action||'Awaiting cycle')}</strong></div>${kv('Raw model confidence',fmt(Number(p.confidence||0)*100)+'%')}${kv('Capability-safe action',mask.effective_action||'—')}${kv('Mask applied',mask.was_masked?'YES':'NO')}${kv('M6 decision',c.safety_decision||'—')}${kv('M7 status',m7Display)}`;$('policy-probabilities').innerHTML=bars(p.all_action_probabilities||{});$('action-steps').innerHTML=[['M5 proposes',p.selected_action,fmt(Number(p.confidence||0)*100)+'% model confidence'],['Capability mask',mask.effective_action,mask.masking_rationale],['M6 guardrail',c.safety_decision,(c.safety_validation?.rejection_reasons||[]).join(' · ')||'Safety decision recorded'],['M7 & verify',m7Display,c.verification_status==='NO_ACTION'?'No post-action check':c.verification_status||'Awaiting outcome']].map(([a,b,d])=>`<div class="action-step"><small>${esc(a)}</small><b>${esc(b)}</b><span>${esc(d)}</span></div>`).join('')}
  async function loadRecoveryHistory(){try{const history=await api('/api/v1/control-loop/history?limit=100');const matching=history.filter(x=>x.portal_id==='college_portal'&&Date.parse(x.timestamp||0)>=state.runStartedAt&&x.verification_status==='RECOVERY_VERIFIED');if(matching.length){state.lastVerified=matching.at(-1);if(state.snapshot)renderRecovery(state.snapshot)}}catch(e){console.warn('Recovery history unavailable',e)}}
  function renderRecovery(s){const acted=(s.history||[]).filter(x=>Date.parse(x.timestamp||0)>=state.runStartedAt&&(x.actuation_status==='EXECUTED'||x.verification_status==='RECOVERY_FAILED')).at(-1);if(acted&&acted.cycle_id!==state.lastActuation?.cycle_id)state.lastActuation=acted;const verified=(s.history||[]).filter(x=>Date.parse(x.timestamp||0)>=state.runStartedAt&&x.verification_status==='RECOVERY_VERIFIED').at(-1);if(verified)state.lastVerified=verified;const proof=state.lastVerified;const proofBefore=proof?.pre_metrics||{},proofAfter=proof?.post_metrics||{};$('verified-proof').innerHTML=proof?`<div class="verified-proof"><span>✓ LATEST VERIFIED CYCLE · ${esc(proof.cycle_id)} · ${esc(new Date(proof.timestamp).toLocaleTimeString())}</span><b>${esc(proof.recommended_action)} executed</b><small>Measured p95 ${fmt(proofBefore.p95_ms)} → ${fmt(proofAfter.p95_ms)} ms · DB pool ${fmt(proofBefore.db_connections)} → ${fmt(proofAfter.db_connections)}%</small></div>`:'<div class="verified-proof pending">Awaiting a verified action in this run.</div>';const c=state.lastVerified||state.lastActuation||s.latest||{},before=c.pre_metrics||{},after=c.post_metrics||{},metrics=[['p95 latency','p95_ms',' ms'],['Error rate','errors','%'],['Queue depth','queue_length',''],['DB pool utilization','db_connections','%'],['Portal throughput','rps',' req/s']];$('recovery-state').textContent=`SHOWN ${c.verification_status||'—'} · LATEST ATTEMPT ${state.lastActuation?.verification_status||'—'}`;$('comparison').innerHTML=`<div class="compare"><div><strong>BEFORE</strong>${metrics.map(([name,key,unit])=>kv(name,before[key]===undefined?'—':fmt(key==='errors'?before[key]*100:before[key])+unit)).join('')}</div><div><strong>ACTION</strong>${kv('M5 recommendation',c.recommended_action)}${kv('M6 safety',c.safety_decision)}${kv('M7 status',c.actuation_status==='SKIPPED'?'NO PORTAL CHANGE':c.actuation_status)}${kv('Verification',c.verification_status)}</div><div><strong>AFTER</strong>${metrics.map(([name,key,unit])=>kv(name,after[key]===undefined?'Not recorded':fmt(key==='errors'?after[key]*100:after[key])+unit)).join('')}</div></div>`}
  function renderWarning(w){
    const node=document.createElement('div'),cleared=w.severity==='RECOVERY';
    node.className='incident '+(cleared?'condition-clear':'warning-red');
    const status=cleared?(w.verification_status==='RECOVERY_VERIFIED'?'M7 POST-ACTION CHECK PASSED':'CONDITION CLEARED'):w.severity==='CRITICAL'?'CRITICAL WARNING':'WARNING';
    const did=w.what_portalpulse_did||`${w.recommended_action||'NO_OP'} · ${w.remediation_state||'MONITORING'}`;
    node.innerHTML=`<button aria-label="Dismiss notification">×</button><span class="incident-kind">${cleared?'✦':'⚠'} ${status} · ${esc(w.timestamp?new Date(w.timestamp).toLocaleTimeString():'—')}</span><b>${esc(w.title||w.id)}</b><small>${esc(w.current_metric||'—')} · threshold ${esc(w.threshold||'—')}</small><p>${esc(w.why_it_happened||w.trigger_condition||'Observed portal condition.')}</p><span class="incident-did">${esc(did)}</span>`;
    node.querySelector('button').onclick=()=>node.remove();return node;
  }
  function notify(w){if(state.warnings.some(x=>x.id===w.id&&x.timestamp===w.timestamp))return;state.warnings.unshift(w);$('incidents').prepend(renderWarning(w));$('response-incidents').prepend(renderWarning(w));const toast=renderWarning(w);$('toasts').prepend(toast);while($('toasts').children.length>1)$('toasts').lastElementChild.remove();setTimeout(()=>toast.remove(),5000);$('incident-count').textContent=state.warnings.length}
  const nirantarExamples=[
    {kind:'TATKAL DEMAND',title:'Tatkal bookings are moving into a short queue',detail:'New booking requests are metered so active checkouts can finish. Your place stays visible while capacity frees up.',meta:'Example notice · queue admission'},
    {kind:'BOOKING CONFIRMATION',title:'Confirmation may take a little longer',detail:'The booking service is checking transactions before showing a final status. Avoid submitting the same payment twice.',meta:'Example notice · transaction protection'},
    {kind:'SERVICE RECOVERY',title:'Booking flow is returning to normal',detail:'Queue pressure has eased. New sessions are being admitted gradually while response times are checked.',meta:'Example notice · staged recovery'}
  ];
  let nirantarExampleIndex=0;
  function showNirantarNotice(notice,live=false){$('nirantar-preview').hidden=false;$('nirantar-warning').innerHTML=`<div class="nirantar-notice"><button type="button" class="nirantar-dismiss" aria-label="Dismiss Nirantar notice">×</button><small>${esc(notice.kind||'NIRANTAR NOTICE')}</small><strong>${esc(notice.title||'Portal update')}</strong><p>${esc(notice.detail||'Please check the portal for the latest status.')}</p><span>${esc(live?'Nirantar event · '+new Date().toLocaleTimeString():notice.meta||'Example notice')}</span></div>`}
  const tourSteps=[
    {view:'command',title:'The live command center',description:'This is the story of one local portal under changing demand. The numbers at the top come from the latest snapshot; the control chart updates as the backend completes cycles.',read:'Blue is measured p95 latency. Orange is DB pool use. Vertical event markers mean M6 blocked or M7 applied an action. A green marker requires a verified recovery.',action:'Press Run full scenario to watch demand ramp, then inspect the changing blue and orange lines.',visual:'command'},
    {view:'traffic',title:'Create and control traffic',description:'Start runs the entire result-day sequence. Pause and Resume control the traffic generator; Reset clears local faults and starts from baseline. Replay result-day rush jumps the generator to the high-demand phase.',read:'Virtual users are a scenario target. Requests per second, in-flight work, response times, failures, and DB use are measurements from actual local HTTP requests.',action:'Start the complete demo, then use Pause to see values settle. Inject DB pressure later in AI Models to test a fault.',visual:'traffic'},
    {view:'traffic',title:'Read the four real-time graphs',description:'Each point is a collected sample. Curves connect those samples smoothly so the direction is easier to follow; they do not invent extra measurements.',read:'Request rate shows served traffic; p95 is the time within which 95% of requests finished; DB pool shows occupied connections; failure rate counts unsuccessful responses. Hover points to inspect the sample.',action:'Watch all four together: a rising DB pool with rising p95 and failures means the portal is under pressure.',visual:'graphs'},
    {view:'traffic',title:'See what recovery proved',description:'The Recovery section lives below Traffic. It compares M1 measurements before and after an M7 attempt and lists the incident timeline.',read:'An applied action is not automatically a recovered portal. “Verified” means the backend’s post-action rule passed on actual local telemetry; otherwise the action remains unverified or failed.',action:'Scroll to Traffic → Recovery and compare p95, errors, queue, DB pool, and throughput.',visual:'recovery'},
    {view:'intelligence',title:'Follow the architecture',description:'The embedded interactive diagram is generated with Archify from the actual PortalPulse control flow. Its arrows show ownership and feedback, while the live strip beneath it shows this cycle’s output and timing.',read:'M1 observes → M2 forecasts → M3 detects → M4 diagnoses → M5 recommends → M6 gates → M7 acts → verification feeds the next cycle.',action:'Use the diagram’s zoom controls, then select Trace latest cycle to follow live stages below it.',visual:'architecture'},
    {view:'intelligence',title:'Check that models ran',description:'Each model card shows the current output and a trend across actual cycles. Model Runtime displays the loaded checkpoint flag, model version, inference status, and timing.',read:'A loaded model plus “inference complete” is evidence of a real local model call. “Fallback” or “not loaded” is shown when that is the actual state. Forecast points are predictions; the historical trend is observed cycles.',action:'Compare M2 predicted demand with M1 observed requests, then inspect M3 score, M4 cause, and M5 action probabilities.',visual:'models'},
    {view:'intelligence',title:'Watch pressure meet control',description:'M5 proposes a portal action, M6 checks it against safety rules, and M7 applies approved changes to the local simulator. The response cards show pressure, the last actual intervention, and measured outcome.',read:'A red pressure card means the portal is stressed. A blue card means M7 actually intervened. Green means measured recovery passed; red means the outcome failed verification. A safety hold is never shown as an applied change.',action:'Inject DB pressure, then watch the red pressure card and blue intervention card update from actual cycles.',visual:'decision'},
    {view:'guide',title:'Keep the two portal stories separate',description:'The Why it matters page contains the Nirantar example and its own Tatkal-style notice preview. IEMCRP control data and incidents remain in Traffic and AI Models.',read:'Open Nirantar with overlay keeps the real external site interactive and places clearly labeled local example cards above it. Open Nirantar directly has only its native notifications.',action:'Open Nirantar with overlay to see the cross-site presentation, or return to Traffic for actual IEMCRP control results.',visual:'nirantar'}
  ];
  const helpStep={command:0,controls:1,recovery:3,models:5,decision:6,impact:6,nirantar:7};
  let tourIndex=0;
  function renderTour(){
    const t=tourSteps[tourIndex],s=state.snapshot||{},c=s.latest||{};
    $('tour-counter').textContent=`STEP ${tourIndex+1} OF ${tourSteps.length}`;
    $('tour-title').textContent=t.title;$('tour-description').textContent=t.description;
    $('tour-interpretation').textContent=t.read;$('tour-action').textContent=t.action;
    $('tour-back').disabled=tourIndex===0;$('tour-next').textContent=tourIndex===tourSteps.length-1?'Finish ✓':'Next →';
    const metrics=t.visual==='decision'?[["M5",c.recommended_action||'NO_OP'],['M6',c.safety_decision||'—'],['M7',c.actuation_status==='SKIPPED'?'No portal change':c.actuation_status||'—']]:t.visual==='models'?[["M2",fmt(c.forecast?.['5m_forecast']?.requests_per_sec)+' req/s'],['M3',fmt(c.anomaly?.anomaly_score,3)],['M5',c.recommended_action||'NO_OP']]:[['Requests',fmt(s.traffic?.real_requests_per_sec)+' /s'],['p95',fmt(s.traffic?.p95)+' ms'],['DB pool',fmt(s.pool?.utilization_percent)+'%']];
    $('tour-visual-content').innerHTML=`<span>LIVE RIGHT NOW · ${esc(c.cycle_id||'WAITING FOR CYCLE')}</span>${metrics.map(([k,v])=>`<b>${esc(k)} <em>${esc(v)}</em></b>`).join('')}`;
  }
  function openTour(i=0){tourIndex=Math.max(0,Math.min(tourSteps.length-1,i));renderTour();if(!$('tour-dialog').open)$('tour-dialog').showModal()}
  $('tour-close').onclick=()=>$('tour-dialog').close();
  $('tour-back').onclick=()=>{tourIndex=Math.max(0,tourIndex-1);renderTour()};
  $('tour-next').onclick=()=>{if(tourIndex===tourSteps.length-1){$('tour-dialog').close();return}tourIndex++;renderTour()};
  $('tour-explore').onclick=()=>{const t=tourSteps[tourIndex];$('tour-dialog').close();navigate(t.view);const target=({recovery:'traffic-recovery',decision:'model-decision',architecture:'architecture-viewer',nirantar:'nirantar-view'})[t.visual];if(target)setTimeout(()=>$(target)?.scrollIntoView({behavior:'smooth',block:'start'}),350)};
  $('robot-launch').onclick=()=>openTour(0);
  $('coach-close').onclick=()=>{$('coach-popup').hidden=true};
  let coachTimer;
  function showCoach(title,message,watch,duration=14000,kind='info',eventMetrics=null){
    const s=state.snapshot||{},c=s.latest||{};
    $('coach-title').textContent=title;$('coach-message').textContent=message;$('coach-watch').textContent=watch;
    const m7=eventMetrics?'APPLIED':!s.traffic?.is_running?'IDLE':c.actuation_status==='EXECUTED'?'APPLIED':c.safety_decision==='REJECTED'?'HELD BY M6':'MONITORING';
    $('coach-metrics').innerHTML=`<span>${eventMetrics?'Post-action':'Current'} requests <b>${fmt(eventMetrics?.rps??s.traffic?.real_requests_per_sec)} /s</b></span><span>p95 <b>${fmt(eventMetrics?.p95_ms??s.traffic?.p95)} ms</b></span><span>M7 <b>${esc(m7)}</b></span>`;
    $('coach-popup').hidden=false;$('coach-popup').classList.toggle('coach-action',kind==='action');$('coach-popup').classList.toggle('coach-danger',kind==='danger');$('coach-popup').classList.remove('coach-enter');void $('coach-popup').offsetWidth;$('coach-popup').classList.add('coach-enter');
    clearTimeout(coachTimer);if(duration)coachTimer=setTimeout(()=>{$('coach-popup').hidden=true},duration);
  }
  const buttonStories={
    start:['The laptop-safe scenario has started','The generator sends real local requests with a hard cap of 6 workers and 12 requests per second. It stops automatically within 100 seconds. M2–M5 run on measured data; M6 checks M7 actions.','Watch Traffic graphs and AI Models → Automation Explainer.'],
    pause:['Traffic generation paused','New scenario traffic and model cycles are paused to reduce laptop load. Earlier readings remain visible as history.','Use Resume when ready or the red Stop load button to end the run.'],
    resume:['Traffic generation resumed','The generator is sending local requests again. New measured samples will extend the graphs.','Watch request rate, p95 latency, failures, and DB pool together.'],
    reset:['Demo reset to baseline','The local traffic generator and injected faults were reset. Model cycles idle until another run starts.','Press Start complete demo only when ready.'],
    stop:['Load stopped immediately','All generated request workers were cancelled, injected faults were cleared, and model cycles are idle. The measured history stays on the page.','You can inspect the graphs without generating more traffic.']
  };
  const triggerStories={
    database:['Local DB pressure injected','This operator test saturates the simulator’s database pool. It changes input conditions; it does not directly order M7 to act.','Watch DB pool and p95 on Traffic, then M3, M5, and the M6 reason on AI Models.'],
    'result-rush':['Result-day rush replayed','The traffic generator moved to the high-demand phase so request rate and concurrency can rise.','Watch the Traffic phase track and the measured request-rate graph.'],
    'rate-limit':['Rate-limit condition triggered','This local scenario applies a request limit so you can see throttling and HTTP 429 behavior.','Watch Traffic failures and the incident timeline.'],
    'circuit-breaker':['Circuit-breaker condition triggered','This local scenario opens the circuit to a struggling dependency. It is an operator test input, separate from an M7 recommendation.','Watch response failures and the next model cycle.'],
    recovery:['Local fault cleared','The injected test fault was cleared manually. This does not count as M7 recovery; the before and after panel shows what the portal actually measured.','Watch Traffic → Recovery for stabilized p95, errors, DB pool, and verification status.']
  };
  const viewStories={command:['Command center','One chart follows actual latency and DB pressure across control cycles; markers distinguish safety blocks, applied actions, and verified recovery.','Try Run full scenario, then follow the color-coded events.'],traffic:['Traffic & recovery','Four measured graphs show request rate, p95, DB pressure, and failures. Recovery and incidents are below the graphs on this page.','Watch how the lines change together, then compare the before and after samples.'],intelligence:['AI Models & decision','The Archify diagram shows the full path. The live strip, model cards, and automation explainer report what the current cycle actually did.','Trace the latest cycle, then compare pressure, safety decision, M7 intervention, and outcome.'],guide:['System context','This page explains the wider system and keeps the Nirantar notice preview separate from IEMCRP traffic and incidents.','Tap Preview Nirantar notices to see a Tatkal-specific example.']};
  document.addEventListener('click',e=>{
    const nav=e.target.closest('[data-view]');if(nav){const story=viewStories[nav.dataset.view];if(story)showCoach(...story,8500)}
  });
  let replayToken=0;
  $('replay-cycle').onclick=async()=>{if(!state.snapshot?.latest)return;showCoach('Tracing the latest model cycle','The highlighted live stage moves through observed traffic, model inference, safety, actuation, and verification. The Archify diagram above shows the underlying architecture.','Follow the highlighted status strip below the diagram.',10000);const token=++replayToken;const cycle=state.snapshot.latest.cycle_id;$('replay-cycle').disabled=true;$('flow-cycle').textContent=`Visual replay · ${cycle}`;for(let i=0;i<stages.length;i++){if(token!==replayToken)break;state.replayIndex=i;renderPipeline(state.snapshot);await new Promise(resolve=>setTimeout(resolve,600))}if(token===replayToken){$('replay-cycle').disabled=false;state.replayIndex=-1;renderPipeline(state.snapshot)}};
  async function refresh(){try{const s=await api('/api/v1/live-demo/snapshot');state.snapshot=s;if(!requestedNirantar&&s.nirantar_url&&currentNirantarURL!==s.nirantar_url)setNirantar(s.nirantar_url);$('connection').textContent='BACKEND CONNECTED';$('connection').style.color='#84f5d4';$('phase').textContent=s.traffic.phase.replaceAll('_',' ');const stopReason=s.traffic.stop_reason?.startsWith('THERMAL_LIMIT')?'Stopped by CPU temperature guard':s.traffic.stop_reason==='TIME_LIMIT'?'Stopped at the 100-second safety limit':'Traffic stopped';$('status').textContent=`${s.traffic.is_running?s.traffic.is_paused?'Paused':'Generating portal requests':stopReason} · ${s.loop.last_error?'Control-loop error: '+s.loop.last_error:'Control loop '+s.loop.phase}`;$('cycle-count').textContent=s.latest?.cycle_id||'Awaiting cycle';ingestCycles(s);renderMetrics(s);renderTraffic(s);renderControlStory(s);renderCommandArchitecture(s);renderPipeline(s);renderModels(s);renderRecovery(s)}catch(e){$('connection').textContent='BACKEND UNREACHABLE';$('connection').style.color='#ffb3bd';$('status').textContent=String(e)}}
  document.querySelectorAll('[data-action]').forEach(b=>b.onclick=async()=>{try{await api('/api/v1/live-demo/'+b.dataset.action,'POST');if(['start','reset'].includes(b.dataset.action)){state.lastActuation=null;state.lastVerified=null;state.pinnedMitigation=null;state.pinnedVerified=null;sessionStorage.removeItem('portalpulse_demo_evidence');state.runStartedAt=Date.now();state.series=[];state.cycles=[];state.cycleIds=[];state.scoreHistory=[]}await refresh();showCoach(...buttonStories[b.dataset.action])}catch(e){const message=String(e);$('status').textContent=message;showCoach(message.includes('CPU package')?'Laptop temperature guard held the run':'Control did not complete',message,message.includes('CPU package')?'The old graphs remain available. Let the laptop cool before starting traffic again.':'Check the backend connection and try again.',12000,'danger')}});
  document.querySelectorAll('[data-trigger]').forEach(b=>b.onclick=async()=>{try{await api('/api/v1/live-demo/trigger/'+b.dataset.trigger,'POST');await refresh();showCoach(...triggerStories[b.dataset.trigger])}catch(e){$('status').textContent=String(e);showCoach('Scenario trigger failed',String(e),'Check the backend connection and try again.')}});
  $('test-notifications').onclick=()=>{const notice=nirantarExamples[nirantarExampleIndex%nirantarExamples.length];showNirantarNotice(notice);nirantarExampleIndex++};
  $('nirantar-warning').addEventListener('click',e=>{if(e.target.closest('.nirantar-dismiss'))$('nirantar-preview').hidden=true});
  $('drawer-toggle').onclick=()=>{const open=$('drawer').classList.toggle('open');if(open)showCoach('Incident drawer opened','These are IEMCRP warning and recovery events emitted from observed conditions. They are separate from the Nirantar preview notices.','Read the metric, threshold, cause, and action status on each incident.',9000)};$('close-drawer').onclick=()=>$('drawer').classList.remove('open');$('open-drawer-inline').onclick=()=>{$('drawer').classList.add('open');showCoach('Incident timeline opened','The drawer contains measured IEMCRP events and their remediation states.','Compare an incident time with the Traffic → Recovery graph.',9000)};
  const stream=new EventSource(base+'/api/v1/stream/events');
  ['warning','recovery'].forEach(type=>stream.addEventListener(type,event=>{try{const w=JSON.parse(event.data);if(type==='recovery'&&!w.is_recovered&&w.verification_status!=='RECOVERY_VERIFIED')return;if(w.portal_id==='nirantar'){showNirantarNotice({kind:type==='recovery'?'SERVICE RECOVERY':'NIRANTAR ALERT',title:w.title||w.message||'Portal status update',detail:w.description||w.detail||'Check the Nirantar portal for the latest status.'},true);return}if(w.portal_id&&w.portal_id!=='college_portal')return;notify(w);if(type==='recovery'&&String(w.id||'').startsWith('REC_STABILIZED_'))showCoach('PulseBot verified a later recovery',`${(w.action||'The M7 action').replaceAll('_',' ')} ran in the local portal. ${w.current_result||'The next measured request window improved.'} This check uses the follow-up M1 cycle, and monitoring continues.`, 'Compare the action and its later measured result under Traffic → Recovery.',13000,'action')}catch(e){console.error(e)}}));
  stream.addEventListener('pipeline_stage',event=>{try{const x=JSON.parse(event.data);if(x.portal_id==='college_portal'){state.latestStage=x.stage;if(state.snapshot)renderPipeline(state.snapshot)}}catch(e){console.error(e)}});
  const announcedActuations=new Set();
  stream.addEventListener('actuation',event=>{try{
    const x=JSON.parse(event.data);if(x.portal_id!=='college_portal'||announcedActuations.has(x.cycle_id))return;
    if(x.actuation_record?.status!=='SUCCESS'&&x.status!=='EXECUTED')return;
    announcedActuations.add(x.cycle_id);
    const before=x.before_metrics||{},after=x.after_metrics||{},action=(x.action||'PORTAL ACTION').replaceAll('_',' ');
    const measured=`Measured p95 ${fmt(before.p95_ms,0)} → ${fmt(after.p95_ms,0)} ms; DB pool ${fmt(before.db_connections,0)} → ${fmt(after.db_connections,0)}%.`;
    if(x.verification_status==='RECOVERY_VERIFIED')showCoach(`M7 applied ${action}`,`PulseBot saw the safety-approved action execute in the local portal. ${measured} The post-action sample passed verification for this cycle; the loop continues monitoring if pressure returns.`, 'Watch the blue intervention card and the before → after graph in AI Models.',16000,'action',after);
    else if(x.verification_status==='OBSERVING')showCoach(`M7 applied ${action}; checking the next window`,`The local actuator ran. ${measured} The current three-second window still includes pre-action requests, so PortalPulse waits for a later measured sample before claiming recovery.`, 'Watch the blue intervention card and the next M1 cycle.',16000,'action',after);
    else showCoach(`M7 applied ${action}, but recovery failed verification`,`The local actuator ran, yet later measurements did not improve enough. ${measured} PortalPulse does not call this a recovery.`, 'Inspect Traffic → Recovery and the red result in the action history.',16000,'danger',after);
  }catch(e){console.error(e)}});
  ['forecast','anomaly','rca','action','safety','actuation','control_cycle'].forEach((type,i)=>stream.addEventListener(type,()=>{state.latestStage=['M2','M3','M4','M5','M6','M7','M1'][i];if(state.snapshot)renderPipeline(state.snapshot);if(type==='control_cycle')refresh()}));
  stream.addEventListener('demo_reset',()=>{state.warnings=[];state.pinnedMitigation=null;state.pinnedVerified=null;sessionStorage.removeItem('portalpulse_demo_evidence');$('incidents').replaceChildren();$('response-incidents').replaceChildren();$('toasts').replaceChildren();$('incident-count').textContent='0'});
  stream.onerror=()=>{$('connection').textContent='SSE RECONNECTING'};
  preloadCycleHistory();
  async function poll(){await refresh();setTimeout(poll,document.hidden?15000:state.snapshot?.traffic?.is_running?1500:6000)}
  poll();
})();
