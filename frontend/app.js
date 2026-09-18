import {ConnectomePanel} from './connectome_panel.js';
import {EEGPanel} from './eeg_panel.js';
import {FlyPanel} from './body_panel.js';
import {t as tr, initI18n} from './i18n.js';

const $=id=>document.getElementById(id);
const eeg=new EEGPanel($('eeg'));
let brain,fly,networkInfo,bodyInfo,ws,state,metrics,lastReceived=0,lastTrialKey='',trialCache=new Map(),generation=0,lastEvents='',connected=false;
const className=v=>v===0?tr('left'):v===1?tr('right'):'—';
const cmdText=c=>c==='LEFT'?tr('left'):c==='RIGHT'?tr('right'):c==='WAIT'?tr('waiting'):c==='HOLD'?tr('no-bias'):c;
const text=(id,value)=>{if($(id).textContent!==String(value))$(id).textContent=value};
function send(action,value){if(ws?.readyState===WebSocket.OPEN)ws.send(JSON.stringify({action,value}))}
$('play').onclick=()=>send(state?.running?'pause':'play');
$('next').onclick=()=>send('next');
$('reset').onclick=()=>{fly?.reset();eeg.previous=null;eeg.trial=null;lastTrialKey='';send('reset')};
$('lesion').onclick=()=>send('lesion',!state?.lesion);
$('truth-mode').onclick=()=>send('mode','truth');$('decoded-mode').onclick=()=>send('mode','decoded');$('manual-mode').onclick=()=>send('mode','manual');
$('manual-left').onclick=()=>send('manual','L');$('manual-right').onclick=()=>send('manual','R');
$('steering-gain').oninput=e=>send('steering_gain',Number(e.target.value));
$('speed').oninput=e=>send('speed',Number(e.target.value));$('reset-view').onclick=()=>brain?.reset();
for(const id of ['about','details'])$(id).onclick=()=>$('info-dialog').showModal();
$('close-dialog').onclick=()=>$('info-dialog').close();
$('info-dialog').onclick=e=>{if(e.target===$('info-dialog'))$('info-dialog').close()};
$('retry').onclick=async()=>{await fetch('/api/retry',{method:'POST'});$('retry').hidden=true;poll()};

