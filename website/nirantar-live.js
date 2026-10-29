(() => {
  const $=id=>document.getElementById(id);
  const allowed=['bronze-tinsel-n8pb.here.now','127.0.0.1','localhost'];
  let site='https://bronze-tinsel-n8pb.here.now/';
  try{const candidate=new URL(new URLSearchParams(location.search).get('site')||site);if(['https:','http:'].includes(candidate.protocol)&&allowed.includes(candidate.hostname))site=candidate.href}catch{}
  $('nirantar-site').src=site;
  $('direct-site').href=site;
  const examples=[
    {title:'Tatkal requests are entering a short queue',detail:'In this preview, new bookings are admitted in batches while active checkouts finish. The queue and wait estimate are an example, not a Nirantar measurement.',kind:'warning'},
    {title:'Booking confirmations are slower than usual',detail:'In this preview, passengers should wait for the final transaction status before trying the same payment again. This is an illustrative advisory.',kind:'warning'},
    {title:'Booking flow is being admitted normally',detail:'This example shows the blue follow-up notice after a queue clears. No live Nirantar recovery is inferred.',kind:'recovery'}
  ];
  let exampleIndex=0,liveCount=0;
  function card({title,detail,kind='warning',source='EXAMPLE · LOCAL OVERLAY',footer=''}){
    const node=document.createElement('article');node.className='notice '+kind;
    const close=document.createElement('button');close.textContent='×';close.setAttribute('aria-label','Dismiss notice');close.onclick=()=>node.remove();
    const label=document.createElement('small');label.textContent=source;
    const heading=document.createElement('strong');heading.textContent=title;
    const body=document.createElement('p');body.textContent=detail;
    const foot=document.createElement('footer');foot.textContent=footer||new Date().toLocaleTimeString();
    node.append(close,label,heading,body,foot);$('notice-stack').prepend(node);
    while($('notice-stack').children.length>3)$('notice-stack').lastElementChild.remove();
  }
  $('preview-notice').onclick=()=>{card(examples[exampleIndex++%examples.length]);$('bridge-state').textContent='PortalPulse overlay · preview mode'};
  const stream=new EventSource('/api/v1/stream/events');
  for(const type of ['warning','recovery'])stream.addEventListener(type,event=>{try{
    const item=JSON.parse(event.data);if(item.portal_id!=='nirantar')return;
    liveCount++;$('bridge-state').textContent=`${liveCount} local Nirantar bridge event${liveCount===1?'':'s'}`;
    card({title:item.title||item.id||'Nirantar status update',detail:item.why_it_happened||item.message||item.trigger_condition||'Local bridge event received.',kind:type==='recovery'?'recovery':'warning',source:'LIVE NIRANTAR EVENT · LOCAL BRIDGE',footer:`${item.what_portalpulse_did||item.remediation_state||'Observed by PortalPulse'} · ${new Date().toLocaleTimeString()}`});
  }catch(error){console.error(error)}});
})();