async function getTrial(index){
  if(!trialCache.has(index))trialCache.set(index,fetch(`/api/trials/${index}`).then(r=>{if(!r.ok)throw Error('EEG trial could not be loaded');return r.json()}).catch(e=>{trialCache.delete(index);throw e}));
  return trialCache.get(index);
}
async function updateTrial(s){
  const key=`${s.trial}:${s.sequence}`;
  if(key===lastTrialKey)return;
  lastTrialKey=key;const g=++generation;
  try{const trial=await getTrial(s.trial);if(g!==generation)return;eeg.setTrial(trial);text('artifact',trial.artifact?tr('artifact-flag'):tr('artifact-real'));getTrial((s.trial+1)%metrics.evaluation_trials).catch(()=>{});}
  catch(e){text('connection',tr('eeg-load-error'));text('loading-message',e.message);$('loading').hidden=false;$('retry').hidden=false;}
}
function update(s){
  state=s;lastReceived=performance.now();updateTrial(s);brain?.update(s.activity);fly?.update(s);
  $('truth-mode').classList.toggle('selected',s.mode==='truth');$('decoded-mode').classList.toggle('selected',s.mode==='decoded');$('manual-mode').classList.toggle('selected',s.mode==='manual');
  $('manual-control').hidden=s.mode!=='manual';
  $('manual-left').classList.toggle('selected',s.manual_side==='L');$('manual-right').classList.toggle('selected',s.manual_side==='R');
  text('mode-info',s.lesion?tr('mode-lesion'):s.mode==='truth'?tr('mode-truth'):s.mode==='manual'?tr('mode-manual'):tr('mode-decoded'));
  $('lesion').classList.toggle('cut',s.lesion);text('lesion',s.lesion?tr('restore'):tr('cut'));
  $('trial-top').innerHTML=`${String(s.trial+1).padStart(3,'0')} <i>/ ${metrics.evaluation_trials}</i>`;
  text('truth-value',className(s.label)+' '+tr('hand'));text('prediction',s.prediction===null?tr('acquiring-dots'):className(s.prediction)+' '+tr('hand'));
  const drive=s.time<2?null:(s.mode==='truth'?s.label:(s.mode==='manual'?(s.manual_side==='L'?0:s.manual_side==='R'?1:null):s.prediction));
  $('eeg-class').innerHTML=drive===null?tr('acquiring')+'<span class="class-arrow">⌁</span>':`${className(drive)} ${tr('hand')} MI<span class="class-arrow">${drive===0?'↖':'↗'}</span>`;
  text('drive-source',s.time<2?tr('decision-arrives'):`${s.mode==='truth'?tr('label'):s.mode==='manual'?tr('manual-label'):tr('decoder')} → DNa02 body ${s.input_body_id} · ${tr('engineered-input')}`);
  text('response-drive',s.lesion?tr('response-lesion'):drive===null?tr('response-waiting'):`${s.mode==='truth'?tr('label'):s.mode==='manual'?tr('manual-label'):tr('decoder')} ${className(drive)} → ${tr('neural-out')} ${cmdText(s.command)}`);
  const turn=s.response_turn_deg||0;
  text('response-turn',s.lesion?`${tr('turn-lesion')}${(s.cut_turn_deg||0).toFixed(1)}° · CPG ${s.body.signals.map(v=>v.toFixed(2)).join(' / ')}`:s.time<=2?tr('turn-before'):`${tr('turn-prefix')}${turn>=0?tr('turn-left'):tr('turn-right')} ${Math.abs(turn).toFixed(1)}° · ${s.time<3.8?tr('stimulating'):tr('after-stimulus')}`);
  text('confidence',s.confidence===null?'—':(s.confidence*100).toFixed(1)+'%');$('confidence-bar').style.width=(s.confidence||0)*100+'%';
  const netState=s.phase==='ACQUIRE'?tr('awaiting-input'):s.phase==='INPUT'?`${className(drive)} ${tr('input-active')}`:s.phase==='PROPAGATE'?tr('activity-propagating'):s.phase==='MOTOR'?tr('reading-motor'):(s.command==='HOLD'?tr('no-lateralized-output'):`${cmdText(s.command)} ${tr('motor-response')}`);
  text('network-state',netState);
  for(const [name,key]of [['left','L'],['right','R']]){text(`${name}-activity`,s.motors[key].toFixed(5));$(`${name}-bar`).style.width=Math.min(100,s.motors_normalized[key]*100)+'%'}
  const command=s.lesion?tr('disconnected'):s.command==='WAIT'?tr('integrating'):s.command==='HOLD'?tr('no-bias'):`${cmdText(s.command)} ${tr('bias')}`;
  $('command').innerHTML=`${command}<i>${s.command==='LEFT'?'↶':s.command==='RIGHT'?'↷':'·'}</i>`;
  $('heading').innerHTML=`${String(Math.round(((s.fly.heading*180/Math.PI)%360+360)%360)).padStart(3,'0')}<span>°</span>`;
  $('distance').innerHTML=s.distance.toFixed(2)+'<span> mm</span>';text('targets',String(s.hits).padStart(2,'0'));
  text('physics-time',`BODY ${s.body.physics_time.toFixed(3)} s · 0.1×`);text('contact-count',`${s.body.contacts} ${tr('contacts')}`);text('upright',s.body.upright>.5?tr('upright'):tr('fallen'));
  text('arena-status',s.running?tr('physics-live'):tr('paused'));text('connection',s.error?tr('physics-stopped'):s.running?tr('simulation-running'):tr('simulation-paused'));
  if(s.error)text('mode-info',s.error);
  $('play').innerHTML=s.running?`Ⅱ <span>${tr('pause')}</span>`:`▶ <span>${tr('resume')}</span>`;
  const events=JSON.stringify(s.events);
  if(events!==lastEvents){lastEvents=events;$('events').innerHTML=s.events.length?s.events.slice(0,4).map(e=>`<div class="event ${e.command==='RIGHT'?'right':''}"><time>${e.time.toFixed(1)}s</time><span>${tr('trial')} ${String(e.trial).padStart(3,'0')}</span><b>${cmdText(e.command)}</b><i>Δ ${e.turn_deg>=0?'+':''}${(e.turn_deg||0).toFixed(1)}°</i></div>`).join(''):`<div class="empty-log">${tr('empty-log')}</div>`}
  document.querySelectorAll('[data-stage]').forEach(el=>el.classList.toggle('active',el.dataset.stage===s.phase));
}
function details(){
  const n=networkInfo.provenance;
  const rows=[[tr('detail-eeg'),'BNCI2014_001 / BCI Competition IV 2a'],[tr('detail-split'),`A01T training (${metrics.training_trials}) → A01E held-out evaluation (${metrics.evaluation_trials})`],[tr('detail-accuracy'),`${(metrics.accuracy*100).toFixed(1)}% · no test fitting or tuning`],[tr('detail-confusion'),`True rows L/R; prediction columns L/R:<br>[ ${metrics.confusion_matrix[0].join(' , ')} ]<br>[ ${metrics.confusion_matrix[1].join(' , ')} ]`],[tr('detail-decoder'),'Causal 8–30 Hz Butterworth → CSP (4) → shrinkage LDA; first 2 cue-aligned seconds, 22 channels. LDA posterior is uncalibrated.'],[tr('detail-structure'),`MANC v1.0 EM reconstruction: ${n.neuron_count.toLocaleString()} neurons; ${n.edge_count.toLocaleString()} retained directed connections (≥5 synapses), from ${n.original_edge_count.toLocaleString()} released edges. No generated connections.`],[tr('detail-display'),`${networkInfo.view.display_nodes} neurons / ${networkInfo.view.display_edges} measured edges displayed. ALL retained neurons/edges are simulated. Coordinates are source metadata under a common affine transform; cell brightness is individually normalized model activity, not recorded physiology. Edge brightness is derived from endpoint activity, not measured synaptic current.`],[tr('detail-input'),'Engineered EEG interface: left MI → left DNa02 #10126; right MI → right DNa02 #10118. These are verified MANC identities, not an experimentally measured human–fly mapping.'],[tr('detail-motor'),`${n.motor_annotation.count} published leg MNs matched by body ID. ${n.motor_annotation.excluded_absent_from_traced_release.length} other table entries are absent from this traced release and excluded. Raw means are shown; bar length uses a shared isolated-DNa02 calibration.`],[tr('detail-neural'),'Assumed delayed rectified rate dynamics, τ=25 ms, delay=10 ms. Synapse counts are measured; row normalization, gain, transmitter-based signs and time constants are not fitted physiology.'],[tr('detail-body'),`${bodyInfo.model} · ${bodyInfo.engine}. Micro-CT-derived meshes; ${bodyInfo.leg_position_actuators} joint position actuators, 6 adhesion actuators; gravity, contact and free-body integration. No scripted body translation/rotation.`],[tr('detail-bridge'),'Engineered mapping: ipsilateral motor-population activity reduces that side’s walking CPG amplitude; adjustable 1–2× steering gain (default 2×), amplitude floor 0.25. Published FlyGym hybrid corrections remain active. Baseline CPG walking is not generated by MANC; EEG modulates steering through MANC.'],[tr('detail-clocks'),'EEG plays at 1×. Neural/body time advances at 0.1× for visible slow motion. MuJoCo dt=0.1 ms, controller dt=1 ms, neural dt=5 ms.'],[tr('detail-control'),'Cut synapses sets all network propagation to zero. CPG walking continues; existing body momentum, gait phase and baseline yaw drift can still produce rotation. After cutting, future EEG cannot affect motion; this does not undo previous steering or impose straight walking. Restore synapses reconnects the measured graph.'],[tr('detail-sources'),'<a href="https://www.janelia.org/project-team/flyem/manc-connectome" target="_blank" rel="noopener">Official MANC ↗</a> · <a href="https://doi.org/10.7554/eLife.96084" target="_blank" rel="noopener">Motor annotation paper ↗</a> · <a href="https://github.com/NeLy-EPFL/flygym/tree/v2.1.0" target="_blank" rel="noopener">NeuroMechFly ↗</a>']];
  $('details-content').innerHTML='<table class="details-table">'+rows.map(([k,v])=>`<tr><td>${k}</td><td>${v}</td></tr>`).join('')+'</table>';
}
function connect(){
  ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);
  ws.onopen=()=>{$('steering-gain').value='2';connected=true;lastTrialKey='';eeg.previous=null;eeg.trial=null;fly?.reset();$('loading').hidden=true};
  ws.onmessage=e=>update(JSON.parse(e.data));
  ws.onclose=()=>{connected=false;text('connection',tr('disconnected'));text('arena-status',tr('offline'));text('loading-message',tr('connection-lost'));$('loading').hidden=false;setTimeout(connect,2000)};
  ws.onerror=()=>text('connection',tr('reconnecting'));
}
async function poll(){
  try{
    const r=await fetch('/api/status');if(!r.ok)throw Error(tr('server-unavailable'));const s=await r.json();text('loading-message',s.message);
    if(s.state==='error'){$('retry').hidden=false;text('connection',tr('data-unavailable'));return}
    if(s.state!=='ready'){setTimeout(poll,1200);return}
    const response=await fetch('/api/bootstrap');if(!response.ok)throw Error('Could not load experiment');const boot=await response.json();metrics=boot.metrics;networkInfo=boot.graph;bodyInfo=boot.body_geometry.provenance;
    text('node-count',boot.graph.provenance.neuron_count.toLocaleString());text('edge-count',boot.graph.provenance.edge_count.toLocaleString());
    if(!brain)brain=new ConnectomePanel($('brain'),boot.graph);
    if(!fly)fly=new FlyPanel($('fly'),boot.body_geometry);
    document.querySelector('.brain-tools span').textContent=`${boot.graph.nodes.length.toLocaleString()} DISPLAYED · HOVER FOR REAL BODY ID · DRAG / ZOOM`;
    details();connect();
  }catch(e){text('loading-message',e.message+' — '+tr('retrying-in'));setTimeout(poll,3000)}
}
let lastPaint=0;
function animate(now){
  if(now-lastPaint<33){requestAnimationFrame(animate);return}lastPaint=now;
  const advance=state?.running&&connected?Math.min(.1,(now-lastReceived)/1000)*state.speed:0;
  const t=state?Math.min(4.999,state.time+advance):0;
  eeg.render(t);brain?.render((state?.elapsed||0)+advance,Boolean(state?.running&&connected));fly?.render();
  $('timeline-progress').style.width=t/5*100+'%';$('trial-time').innerHTML=t.toFixed(2)+' <i>/ 5.00 s</i>';
  requestAnimationFrame(animate);
}
document.addEventListener('neurofly-lang',()=>{if(state)update(state);if(networkInfo)details();});
initI18n();
poll();requestAnimationFrame(animate);
